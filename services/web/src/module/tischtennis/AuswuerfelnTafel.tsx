import { useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand } from "../../ui";
import type { Auslosung, Turnier } from "./api";
import stil from "./TischtennisSeite.module.css";
import { dauer } from "./zeit";

interface Props {
  turnier: Turnier;
  onLosen: (saat?: number) => Promise<Auslosung | null>;
  onUebernehmen: (saat: number) => Promise<boolean>;
  onZuruecksetzen: () => Promise<boolean>;
}

const MODUSWORT: Record<string, string> = {
  gruppen_ko: "Gruppen und KO-Raster",
  ko: "KO-Raster",
  schweizer: "Schweizer System",
};

/**
 * Der Würfel.
 *
 * Die Vorschau ist der Kern dieser Fläche: das Los ist zu sehen, bevor es
 * gilt. „Nochmal“ wirft weg und würfelt neu, ohne dass etwas gespeichert
 * wurde - erst „Übernehmen“ schreibt den Spielplan. Andersherum (speichern,
 * ansehen, verwerfen) müsste jedes Verwerfen den halben Spielplan wieder
 * aufräumen, und ein Fehler dabei wäre ein Turnier mit Spielen aus zwei
 * verschiedenen Losen.
 */
export function AuswuerfelnTafel({
  turnier,
  onLosen,
  onUebernehmen,
  onZuruecksetzen,
}: Props) {
  const [vorschau, setVorschau] = useState<Auslosung | null>(null);
  const [laeuft, setLaeuft] = useState(false);

  async function wuerfeln() {
    setLaeuft(true);
    setVorschau(await onLosen());
    setLaeuft(false);
  }

  async function uebernehmen() {
    if (vorschau === null) return;
    setLaeuft(true);
    const geklappt = await onUebernehmen(vorschau.saat);
    setLaeuft(false);
    if (geklappt) setVorschau(null);
  }

  if (turnier.zustand !== "planung") {
    return (
      <>
        <Karte>
          <h2 className={stil.abschnittstitel}>Der Spielplan steht</h2>
          <p className={stil.nebensache}>
            Ausgewürfelt mit der Saat <strong>{turnier.saat}</strong>. Mit derselben Saat
            entsteht dasselbe Los wieder – deshalb steht sie hier und nicht im
            Verborgenen.
          </p>
          <p className={stil.nebensache}>
            Noch einmal zu würfeln heißt, die {turnier.anzahl_spiele} Spiele samt
            Ergebnissen zu verwerfen. Das geht, aber nicht versehentlich:
          </p>
          <Knopf
            auspraegung="sekundaer"
            disabled={laeuft}
            onClick={() => {
              setLaeuft(true);
              void onZuruecksetzen().finally(() => setLaeuft(false));
            }}
          >
            Spielplan verwerfen und zurück in die Planung
          </Knopf>
        </Karte>
      </>
    );
  }

  if (turnier.anzahl_teilnehmer < 2) {
    return (
      <Leerzustand titel="Erst die Teilnehmer">
        Ab zwei eingetragenen Namen lässt sich auswürfeln. Bisher ist es{" "}
        {turnier.anzahl_teilnehmer === 0 ? "keiner" : "einer"}.
      </Leerzustand>
    );
  }

  return (
    <>
      <Karte>
        <h2 className={stil.abschnittstitel}>Auswürfeln</h2>
        <p className={stil.nebensache}>
          {turnier.anzahl_teilnehmer} Teilnehmer, {MODUSWORT[turnier.modus]}
          {turnier.modus === "gruppen_ko" &&
            `, ${turnier.anzahl_gruppen} Gruppen, ${turnier.weiter_pro_gruppe} je Gruppe weiter`}
          {turnier.modus === "schweizer" && `, ${turnier.runden} Runden`}. Zu ändern unter
          „Einstellungen“.
        </p>
        <Knopf auspraegung="primaer" disabled={laeuft} onClick={() => void wuerfeln()}>
          {laeuft ? "Würfelt …" : vorschau ? "Nochmal würfeln" : "Würfeln"}
        </Knopf>
      </Karte>

      {vorschau !== null && (
        <section aria-labelledby="vorschau">
          <h2 id="vorschau" className={stil.abschnittstitel}>
            Vorschau
          </h2>

          <Hinweis>
            {vorschau.anzahl_spiele} Spiele, geschätzt {dauer(vorschau.dauer_minuten)} auf{" "}
            {turnier.tische} {turnier.tische === 1 ? "Tisch" : "Tischen"}. Gespeichert ist
            davon noch nichts.
          </Hinweis>

          {vorschau.hinweis && <Hinweis ton="warnung">{vorschau.hinweis}</Hinweis>}

          {vorschau.gruppen.length > 0 && (
            <div className={stil.gruppen}>
              {vorschau.gruppen.map((gruppe) => (
                <Karte key={gruppe.name}>
                  <h3 className={stil.gruppenname}>{gruppe.name}</h3>
                  <ol className={stil.gruppenliste}>
                    {gruppe.teilnehmer.map((wer) => (
                      <li key={wer}>{wer}</li>
                    ))}
                  </ol>
                </Karte>
              ))}
            </div>
          )}

          <Karte blank>
            <ol className={stil.liste}>
              {vorschau.paarungen.map((paarung, stelle) => (
                <li key={`${paarung.bezeichnung}-${stelle}`} className={stil.zeile}>
                  <span>
                    {paarung.heim} gegen {paarung.gast}
                  </span>
                  <Etikett ton="neutral">{paarung.bezeichnung}</Etikett>
                </li>
              ))}
            </ol>
          </Karte>

          <div className={stil.aktionen}>
            <Knopf
              auspraegung="primaer"
              disabled={laeuft}
              onClick={() => void uebernehmen()}
            >
              Übernehmen und Turnier starten
            </Knopf>
            <Knopf
              auspraegung="leise"
              disabled={laeuft}
              onClick={() => setVorschau(null)}
            >
              Verwerfen
            </Knopf>
          </div>
          <p className={stil.nebensache}>Saat dieses Loses: {vorschau.saat}</p>
        </section>
      )}
    </>
  );
}
