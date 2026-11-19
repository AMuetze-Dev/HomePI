import { useCallback, useEffect, useState } from "react";

import { BEWEGUNG_SCHLUESSEL as SCHLUESSEL } from "./darstellung";

function gespeichert(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "reduziert";
  } catch {
    // Privates Fenster oder blockierte Speicherung - dann eben voll.
    return false;
  }
}

/**
 * Übergänge abbestellen - unabhängig von der Einstellung des Geräts.
 *
 * Heisst als Hook englisch „use", weil die Hook-Regeln von React einen Hook
 * am Präfix erkennen. Ohne das meldet der Linter jeden Aufruf.
 *
 * Warum überhaupt ein eigener Schalter, wo `prefers-reduced-motion` doch
 * existiert: Auf einem Pi im Wohnzimmer bedient oft jemand das Gerät,
 * dessen Systemeinstellung jemand anderem gehört. Der Schalter hier gilt
 * zusätzlich, nie stattdessen - wer die Bewegung am Gerät abbestellt hat,
 * bekommt sie auch dann nicht, wenn der Schalter aus ist (siehe
 * styles/basis.css).
 */
export function useBewegung() {
  const [reduziert, setzeReduziert] = useState(gespeichert);

  useEffect(() => {
    const wurzel = document.documentElement;
    if (reduziert) wurzel.setAttribute("data-bewegung", "reduziert");
    else wurzel.removeAttribute("data-bewegung");

    try {
      if (reduziert) localStorage.setItem(SCHLUESSEL, "reduziert");
      else localStorage.removeItem(SCHLUESSEL);
    } catch {
      // Nicht speichern zu können ist kein Grund, die Ansicht zu verweigern.
    }
  }, [reduziert]);

  const setze = useCallback((an: boolean) => setzeReduziert(an), []);

  return { reduziert, setzeReduziert: setze };
}
