import { useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand } from "../../ui";
import type { Auslosung, Richtung, Spiel, Teilnehmer, Turnier } from "./api";
import stil from "./TischtennisSeite.module.css";
import { dauer, uhrzeit } from "./zeit";

interface Props {
  turnier: Turnier;
  teilnehmer: Teilnehmer[];
  spiele: Spiel[];
  darfEinrichten: boolean;
  onTeilnehmerAnlegen: (name: string) => Promise<boolean>;
  onTeilnehmerEntfernen: (id: string) => void;
  onLosen: () => Promise<Auslosung | null>;
  onUebernehmen: (saat: number) => Promise<boolean>;
  onZuruecksetzen: () => void;
  onBeginnen: (id: string) => void;
  onSieger: (spielId: string, siegerId: string) => void;
  onZuruecknehmen: (id: string) => void;
  onVerschieben: (id: string, richtung: Richtung) => void;
  onNaechsteRunde: () => void;
}

/**
 * Ein Bereich für alles, was die Turnierleitung tut.
 *
 * Vorher waren das drei: Teilnehmer, Auswürfeln, Spielplan. Das war
 * richtig, solange ein Ergebnis aus sechs Zahlen bestand — seit es ein
 * Name ist, ist der Spielplan eine Liste mit zwei Knöpfen je Zeile, und
 * drei Reiter für zwei Handgriffe sind einer zu viel.
 *
 * Die Fläche folgt dem Abend: vor dem Auswürfeln sieht man die Namen und
 * den Würfel, danach die Spiele. Nichts davon muss jemand erklären.
 */
export function TurnierTafel({
  turnier,
  teilnehmer,
  spiele,
  darfEinrichten,
  onTeilnehmerAnlegen,
  onTeilnehmerEntfernen,
  onLosen,
  onUebernehmen,
  onZuruecksetzen,
  onBeginnen,
  onSieger,
  onZuruecknehmen,
  onVerschieben,
  onNaechsteRunde,
}: Props) {
  if (turnier.zustand === "planung") {
    return (
      <>
        <Teilnehmerliste
          teilnehmer={teilnehmer}
          onAnlegen={onTeilnehmerAnlegen}
          onEntfernen={onTeilnehmerEntfernen}
        />
        {darfEinrichten ? (
          <Wuerfel turnier={turnier} onLosen={onLosen} onUebernehmen={onUebernehmen} />
        ) : (
          <Hinweis>Auswürfeln darf, wer dieses Artefakt verwaltet.</Hinweis>
        )}
      </>
    );
  }

  return (
    <Spielplan
      turnier={turnier}
      spiele={spiele}
      darfEinrichten={darfEinrichten}
      onBeginnen={onBeginnen}
      onSieger={onSieger}
      onZuruecknehmen={onZuruecknehmen}
      onVerschieben={onVerschieben}
      onNaechsteRunde={onNaechsteRunde}
      onZuruecksetzen={onZuruecksetzen}
    />
  );
}

function Teilnehmerliste({
  teilnehmer,
  onAnlegen,
  onEntfernen,
}: {
  teilnehmer: Teilnehmer[];
  onAnlegen: (name: string) => Promise<boolean>;
  onEntfernen: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;
    setLaeuft(true);
    const geklappt = await onAnlegen(name.trim());
    setLaeuft(false);
    // Nur leeren, wenn es geklappt hat - sonst tippt man den Namen neu.
    if (geklappt) setName("");
  }

  return (
    <section aria-labelledby="mitspieler">
      <div className={stil.abschnittskopf}>
        <h2 id="mitspieler" className={stil.abschnittstitel}>
          Wer spielt mit?
        </h2>
      </div>

      <Karte>
        {/* Das Formular steht oben: hier werden zwanzig Namen hintereinander
            eingetippt, und nach jedem rutschte es sonst eine Zeile tiefer. */}
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
            autoFocus
            required
          />
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={name.trim() === "" || laeuft}
            className={stil.absenden}
          >
            Eintragen
          </Knopf>
        </form>

        {teilnehmer.length === 0 ? (
          <p className={stil.nebensache}>
            Noch niemand dabei. Ab zwei Namen lässt sich auswürfeln.
          </p>
        ) : (
          <ul className={stil.namen}>
            {teilnehmer.map((wer) => (
              <li key={wer.id} className={stil.namenschild}>
                {wer.name}
                <Knopf
                  groesse="sm"
                  auspraegung="leise"
                  onClick={() => onEntfernen(wer.id)}
                  aria-label={`${wer.name} entfernen`}
                >
                  ×
                </Knopf>
              </li>
            ))}
          </ul>
        )}
      </Karte>
    </section>
  );
}

function Wuerfel({
  turnier,
  onLosen,
  onUebernehmen,
}: {
  turnier: Turnier;
  onLosen: () => Promise<Auslosung | null>;
  onUebernehmen: (saat: number) => Promise<boolean>;
}) {
  const [vorschau, setVorschau] = useState<Auslosung | null>(null);
  const [laeuft, setLaeuft] = useState(false);

  async function wuerfeln() {
    setLaeuft(true);
    setVorschau(await onLosen());
    setLaeuft(false);
  }

  if (turnier.anzahl_teilnehmer < 2) return null;

  return (
    <section aria-labelledby="auswuerfeln">
      <div className={stil.abschnittskopf}>
        <h2 id="auswuerfeln" className={stil.abschnittstitel}>
          Auswürfeln
        </h2>
      </div>

      <Karte>
        <Knopf auspraegung="primaer" disabled={laeuft} onClick={() => void wuerfeln()}>
          {laeuft ? "Würfelt …" : vorschau ? "Nochmal würfeln" : "Würfeln"}
        </Knopf>

        {vorschau !== null && (
          <>
            <p className={stil.nebensache}>
              {`${vorschau.anzahl_spiele} Spiele, geschätzt ${dauer(vorschau.dauer_minuten)} ` +
                `auf ${turnier.tische} ${turnier.tische === 1 ? "Tisch" : "Tischen"}. ` +
                "Gespeichert ist davon noch nichts."}
            </p>
            {vorschau.hinweis && <Hinweis ton="warnung">{vorschau.hinweis}</Hinweis>}

            <div className={stil.gruppen}>
              {vorschau.gruppen.map((gruppe) => (
                <div key={gruppe.name}>
                  <h3 className={stil.gruppenname}>{gruppe.name}</h3>
                  <ol className={stil.gruppenliste}>
                    {gruppe.teilnehmer.map((wer) => (
                      <li key={wer}>{wer}</li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>

            <ul className={stil.begegnungen}>
              {vorschau.paarungen.map((paarung, stelle) => (
                <li key={`${paarung.bezeichnung}-${stelle}`} className={stil.begegnung}>
                  <span>{paarung.heim}</span>
                  <span className={stil.gegen}>gegen</span>
                  <span>{paarung.gast}</span>
                </li>
              ))}
            </ul>

            <div className={stil.aktionen}>
              <Knopf
                auspraegung="primaer"
                disabled={laeuft}
                onClick={() => {
                  setLaeuft(true);
                  void onUebernehmen(vorschau.saat).finally(() => setLaeuft(false));
                }}
              >
                Übernehmen und starten
              </Knopf>
              <Knopf auspraegung="leise" onClick={() => setVorschau(null)}>
                Verwerfen
              </Knopf>
            </div>
          </>
        )}
      </Karte>
    </section>
  );
}

function Spielplan({
  turnier,
  spiele,
  darfEinrichten,
  onBeginnen,
  onSieger,
  onZuruecknehmen,
  onVerschieben,
  onNaechsteRunde,
  onZuruecksetzen,
}: {
  turnier: Turnier;
  spiele: Spiel[];
  darfEinrichten: boolean;
  onBeginnen: (id: string) => void;
  onSieger: (spielId: string, siegerId: string) => void;
  onZuruecknehmen: (id: string) => void;
  onVerschieben: (id: string, richtung: Richtung) => void;
  onNaechsteRunde: () => void;
  onZuruecksetzen: () => void;
}) {
  const offen = spiele.filter((spiel) => spiel.zustand !== "beendet");
  const gewertet = spiele.filter(
    (spiel) => spiel.zustand === "beendet" && !spiel.freilos,
  );
  const ansetzbar = turnier.offene_spiele === 0 && turnier.zustand !== "beendet";

  return (
    <>
      {ansetzbar && (
        <Hinweis ton="warnung">
          Alle Spiele sind gewertet.{" "}
          <Knopf groesse="sm" auspraegung="primaer" onClick={onNaechsteRunde}>
            {turnier.modus === "gruppen_ko" && !turnier.ko_steht
              ? "KO-Raster ansetzen"
              : "Nächste Runde ansetzen"}
          </Knopf>
        </Hinweis>
      )}

      {turnier.zustand === "beendet" && <Hinweis>Das Turnier ist durch.</Hinweis>}

      <section aria-labelledby="offen">
        <div className={stil.abschnittskopf}>
          <h2 id="offen" className={stil.abschnittstitel}>
            {offen.length === 0 ? "Nichts mehr offen" : `Noch ${offen.length} zu spielen`}
          </h2>
        </div>

        {offen.length === 0 ? (
          <Leerzustand titel="Alles gewertet">
            Setze die nächste Runde an, oder sieh im Dashboard nach, wie es steht.
          </Leerzustand>
        ) : (
          <Karte blank>
            <ul className={stil.liste}>
              {offen.map((spiel) => (
                <li key={spiel.id} className={stil.spielzeile}>
                  <div className={stil.spielkopf}>
                    <span className={stil.nebensache}>
                      {spiel.bezeichnung}
                      {spiel.tisch !== null && ` · Tisch ${spiel.tisch}`}
                      {spiel.zustand === "geplant" &&
                        spiel.erwartet_ab !== null &&
                        ` · ab ${uhrzeit(spiel.erwartet_ab)}`}
                    </span>
                    {spiel.zustand === "laeuft" && <Etikett ton="warnung">läuft</Etikett>}
                    {/* Schieben, wenn jemand gerade keine Zeit hat.
                        Trotzdem anzupfeifen waere die schlechtere Loesung:
                        dann stimmt die Warteschlange im Dashboard nicht
                        mehr, und die Glocke laeutet beim Falschen. */}
                    {spiel.zustand === "geplant" && darfEinrichten && (
                      <span className={stil.schieben}>
                        <Knopf
                          groesse="sm"
                          auspraegung="leise"
                          onClick={() => onVerschieben(spiel.id, "hoch")}
                          aria-label={`Spiel ${spiel.nummer} nach vorn schieben`}
                        >
                          ↑
                        </Knopf>
                        <Knopf
                          groesse="sm"
                          auspraegung="leise"
                          onClick={() => onVerschieben(spiel.id, "runter")}
                          aria-label={`Spiel ${spiel.nummer} nach hinten schieben`}
                        >
                          ↓
                        </Knopf>
                      </span>
                    )}
                  </div>

                  {spiel.heim_id && spiel.gast_id ? (
                    <div className={stil.siegerwahl}>
                      {/* Ein Tippen auf den Namen - das ist das ganze
                          Ergebnis. Zwei Knöpfe statt eines Formulars, weil
                          hier jemand mit dem Schläger in der Hand steht. */}
                      <Knopf
                        auspraegung="sekundaer"
                        onClick={() => onSieger(spiel.id, spiel.heim_id ?? "")}
                      >
                        {spiel.heim} gewinnt
                      </Knopf>
                      <Knopf
                        auspraegung="sekundaer"
                        onClick={() => onSieger(spiel.id, spiel.gast_id ?? "")}
                      >
                        {spiel.gast} gewinnt
                      </Knopf>
                      {spiel.zustand === "geplant" && (
                        <Knopf
                          groesse="sm"
                          auspraegung="leise"
                          onClick={() => onBeginnen(spiel.id)}
                          aria-label={`Spiel ${spiel.nummer} anpfeifen`}
                        >
                          Anpfiff
                        </Knopf>
                      )}
                    </div>
                  ) : (
                    <span className={stil.nebensache}>
                      {spiel.heim ?? spiel.heim_herkunft} gegen{" "}
                      {spiel.gast ?? spiel.gast_herkunft}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Karte>
        )}
      </section>

      {gewertet.length > 0 && (
        <section aria-labelledby="gewertet">
          <div className={stil.abschnittskopf}>
            <h2 id="gewertet" className={stil.abschnittstitel}>
              Gewertet
            </h2>
          </div>
          <Karte blank>
            <ul className={stil.liste}>
              {gewertet.map((spiel) => (
                <li key={spiel.id} className={stil.zeile}>
                  <span>
                    <span
                      className={
                        spiel.sieger_id === spiel.heim_id ? stil.sieger : undefined
                      }
                    >
                      {spiel.heim}
                    </span>
                    <span className={stil.gegen}> gegen </span>
                    <span
                      className={
                        spiel.sieger_id === spiel.gast_id ? stil.sieger : undefined
                      }
                    >
                      {spiel.gast}
                    </span>
                  </span>
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    onClick={() => onZuruecknehmen(spiel.id)}
                    aria-label={`Ergebnis von Spiel ${spiel.nummer} zurücknehmen`}
                  >
                    Zurücknehmen
                  </Knopf>
                </li>
              ))}
            </ul>
          </Karte>
        </section>
      )}

      {darfEinrichten && (
        <Karte>
          <p className={stil.nebensache}>
            {`Ausgewürfelt mit der Saat ${turnier.saat}. Verwerfen heißt: die ` +
              `${turnier.anzahl_spiele} Spiele samt Ergebnissen sind weg.`}
          </p>
          <Knopf auspraegung="leise" onClick={onZuruecksetzen}>
            Spielplan verwerfen
          </Knopf>
        </Karte>
      )}
    </>
  );
}
