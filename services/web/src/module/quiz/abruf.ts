import { useCallback, useEffect, useRef, useState } from "react";

import { meldung } from "../../api/client";
import { ladeRundenstand, type Rundenstand } from "./api";

/**
 * Jede anderthalb Sekunden. Ein Quiz ist schneller als ein Tischtennisspiel:
 * Wer nach dem Zeigen fünf Sekunden auf die Frage wartet, hat ein Drittel
 * seiner Zeit verloren. Zwanzig Handys sind damit gut dreizehn Anfragen je
 * Sekunde - das trägt ein Pi 5 mühelos.
 */
export const TAKT = 1500;

export type Abruf =
  | { phase: "laedt" }
  | { phase: "fertig"; stand: Rundenstand; versatz: number }
  | { phase: "fehler"; nachricht: string; unbekannt: boolean };

/**
 * Versatz zwischen Server- und Geräteuhr in Millisekunden.
 *
 * Der Countdown rechnet mit der Uhr des Servers. Die des Handys liegt gern
 * eine halbe Minute daneben, und dann liefe die Zeit auf jedem Gerät anders
 * ab - oder wäre schon vorbei, bevor die Frage erscheint.
 */
export function versatzVon(serverJetzt: string, empfangen: number): number {
  return Date.parse(serverJetzt) - empfangen;
}

/** Ganze Sekunden bis zur Frist, nie unter null. */
export function restSekunden(frist: string, versatz: number, jetzt = Date.now()): number {
  return Math.max(0, Math.ceil((Date.parse(frist) - (jetzt + versatz)) / 1000));
}

/** Der Stand einer Runde, im Takt nachgefragt. */
export function useRundenstand(code: string | null) {
  const [abruf, setAbruf] = useState<Abruf>({ phase: "laedt" });
  const aktuell = useRef(code);
  aktuell.current = code;

  const uebernehmen = useCallback((stand: Rundenstand) => {
    setAbruf({ phase: "fertig", stand, versatz: versatzVon(stand.jetzt, Date.now()) });
  }, []);

  const holen = useCallback(
    async (signal?: AbortSignal) => {
      if (!aktuell.current) return;
      try {
        uebernehmen(await ladeRundenstand(aktuell.current, signal));
      } catch (fehler) {
        if (signal?.aborted) return;
        const unbekannt = (fehler as { status?: number }).status === 404;
        // Ein abgerissener Abruf tauscht eine stehende Anzeige nicht gegen
        // eine Fehlerseite: das WLAN im Saal ist mal weg, und der Stand von
        // eben ist besser als nichts. Nur eine unbekannte Runde ist endgültig.
        setAbruf((vorher) =>
          vorher.phase === "fertig" && !unbekannt
            ? vorher
            : { phase: "fehler", nachricht: meldung(fehler), unbekannt },
        );
      }
    },
    [uebernehmen],
  );

  useEffect(() => {
    if (!code) return;
    setAbruf({ phase: "laedt" });
    const controller = new AbortController();
    void holen(controller.signal);
    const uhr = window.setInterval(() => void holen(controller.signal), TAKT);
    return () => {
      controller.abort();
      window.clearInterval(uhr);
    };
  }, [code, holen]);

  return { abruf, uebernehmen, neuLaden: holen };
}

/** Die eingetippte Schreibweise eines Codes: groß, ohne Leer- und Bindestriche. */
export function codeAusEingabe(eingabe: string): string {
  return eingabe.replace(/[\s-]/g, "").toUpperCase();
}
