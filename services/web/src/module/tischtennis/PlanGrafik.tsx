import { Etikett, Hinweis, Karte, Leerzustand } from "../../ui";
import type { Spiel, Tabelle } from "./api";
import { Raster } from "./Raster";
import stil from "./TischtennisSeite.module.css";

/**
 * Der Spielplan als Bild — die Ansicht, die das Dashboard zeigt.
 *
 * Oben die Gruppen: je eine Karte mit ihrer Tabelle und darunter den
 * Begegnungen, abgehakt sobald sie gewertet sind. Unten das KO-Raster,
 * sobald es steht.
 *
 * Eine Liste aus achtzehn Zeilen beantwortet die Frage „wer spielt gegen
 * wen“ auch — aber erst, nachdem man sie gelesen hat. Dieses Bild
 * beantwortet sie im Vorbeigehen, und dafür hängt es im Saal.
 */
export function PlanGrafik({
  tabellen,
  spiele,
}: {
  tabellen: Tabelle[];
  spiele: Spiel[];
}) {
  const ko = spiele.filter((spiel) => spiel.phase === "ko");
  const gruppen = tabellen.filter((tabelle) => tabelle.titel.startsWith("Gruppe"));
  const einzeln = tabellen.filter((tabelle) => !tabelle.titel.startsWith("Gruppe"));

  if (tabellen.length === 0 && ko.length === 0) {
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
              (gruppen.length === 0 && spiel.phase !== "ko"),
          )}
        />
      ))}

      {ko.length > 0 && (
        <section aria-labelledby="raster">
          <h2 id="raster" className={stil.abschnittstitel}>
            KO-Raster
          </h2>
          <Karte>
            <Raster spiele={ko} />
          </Karte>
        </section>
      )}
    </div>
  );
}

function Gruppenkarte({ tabelle, spiele }: { tabelle: Tabelle; spiele: Spiel[] }) {
  // Ohne Leerzeichen: aria-labelledby ist eine Liste von Kennungen, und
  // "gruppe-Gruppe A" waere zwei davon gewesen - die Ueberschrift haette
  // dann keinen Namen mehr getragen.
  const kennung = `gruppe-${tabelle.titel.replace(/\s+/g, "-")}`;

  return (
    <section aria-labelledby={kennung}>
      <h2 id={kennung} className={stil.abschnittstitel}>
        {tabelle.titel}
      </h2>

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
    </section>
  );
}
