import { useEffect, useMemo, useRef, useState } from "react";

import { Hinweis, Karte, Knopf } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import type { Aendern } from "./PrueflingTafel";
import { Sinnbild } from "./Symbole";
import { uhr, zeitstand } from "./zeit";

/** Was der eine Knopf gerade tut: Symbol für die Handlung, Symbol für das,
 *  was danach läuft. Der Satz dazu steht im Tooltip und für Screenreader. */
const AKTION: Record<
  NonNullable<ReturnType<typeof zeitstand>["naechste"]>,
  {
    wort: string;
    symbol: "start" | "weiter" | "stopp";
    ziel: "praesentation" | "gespraech" | "gesamt";
  }
> = {
  praesentation_starten: {
    wort: "Präsentation starten",
    symbol: "start",
    ziel: "praesentation",
  },
  fachgespraech_starten: {
    wort: "Fachgespräch starten",
    symbol: "weiter",
    ziel: "gespraech",
  },
  beenden: { wort: "Prüfung beenden", symbol: "stopp", ziel: "gesamt" },
};

/** Tickt nur, solange eine Messung läuft - sonst gibt es nichts zu zählen. */
function useJetzt(aktiv: boolean, versatz: number): number {
  const [jetzt, setJetzt] = useState(() => Date.now() + versatz);
  useEffect(() => {
    setJetzt(Date.now() + versatz);
    if (!aktiv) return;
    const takt = window.setInterval(() => setJetzt(Date.now() + versatz), 500);
    return () => window.clearInterval(takt);
  }, [aktiv, versatz]);
  return jetzt;
}

/** Hält den Bildschirm an, solange gemessen wird. Wird es verweigert, läuft
 *  die Prüfung trotzdem - der Bildschirm wird dann eben dunkel. */
function useWachhalten(aktiv: boolean): void {
  useEffect(() => {
    if (!aktiv || !("wakeLock" in navigator)) return;
    let sperre: WakeLockSentinel | null = null;
    let vorbei = false;
    const holen = () => {
      navigator.wakeLock
        .request("screen")
        .then((s) => {
          if (vorbei) void s.release();
          else sperre = s;
        })
        .catch(() => undefined);
    };
    const sichtbar = () => document.visibilityState === "visible" && holen();
    holen();
    document.addEventListener("visibilitychange", sichtbar);
    return () => {
      vorbei = true;
      document.removeEventListener("visibilitychange", sichtbar);
      void sperre?.release().catch(() => undefined);
    };
  }, [aktiv]);
}

function signal(muster: number | number[]): void {
  try {
    navigator.vibrate?.(muster);
    const ton = new AudioContext();
    const schwinger = ton.createOscillator();
    const laut = ton.createGain();
    schwinger.frequency.value = 880;
    laut.gain.value = 0.15;
    schwinger.connect(laut).connect(ton.destination);
    schwinger.start();
    schwinger.stop(ton.currentTime + 0.6);
    schwinger.onended = () => void ton.close();
  } catch {
    /* ohne Ton - die Anzeige färbt sich trotzdem */
  }
}

export function Zeitmessung({
  katalog,
  pruefling: p,
  aendern,
}: {
  katalog: api.Katalog;
  pruefling: api.Pruefling;
  aendern: Aendern;
}) {
  // Gegen die Uhr des Servers gerechnet, nicht gegen die des Tablets: Die
  // Zeitstempel setzt der Server, und jede Abweichung zwischen beiden Uhren
  // verschöbe sonst die Prüfungszeit.
  const versatz = useMemo(() => Date.parse(p.jetzt) - Date.now(), [p.jetzt]);
  const grenzen = {
    praesiMin: katalog.praesi_grenze_min,
    gesamtMin: katalog.gesamt_grenze_min,
  };
  const vorab = zeitstand(p.zeiten, Date.now() + versatz, grenzen);
  const jetzt = useJetzt(vorab.laeuft, versatz);
  const s = zeitstand(p.zeiten, jetzt, grenzen);
  useWachhalten(s.laeuft);

  // Ein Signal je überschrittener Grenze, nicht eines je Takt.
  const gemeldet = useRef({ praesi: s.praesiUeber, gesamt: s.gesamtUeber });
  useEffect(() => {
    if (s.laeuft && s.praesiUeber && !gemeldet.current.praesi) signal(200);
    if (s.laeuft && s.gesamtUeber && !gemeldet.current.gesamt)
      signal([300, 150, 300, 150, 300]);
    gemeldet.current = { praesi: s.praesiUeber, gesamt: s.gesamtUeber };
  }, [s.laeuft, s.praesiUeber, s.gesamtUeber]);

  const schalte = (aktion: api.Zeitaktion) =>
    void aendern(() => api.schalteZeit(p.id, aktion));

  const knopf = s.naechste ? AKTION[s.naechste] : null;

  return (
    <Karte>
      <section aria-labelledby="zeitmessung" className={stil.sektion}>
        <h3 id="zeitmessung" className="nur-vorlesen">
          Zeitmessung
        </h3>
        <div className={stil.zeitleiste}>
          <div className={stil.uhren}>
            <Uhr
              name="Präsentation"
              symbol="praesentation"
              ms={s.praesiMs}
              grenze={`${katalog.praesi_grenze_min}:00`}
              ueber={s.praesiUeber}
            />
            <Uhr name="Fachgespräch" symbol="gespraech" ms={s.fgMs} />
            <Uhr
              name="Gesamt"
              symbol="gesamt"
              ms={s.gesamtMs}
              grenze={`${katalog.gesamt_grenze_min}:00`}
              ueber={s.gesamtUeber}
            />
          </div>
          <div className={stil.knopfreihe}>
            {knopf && s.naechste && (
              <Knopf
                auspraegung="primaer"
                aria-label={knopf.wort}
                title={knopf.wort}
                onClick={() => schalte(s.naechste!)}
              >
                <Sinnbild name={knopf.symbol} gefuellt />
                <Sinnbild name={knopf.ziel} />
              </Knopf>
            )}
            {p.zeiten.praesi_start && (
              <Knopf
                auspraegung="leise"
                aria-label="Zeitmessung zurücksetzen"
                title="Zeitmessung zurücksetzen"
                onClick={() =>
                  window.confirm("Zeitmessung zurücksetzen?") && schalte("zuruecksetzen")
                }
              >
                <Sinnbild name="zurueck" />
              </Knopf>
            )}
          </div>
        </div>
        {s.gesamtUeber && (
          <Hinweis ton="fehler">
            {katalog.gesamt_grenze_min} Minuten überschritten.
          </Hinweis>
        )}
        {s.praesiUeber && !s.gesamtUeber && (
          <Hinweis ton="warnung">
            Präsentation über {katalog.praesi_grenze_min} Minuten.
          </Hinweis>
        )}
      </section>
    </Karte>
  );
}

/** Eine Uhr: Symbol, Zeit, Grenze. Den Namen hört der Screenreader. */
function Uhr({
  name,
  symbol,
  ms,
  grenze,
  ueber = false,
}: {
  name: string;
  symbol: "praesentation" | "gespraech" | "gesamt";
  ms: number;
  grenze?: string;
  ueber?: boolean;
}) {
  return (
    <div
      role="timer"
      aria-label={name}
      title={name}
      className={ueber ? `${stil.uhrzeile} ${stil.ueber}` : stil.uhrzeile}
    >
      <Sinnbild name={symbol} />
      <span className={stil.uhr}>{uhr(ms)}</span>
      {grenze && <span className={stil.grenze}>/{grenze}</span>}
    </div>
  );
}
