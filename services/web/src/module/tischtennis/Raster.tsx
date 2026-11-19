import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { Spiel } from "./api";
import stil from "./TischtennisSeite.module.css";

/**
 * Was „Sieger aus Spiel 7“ mit Spiel 7 verbindet.
 *
 * Mit der Maus genügt das Zeigen: Solange der Zeiger auf dem Verweis
 * steht, leuchtet das Spiel auf, aus dem er kommt. Am Telefon gibt es kein
 * Zeigen, dort hält ein Tippen die Hervorhebung fest - bis man denselben
 * Verweis noch einmal antippt oder irgendwo anders hin. Ein Tippen rollt
 * das Spiel außerdem ins Bild, denn es steht oft in einer anderen Karte:
 * Der Verliererzweig verweist auf das Raster darüber.
 *
 * Ein Rahmen um alle Raster statt eines Zustands in jedem, weil der
 * Verweis genau diese Grenze überquert.
 */
interface Verweise {
  /** Das Spiel, das gerade hervorsticht - oder keines. */
  markiert: number | null;
  festgehalten: number | null;
  /** Gibt es dieses Spiel hier überhaupt? Sonst bleibt der Verweis Text. */
  vorhanden: (nummer: number) => boolean;
  zeigen: (nummer: number | null) => void;
  antippen: (nummer: number) => void;
  kennung: (nummer: number) => string;
}

const VerweisKontext = createContext<Verweise | null>(null);

export function VerweisRahmen({
  spiele,
  children,
}: {
  spiele: Spiel[];
  children: ReactNode;
}) {
  const praefix = useId();
  const [gezeigt, setGezeigt] = useState<number | null>(null);
  const [festgehalten, setFestgehalten] = useState<number | null>(null);
  const nummern = useMemo(() => new Set(spiele.map((spiel) => spiel.nummer)), [spiele]);

  const kennung = useCallback((nummer: number) => `${praefix}spiel-${nummer}`, [praefix]);

  const antippen = useCallback(
    (nummer: number) => {
      // Das Zeigen gehört der Maus. Am Telefon gilt der Finger nach dem
      // Tippen noch als "darüber", bis man woanders hintippt - ohne dieses
      // Zurücksetzen bliebe das Spiel nach dem zweiten Tippen hell.
      setGezeigt(null);
      if (festgehalten === nummer) {
        setFestgehalten(null);
        return;
      }
      setFestgehalten(nummer);
      const ziel = document.getElementById(kennung(nummer));
      const ruhig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      ziel?.scrollIntoView?.({
        behavior: ruhig ? "auto" : "smooth",
        block: "nearest",
        inline: "nearest",
      });
    },
    [festgehalten, kennung],
  );

  // Irgendwo anders hintippen löst die Hervorhebung. Ein Verweis selbst
  // ist ausgenommen: Was er tut, entscheidet `antippen`.
  useEffect(() => {
    if (festgehalten === null) return;
    function woanders(ereignis: PointerEvent) {
      const ziel = ereignis.target;
      if (ziel instanceof Element && ziel.closest("[data-verweis]")) return;
      setFestgehalten(null);
    }
    document.addEventListener("pointerdown", woanders);
    return () => document.removeEventListener("pointerdown", woanders);
  }, [festgehalten]);

  const wert = useMemo<Verweise>(
    () => ({
      markiert: gezeigt ?? festgehalten,
      festgehalten,
      vorhanden: (nummer) => nummern.has(nummer),
      zeigen: setGezeigt,
      antippen,
      kennung,
    }),
    [gezeigt, festgehalten, nummern, antippen, kennung],
  );

  return <VerweisKontext.Provider value={wert}>{children}</VerweisKontext.Provider>;
}

/**
 * Das KO-Raster als Bild.
 *
 * Eine Spalte je Runde, die Paarungen darin gleichmäßig verteilt: damit
 * steht das Halbfinale auf der Höhe zwischen seinen beiden Viertelfinals,
 * und der Weg nach vorn ist zu sehen, ohne ihn aus Spielnummern
 * zusammenzusuchen. Die Verbindungslinien sind reine Dekoration aus CSS —
 * sie tragen keine Aussage, die nicht schon im Text steht.
 *
 * Bewusst keine Zeichnung mit festen Koordinaten: Namen sind
 * unterschiedlich lang, und ein Raster, das bei „Maximilian“ bricht, ist
 * schlechter als eines, das mitwächst.
 */
export function Raster({
  spiele,
  beschriftung = "KO-Raster",
}: {
  spiele: Spiel[];
  beschriftung?: string;
}) {
  const runden = [...new Set(spiele.map((spiel) => spiel.runde))].sort((a, b) => a - b);
  const verweise = useContext(VerweisKontext);

  return (
    <div className={stil.raster} role="group" aria-label={beschriftung}>
      {runden.map((runde) => {
        const dieser = spiele.filter((spiel) => spiel.runde === runde);
        return (
          <div key={runde} className={stil.rasterspalte}>
            <h3 className={stil.rundenname}>
              {dieser[0]?.bezeichnung ?? `Runde ${runde}`}
            </h3>
            <ol className={stil.rasterliste}>
              {dieser.map((spiel) => (
                <li
                  key={spiel.id}
                  id={verweise?.kennung(spiel.nummer)}
                  className={stil.rasterspiel}
                  aria-label={`Spiel ${spiel.nummer}`}
                  aria-current={verweise?.markiert === spiel.nummer ? true : undefined}
                >
                  {/* Die Nummer, auf die „Sieger aus Spiel 7“ zeigt. Ohne sie
                      verwiese der Satz auf etwas, das nirgends steht - und
                      an der Wand im Saal zeigt niemand mit der Maus. */}
                  <span className={stil.rasternummer} aria-hidden="true">
                    {spiel.nummer}
                  </span>
                  <div className={stil.rasterpaar}>
                    <Seite spiel={spiel} wer="heim" />
                    <Seite spiel={spiel} wer="gast" />
                  </div>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Ein Platz im Raster.
 *
 * Steht der Name noch nicht fest, steht da, woher er kommt — „Sieger aus
 * Spiel 13“. Eine leere Zeile wäre an dieser Stelle die Auskunft, dass
 * niemand spielt, und das stimmt nicht.
 */
function Seite({ spiel, wer }: { spiel: Spiel; wer: "heim" | "gast" }) {
  const name = wer === "heim" ? spiel.heim : spiel.gast;
  const herkunft = wer === "heim" ? spiel.heim_herkunft : spiel.gast_herkunft;
  const kennung = wer === "heim" ? spiel.heim_id : spiel.gast_id;
  const ausSpiel = wer === "heim" ? spiel.heim_aus_spiel : spiel.gast_aus_spiel;
  const verweise = useContext(VerweisKontext);
  const gewonnen = kennung !== null && kennung === spiel.sieger_id;
  const verloren = spiel.sieger_id !== null && !gewonnen && kennung !== null;

  return (
    <div
      className={[
        stil.rasterplatz,
        gewonnen ? stil.rastersieger : "",
        verloren ? stil.rasterverloren : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {name === null && herkunft && ausSpiel !== null && verweise?.vorhanden(ausSpiel) ? (
        <button
          type="button"
          data-verweis=""
          className={stil.rasterverweis}
          aria-pressed={verweise.festgehalten === ausSpiel}
          onPointerEnter={(ereignis) => {
            if (ereignis.pointerType === "mouse") verweise.zeigen(ausSpiel);
          }}
          onPointerLeave={() => verweise.zeigen(null)}
          onClick={() => verweise.antippen(ausSpiel)}
        >
          {herkunft}
        </button>
      ) : (
        <span className={stil.rastername}>{name ?? herkunft ?? "offen"}</span>
      )}
      {/* Sichtbar trägt das die Zeile selbst: halbfett, mit einem Strich an
          der Kante, und der Verlierer tritt zurück. Ein Etikett „weiter"
          dahinter sagte dasselbe ein zweites Mal -- und zwar in jeder
          entschiedenen Paarung des Rasters, also am Ende in der Hälfte
          aller Zeilen.
          Vorgelesen bleibt es stehen: Schriftschnitt und Strich kommen bei
          einem Screenreader nicht an. */}
      {gewonnen && <span className="nur-vorlesen">weiter</span>}
    </div>
  );
}
