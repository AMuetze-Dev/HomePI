import type { AntwortEingabe, OeffentlicheFrage } from "./api";

/**
 * Was ein Spieler gerade eintippt, je Fragetyp.
 *
 * Bewusst ein Entwurf neben dem gespeicherten Stand: Das Handy fragt jede
 * anderthalb Sekunden nach, und ein Abruf darf nicht mitten ins Tippen
 * hinein überschreiben, was noch nicht abgeschickt ist.
 */
export interface Entwurf {
  text: string;
  zahl: string;
  auswahl: number[];
  x: number | null;
  y: number | null;
  reihenfolge: string[];
}

export function leererEntwurf(frage: OeffentlicheFrage): Entwurf {
  const mitte =
    frage.minimum !== null && frage.maximum !== null
      ? String((frage.minimum + frage.maximum) / 2)
      : "";
  return {
    text: "",
    zahl: frage.typ === "schaetzung" ? mitte : "",
    auswahl: [],
    x: null,
    y: null,
    reihenfolge: frage.elemente.map((e) => e.kennung),
  };
}

/** Aus einer schon abgegebenen Antwort - nach einem Neuladen der Seite. */
export function entwurfAus(
  frage: OeffentlicheFrage,
  wert: Record<string, unknown>,
): Entwurf {
  const leer = leererEntwurf(frage);
  return {
    text: typeof wert.text === "string" ? wert.text : leer.text,
    zahl: typeof wert.zahl === "number" ? String(wert.zahl) : leer.zahl,
    auswahl: Array.isArray(wert.auswahl) ? (wert.auswahl as number[]) : leer.auswahl,
    x: typeof wert.x === "number" ? wert.x : null,
    y: typeof wert.y === "number" ? wert.y : null,
    reihenfolge: Array.isArray(wert.reihenfolge)
      ? (wert.reihenfolge as string[])
      : leer.reihenfolge,
  };
}

/** Der Entwurf als Anfrage - nur das Feld, das für den Typ zählt. */
export function alsEingabe(frage: OeffentlicheFrage, entwurf: Entwurf): AntwortEingabe {
  switch (frage.typ) {
    case "zahl":
    case "schaetzung":
      return { zahl: Number(entwurf.zahl.replace(",", ".")), eingeloggt: true };
    case "auswahl":
      return { auswahl: entwurf.auswahl, eingeloggt: true };
    case "hotspot":
      return entwurf.x === null || entwurf.y === null
        ? { eingeloggt: true }
        : { x: entwurf.x, y: entwurf.y, eingeloggt: true };
    case "sortieren":
      return { reihenfolge: entwurf.reihenfolge, eingeloggt: true };
    default:
      return { text: entwurf.text, eingeloggt: true };
  }
}

/** Ob sich der Entwurf abschicken lässt - sonst bleibt der Knopf grau. */
export function vollstaendig(frage: OeffentlicheFrage, entwurf: Entwurf): boolean {
  switch (frage.typ) {
    case "zahl":
    case "schaetzung":
      return (
        entwurf.zahl.trim() !== "" &&
        Number.isFinite(Number(entwurf.zahl.replace(",", ".")))
      );
    case "auswahl":
      return entwurf.auswahl.length > 0;
    case "hotspot":
      return entwurf.x !== null && entwurf.y !== null;
    case "sortieren":
      return entwurf.reihenfolge.length > 0;
    default:
      return entwurf.text.trim() !== "";
  }
}
