import type { Spiel } from "./api";
import stil from "./TischtennisSeite.module.css";

/**
 * Das KO-Raster als Bild.
 *
 * Eine Spalte je Runde, die Paarungen darin gleichmäßig verteilt: damit
 * steht das Halbfinale auf der Höhe zwischen seinen beiden Viertelfinals,
 * und der Weg nach vorn ist zu sehen, ohne ihn aus Spielnummern
 * zusammenzusuchen. Die Verbindungslinien sind reine Dekoration aus CSS —
 * sie tragen keine Aussage, die nicht schon im Text steht.
 *
 * Bewusst keine Zeichnung mit festen Koordinaten: Namen sind
 * unterschiedlich lang, und ein Raster, das bei „Maximilian“ bricht, ist
 * schlechter als eines, das mitwächst.
 */
export function Raster({
  spiele,
  beschriftung = "KO-Raster",
}: {
  spiele: Spiel[];
  beschriftung?: string;
}) {
  const runden = [...new Set(spiele.map((spiel) => spiel.runde))].sort((a, b) => a - b);

  return (
    <div className={stil.raster} role="group" aria-label={beschriftung}>
      {runden.map((runde) => {
        const dieser = spiele.filter((spiel) => spiel.runde === runde);
        return (
          <div key={runde} className={stil.rasterspalte}>
            <h3 className={stil.rundenname}>
              {dieser[0]?.bezeichnung ?? `Runde ${runde}`}
            </h3>
            <ol className={stil.rasterliste}>
              {dieser.map((spiel) => (
                <li key={spiel.id} className={stil.rasterspiel}>
                  <Seite spiel={spiel} wer="heim" />
                  <Seite spiel={spiel} wer="gast" />
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Ein Platz im Raster.
 *
 * Steht der Name noch nicht fest, steht da, woher er kommt — „Sieger aus
 * Spiel 13“. Eine leere Zeile wäre an dieser Stelle die Auskunft, dass
 * niemand spielt, und das stimmt nicht.
 */
function Seite({ spiel, wer }: { spiel: Spiel; wer: "heim" | "gast" }) {
  const name = wer === "heim" ? spiel.heim : spiel.gast;
  const herkunft = wer === "heim" ? spiel.heim_herkunft : spiel.gast_herkunft;
  const kennung = wer === "heim" ? spiel.heim_id : spiel.gast_id;
  const gewonnen = kennung !== null && kennung === spiel.sieger_id;
  const verloren = spiel.sieger_id !== null && !gewonnen && kennung !== null;

  return (
    <div
      className={[
        stil.rasterplatz,
        gewonnen ? stil.rastersieger : "",
        verloren ? stil.rasterverloren : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className={stil.rastername}>{name ?? herkunft ?? "offen"}</span>
      {/* Sichtbar trägt das die Zeile selbst: halbfett, mit einem Strich an
          der Kante, und der Verlierer tritt zurück. Ein Etikett „weiter"
          dahinter sagte dasselbe ein zweites Mal -- und zwar in jeder
          entschiedenen Paarung des Rasters, also am Ende in der Hälfte
          aller Zeilen.
          Vorgelesen bleibt es stehen: Schriftschnitt und Strich kommen bei
          einem Screenreader nicht an. */}
      {gewonnen && <span className="nur-vorlesen">weiter</span>}
    </div>
  );
}
