import type { FrageDaten, FrageEingabe, Fragetyp } from "./api";
import { TYPWORT } from "./texte";

/** Was ein neuer Fragetyp vorbelegt mitbringt - nie ein leeres Formular,
 *  das beim Speichern drei Fehler meldet. */
export function vorlage(typ: Fragetyp): FrageDaten {
  switch (typ) {
    case "freitext":
      return { typ, loesungen: [""] };
    case "bild":
      return { typ, loesungen: [] };
    case "zahl":
      return { typ, loesung: 0, toleranz: 0, einheit: "" };
    case "schaetzung":
      return { typ, minimum: 0, maximum: 100, schritt: 1, loesung: 50, einheit: "" };
    case "auswahl":
      return {
        typ,
        optionen: [
          { text: "", richtig: true },
          { text: "", richtig: false },
        ],
      };
    case "buzzer":
      return { typ, loesung: "" };
    case "hotspot":
      return { typ, ziele: [{ x: 50, y: 50, radius: 10 }] };
    case "sortieren":
      return { typ, elemente: ["", ""] };
  }
}

export const LEERE_FRAGE: FrageEingabe = {
  text: "",
  kategorie: "",
  punkte: 1,
  zeitlimit: 30,
  daten: vorlage("freitext"),
};

export const TYPEN = Object.keys(TYPWORT) as Fragetyp[];

export function zeilen(text: string): string[] {
  return text.split("\n");
}

/** Leere Zeilen fliegen vor dem Speichern raus - eine Lösung "" ist keine. */
export function bereinigt(frage: FrageEingabe): FrageEingabe {
  const d = frage.daten;
  const ohneLeere = (liste: string[]) => liste.map((t) => t.trim()).filter(Boolean);
  let daten: FrageDaten = d;
  if (d.typ === "freitext" || d.typ === "bild")
    daten = { ...d, loesungen: ohneLeere(d.loesungen) };
  if (d.typ === "sortieren") daten = { ...d, elemente: ohneLeere(d.elemente) };
  if (d.typ === "auswahl")
    daten = { ...d, optionen: d.optionen.filter((o) => o.text.trim() !== "") };
  // Ausdruecklich Feld fuer Feld: Beim Bearbeiten ist `frage` eine
  // gespeicherte Frage samt id und position, und die gehoeren nicht in den
  // Koerper der Anfrage.
  return {
    text: frage.text.trim(),
    kategorie: frage.kategorie.trim(),
    punkte: frage.punkte,
    zeitlimit: frage.zeitlimit,
    daten,
  };
}
