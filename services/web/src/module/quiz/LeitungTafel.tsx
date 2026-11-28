import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { meldung } from "../../api/client";
import { QrKarte } from "../../seiten/QrKarte";
import {
  Abschnitt,
  Etikett,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Schalter,
  Statuspunkt,
  Tafel,
  Feld,
} from "../../ui";
import { TAKT } from "./abruf";
import {
  bewerteAntwort,
  entferneSpieler,
  eroeffneRunde,
  korrigiere,
  ladeKataloge,
  ladeRunden,
  ladeSteuerung,
  loescheRunde,
  steuere,
  stelleWiederkehrAus,
  type Aktion,
  type AntwortSicht,
  type Katalog,
  type Phase,
  type Runde,
  type SpielerSicht,
  type Steuerung,
  type Wiederkehrcode,
  mediumAdresse,
  legeTeamAn,
  loescheTeam,
  weiseTeamZu,
  ladeAuswertung,
  ergebnisAdresse,
  type TeamPlatz,
  type FrageAuswertung,
} from "./api";
import { beitrittsAdresse, useBasisAdresse } from "./adresse";
import { loesungstext, TYPWORT } from "./texte";
import stil from "./Quiz.module.css";

const PHASEWORT: Record<Phase, string> = {
  keine: "keine Frage gewählt",
  bereit: "gewählt, noch verdeckt",
  offen: "offen",
  gesperrt: "Eingabe gesperrt",
  aufgeloest: "aufgelöst",
};

const STATUSWORT: Record<Runde["status"], string> = {
  lobby: "wartet auf Start",
  laeuft: "läuft",
  beendet: "beendet",
};

/** Die Runden der Leitung - Liste oder eine Runde, je nach `?runde=`. */
export function LeitungTafel({ darfLeiten }: { darfLeiten: boolean }) {
  const [suche, setSuche] = useSearchParams();
  const rundeId = suche.get("runde");
  if (rundeId) {
    return (
      <RundenSteuerung
        id={rundeId}
        darfLeiten={darfLeiten}
        zurueck={() => setSuche({})}
      />
    );
  }
  return (
    <RundenListe darfLeiten={darfLeiten} oeffnen={(id) => setSuche({ runde: id })} />
  );
}

type Liste =
  | { phase: "laedt" }
  | { phase: "fertig"; runden: Runde[]; kataloge: Katalog[] }
  | { phase: "fehler"; nachricht: string };

function RundenListe({
  darfLeiten,
  oeffnen,
}: {
  darfLeiten: boolean;
  oeffnen: (id: string) => void;
}) {
  const [liste, setListe] = useState<Liste>({ phase: "laedt" });
  const [katalog, setKatalog] = useState("");
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([ladeRunden(controller.signal), ladeKataloge(controller.signal)])
      .then(([runden, kataloge]) => {
        setListe({ phase: "fertig", runden, kataloge });
        setKatalog(
          (vorher) => vorher || kataloge.find((k) => k.anzahl_fragen > 0)?.id || "",
        );
      })
      .catch((grund: unknown) => {
        if (!controller.signal.aborted)
          setListe({ phase: "fehler", nachricht: meldung(grund) });
      });
    return () => controller.abort();
  }, []);

  async function eroeffnen() {
    setFehler("");
    try {
      oeffnen((await eroeffneRunde(katalog)).id);
    } catch (grund) {
      setFehler(meldung(grund));
    }
  }

  if (liste.phase === "laedt") {
    return (
      <Tafel titel="Runden">
        <div className={stil.laden} role="status" aria-label="Runden werden geladen">
          <Platzhalter hoehe="3rem" />
          <Platzhalter hoehe="8rem" />
        </div>
      </Tafel>
    );
  }
  if (liste.phase === "fehler") {
    return (
      <Tafel titel="Runden">
        <Hinweis ton="fehler" dringend>
          {liste.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const spielbar = liste.kataloge.filter((k) => k.anzahl_fragen > 0);
  const laufend = liste.runden.filter((r) => r.status !== "beendet").length;
  return (
    <Tafel titel="Runden" beiwort={`${laufend} offen · ${liste.runden.length} insgesamt`}>
      {darfLeiten && (
        <Karte>
          {spielbar.length === 0 ? (
            <Leerzustand
              titel="Noch kein Katalog mit Fragen"
              aktion={
                <Link to="/modul/quiz/kataloge" className={stil.verweis}>
                  Zu den Fragenkatalogen
                </Link>
              }
            >
              Eine Runde spielt die Fragen eines Katalogs. Leg zuerst einen an und schreib
              ein paar Fragen hinein.
            </Leerzustand>
          ) : (
            <div className={stil.eroeffnen}>
              <label className={stil.auswahl}>
                <span>Fragenkatalog</span>
                <select value={katalog} onChange={(e) => setKatalog(e.target.value)}>
                  {spielbar.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.titel} ({k.anzahl_fragen} Fragen)
                    </option>
                  ))}
                </select>
              </label>
              <Knopf onClick={() => void eroeffnen()} disabled={!katalog}>
                Runde eröffnen
              </Knopf>
            </div>
          )}
          {fehler && (
            <Hinweis ton="fehler" dringend>
              {fehler}
            </Hinweis>
          )}
        </Karte>
      )}

      {liste.runden.length === 0 ? (
        <Leerzustand titel="Noch keine Runde">
          Eröffne eine Runde: Sie bekommt einen Code, mit dem die Mitspieler ohne Konto
          beitreten.
        </Leerzustand>
      ) : (
        <ul className={stil.liste}>
          {liste.runden.map((runde) => (
            <li key={runde.id} className={stil.listenzeile}>
              <button
                type="button"
                className={stil.zeilenknopf}
                onClick={() => oeffnen(runde.id)}
              >
                <span className={stil.code}>{runde.code}</span>
                <span className={stil.zeilentext}>{runde.katalog_titel}</span>
                <span className={stil.nebensache}>
                  {STATUSWORT[runde.status]} · {runde.anzahl_spieler} Spieler
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Tafel>
  );
}

type Stand =
  | { phase: "laedt" }
  | { phase: "fertig"; steuerung: Steuerung }
  | { phase: "fehler"; nachricht: string };

function RundenSteuerung({
  id,
  darfLeiten,
  zurueck,
}: {
  id: string;
  darfLeiten: boolean;
  zurueck: () => void;
}) {
  const [stand, setStand] = useState<Stand>({ phase: "laedt" });
  const [fehler, setFehler] = useState("");
  const [wiederkehr, setWiederkehr] = useState<{
    name: string;
    code: Wiederkehrcode;
  } | null>(null);
  const [timer, setTimer] = useState(true);
  const basis = useBasisAdresse();

  const holen = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setStand({ phase: "fertig", steuerung: await ladeSteuerung(id, signal) });
      } catch (grund) {
        if (signal?.aborted) return;
        setStand((vorher) =>
          vorher.phase === "fertig"
            ? vorher
            : { phase: "fehler", nachricht: meldung(grund) },
        );
      }
    },
    [id],
  );

  useEffect(() => {
    const controller = new AbortController();
    void holen(controller.signal);
    const uhr = window.setInterval(() => void holen(controller.signal), TAKT);
    return () => {
      controller.abort();
      window.clearInterval(uhr);
    };
  }, [holen]);

  async function handeln(aktion: () => Promise<Steuerung | void>) {
    setFehler("");
    try {
      const neu = await aktion();
      if (neu) setStand({ phase: "fertig", steuerung: neu });
      else await holen();
    } catch (grund) {
      setFehler(meldung(grund));
    }
  }

  const tu = (aktion: Aktion) => void handeln(() => steuere(id, aktion));

  if (stand.phase === "laedt") {
    return (
      <Tafel titel="Runde">
        <div className={stil.laden} role="status" aria-label="Runde wird geladen">
          <Platzhalter hoehe="6rem" />
          <Platzhalter hoehe="14rem" />
        </div>
      </Tafel>
    );
  }
  if (stand.phase === "fehler") {
    return (
      <Tafel titel="Runde">
        <Hinweis ton="fehler" dringend>
          {stand.nachricht}
        </Hinweis>
        <div>
          <Knopf auspraegung="sekundaer" onClick={zurueck}>
            Zurück zu den Runden
          </Knopf>
        </div>
      </Tafel>
    );
  }

  const s = stand.steuerung;
  const { runde, frage } = s;
  const beendet = runde.status === "beendet";
  const index = frage ? s.fragen.findIndex((f) => f.id === frage.id) : -1;
  const naechste = s.fragen[index + 1];

  return (
    <Tafel
      titel={runde.katalog_titel}
      beiwort={
        <>
          <span className={stil.code}>{runde.code}</span> · {STATUSWORT[runde.status]} ·{" "}
          {s.spieler.length} Spieler
        </>
      }
      aktionen={
        <Knopf auspraegung="leise" groesse="sm" onClick={zurueck}>
          Alle Runden
        </Knopf>
      }
    >
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <div className={stil.leitung}>
        <div className={stil.leitungHaupt}>
          <Karte>
            <div className={stil.aktuell}>
              <div className={stil.fragemeta}>
                <Etikett ton={s.phase === "offen" ? "gut" : "neutral"}>
                  {PHASEWORT[s.phase]}
                </Etikett>
                {frage && (
                  <span>
                    Frage {index + 1} von {s.fragen.length} · {TYPWORT[frage.daten.typ]} ·{" "}
                    {frage.punkte} P.
                  </span>
                )}
              </div>
              {frage ? (
                <>
                  <h2 className={stil.fragetext}>{frage.text}</h2>
                  <p className={stil.nebensache}>Lösung: {loesungstext(frage)}</p>
                  {frage.medien.includes("ton") && (
                    <audio
                      controls
                      src={mediumAdresse(frage.id, "ton", frage.id)}
                      className={stil.ton}
                      aria-label="Ton zur Frage"
                    />
                  )}
                </>
              ) : (
                <p>
                  Wähle unten die erste Frage. Die Spieler sehen sie erst, wenn du sie
                  zeigst.
                </p>
              )}

              {darfLeiten && !beendet && frage && (
                <div className={stil.knopfzeile}>
                  {s.phase === "bereit" && (
                    <>
                      <Knopf onClick={() => tu({ art: "zeigen", timer })}>
                        Frage zeigen
                      </Knopf>
                      {frage.zeitlimit !== null && (
                        <span className={stil.schalterzeile}>
                          <Schalter
                            beschriftung={`Timer ${frage.zeitlimit} s`}
                            an={timer}
                            beiWechsel={setTimer}
                          />
                          <span aria-hidden="true">Timer {frage.zeitlimit} s</span>
                        </span>
                      )}
                    </>
                  )}
                  {s.phase === "offen" && frage.daten.typ !== "buzzer" && (
                    <Knopf auspraegung="sekundaer" onClick={() => tu({ art: "sperren" })}>
                      Eingabe sperren
                    </Knopf>
                  )}
                  {s.phase === "gesperrt" && (
                    <Knopf auspraegung="sekundaer" onClick={() => tu({ art: "oeffnen" })}>
                      Wieder öffnen
                    </Knopf>
                  )}
                  {(s.phase === "offen" || s.phase === "gesperrt") && (
                    <Knopf
                      auspraegung={frage.daten.typ === "buzzer" ? "sekundaer" : "primaer"}
                      onClick={() => tu({ art: "aufloesen" })}
                    >
                      Auflösen
                    </Knopf>
                  )}
                  {s.phase === "aufgeloest" && naechste && (
                    <Knopf onClick={() => tu({ art: "frage", frage_id: naechste.id })}>
                      Nächste Frage
                    </Knopf>
                  )}
                  {frage.hat_bild && s.phase !== "bereit" && (
                    <Knopf
                      auspraegung="leise"
                      onClick={() => tu({ art: "bild", sichtbar: !s.bild_sichtbar })}
                    >
                      {s.bild_sichtbar ? "Bild verbergen" : "Bild zeigen"}
                    </Knopf>
                  )}
                </div>
              )}
            </div>
          </Karte>

          {frage?.daten.typ === "buzzer" ? (
            <BuzzerReihe s={s} darfLeiten={darfLeiten && !beendet} tu={tu} />
          ) : (
            frage && (
              <Antworten
                antworten={s.antworten}
                anzahlSpieler={s.spieler.length}
                aufgeloest={s.phase === "aufgeloest"}
                darfLeiten={darfLeiten}
                bewerten={(antwort, punkte) =>
                  void handeln(() => bewerteAntwort(id, antwort.id, punkte))
                }
              />
            )
          )}

          <Abschnitt
            titel="Fragen"
            beiwort={`${s.beantwortet.length} von ${s.fragen.length} gespielt`}
          >
            <ol className={stil.liste}>
              {s.fragen.map((f, i) => (
                <li
                  key={f.id}
                  className={stil.listenzeile}
                  aria-current={f.id === frage?.id ? "true" : undefined}
                >
                  <span className={stil.sortiernummer}>{i + 1}</span>
                  <span className={stil.zeilentext}>
                    {f.text}
                    <span className={stil.nebensache}> · {TYPWORT[f.daten.typ]}</span>
                  </span>
                  {s.beantwortet.includes(f.id) && <Etikett ton="gut">gespielt</Etikett>}
                  {darfLeiten && !beendet && f.id !== frage?.id && (
                    <Knopf
                      auspraegung="leise"
                      groesse="sm"
                      onClick={() => tu({ art: "frage", frage_id: f.id })}
                      aria-label={`Frage ${i + 1} wählen`}
                    >
                      Wählen
                    </Knopf>
                  )}
                </li>
              ))}
            </ol>
          </Abschnitt>

          <Auswertung rundeId={id} gespielt={s.beantwortet.length} />
        </div>

        <aside className={stil.leitungSeite}>
          {!beendet && (
            <Karte>
              <QrKarte
                url={basis === null ? null : beitrittsAdresse(basis, runde.code)}
              />
              <Link
                className={stil.verweis}
                to={`/modul/quiz/tafel?code=${runde.code}`}
                target="_blank"
                rel="noopener"
              >
                Anzeigetafel in neuem Fenster
              </Link>
            </Karte>
          )}
          {darfLeiten && !beendet && (
            <span className={stil.schalterzeile}>
              <Schalter
                beschriftung="Beitritt offen"
                an={runde.beitritt_offen}
                beiWechsel={(offen) => tu({ art: "beitritt", offen })}
              />
              <span aria-hidden="true">
                {runde.beitritt_offen
                  ? "Beitritt offen"
                  : "Beitritt geschlossen - nur Rückkehrer"}
              </span>
            </span>
          )}
          <Teams
            teams={s.teams}
            darfLeiten={darfLeiten && !beendet}
            anlegen={(name) => handeln(() => legeTeamAn(id, name))}
            aufloesen={(team) => {
              if (
                window.confirm(
                  `Team „${team.name}“ auflösen? Die Mitglieder spielen allein weiter.`,
                )
              )
                void handeln(() => loescheTeam(id, team.id));
            }}
          />
          {/* Neben der Spielerliste, nicht oben: dort hat die Leitung eben
              geklickt, und dort muss sie den Code ablesen. */}
          {wiederkehr && (
            <Hinweis ton="gut">
              Wiederkehrcode für {wiederkehr.name}:{" "}
              <strong className={stil.code}>{wiederkehr.code.code}</strong>. Gilt 15
              Minuten und genau einmal. Unter „Ich war schon dabei“ mit dem Namen
              eingeben.
            </Hinweis>
          )}
          <SpielerListe
            spieler={s.spieler}
            teams={s.teams}
            zuordnen={(wer, team) => void handeln(() => weiseTeamZu(id, wer.id, team))}
            darfLeiten={darfLeiten}
            korrigieren={(wer, punkte) =>
              void handeln(() => korrigiere(id, wer.id, punkte))
            }
            wiederkehr={(wer) =>
              void handeln(async () => {
                setWiederkehr({
                  name: wer.name,
                  code: await stelleWiederkehrAus(id, wer.id),
                });
              })
            }
            entfernen={(wer) => {
              if (
                window.confirm(
                  `${wer.name} aus der Runde entfernen? Die Punkte gehen verloren.`,
                )
              )
                void handeln(() => entferneSpieler(id, wer.id));
            }}
          />
          {darfLeiten && (
            <div className={stil.knopfzeile}>
              {!beendet && (
                <Knopf
                  auspraegung="sekundaer"
                  onClick={() => {
                    if (window.confirm("Runde beenden? Danach tritt niemand mehr bei."))
                      tu({ art: "beenden" });
                  }}
                >
                  Runde beenden
                </Knopf>
              )}
              <Knopf
                auspraegung="leise"
                onClick={() => {
                  if (window.confirm(`Runde ${runde.code} samt Punkten löschen?`))
                    void handeln(async () => {
                      await loescheRunde(id);
                      zurueck();
                    });
                }}
              >
                Runde löschen
              </Knopf>
            </div>
          )}
        </aside>
      </div>
    </Tafel>
  );
}

function BuzzerReihe({
  s,
  darfLeiten,
  tu,
}: {
  s: Steuerung;
  darfLeiten: boolean;
  tu: (aktion: Aktion) => void;
}) {
  const dran = s.buzzer.find((b) => b.urteil === "wartet");
  const offen = s.phase === "offen" || s.phase === "gesperrt";
  return (
    <Abschnitt
      titel="Buzzer"
      beiwort={dran ? `${dran.spieler} ist dran` : "noch niemand"}
    >
      {s.buzzer.length === 0 ? (
        <p className={stil.nebensache}>
          {s.phase === "offen"
            ? "Warte auf den ersten Druck."
            : "Zeig die Frage, dann gilt der Buzzer."}
        </p>
      ) : (
        <ol className={stil.liste}>
          {s.buzzer.map((b) => (
            <li key={b.spieler_id} className={stil.listenzeile}>
              <span className={stil.sortiernummer}>{b.position}</span>
              <span className={stil.zeilentext}>{b.spieler}</span>
              <Etikett
                ton={
                  b.urteil === "richtig"
                    ? "gut"
                    : b.urteil === "falsch"
                      ? "fehler"
                      : "akzent"
                }
              >
                {b.urteil}
              </Etikett>
            </li>
          ))}
        </ol>
      )}
      {darfLeiten && offen && (
        <div className={stil.knopfzeile}>
          <Knopf disabled={!dran} onClick={() => tu({ art: "buzzer", richtig: true })}>
            Richtig
          </Knopf>
          <Knopf
            auspraegung="sekundaer"
            disabled={!dran}
            onClick={() => tu({ art: "buzzer", richtig: false })}
          >
            Falsch - nächster
          </Knopf>
          <Knopf auspraegung="leise" onClick={() => tu({ art: "buzzer/zuruecksetzen" })}>
            Buzzer freigeben
          </Knopf>
        </div>
      )}
    </Abschnitt>
  );
}

function Antworten({
  antworten,
  anzahlSpieler,
  aufgeloest,
  darfLeiten,
  bewerten,
}: {
  antworten: AntwortSicht[];
  anzahlSpieler: number;
  aufgeloest: boolean;
  darfLeiten: boolean;
  bewerten: (antwort: AntwortSicht, punkte: number) => void;
}) {
  return (
    <Abschnitt titel="Antworten" beiwort={`${antworten.length} von ${anzahlSpieler}`}>
      {antworten.length === 0 ? (
        <p className={stil.nebensache}>Noch keine Antwort.</p>
      ) : (
        <ul className={stil.liste}>
          {antworten.map((antwort) => (
            <li key={antwort.id} className={stil.listenzeile}>
              <span className={stil.zeilentext}>
                <strong>{antwort.spieler}</strong> {antwort.anzeige}
              </span>
              {!antwort.eingeloggt && <Etikett>Entwurf</Etikett>}
              {aufgeloest && (
                <PunkteFeld
                  antwort={antwort}
                  darfLeiten={darfLeiten}
                  bewerten={bewerten}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </Abschnitt>
  );
}

function PunkteFeld({
  antwort,
  darfLeiten,
  bewerten,
}: {
  antwort: AntwortSicht;
  darfLeiten: boolean;
  bewerten: (antwort: AntwortSicht, punkte: number) => void;
}) {
  const [wert, setWert] = useState(String(antwort.punkte ?? ""));
  useEffect(() => setWert(String(antwort.punkte ?? "")), [antwort.punkte]);
  const ton = antwort.richtig === null ? "warnung" : antwort.richtig ? "gut" : "neutral";

  if (!darfLeiten) return <Etikett ton={ton}>{antwort.punkte ?? "?"} P.</Etikett>;
  return (
    <form
      className={stil.punkteform}
      onSubmit={(e) => {
        e.preventDefault();
        if (wert.trim() !== "") bewerten(antwort, Number(wert));
      }}
    >
      <label className={stil.punkteLabel}>
        <span className="nur-vorlesen">Punkte für {antwort.spieler}</span>
        <input
          className={stil.punkteEingabe}
          type="number"
          inputMode="numeric"
          value={wert}
          onChange={(e) => setWert(e.target.value)}
          data-offen={antwort.richtig === null}
        />
      </label>
      <Knopf
        auspraegung="leise"
        groesse="sm"
        type="submit"
        aria-label={`Punkte für ${antwort.spieler} speichern`}
      >
        ✓
      </Knopf>
    </form>
  );
}

function SpielerListe({
  spieler,
  teams,
  zuordnen,
  darfLeiten,
  korrigieren,
  wiederkehr,
  entfernen,
}: {
  spieler: SpielerSicht[];
  teams: TeamPlatz[];
  zuordnen: (wer: SpielerSicht, team: string | null) => void;
  darfLeiten: boolean;
  korrigieren: (wer: SpielerSicht, punkte: number) => void;
  wiederkehr: (wer: SpielerSicht) => void;
  entfernen: (wer: SpielerSicht) => void;
}) {
  return (
    <Abschnitt
      titel="Spieler"
      beiwort={`${spieler.filter((s) => s.verbunden).length} verbunden`}
    >
      {spieler.length === 0 ? (
        <p className={stil.nebensache}>Noch niemand beigetreten. Zeig den QR-Code.</p>
      ) : (
        <ul className={stil.liste}>
          {spieler.map((wer) => (
            <li key={wer.id} className={stil.spielerzeile}>
              <span className={stil.spielername}>
                <Statuspunkt ton={wer.verbunden ? "gut" : "neutral"} />
                <span>
                  {wer.rang}. {wer.name}
                </span>
                <strong className={stil.platzpunkte}>{wer.punkte}</strong>
              </span>
              {teams.length > 0 && (
                <label className={stil.auswahl}>
                  <span className="nur-vorlesen">Team von {wer.name}</span>
                  <select
                    value={wer.team_id ?? ""}
                    disabled={!darfLeiten}
                    onChange={(e) => zuordnen(wer, e.target.value || null)}
                  >
                    <option value="">ohne Team</option>
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {darfLeiten && (
                <span className={stil.sortierknoepfe}>
                  <Knopf
                    auspraegung="leise"
                    groesse="sm"
                    onClick={() => korrigieren(wer, 1)}
                    aria-label={`${wer.name} einen Punkt geben`}
                  >
                    +1
                  </Knopf>
                  <Knopf
                    auspraegung="leise"
                    groesse="sm"
                    onClick={() => korrigieren(wer, -1)}
                    aria-label={`${wer.name} einen Punkt abziehen`}
                  >
                    −1
                  </Knopf>
                  <Knopf
                    auspraegung="leise"
                    groesse="sm"
                    onClick={() => wiederkehr(wer)}
                    aria-label={`Wiederkehrcode für ${wer.name}`}
                  >
                    Code
                  </Knopf>
                  <Knopf
                    auspraegung="leise"
                    groesse="sm"
                    onClick={() => entfernen(wer)}
                    aria-label={`${wer.name} entfernen`}
                  >
                    ×
                  </Knopf>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Abschnitt>
  );
}

function Teams({
  teams,
  darfLeiten,
  anlegen,
  aufloesen,
}: {
  teams: TeamPlatz[];
  darfLeiten: boolean;
  anlegen: (name: string) => Promise<void>;
  aufloesen: (team: TeamPlatz) => void;
}) {
  const [name, setName] = useState("");
  if (!darfLeiten && teams.length === 0) return null;
  return (
    <Abschnitt
      titel="Teams"
      beiwort={teams.length ? `${teams.length} Teams` : "jeder für sich"}
    >
      {teams.length === 0 ? (
        <p className={stil.nebensache}>
          Ohne Teams spielt jeder für sich. Legst du Teams an, wählen neue Spieler beim
          Beitritt eines - und pro Team zählt nur ein Buzzer.
        </p>
      ) : (
        <ol className={stil.liste}>
          {teams.map((team) => (
            <li key={team.id} className={stil.listenzeile}>
              <span className={stil.zeilentext}>
                {team.rang}. {team.name}
                <span className={stil.nebensache}>
                  {" "}
                  · {team.mitglieder} {team.mitglieder === 1 ? "Person" : "Personen"}
                </span>
              </span>
              <strong className={stil.platzpunkte}>{team.punkte}</strong>
              {darfLeiten && (
                <Knopf
                  auspraegung="leise"
                  groesse="sm"
                  onClick={() => aufloesen(team)}
                  aria-label={`Team ${team.name} auflösen`}
                >
                  ×
                </Knopf>
              )}
            </li>
          ))}
        </ol>
      )}
      {darfLeiten && (
        <form
          className={stil.eroeffnen}
          onSubmit={(e) => {
            e.preventDefault();
            void anlegen(name).then(() => setName(""));
          }}
        >
          <Feld
            beschriftung="Neues Team"
            value={name}
            maxLength={30}
            onChange={(e) => setName(e.target.value)}
          />
          <Knopf type="submit" auspraegung="sekundaer" disabled={name.trim() === ""}>
            Team anlegen
          </Knopf>
        </form>
      )}
    </Abschnitt>
  );
}

type Rueckblick =
  | { phase: "zu" }
  | { phase: "laedt" }
  | { phase: "fertig"; fragen: FrageAuswertung[] }
  | { phase: "fehler"; nachricht: string };

/** Die gespielten Fragen im Rückblick - auf Knopfdruck, nicht im Takt:
 *  wer auswertet, will nicht, dass die Liste unter dem Lesen springt. */
function Auswertung({ rundeId, gespielt }: { rundeId: string; gespielt: number }) {
  const [rueckblick, setRueckblick] = useState<Rueckblick>({ phase: "zu" });

  async function laden() {
    setRueckblick({ phase: "laedt" });
    try {
      setRueckblick({ phase: "fertig", fragen: await ladeAuswertung(rundeId) });
    } catch (grund) {
      setRueckblick({ phase: "fehler", nachricht: meldung(grund) });
    }
  }

  return (
    <Abschnitt titel="Auswertung" beiwort={`${gespielt} gespielt`}>
      <div className={stil.knopfzeile}>
        <Knopf
          auspraegung="sekundaer"
          onClick={() => void laden()}
          disabled={gespielt === 0}
        >
          {rueckblick.phase === "fertig"
            ? "Auswertung aktualisieren"
            : "Auswertung zeigen"}
        </Knopf>
        <a className={stil.verweis} href={ergebnisAdresse(rundeId)} download>
          Ergebnis als CSV
        </a>
      </div>
      {rueckblick.phase === "laedt" && (
        <div role="status" aria-label="Auswertung wird geladen">
          <Platzhalter hoehe="6rem" />
        </div>
      )}
      {rueckblick.phase === "fehler" && (
        <Hinweis ton="fehler" dringend>
          {rueckblick.nachricht}
        </Hinweis>
      )}
      {rueckblick.phase === "fertig" &&
        (rueckblick.fragen.length === 0 ? (
          <p className={stil.nebensache}>Noch keine Frage aufgelöst.</p>
        ) : (
          <div className={stil.auswertung}>
            {rueckblick.fragen.map((f) => (
              <Karte key={f.frage_id}>
                <div className={stil.fragemeta}>
                  <span>
                    Frage {f.nummer} · {TYPWORT[f.typ]}
                  </span>
                  <Etikett ton={f.richtig > 0 ? "gut" : "neutral"}>
                    {f.richtig} von {f.gesamt} richtig
                  </Etikett>
                </div>
                <h3 className={stil.zeilentext}>{f.text}</h3>
                <p className={stil.nebensache}>Lösung: {f.loesung}</p>
                <ul className={stil.liste}>
                  {f.antworten.map((a, i) => (
                    <li key={i} className={stil.listenzeile}>
                      <span className={stil.zeilentext}>
                        <strong>{a.spieler}</strong> {a.anzeige}
                      </span>
                      <Etikett
                        ton={
                          a.richtig === null ? "warnung" : a.richtig ? "gut" : "neutral"
                        }
                      >
                        {a.punkte ?? "?"} P.
                      </Etikett>
                    </li>
                  ))}
                </ul>
              </Karte>
            ))}
          </div>
        ))}
    </Abschnitt>
  );
}
