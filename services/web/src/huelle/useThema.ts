import { useCallback, useEffect, useState } from "react";

export type Thema = "system" | "hell" | "dunkel";

const SCHLUESSEL = "homepi.thema";

function gespeichertesThema(): Thema {
  try {
    const wert = localStorage.getItem(SCHLUESSEL);
    if (wert === "hell" || wert === "dunkel") return wert;
  } catch {
    // Privates Fenster oder blockierte Speicherung - dann eben das System.
  }
  return "system";
}

function systemIstDunkel(): boolean {
  return globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/**
 * Thema lesen und setzen.
 *
 * Heisst als einzige Funktion im Projekt englisch: die Hook-Regeln von React
 * erkennen einen Hook am Praefix "use". Ohne das meldet der Linter jeden
 * Aufruf als Regelverstoss.
 *
 * Solange der Benutzer nichts gewählt hat, folgt die Oberfläche dem System -
 * es wird also kein Attribut gesetzt und `light-dark()` entscheidet allein.
 * Erst eine ausdrückliche Wahl schreibt `data-thema` und überstimmt das
 * System dauerhaft.
 */
export function useThema() {
  const [thema, setzeThemaIntern] = useState<Thema>(gespeichertesThema);
  const [systemDunkel, setzeSystemDunkel] = useState(systemIstDunkel);

  // Auf Systemwechsel reagieren, solange kein eigenes Thema gewählt ist -
  // sonst bliebe der Umschalter nach einem Wechsel falsch beschriftet.
  useEffect(() => {
    const abfrage = globalThis.matchMedia?.("(prefers-color-scheme: dark)");
    if (!abfrage) return;

    const beiWechsel = (ereignis: MediaQueryListEvent) =>
      setzeSystemDunkel(ereignis.matches);
    abfrage.addEventListener("change", beiWechsel);
    return () => abfrage.removeEventListener("change", beiWechsel);
  }, []);

  useEffect(() => {
    const wurzel = document.documentElement;
    if (thema === "system") {
      wurzel.removeAttribute("data-thema");
    } else {
      wurzel.setAttribute("data-thema", thema);
    }

    try {
      if (thema === "system") localStorage.removeItem(SCHLUESSEL);
      else localStorage.setItem(SCHLUESSEL, thema);
    } catch {
      // Nicht speichern zu können ist kein Grund, die Ansicht zu verweigern.
    }
  }, [thema]);

  const istDunkel = thema === "dunkel" || (thema === "system" && systemDunkel);

  const wechsle = useCallback(() => {
    setzeThemaIntern(istDunkel ? "hell" : "dunkel");
  }, [istDunkel]);

  return { thema, istDunkel, wechsle, setzeThema: setzeThemaIntern };
}
