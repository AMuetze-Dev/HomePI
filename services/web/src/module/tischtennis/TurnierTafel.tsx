import { useState } from "react";

import {
  Abschnitt,
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Regel,
  Reihe,
  Tabelle,
  Zelle,
} from "../../ui";
import type {
  Auslosung,
  Liste,
  Richtung,
  Spiel,
  Teilnehmer,
  Turnier,
  Uebernahme,
} from "./api";
import stil from "./TischtennisSeite.module.css";
import { dauer, uhrzeit } from "./zeit";

interface Props {
  turnier: Turnier;
  teilnehmer: Teilnehmer[];
  spiele: Spiel[];
  /** Gespeicherte Namenslisten - Vorlagen, die an keinem Turnier hängen. */
  listen: Liste[];
  darfEinrichten: boolean;
  onTeilnehmerAnlegen: (name: string) => Promise<boolean>;
  onTeilnehmerEntfernen: (id: string) => void;
  /** `null`, wenn es nicht geklappt hat - die Meldung zeigt die Seite. */
  onListeLaden: (id: string) => Promise<Uebernahme | null>;
  /** Mit `id` wird diese Liste überschrieben, ohne entsteht eine neue. */
  onListeSpeichern: (name: string, id?: string) => Promise<boolean>;
  onListeLoeschen: (id: string) => void;
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
  listen,
  darfEinrichten,
  onTeilnehmerAnlegen,
  onTeilnehmerEntfernen,
  onListeLaden,
  onListeSpeichern,
  onListeLoeschen,
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
        <GespeicherteListen
          teilnehmer={teilnehmer}
          listen={listen}
          onLaden={onListeLaden}
          onSpeichern={onListeSpeichern}
          onLoeschen={onListeLoeschen}
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
  // Höchstens ein Name ist aufgeklappt: Wer zwei entfernen will, tut das
  // nacheinander, und dazwischen steht die Liste wieder ruhig da.
  const [offen, setOffen] = useState<string | null>(null);

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
    <Abschnitt
      titel="Wer spielt mit?"
      id="mitspieler"
      beiwort={teilnehmer.length > 0 ? `${teilnehmer.length} Namen` : undefined}
    >
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
            Noch niemand dabei. Ab zwei Namen lässt sich auswürfeln - oder lade unten eine
            gespeicherte Liste.
          </p>
        ) : (
          /* Eine durchgezählte Liste in Spalten statt runder Schildchen mit
             Kreuz: Die Namen sind das, was man hier liest, und die eine
             Handlung - entfernen - steht erst da, wenn man einen Namen
             antippt. */
          <ol className={stil.namen} aria-label="Eingetragene Namen">
            {teilnehmer.map((wer, stelle) => {
              const istOffen = offen === wer.id;
              return (
                <li key={wer.id} className={stil.namenszeile}>
                  <div className={stil.namensinhalt}>
                    <button
                      type="button"
                      className={stil.namenskopf}
                      aria-expanded={istOffen}
                      onClick={() => setOffen(istOffen ? null : wer.id)}
                    >
                      <span className={stil.laufnummer} aria-hidden="true">
                        {String(stelle + 1).padStart(2, "0")}
                      </span>
                      <span className={stil.namenstext}>{wer.name}</span>
                    </button>
                    {istOffen && (
                      <Knopf
                        groesse="sm"
                        auspraegung="leise"
                        onClick={() => {
                          setOffen(null);
                          onEntfernen(wer.id);
                        }}
                        aria-label={`${wer.name} entfernen`}
                      >
                        Entfernen
                      </Knopf>
                    )}
                  </div>
                  <Regel />
                </li>
              );
            })}
          </ol>
        )}
      </Karte>
    </Abschnitt>
  );
}

/** Was das Laden einer Liste bewirkt hat, in einem Satz. */
function bericht(ergebnis: Uebernahme): string {
  const neu = ergebnis.eingetragen.length;
  const schon = ergebnis.schon_dabei.length;
  if (neu === 0) return "Alle Namen dieser Liste waren schon dabei.";
  const teil = `${neu} eingetragen`;
  if (schon === 0) return `${teil}.`;
  return `${teil}, ${schon} ${schon === 1 ? "war" : "waren"} schon dabei.`;
}

const gleich = (a: string, b: string) =>
  a.trim().toLocaleLowerCase("de") === b.trim().toLocaleLowerCase("de");

/**
 * Namen einmal speichern, vor jedem Turnier laden.
 *
 * Laden trägt nur nach, wer noch fehlt - es ersetzt nie. Deshalb lassen
 * sich zwei Listen nacheinander laden („Stammtisch" und „Gäste"), und ein
 * Name, der schon steht, behält seine Notiz.
 */
function GespeicherteListen({
  teilnehmer,
  listen,
  onLaden,
  onSpeichern,
  onLoeschen,
}: {
  teilnehmer: Teilnehmer[];
  listen: Liste[];
  onLaden: (id: string) => Promise<Uebernahme | null>;
  onSpeichern: (name: string, id?: string) => Promise<boolean>;
  onLoeschen: (id: string) => void;
}) {
  const [offen, setOffen] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(false);
  const [meldungstext, setMeldungstext] = useState("");
  const [formularOffen, setFormularOffen] = useState(false);
  const [listenname, setListenname] = useState("");
  const [sichert, setSichert] = useState(false);

  // Gleicher Name heißt überschreiben - und das steht auf dem Knopf, bevor
  // es passiert. Groß- und Kleinschreibung zählen dabei nicht.
  const gleichnamig =
    listenname.trim() === ""
      ? undefined
      : listen.find((liste) => gleich(liste.name, listenname));

  async function laden(liste: Liste) {
    setLaedt(true);
    setMeldungstext("");
    const ergebnis = await onLaden(liste.id);
    setLaedt(false);
    if (ergebnis) {
      setMeldungstext(bericht(ergebnis));
      setOffen(null);
    }
  }

  async function sichern(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    const name = gleichnamig ? gleichnamig.name : listenname.trim();
    if (name === "" || sichert) return;
    setSichert(true);
    const geklappt = await onSpeichern(name, gleichnamig?.id);
    setSichert(false);
    if (!geklappt) return;
    setMeldungstext(`„${name}“ ${gleichnamig ? "überschrieben" : "gespeichert"}.`);
    setListenname("");
    setFormularOffen(false);
  }

  return (
    <Abschnitt
      titel="Gespeicherte Listen"
      id="listen"
      beiwort={listen.length > 0 ? String(listen.length) : undefined}
    >
      {meldungstext && (
        <p role="status" className={stil.nebensache}>
          {meldungstext}
        </p>
      )}

      {listen.length === 0 ? (
        <p className={stil.nebensache}>
          Noch keine Liste. Trag die Namen einmal ein und speichere sie - beim nächsten
          Turnier sind sie mit einem Klick wieder da.
        </p>
      ) : (
        <Tabelle beschriftung="Gespeicherte Listen" raster="1fr auto" rechtsBuendig>
          {listen.map((liste) => {
            const istOffen = offen === liste.id;
            return (
              <Reihe
                key={liste.id}
                onKlick={() => setOffen(istOffen ? null : liste.id)}
                offen={istOffen}
                ausklappung={
                  <div className={stil.listenausklappung}>
                    <p className={stil.nebensache}>{liste.namen.join(", ")}</p>
                    <div className={stil.knopfzeile}>
                      <Knopf
                        groesse="sm"
                        auspraegung="primaer"
                        disabled={laedt}
                        onClick={() => void laden(liste)}
                      >
                        Übernehmen
                      </Knopf>
                      <Knopf
                        groesse="sm"
                        auspraegung="leise"
                        aria-label="Liste löschen"
                        onClick={() => {
                          setOffen(null);
                          onLoeschen(liste.id);
                        }}
                      >
                        Löschen
                      </Knopf>
                    </div>
                  </div>
                }
              >
                <Zelle>{liste.name}</Zelle>
                <Zelle rechts leise>
                  {liste.namen.length} Namen
                </Zelle>
              </Reihe>
            );
          })}
        </Tabelle>
      )}

      {formularOffen ? (
        <form onSubmit={(e) => void sichern(e)} className={stil.listenformular}>
          <Feld
            beschriftung="Name der Liste"
            value={listenname}
            onChange={(e) => setListenname(e.target.value)}
            autoComplete="off"
            autoFocus
            required
          />
          {gleichnamig && (
            <p className={stil.nebensache}>
              Gibt es schon - ersetzt die {gleichnamig.namen.length} Namen von „
              {gleichnamig.name}“ durch die {teilnehmer.length} eingetragenen.
            </p>
          )}
          <div className={stil.knopfzeile}>
            <Knopf
              type="submit"
              auspraegung="primaer"
              disabled={listenname.trim() === "" || sichert}
            >
              {gleichnamig ? "Überschreiben" : "Speichern"}
            </Knopf>
            <Knopf
              auspraegung="leise"
              onClick={() => {
                setFormularOffen(false);
                setListenname("");
              }}
            >
              Abbrechen
            </Knopf>
          </div>
        </form>
      ) : (
        teilnehmer.length > 0 && (
          <div className={stil.knopfzeile}>
            <Knopf onClick={() => setFormularOffen(true)}>Als Liste speichern</Knopf>
          </div>
        )
      )}
    </Abschnitt>
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
    <Abschnitt titel="Auswürfeln" id="auswuerfeln">
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
    </Abschnitt>
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
  // Ein Freilos ist kein Spiel: niemand steht dafuer am Tisch. Es steht im
  // Raster, wo es erklaert, warum einer durch ist - aber nicht in der
  // Liste dessen, was noch zu spielen ist.
  const offen = spiele.filter((spiel) => spiel.zustand !== "beendet" && !spiel.freilos);
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

      <Abschnitt
        titel={
          offen.length === 0 ? "Nichts mehr offen" : `Noch ${offen.length} zu spielen`
        }
        id="offen"
      >
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

                  {spiel.heim_id && spiel.gast_id && (
                    /* Die Knoepfe sagen "Anna gewinnt" - wer gegen wen
                       spielt, musste man sich vorher aus zwei Knoepfen
                       zusammensetzen. */
                    <span className={stil.paarungZeile}>
                      {spiel.heim} gegen {spiel.gast}
                    </span>
                  )}

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
      </Abschnitt>

      {gewertet.length > 0 && (
        <Gewertet spiele={gewertet} onZuruecknehmen={onZuruecknehmen} />
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

/** So viele Ergebnisse stehen da, bevor die Liste gekuerzt wird. */
const ZULETZT = 10;

/**
 * Was schon gewertet ist - das Neueste zuerst, und nicht alles auf einmal.
 *
 * Bei einem Abend mit vierzig Spielen stand hier vorher jedes Ergebnis mit
 * einem eigenen "Zuruecknehmen"-Knopf: vierzig Knoepfe fuer eine Handlung,
 * die man einmal am Abend braucht, und das Ergebnis, das man gerade
 * eingetragen hat, ganz unten. Jetzt steht es oben; korrigiert wird in der
 * geoeffneten Zeile.
 */
function Gewertet({
  spiele,
  onZuruecknehmen,
}: {
  spiele: Spiel[];
  onZuruecknehmen: (id: string) => void;
}) {
  const [offen, setOffen] = useState<string | null>(null);
  const [alle, setAlle] = useState(false);

  const neuestesZuerst = [...spiele].sort(
    (a, b) =>
      (b.beendet_am ?? "").localeCompare(a.beendet_am ?? "") || b.nummer - a.nummer,
  );
  const gezeigt = alle ? neuestesZuerst : neuestesZuerst.slice(0, ZULETZT);

  return (
    <Abschnitt titel="Gewertet" id="gewertet" beiwort={`${spiele.length}`}>
      <Tabelle beschriftung="Gewertet" raster="1fr auto">
        {gezeigt.map((spiel) => (
          <Reihe
            key={spiel.id}
            onKlick={() => setOffen(offen === spiel.id ? null : spiel.id)}
            offen={offen === spiel.id}
            ausklappung={
              <div className={stil.korrektur}>
                <span className={stil.nebensache}>
                  {spiel.bezeichnung} · Spiel {spiel.nummer}
                </span>
                <Knopf
                  groesse="sm"
                  auspraegung="leise"
                  onClick={() => onZuruecknehmen(spiel.id)}
                  aria-label={`Ergebnis von Spiel ${spiel.nummer} zurücknehmen`}
                >
                  Zurücknehmen
                </Knopf>
              </div>
            }
          >
            <Zelle>
              <span
                className={spiel.sieger_id === spiel.heim_id ? stil.sieger : undefined}
              >
                {spiel.heim}
              </span>
              <span className={stil.gegen}>gegen</span>
              <span
                className={spiel.sieger_id === spiel.gast_id ? stil.sieger : undefined}
              >
                {spiel.gast}
              </span>
            </Zelle>
            <Zelle leise rechts>
              {uhrzeit(spiel.beendet_am)}
            </Zelle>
          </Reihe>
        ))}
      </Tabelle>

      {!alle && spiele.length > ZULETZT && (
        <Knopf groesse="sm" auspraegung="leise" onClick={() => setAlle(true)}>
          Alle {spiele.length} zeigen
        </Knopf>
      )}
    </Abschnitt>
  );
}
