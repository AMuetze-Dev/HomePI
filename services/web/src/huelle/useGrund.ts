import { useCallback, useEffect, useState } from "react";

import {
  DARSTELLUNG_GEAENDERT,
  GRUND_SCHLUESSEL,
  istGrund,
  type Grund,
} from "./darstellung";

function gespeichert(): Grund {
  try {
    const wert = localStorage.getItem(GRUND_SCHLUESSEL);
    if (istGrund(wert)) return wert;
  } catch {
    // Privates Fenster oder blockierte Speicherung - dann eben der Entwurf.
  }
  return "nocturne";
}

/**
 * Den Stich des Grundes wählen.
 *
 * Heisst als Hook englisch „use", weil die Hook-Regeln von React einen Hook
 * am Präfix erkennen. Ohne das meldet der Linter jeden Aufruf.
 *
 * Geändert wird dabei nur der Grund samt seiner Flächen und Ränder, nicht
 * der Akzent: Der trägt Bedeutung und soll nicht mit dem Geschmack wandern.
 * „nocturne" setzt kein Attribut — es ist der Entwurf, wie er gezeichnet
 * wurde, und steht so in `tokens.css`.
 */
export function useGrund() {
  const [grund, setzeGrundIntern] = useState<Grund>(gespeichert);

  // Kommt die Wahl aus dem Konto, steht sie schon im Speicher - hier nur
  // nachziehen, damit eine offene Einstellungsseite den neuen Stand zeigt.
  useEffect(() => {
    const nachziehen = () => setzeGrundIntern(gespeichert());
    window.addEventListener(DARSTELLUNG_GEAENDERT, nachziehen);
    return () => window.removeEventListener(DARSTELLUNG_GEAENDERT, nachziehen);
  }, []);

  useEffect(() => {
    const wurzel = document.documentElement;
    if (grund === "nocturne") wurzel.removeAttribute("data-grund");
    else wurzel.setAttribute("data-grund", grund);

    try {
      if (grund === "nocturne") localStorage.removeItem(GRUND_SCHLUESSEL);
      else localStorage.setItem(GRUND_SCHLUESSEL, grund);
    } catch {
      // Nicht speichern zu können ist kein Grund, die Ansicht zu verweigern.
    }
  }, [grund]);

  const setze = useCallback((wert: Grund) => setzeGrundIntern(wert), []);

  return { grund, setzeGrund: setze };
}
