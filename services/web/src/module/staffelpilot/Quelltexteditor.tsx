import { useLayoutEffect, useRef } from "react";

import { type Stueck, einrueckung, zeilen, zerlege } from "./quelltext";
import stil from "./StaffelpilotSeite.module.css";

/** Wie viele Leerzeichen eine Stufe sind. Python-Üblich und PEP 8. */
const STUFE = "    ";

const KLASSE: Record<Stueck["art"], string | undefined> = {
  text: undefined,
  kommentar: stil.tkKommentar,
  zeichenkette: stil.tkZeichenkette,
  schluessel: stil.tkSchluessel,
  zahl: stil.tkZahl,
  dekorator: stil.tkDekorator,
  eingebaut: stil.tkEingebaut,
};

/**
 * Ein Editor für Regeldateien — eingefärbt, mit Zeilennummern.
 *
 * **Wie es gemacht ist:** ein durchsichtiges `textarea` über einem `pre` mit
 * denselben Zeichen. Das Browser-Textfeld behält damit alles, was es gut kann
 * — Schreibmarke, Auswahl, Rückgängig, Bildlauf, Vorlesen —, und das `pre`
 * darunter liefert nur die Farbe. Ein nachgebauter Editor müsste jede dieser
 * Eigenschaften selbst bauen und bekäme sie schlechter hin.
 *
 * Beide brauchen **dieselbe** Schrift, Größe, Zeilenhöhe und Polsterung;
 * weicht eine davon ab, laufen Text und Farbe auseinander. Deshalb stehen sie
 * im Stil in einer gemeinsamen Regel.
 *
 * **Warum ohne Editorpaket:** dieses Projekt hat drei Laufzeitabhängigkeiten
 * und bindet nicht einmal eine Schrift von außen ein, weil es auf einem
 * Raspberry Pi läuft. Siehe `quelltext.ts`.
 */
export function Quelltexteditor({
  wert,
  onAendern,
  beschriftung = "Quelltext",
  zeilenMindestens = 20,
}: {
  wert: string;
  onAendern: (wert: string) => void;
  beschriftung?: string;
  zeilenMindestens?: number;
}) {
  const feld = useRef<HTMLTextAreaElement>(null);
  const farbe = useRef<HTMLPreElement>(null);
  const leiste = useRef<HTMLDivElement>(null);
  /** Wohin die Schreibmarke nach der nächsten Änderung gehört. */
  const marke = useRef<[number, number] | null>(null);
  /** Ob der nächste Tabulator den Fokus weiterreichen soll. */
  const raus = useRef(false);

  // Den Bildlauf gleichziehen: scrollt das Textfeld, müssen Farbe und
  // Zeilennummern mit, sonst stehen sie beim Scrollen versetzt.
  function mitlaufen() {
    const quelle = feld.current;
    if (!quelle) return;
    if (farbe.current) {
      farbe.current.scrollTop = quelle.scrollTop;
      farbe.current.scrollLeft = quelle.scrollLeft;
    }
    if (leiste.current) leiste.current.scrollTop = quelle.scrollTop;
  }

  // Nach jeder Änderung: erst die Schreibmarke dorthin, wo sie hingehört,
  // dann den Bildlauf gleichziehen. Beides vor dem Zeichnen.
  useLayoutEffect(() => {
    const ziel = feld.current;
    if (ziel && marke.current) {
      const [von, bis] = marke.current;
      ziel.setSelectionRange(von, bis);
      marke.current = null;
    }
    mitlaufen();
  }, [wert]);

  const anzahl = Math.max(zeilen(wert), zeilenMindestens);

  /** Tabulator rückt ein, statt den Fokus weiterzureichen. */
  function taste(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    const ziel = e.currentTarget;
    const { selectionStart: von, selectionEnd: bis } = ziel;

    // Jede andere Taste nimmt den Ausgang wieder zurück: Escape gilt für den
    // nächsten Tabulator, nicht für den übernächsten.
    if (e.key !== "Escape" && e.key !== "Tab") raus.current = false;

    if (e.key === "Escape") {
      // Der Ausgang. Weil der Tabulator hier einrückt, käme man mit der
      // Tastatur sonst nicht mehr aus dem Feld heraus -- ein Feld, das die
      // Tastatur festhält, ist kein Editor, sondern eine Falle.
      raus.current = true;
      return;
    }

    if (e.key === "Tab") {
      if (raus.current) {
        // Nach Escape einmal durchlassen: der Fokus geht weiter.
        raus.current = false;
        return;
      }
      // Ohne das springt der Fokus weiter -- in einem Feld mit Python ist das
      // die eine Taste, die man am häufigsten braucht.
      e.preventDefault();
      if (e.shiftKey) {
        const anfang = wert.lastIndexOf("\n", von - 1) + 1;
        const zeile = wert.slice(anfang, von);
        const weg = zeile.startsWith(STUFE)
          ? STUFE.length
          : zeile.startsWith(" ")
            ? 1
            : 0;
        if (!weg) return;
        setzen(wert.slice(0, anfang) + wert.slice(anfang + weg), von - weg, bis - weg);
        return;
      }
      setzen(wert.slice(0, von) + STUFE + wert.slice(bis), von + STUFE.length);
      return;
    }

    if (e.key === "Enter") {
      // Einrückung halten und nach einem Doppelpunkt eine Stufe tiefer. In
      // Python ist das keine Bequemlichkeit, sondern die Bedeutung.
      e.preventDefault();
      const tiefe = einrueckung(wert, von);
      setzen(wert.slice(0, von) + "\n" + tiefe + wert.slice(bis), von + 1 + tiefe.length);
    }
  }

  function setzen(neu: string, von: number, bis = von) {
    // Die Marke wird gemerkt und im Layout-Effekt gesetzt, nicht hier und
    // nicht in `requestAnimationFrame`.
    //
    // Mit `requestAnimationFrame` war es ein Wettlauf: der nächste
    // Tastendruck kam vorher, landete an der alten Stelle, und aus
    // "{Tab}melde(1)" wurde "elde(1)m". Ein Layout-Effekt läuft nach dem
    // Schreiben des DOM und vor dem Zeichnen -- dazwischen passiert nichts.
    marke.current = [von, bis];
    onAendern(neu);
  }

  return (
    <>
      <div className={stil.editorRahmen}>
        <div className={stil.editorLeiste} ref={leiste} aria-hidden="true">
          {Array.from({ length: anzahl }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>

        <div className={stil.editorFlaeche}>
          {/* Die Farbe liegt darunter und nimmt keine Eingaben an. */}
          <pre className={stil.editorFarbe} ref={farbe} aria-hidden="true">
            {zerlege(wert).map((s, i) => (
              <span key={i} className={KLASSE[s.art]}>
                {s.text}
              </span>
            ))}
            {/* Eine Leerzeile am Ende: ohne sie schneidet das `pre` die letzte
              Zeile ab, wenn der Text mit \n endet. */}
            {"\n"}
          </pre>

          <textarea
            ref={feld}
            className={stil.editorEingabe}
            aria-label={beschriftung}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            value={wert}
            rows={anzahl}
            onChange={(e) => onAendern(e.target.value)}
            onKeyDown={taste}
            onScroll={mitlaufen}
          />
        </div>
      </div>

      {/* Der Ausgang muss dastehen. Dass der Tabulator einrueckt, merkt man
          sofort; dass Escape ihn wieder freigibt, raet niemand. */}
      <p className={stil.editorFuss}>
        <kbd>Tab</kbd> rückt ein, <kbd>Umschalt</kbd>+<kbd>Tab</kbd> zurück.{" "}
        <kbd>Esc</kbd>, dann <kbd>Tab</kbd> verlässt das Feld.
      </p>
    </>
  );
}
