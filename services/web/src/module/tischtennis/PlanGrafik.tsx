import { Abschnitt, Etikett, Hinweis, Karte, Leerzustand } from "../../ui";
import type { Phase, Spiel, Tabelle } from "./api";
import { Raster } from "./Raster";
import stil from "./TischtennisSeite.module.css";

/**
 * Der Spielplan als Bild — die Ansicht, die das Dashboard zeigt.
 *
 * Eine Liste aus achtzehn Zeilen beantwortet die Frage „wer spielt gegen
 * wen“ auch — aber erst, nachdem man sie gelesen hat. Dieses Bild
 * beantwortet sie im Vorbeigehen, und dafür hängt es im Saal.
 *
 * **Tabelle oder Raster, nie beides.** Solange die Gruppen laufen, ist die
 * Tabelle die Auskunft: sie sagt, wer weiterkommt. Sobald das Raster steht,
 * ist sie Vergangenheit — wer im Viertelfinale steht, interessiert nicht
 * mehr, mit welchem Punktestand er dorthin kam. Dann verschwindet sie, und
 * das Raster bekommt den Platz.
 */

/** Die drei Stränge des Rasters, in der Reihenfolge, in der sie hängen. */
const ZWEIGE: { phase: Phase; titel: string; erklaerung?: string }[] = [
  { phase: "ko", titel: "KO-Raster" },
  {
    phase: "ko_verlierer",
    titel: "Verliererrunde",
    erklaerung: "Zweite Chance: erst die zweite Niederlage ist das Aus.",
  },
  { phase: "ko_finale", titel: "Endspiel" },
];

export function PlanGrafik({
  tabellen,
  spiele,
}: {
  tabellen: Tabelle[];
  spiele: Spiel[];
}) {
  const zweige = ZWEIGE.map((zweig) => ({
    ...zweig,
    spiele: spiele.filter((spiel) => spiel.phase === zweig.phase),
  })).filter((zweig) => zweig.spiele.length > 0);

  // Steht das Raster, trägt es die Auskunft. Dann ist die Tabelle nur noch
  // Beiwerk, das mitscrollen muss.
  const rasterSteht = zweige.length > 0;
  const gruppen = rasterSteht
    ? []
    : tabellen.filter((tabelle) => tabelle.titel.startsWith("Gruppe"));
  const einzeln = rasterSteht
    ? []
    : tabellen.filter((tabelle) => !tabelle.titel.startsWith("Gruppe"));

  if (!rasterSteht && tabellen.length === 0) {
    return (
      <Leerzustand titel="Noch kein Spielplan">
        Sobald ausgewürfelt ist, steht hier, wer gegen wen spielt.
      </Leerzustand>
    );
  }

  return (
    <div className={stil.plangrafik}>
      {[...gruppen, ...einzeln].map((tabelle) => (
        <Gruppenkarte
          key={tabelle.titel}
          tabelle={tabelle}
          spiele={spiele.filter(
            (spiel) =>
              spiel.gruppe === tabelle.titel ||
              (gruppen.length === 0 && !spiel.phase.startsWith("ko")),
          )}
        />
      ))}

      {zweige.map((zweig) => (
        <Zweigkarte
          key={zweig.phase}
          titel={zweig.titel}
          erklaerung={zweig.erklaerung}
          spiele={zweig.spiele}
        />
      ))}
    </div>
  );
}

/**
 * Ein Strang des Rasters.
 *
 * Eigene Karte je Zweig, weil Sieger- und Verliererrunde nichts miteinander
 * zu tun haben: ihre Runden zählen getrennt, und in einer Spaltenreihe
 * nebeneinander stünde das Halbfinale neben der dritten Verliererrunde, als
 * wären sie derselbe Weg.
 */
function Zweigkarte({
  titel,
  erklaerung,
  spiele,
}: {
  titel: string;
  erklaerung?: string | undefined;
  spiele: Spiel[];
}) {
  const kennung = `zweig-${titel.replace(/\s+/g, "-")}`;

  return (
    <Abschnitt titel={titel} id={kennung} beiwort={erklaerung}>
      <Karte>
        <Raster spiele={spiele} beschriftung={titel} />
      </Karte>
    </Abschnitt>
  );
}

function Gruppenkarte({ tabelle, spiele }: { tabelle: Tabelle; spiele: Spiel[] }) {
  // Ohne Leerzeichen: aria-labelledby ist eine Liste von Kennungen, und
  // "gruppe-Gruppe A" waere zwei davon gewesen - die Ueberschrift haette
  // dann keinen Namen mehr getragen.
  const kennung = `gruppe-${tabelle.titel.replace(/\s+/g, "-")}`;

  return (
    <Abschnitt titel={tabelle.titel} id={kennung}>
      {tabelle.entscheidung_offen.length > 0 && (
        <Hinweis ton="warnung">
          {`Punktgleich an der Grenze: ${tabelle.entscheidung_offen.join(" und ")}. ` +
            "Das Entscheidungsspiel steht im Plan, sobald die Gruppe durch ist."}
        </Hinweis>
      )}

      <Karte>
        <ol className={stil.rangliste}>
          {tabelle.zeilen.map((zeile) => (
            <li key={zeile.teilnehmer} className={stil.rang}>
              <span className={stil.platzziffer}>{zeile.platz}</span>
              <span className={stil.rangname}>{zeile.teilnehmer}</span>
              <span className={stil.nebensache}>
                {zeile.siege} {zeile.siege === 1 ? "Sieg" : "Siege"}
              </span>
            </li>
          ))}
        </ol>

        {spiele.length > 0 && (
          <ul className={stil.begegnungen}>
            {spiele.map((spiel) => (
              <li key={spiel.id} className={stil.begegnung}>
                <span
                  className={spiel.sieger_id === spiel.heim_id ? stil.sieger : undefined}
                >
                  {spiel.heim ?? spiel.heim_herkunft}
                </span>
                <span className={stil.gegen}>gegen</span>
                <span
                  className={spiel.sieger_id === spiel.gast_id ? stil.sieger : undefined}
                >
                  {spiel.gast ?? spiel.gast_herkunft ?? "Freilos"}
                </span>
                {spiel.zustand === "laeuft" && <Etikett ton="warnung">läuft</Etikett>}
                {spiel.phase === "entscheidung" && (
                  <Etikett ton="neutral">Entscheidung</Etikett>
                )}
              </li>
            ))}
          </ul>
        )}
      </Karte>
    </Abschnitt>
  );
}
