import stil from "./Regel.module.css";

interface Props {
  /** Kürzere Ausblendung - für schmale Spalten und Telefone. */
  kurz?: boolean;
  className?: string | undefined;
}

/**
 * Die Trennlinie dieses Entwurfs: an beiden Enden ausblendend.
 *
 * Eine Linie, die sauber abschneidet, zieht eine Kante in den Blick und
 * macht aus einer Liste ein Raster aus Kästen. Diese endet in nichts - die
 * Struktur bleibt lesbar, ohne dass der Rahmen mitgelesen wird.
 *
 * Sie ersetzt in der Hülle und auf der Startseite das, was vorher Karten
 * mit Rand taten. Deshalb steht sie in den Bausteinen und nicht als
 * Hilfsklasse in einer Modul-CSS: Beim dritten Nachbau wäre die Länge der
 * Ausblendung an drei Stellen verschieden.
 *
 * `role="presentation"`, nicht `<hr>`: Für einen Screenreader ist die
 * Zeilenstruktur darüber schon durch die Liste ausgesagt. Ein zusätzliches
 * „Trennlinie" nach jedem Eintrag wäre Lärm.
 */
export function Regel({ kurz = false, className }: Props) {
  const klassen = [kurz ? stil.kurz : stil.regel, className].filter(Boolean).join(" ");

  return <div className={klassen} role="presentation" />;
}
