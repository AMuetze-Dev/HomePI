import { useMemo } from "react";

import { Karte, Leerzustand } from "../../ui";
import type { Flussbild, Knotenart } from "./api";
import { alsEuro } from "./geld";
import stil from "./HaushaltsbuchSeite.module.css";
import { baueFlussbild, KNOTEN_BREITE, type Band } from "./sankey";

/** Ein Rand oben und unten, damit nichts an der Kante klebt. */
const RAND = 10;

const WORT: Record<Knotenart, string> = {
  einnahme: "Einnahme",
  konto: "Konto",
  kategorie: "Kategorie",
  posten: "Posten",
};

/**
 * Das Flussbild - ein Sankey, von Hand gezeichnet.
 *
 * Es ist die eine Ansicht, die jemand versteht, ohne dieses Artefakt zu
 * kennen: links kommt Geld herein, rechts geht es weg, und die Dicke eines
 * Bandes sagt wie viel. Genau dafür ist sie gebaut.
 */
export function FlussTafel({ bild }: { bild: Flussbild }) {
  const aufbau = useMemo(() => baueFlussbild(bild), [bild]);

  if (aufbau.plaetze.length === 0) {
    return (
      <Leerzustand titel="Noch nichts zu zeigen">
        Sobald unter <strong>Posten</strong> ein Einkommen und eine Ausgabe stehen,
        zeichnet diese Seite, wohin das Geld läuft.
      </Leerzustand>
    );
  }

  const hoehe = aufbau.hoehe + RAND * 2;

  return (
    <>
      <Karte blank>
        <div className={stil.rollbereich}>
          <svg
            className={stil.flussbild}
            viewBox={`0 0 ${aufbau.breite} ${hoehe}`}
            role="img"
            aria-label="Geldfluss eines Monats: von den Einnahmen über die Konten und Kategorien zu den einzelnen Posten"
          >
            <g transform={`translate(0 ${RAND})`}>
              {aufbau.baender.map((band) => (
                <path key={band.id} className={bandstil(band)} d={band.pfad}>
                  <title>
                    {band.von.beschriftung} → {band.nach.beschriftung}:{" "}
                    {alsEuro(String(band.wert))}
                  </title>
                </path>
              ))}

              {aufbau.plaetze.map((platz) => {
                const letzte = platz.knoten.ebene === bild.ebenen - 1;
                return (
                  <g key={platz.id}>
                    <rect
                      className={`${stil.knoten} ${stil[`knoten_${platz.knoten.art}`]}`}
                      x={platz.x}
                      y={platz.y}
                      width={KNOTEN_BREITE}
                      height={platz.hoehe}
                      rx={2}
                    >
                      <title>
                        {platz.knoten.beschriftung}: {alsEuro(String(platz.wert))}
                      </title>
                    </rect>
                    <text
                      className={stil.knotenname}
                      x={letzte ? platz.x + KNOTEN_BREITE + 6 : platz.x - 6}
                      y={platz.y + platz.hoehe / 2}
                      textAnchor={letzte ? "start" : "end"}
                      dominantBaseline="middle"
                    >
                      {platz.knoten.beschriftung}
                      <tspan className={stil.knotenwert} dx="6">
                        {alsEuro(String(platz.wert))}
                      </tspan>
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </Karte>

      <p className={stil.legende}>
        Jede Spalte ist eine Station: Einnahmen, Konten, Kategorien, einzelne Posten. Alle
        Beträge sind Monatsbeträge — was jährlich abgebucht wird, steht hier mit seiner
        monatlichen Rücklage.
      </p>

      {/* Das Bild selbst ist für einen Screenreader eine Fläche. Die Tabelle
          sagt dasselbe in Worten und steht deshalb hier, nicht als Ersatz
          irgendwo anders. */}
      <table className="nur-vorlesen">
        <caption>Geldfluss in Zahlen</caption>
        <thead>
          <tr>
            <th scope="col">von</th>
            <th scope="col">nach</th>
            <th scope="col">Betrag im Monat</th>
          </tr>
        </thead>
        <tbody>
          {aufbau.baender.map((band) => (
            <tr key={band.id}>
              <td>
                {WORT[band.von.art]} {band.von.beschriftung}
              </td>
              <td>
                {WORT[band.nach.art]} {band.nach.beschriftung}
              </td>
              <td>{alsEuro(String(band.wert))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

/**
 * Die Farbe eines Bandes sagt, woher es kommt.
 *
 * Eingehendes Geld, Verteilung zwischen Konten, Verbrauch - drei Aussagen,
 * drei Töne aus den Tokens. Mehr wäre Dekoration.
 */
function bandstil(band: Band): string {
  return `${stil.band} ${stil[`band_${band.von.art}`]}`;
}
