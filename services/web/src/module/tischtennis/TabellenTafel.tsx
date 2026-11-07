import { Karte, Leerzustand } from "../../ui";
import type { Tabelle } from "./api";
import stil from "./TischtennisSeite.module.css";

/**
 * Die Tabellen - je Gruppe eine, im Schweizer System eine einzige.
 *
 * Die Reihenfolge rechnet das Backend: Punkte, direkter Vergleich,
 * Satzdifferenz, Balldifferenz. Hier wird nichts sortiert, sonst stünde die
 * Regel an zwei Stellen und wäre an einer davon irgendwann anders.
 */
export function TabellenTafel({ tabellen }: { tabellen: Tabelle[] }) {
  if (tabellen.length === 0) {
    return (
      <Leerzustand titel="Noch keine Tabelle">
        Sie entsteht, sobald der Spielplan steht.
      </Leerzustand>
    );
  }

  return (
    <section aria-labelledby="tabellen" className={stil.tabellen}>
      <h2 id="tabellen" className={stil.abschnittstitel}>
        Tabellen
      </h2>
      {tabellen.map((tabelle) => (
        <Karte key={tabelle.titel} blank>
          <div className={stil.tabellenrahmen}>
            <table className={stil.tabelle}>
              <caption className={stil.tabellenkopf}>{tabelle.titel}</caption>
              <thead>
                <tr>
                  <th scope="col">Platz</th>
                  <th scope="col">Name</th>
                  <th scope="col">Spiele</th>
                  <th scope="col">Siege</th>
                  <th scope="col">Punkte</th>
                  <th scope="col">Sätze</th>
                  <th scope="col">Bälle</th>
                </tr>
              </thead>
              <tbody>
                {tabelle.zeilen.map((zeile) => (
                  <tr key={zeile.teilnehmer}>
                    <td>{zeile.platz}</td>
                    <th scope="row" className={stil.namenszelle}>
                      {zeile.teilnehmer}
                    </th>
                    <td>{zeile.spiele}</td>
                    <td>{zeile.siege}</td>
                    <td>{zeile.punkte}</td>
                    <td>
                      {zeile.saetze_fuer}:{zeile.saetze_gegen}
                    </td>
                    <td>
                      {zeile.baelle_fuer}:{zeile.baelle_gegen}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Karte>
      ))}
    </section>
  );
}
