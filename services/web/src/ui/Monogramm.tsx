import stil from "./Monogramm.module.css";

interface Props {
  /** Der volle Name. Die Kürzel entstehen hier, nicht beim Aufrufer. */
  name: string;
  /** Eckig statt rund - so stehen Artefakte neben Personen und sind
   *  trotzdem auf den ersten Blick etwas anderes. */
  form?: "rund" | "feld";
  /** Im Akzent gefasst: das geöffnete Artefakt, das eigene Konto. */
  betont?: boolean;
}

/**
 * Kürzel in einem Feld - für Konten und für Artefakte.
 *
 * Bei einem Konto sind es bis zu zwei Buchstaben („Andreas Mütze" → AM),
 * bei einem Artefakt genau einer („StaffelPilot" → S). Den Unterschied
 * macht nicht ein Schalter, sondern die Zahl der Wörter: ein Artefaktname
 * ist eines, ein Personenname zwei.
 *
 * Breite und Höhe sind fest und `overflow` ist zu. Was hier hineinkommt,
 * darf das Feld nicht verlassen - genau das war der Fehler, als hier noch
 * der Symbolname aus dem Manifest stand und über dem Titel lag.
 */
export function Monogramm({ name, form = "rund", betont = false }: Props) {
  return (
    <span
      className={[
        form === "rund" ? stil.rund : stil.feld,
        betont ? stil.betont : undefined,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-hidden="true"
    >
      {kuerzel(name)}
    </span>
  );
}

/** Bis zu zwei Anfangsbuchstaben, groß. Leerer Name ergibt „?" statt nichts -
 *  ein leeres Feld sähe aus wie ein Ladefehler. */
function kuerzel(name: string): string {
  const woerter = name.trim().split(/\s+/).filter(Boolean);
  if (woerter.length === 0) return "?";

  const buchstaben = woerter.slice(0, 2).map((wort) => wort[0] ?? "");
  return buchstaben.join("").toLocaleUpperCase("de");
}
