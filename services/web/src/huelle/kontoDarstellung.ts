import { useEffect } from "react";

import {
  holeDarstellung,
  speichereDarstellung,
  type Darstellungswahl,
} from "../api/anmeldung";
import { useAnmeldung } from "../anmeldung/kontext";
import {
  BEWEGUNG_SCHLUESSEL,
  DARSTELLUNG_GEAENDERT,
  GRUND_SCHLUESSEL,
  istGrund,
  THEMA_SCHLUESSEL,
} from "./darstellung";

/**
 * Darstellung im Konto statt nur im Browser.
 *
 * Der Browser behält die Wahl trotzdem: Aus ihm setzt `wendeDarstellungAn`
 * die Seite VOR dem ersten Rendern, sonst blitzte sie bei jedem Laden kurz
 * hell auf, bis das Konto geantwortet hat. Das Konto ist die Quelle, der
 * Browser ihr Zwischenspeicher.
 */

function lies(schluessel: string): string | null {
  try {
    return localStorage.getItem(schluessel);
  } catch {
    return null;
  }
}

/** Was in diesem Browser gerade gilt. */
export function lokaleDarstellung(): Darstellungswahl {
  const thema = lies(THEMA_SCHLUESSEL);
  const grund = lies(GRUND_SCHLUESSEL);
  return {
    thema: thema === "hell" || thema === "dunkel" ? thema : "system",
    grund: istGrund(grund) ? grund : "nocturne",
    bewegung_reduziert: lies(BEWEGUNG_SCHLUESSEL) === "reduziert",
  };
}

/**
 * Setzt eine Darstellung auf Seite und Browser.
 *
 * Schreibt in denselben Speicher und dieselben Attribute wie die Hooks
 * `useThema`, `useGrund` und `useBewegung` - und sagt ihnen über ein
 * Ereignis Bescheid, damit eine offene Einstellungsseite nicht den alten
 * Stand anzeigt.
 */
export function uebernehmeDarstellung(wahl: Darstellungswahl): void {
  const wurzel = document.documentElement;
  const grund = istGrund(wahl.grund) ? wahl.grund : "nocturne";

  if (wahl.thema === "system") wurzel.removeAttribute("data-thema");
  else wurzel.setAttribute("data-thema", wahl.thema);
  if (grund === "nocturne") wurzel.removeAttribute("data-grund");
  else wurzel.setAttribute("data-grund", grund);
  if (wahl.bewegung_reduziert) wurzel.setAttribute("data-bewegung", "reduziert");
  else wurzel.removeAttribute("data-bewegung");

  try {
    if (wahl.thema === "system") localStorage.removeItem(THEMA_SCHLUESSEL);
    else localStorage.setItem(THEMA_SCHLUESSEL, wahl.thema);
    if (grund === "nocturne") localStorage.removeItem(GRUND_SCHLUESSEL);
    else localStorage.setItem(GRUND_SCHLUESSEL, grund);
    if (wahl.bewegung_reduziert) localStorage.setItem(BEWEGUNG_SCHLUESSEL, "reduziert");
    else localStorage.removeItem(BEWEGUNG_SCHLUESSEL);
  } catch {
    // Ohne Speicher gilt die Wahl eben bis zum nächsten Laden.
  }

  window.dispatchEvent(new Event(DARSTELLUNG_GEAENDERT));
}

/**
 * Speichert die Wahl im Konto. Scheitert das, bleibt sie im Browser - eine
 * Darstellung ist keine Auskunft, für die man jemanden mit einer
 * Fehlermeldung aufhält.
 */
export function merkeImKonto(wahl: Darstellungswahl): void {
  speichereDarstellung(wahl).catch(() => undefined);
}

/**
 * Gleicht nach dem Anmelden Konto und Browser ab.
 *
 * Hat das Konto eine Wahl, gilt sie auch hier. Hat es noch keine, wandert
 * die aus dem Browser ins Konto - wer vor dem Konto schon dunkel gestellt
 * hat, soll das durch das Anmelden nicht verlieren.
 */
export function useKontoDarstellung(): void {
  const { zustand } = useAnmeldung();

  useEffect(() => {
    if (zustand !== "angemeldet") return;
    const abbruch = new AbortController();

    holeDarstellung(abbruch.signal)
      .then((imKonto) => {
        if (abbruch.signal.aborted) return;
        if (imKonto === null) merkeImKonto(lokaleDarstellung());
        else uebernehmeDarstellung(imKonto);
      })
      .catch(() => {
        // Gateway hakt: Dann gilt, was der Browser weiß.
      });

    return () => abbruch.abort();
  }, [zustand]);
}
