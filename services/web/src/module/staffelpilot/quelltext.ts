/**
 * Python einfärben — ohne Abhängigkeit.
 *
 * Warum selbst und nicht CodeMirror: dieses Projekt hat drei
 * Laufzeitabhängigkeiten (react, react-dom, react-router-dom) und bindet
 * nicht einmal eine Schrift von außen ein, weil es auf einem Raspberry Pi
 * läuft. Ein Editorpaket wären sechs weitere Pakete und ein paar hundert
 * Kilobyte für ein Feld, in dem Regeldateien stehen. Was hier gebraucht wird
 * — Schlüsselwörter, Zeichenketten, Kommentare, Zahlen, Dekoratoren — ist
 * eine überschaubare Menge.
 *
 * **Reine Funktion.** Sie kennt kein DOM und keinen Zustand; prüfen lässt sie
 * sich damit ohne Browser, an echten Regeldateien.
 *
 * Sie versteht Python **nicht**, sie erkennt es nur. Das reicht zum Einfärben
 * und ist ausdrücklich keine Prüfung: ob eine Datei lädt, sagt der Prüfdienst
 * und nicht diese Datei.
 */

/** Was ein Stück Quelltext ist. `text` ist alles Übrige. */
export type Art =
  | "text"
  | "kommentar"
  | "zeichenkette"
  | "schluessel"
  | "zahl"
  | "dekorator"
  | "eingebaut";

export interface Stueck {
  art: Art;
  text: string;
}

/** Pythons Schlüsselwörter, so weit sie in Regeldateien vorkommen. */
// prettier-ignore
const SCHLUESSEL = new Set([
  "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
  "del", "elif", "else", "except", "finally", "for", "from", "global", "if",
  "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
  "return", "try", "while", "with", "yield",
]);

/**
 * Namen, die in jeder Regeldatei bereitstehen.
 *
 * Die oberen vier stellt der Lader: `regel`, `melde`, `spiel`, `ANZAHL`. Sie
 * werden nicht importiert, sondern in einem gestellten Namensraum ausgeführt
 * — wer sie sucht, findet sie in keinem `import`, und genau deshalb lohnt es
 * sich, sie hervorzuheben.
 */
// prettier-ignore
const EINGEBAUT = new Set([
  "regel", "melde", "spiel", "ANZAHL",
  "True", "False", "None", "self",
  "len", "any", "all", "sorted", "set", "list", "dict", "str", "int", "float",
  "print", "range", "enumerate", "zip", "min", "max", "sum", "abs", "round",
]);

const WORT = /[A-Za-z_][A-Za-z0-9_]*/y;
const ZAHL = /\d[\d_]*(\.\d[\d_]*)?/y;

/**
 * Den Quelltext in Stücke zerlegen.
 *
 * Die Reihenfolge der Fälle ist nicht beliebig: Kommentar vor Zeichenkette
 * (ein `#` in Anführungszeichen ist Text, aber ein `"` nach `#` ist ein
 * Kommentar), dreifache Anführungszeichen vor einfachen, und Wörter vor
 * Zahlen — sonst würde aus `regel2` eine `2`.
 */
export function zerlege(quelltext: string): Stueck[] {
  const stuecke: Stueck[] = [];
  let puffer = "";
  let i = 0;

  const schiebe = (art: Art, text: string) => {
    if (puffer) {
      stuecke.push({ art: "text", text: puffer });
      puffer = "";
    }
    stuecke.push({ art, text });
  };

  while (i < quelltext.length) {
    const z = quelltext[i]!;

    // Kommentar bis Zeilenende.
    if (z === "#") {
      const ende = quelltext.indexOf("\n", i);
      const bis = ende === -1 ? quelltext.length : ende;
      schiebe("kommentar", quelltext.slice(i, bis));
      i = bis;
      continue;
    }

    // Zeichenketten. Dreifache zuerst: sonst endet """ sofort nach dem
    // ersten Anführungszeichen, und der Rest der Datei wäre Text.
    if (z === '"' || z === "'") {
      const dreifach = quelltext.slice(i, i + 3);
      const marke = dreifach === z.repeat(3) ? dreifach : z;
      let j = i + marke.length;
      while (j < quelltext.length) {
        if (quelltext[j] === "\\") {
          j += 2;
          continue;
        }
        if (quelltext.startsWith(marke, j)) {
          j += marke.length;
          break;
        }
        // Eine einfache Zeichenkette endet spätestens am Zeilenende --
        // sonst färbt ein vergessenes Anführungszeichen die halbe Datei.
        if (marke.length === 1 && quelltext[j] === "\n") break;
        j += 1;
      }
      schiebe("zeichenkette", quelltext.slice(i, Math.min(j, quelltext.length)));
      i = Math.min(j, quelltext.length);
      continue;
    }

    // Dekorator: @regel(...) steht über jeder Prüfung.
    if (z === "@") {
      WORT.lastIndex = i + 1;
      const treffer = WORT.exec(quelltext);
      if (treffer && treffer.index === i + 1) {
        schiebe("dekorator", quelltext.slice(i, i + 1 + treffer[0].length));
        i += 1 + treffer[0].length;
        continue;
      }
    }

    // Wörter vor Zahlen: sonst wird aus `regel2` eine `2`.
    if (/[A-Za-z_]/.test(z)) {
      WORT.lastIndex = i;
      const treffer = WORT.exec(quelltext)!;
      const wort = treffer[0];
      if (SCHLUESSEL.has(wort)) schiebe("schluessel", wort);
      else if (EINGEBAUT.has(wort)) schiebe("eingebaut", wort);
      else puffer += wort;
      i += wort.length;
      continue;
    }

    if (/\d/.test(z)) {
      ZAHL.lastIndex = i;
      const treffer = ZAHL.exec(quelltext)!;
      schiebe("zahl", treffer[0]);
      i += treffer[0].length;
      continue;
    }

    puffer += z;
    i += 1;
  }

  if (puffer) stuecke.push({ art: "text", text: puffer });
  return stuecke;
}

/** Wie viele Zeilen der Quelltext hat — mindestens eine. */
export function zeilen(quelltext: string): number {
  return quelltext.split("\n").length;
}

/**
 * Die Einrückung der Zeile, in der die Schreibmarke steht.
 *
 * Für die Eingabetaste: in Python ist Einrückung keine Geschmacksfrage, und
 * ein Editor, der nach `if ...:` in Spalte 1 weitermacht, ist unbenutzbar.
 */
export function einrueckung(quelltext: string, stelle: number): string {
  const anfang = quelltext.lastIndexOf("\n", stelle - 1) + 1;
  const zeile = quelltext.slice(anfang, stelle);
  const leer = /^[ \t]*/.exec(zeile)![0];
  // Nach einem Doppelpunkt am Zeilenende eine Stufe tiefer.
  return zeile.trimEnd().endsWith(":") ? leer + "    " : leer;
}
