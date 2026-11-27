import { useEffect, useRef, useState } from "react";

import { Hinweis, Knopf, Platzhalter } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { meldung } from "./zeit";
import { useZitat } from "./Zitat";

type PdfJs = typeof import("pdfjs-dist");
type Dokument = Awaited<ReturnType<PdfJs["getDocument"]>["promise"]>;

let geladen: Promise<PdfJs> | null = null;

/**
 * pdf.js erst, wenn ein Dokument gezeigt wird: Es ist größer als der Rest
 * dieses Artefakts zusammen, und wer nur Prüflinge anlegt, braucht es nie.
 */
function pdfjs(): Promise<PdfJs> {
  geladen ??= Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]).then(([bibliothek, arbeiter]) => {
    bibliothek.GlobalWorkerOptions.workerSrc = arbeiter.default;
    return bibliothek;
  });
  return geladen;
}

/** Breite der Fläche, nachgeführt, wenn sich das Fenster ändert. */
function useBreite(element: React.RefObject<HTMLDivElement | null>): number {
  const [breite, setBreite] = useState(0);
  useEffect(() => {
    const el = element.current;
    if (!el) return;
    const messen = () => setBreite(el.clientWidth);
    messen();
    if (typeof ResizeObserver !== "function") return;
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, [element]);
  return breite;
}

/**
 * Zeichnet selbst, statt das PDF dem Browser zu überlassen: Android-Chrome
 * zeigt eingebettete PDFs gar nicht an, und genau dort - auf dem Tablet -
 * wird bewertet.
 *
 * Alle Seiten stehen untereinander und werden gescrollt wie ein Dokument.
 * Blättern hieß, für jede Seite einen Knopf zu treffen, während man liest.
 */
export function PdfAnsicht({
  pruefling,
  dokument,
}: {
  pruefling: api.Pruefling;
  dokument: api.Dokument;
}) {
  const [pdf, setPdf] = useState<Dokument | null>(null);
  const [grund, setGrund] = useState<{ breite: number; hoehe: number } | null>(null);
  const [fehler, setFehler] = useState("");
  const [zoom, setZoom] = useState(1);
  const flaeche = useRef<HTMLDivElement>(null);
  const breite = useBreite(flaeche);

  useEffect(() => {
    const steuerung = new AbortController();
    let ladeauftrag: ReturnType<PdfJs["getDocument"]> | null = null;
    void (async () => {
      try {
        const [bibliothek, daten] = await Promise.all([
          pdfjs(),
          api.ladeDokumentDaten(pruefling.id, dokument.id, steuerung.signal),
        ]);
        if (steuerung.signal.aborted) return;
        ladeauftrag = bibliothek.getDocument({ data: new Uint8Array(daten) });
        const offen = await ladeauftrag.promise;
        // Die erste Seite gibt das Seitenverhältnis vor - damit steht jede
        // noch nicht gezeichnete Seite schon in ihrer Höhe da, und die
        // Bildlaufleiste springt nicht, während man liest.
        const erste = (await offen.getPage(1)).getViewport({ scale: 1 });
        if (steuerung.signal.aborted) return;
        setGrund({ breite: erste.width, hoehe: erste.height });
        setPdf(offen);
      } catch (e) {
        if (!steuerung.signal.aborted) setFehler(meldung(e));
      }
    })();
    return () => {
      steuerung.abort();
      // Gibt den Worker und den Speicher des Dokuments wieder frei.
      void ladeauftrag?.destroy();
    };
  }, [pruefling.id, dokument.id]);

  if (fehler) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  const seiten = pdf?.numPages ?? 0;
  // Auf die Breite der Spalte, dann gezoomt - so passt eine Seite bei 375 px
  // genauso wie neben dem Raster auf dem Monitor.
  const massstab = grund ? ((breite || 600) / grund.breite) * zoom : 1;

  return (
    <div className={stil.pdf}>
      <div className={stil.pdfleiste}>
        <span className={stil.leise}>{seiten ? `${seiten} Seiten` : "–"}</span>
        <Knopf
          groesse="sm"
          aria-label="Verkleinern"
          disabled={zoom <= 0.5}
          onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
        >
          −
        </Knopf>
        <Knopf
          groesse="sm"
          aria-label="Vergrößern"
          disabled={zoom >= 3}
          onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
        >
          +
        </Knopf>
        <a
          className={stil.verweis}
          href={api.dokumentAdresse(pruefling.id, dokument.id)}
          target="_blank"
          rel="noreferrer"
        >
          Im neuen Tab öffnen
        </a>
      </div>
      <div ref={flaeche} className={stil.pdfflaeche}>
        {!pdf || !grund ? (
          <div role="status" aria-label="Dokument wird geladen">
            <Platzhalter hoehe="24rem" />
          </div>
        ) : (
          Array.from({ length: seiten }, (_, i) => (
            <PdfSeite
              key={i + 1}
              pdf={pdf}
              nummer={i + 1}
              von={seiten}
              name={dokument.dateiname}
              massstab={massstab}
              hoehe={grund.hoehe * massstab}
              wurzel={flaeche}
            />
          ))
        )}
      </div>
    </div>
  );
}

/**
 * Eine Seite. Gezeichnet wird sie erst, wenn sie in die Nähe des sichtbaren
 * Bereichs kommt: Eine Projektdokumentation hat gern 40 Seiten, und alle auf
 * einmal zu zeichnen kostet ein Tablet Sekunden und viel Speicher.
 */
function PdfSeite({
  pdf,
  nummer,
  von,
  name,
  massstab,
  hoehe,
  wurzel,
}: {
  pdf: Dokument;
  nummer: number;
  von: number;
  name: string;
  massstab: number;
  hoehe: number;
  wurzel: React.RefObject<HTMLDivElement | null>;
}) {
  const leinwand = useRef<HTMLCanvasElement>(null);
  // Ohne IntersectionObserver (alte Browser, Tests) wird gleich gezeichnet.
  const [sichtbar, setSichtbar] = useState(typeof IntersectionObserver !== "function");

  useEffect(() => {
    if (sichtbar || !leinwand.current) return;
    const beobachter = new IntersectionObserver(
      (eintraege) => {
        if (eintraege.some((e) => e.isIntersecting)) {
          setSichtbar(true);
          beobachter.disconnect();
        }
      },
      { root: wurzel.current, rootMargin: "800px 0px" },
    );
    beobachter.observe(leinwand.current);
    return () => beobachter.disconnect();
  }, [sichtbar, wurzel]);

  useEffect(() => {
    if (!sichtbar || !leinwand.current) return;
    let abgebrochen = false;
    let auftrag: { cancel: () => void; promise: Promise<unknown> } | null = null;
    void (async () => {
      const blatt = await pdf.getPage(nummer);
      const c = leinwand.current;
      if (abgebrochen || !c) return;
      const dichte = window.devicePixelRatio || 1;
      const ansicht = blatt.getViewport({ scale: massstab * dichte });
      c.width = ansicht.width;
      c.height = ansicht.height;
      c.style.width = `${ansicht.width / dichte}px`;
      c.style.height = `${ansicht.height / dichte}px`;
      const kontext = c.getContext("2d");
      if (!kontext) return;
      auftrag = blatt.render({ canvas: c, canvasContext: kontext, viewport: ansicht });
      await auftrag.promise.catch(() => undefined);
    })();
    return () => {
      abgebrochen = true;
      auftrag?.cancel();
    };
  }, [sichtbar, pdf, nummer, massstab]);

  const zitat = useZitat();

  return (
    <div className={stil.pdfseitenrahmen}>
      <canvas
        ref={leinwand}
        role="img"
        aria-label={`${name}, Seite ${nummer} von ${von}`}
        className={stil.pdfseite}
        style={sichtbar ? undefined : { height: `${hoehe}px`, width: "100%" }}
      />
      {zitat && (
        <button
          type="button"
          className={stil.seitenmarke}
          disabled={!zitat.hatZiel}
          aria-label={`Seite ${nummer} in die Bemerkung übernehmen`}
          title={
            zitat.hatZiel
              ? `„S. ${nummer}:“ in die zuletzt benutzte Bemerkung`
              : "Erst in ein Bemerkungsfeld tippen"
          }
          onClick={() => zitat.zitiere(nummer)}
        >
          S. {nummer}
        </button>
      )}
    </div>
  );
}
