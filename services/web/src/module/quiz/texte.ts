import type { Frage, Fragetyp } from "./api";

/** Die Fragetypen so, wie sie in der Oberfläche heißen. */
export const TYPWORT: Record<Fragetyp, string> = {
  freitext: "Freitext",
  zahl: "Zahl",
  schaetzung: "Schätzfrage",
  auswahl: "Auswahl",
  buzzer: "Buzzer",
  bild: "Bildfrage",
  hotspot: "Bild antippen",
  sortieren: "Sortieren",
  zuordnen: "Zuordnen",
  bildauswahl: "Bildauswahl",
};

function zahl(wert: number, einheit = ""): string {
  return `${String(wert).replace(".", ",")} ${einheit}`.trim();
}

/** Die Lösung einer Frage in einer Zeile - für die Leitung. */
export function loesungstext(frage: Frage): string {
  const d = frage.daten;
  switch (d.typ) {
    case "freitext":
      return d.loesungen.length ? d.loesungen.join(" / ") : "bewertest du von Hand";
    case "bild":
      return d.loesungen.length ? d.loesungen.join(" / ") : "bewertest du von Hand";
    case "zahl":
      return d.toleranz
        ? `${zahl(d.loesung, d.einheit)} (± ${zahl(d.toleranz)})`
        : zahl(d.loesung, d.einheit);
    case "schaetzung":
      return `${zahl(d.loesung, d.einheit)} - wer am nächsten liegt`;
    case "auswahl":
      return d.optionen
        .filter((o) => o.richtig)
        .map((o) => o.text)
        .join(", ");
    case "buzzer":
      return d.loesung || "bewertest du von Hand";
    case "hotspot":
      return `${d.ziele.length} ${d.ziele.length === 1 ? "Stelle" : "Stellen"} im Bild`;
    case "sortieren":
      return d.elemente.join(" → ");
    case "zuordnen":
      return d.paare.map((p) => `${p.links} → ${p.rechts}`).join(", ");
    case "bildauswahl":
      return d.optionen
        .map((o, i) => (o.richtig ? o.text || `Bild ${i + 1}` : null))
        .filter(Boolean)
        .join(", ");
  }
}
