import { useEffect, useMemo, useRef, useState } from "react";

import { Hinweis, Karte, Knopf } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import type { Aendern } from "./PrueflingTafel";
import { uhr, zeitstand } from "./zeit";

const AKTION_WORT: Record<
  NonNullable<ReturnType<typeof zeitstand>["naechste"]>,
  string
> = {
  praesentation_starten: "Präsentation starten",
  fachgespraech_starten: "Fachgespräch starten",
  beenden: "Prüfung beenden",
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

  return (
    <Karte>
      <section aria-labelledby="zeitmessung" className={stil.sektion}>
        <h3 id="zeitmessung" className={stil.sektionstitel}>
          Zeitmessung
        </h3>
        <div className={stil.uhren} aria-live="off">
          <div>
            <p className={stil.beschriftung}>Präsentation</p>
            <p className={s.praesiUeber ? `${stil.uhr} ${stil.ueber}` : stil.uhr}>
              {uhr(s.praesiMs)}
            </p>
            <p className={stil.leise}>Ziel {katalog.praesi_grenze_min}:00</p>
          </div>
          <div>
            <p className={stil.beschriftung}>Fachgespräch</p>
            <p className={stil.uhr}>{uhr(s.fgMs)}</p>
            <p className={stil.leise}>
              {p.zeiten.fg_start ? `Rest ${uhr(s.restMs)}` : " "}
            </p>
          </div>
          <div>
            <p className={stil.beschriftung}>Gesamt</p>
            <p className={s.gesamtUeber ? `${stil.uhr} ${stil.ueber}` : stil.uhr}>
              {uhr(s.gesamtMs)}
            </p>
            <p className={stil.leise}>Grenze {katalog.gesamt_grenze_min}:00</p>
          </div>
        </div>
        <div className={stil.knopfreihe}>
          {s.naechste && (
            <Knopf auspraegung="primaer" onClick={() => schalte(s.naechste!)}>
              {AKTION_WORT[s.naechste]}
            </Knopf>
          )}
          {p.zeiten.praesi_start && (
            <Knopf
              auspraegung="leise"
              onClick={() =>
                window.confirm("Zeitmessung zurücksetzen?") && schalte("zuruecksetzen")
              }
            >
              Zurücksetzen
            </Knopf>
          )}
        </div>
        {s.gesamtUeber && (
          <Hinweis ton="fehler">
            {katalog.gesamt_grenze_min} Minuten überschritten.
          </Hinweis>
        )}
        {s.praesiUeber && !s.gesamtUeber && (
          <Hinweis ton="warnung">
            Die Präsentation überschreitet {katalog.praesi_grenze_min} Minuten.
          </Hinweis>
        )}
      </section>
    </Karte>
  );
}
