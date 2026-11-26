import { useEffect, useRef, useState } from "react";

import { Hinweis, Knopf, Platzhalter } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { meldung } from "./zeit";

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

/**
 * Zeichnet selbst, statt das PDF dem Browser zu überlassen: Android-Chrome
 * zeigt eingebettete PDFs gar nicht an, und genau dort - auf dem Tablet -
 * wird bewertet.
 */
export function PdfAnsicht({
  pruefling,
  dokument,
}: {
  pruefling: api.Pruefling;
  dokument: api.Dokument;
}) {
  const [pdf, setPdf] = useState<Dokument | null>(null);
  const [fehler, setFehler] = useState("");
  const [seite, setSeite] = useState(1);
  const [zoom, setZoom] = useState(1);
  const flaeche = useRef<HTMLDivElement>(null);
  const leinwand = useRef<HTMLCanvasElement>(null);

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
        if (steuerung.signal.aborted) return;
        setPdf(offen);
        setSeite(1);
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

  useEffect(() => {
    if (!pdf || !leinwand.current || !flaeche.current) return;
    let abgebrochen = false;
    let auftrag: { cancel: () => void; promise: Promise<unknown> } | null = null;
    void (async () => {
      const blatt = await pdf.getPage(seite);
      if (abgebrochen || !leinwand.current || !flaeche.current) return;
      // Auf die Breite der Spalte, dann gezoomt - so passt eine Seite bei
      // 375 px genauso wie neben dem Raster auf dem Monitor.
      const breite = flaeche.current.clientWidth || 600;
      const grund = blatt.getViewport({ scale: 1 });
      const dichte = window.devicePixelRatio || 1;
      const massstab = (breite / grund.width) * zoom;
      const ansicht = blatt.getViewport({ scale: massstab * dichte });
      const c = leinwand.current;
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
  }, [pdf, seite, zoom]);

  if (fehler) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  const seiten = pdf?.numPages ?? 0;
  return (
    <div className={stil.pdf}>
      <div className={stil.pdfleiste}>
        <Knopf
          groesse="sm"
          aria-label="Vorige Seite"
          disabled={seite <= 1}
          onClick={() => setSeite((s) => Math.max(1, s - 1))}
        >
          ‹
        </Knopf>
        <span className={stil.leise}>{seiten ? `Seite ${seite} / ${seiten}` : "–"}</span>
        <Knopf
          groesse="sm"
          aria-label="Nächste Seite"
          disabled={seite >= seiten}
          onClick={() => setSeite((s) => Math.min(seiten, s + 1))}
        >
          ›
        </Knopf>
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
        {!pdf && (
          <div role="status" aria-label="Dokument wird geladen">
            <Platzhalter hoehe="24rem" />
          </div>
        )}
        <canvas
          ref={leinwand}
          hidden={!pdf}
          aria-label={`${dokument.dateiname}, Seite ${seite}`}
        />
      </div>
    </div>
  );
}
