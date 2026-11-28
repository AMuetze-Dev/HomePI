import { useCallback, useEffect, useState, type FormEvent } from "react";

import { meldung } from "../../api/client";
import { QrKarte } from "../../seiten/QrKarte";
import { Etikett, Feld, Hinweis, Knopf, Platzhalter } from "../../ui";
import { TAKT } from "./abruf";
import { beitrittsAdresse, leitungsAdresse, useBasisAdresse } from "./adresse";
import {
  bewerteAntwort,
  entferneSpieler,
  ergebnisAdresse,
  korrigiere,
  ladeAuswertung,
  ladeSteuerung,
  legeTeamAn,
  leitungsmediumAdresse,
  loescheRunde,
  loescheTeam,
  neuerModeratorcode,
  steuere,
  stelleWiederkehrAus,
  weiseTeamZu,
  type Aktion,
  type AntwortSicht,
  type Frage,
  type FrageAuswertung,
  type SpielerSicht,
  type Steuerung,
  type TeamPlatz,
  type Wiederkehrcode,
} from "./api";
import { Countdown } from "./Countdown";
import { Dialog } from "./Dialog";
import { Symbol, SymbolKnopf } from "./Symbol";
import { loesungstext, TYPWORT } from "./texte";
import stil from "./Quiz.module.css";

type Stand =
  | { phase: "laedt" }
  | { phase: "fertig"; steuerung: Steuerung; versatz: number }
  | { phase: "fehler"; nachricht: string };

type Fenster =
  null | "qr" | "teams" | "auswertung" | "code" | "ende" | { spieler: SpielerSicht };

const PHASEWORT: Record<Steuerung["phase"], string> = {
  keine: "Keine Frage gewählt",
  bereit: "Verdeckt",
  offen: "Offen",
  gesperrt: "Gesperrt",
  aufgeloest: "Aufgelöst",
};

/**
 * Die Leitung einer Runde - ein Dashboard, kein Formular.
 *
 * Drei Spalten in Bildschirmhöhe: links die Fragen, in der Mitte die Bühne
 * mit der einen nächsten Handlung, rechts die Spieler. Nichts davon zwingt
 * die Seite zum Scrollen; was länger wird, scrollt in seiner Spalte. Alles,
 * was gebraucht wird, aber nicht dauernd zu sehen sein muss, liegt hinter
 * einem Symbol in der Kopfleiste und öffnet sich als Dialog.
 */
export function Dashboard({ id, zurueck }: { id: string; zurueck: () => void }) {
  const [stand, setStand] = useState<Stand>({ phase: "laedt" });
  const [fehler, setFehler] = useState("");
  const [fenster, setFenster] = useState<Fenster>(null);
  const [timer, setTimer] = useState(true);
  const [code, setCode] = useState<string | null>(null);
  const [wiederkehr, setWiederkehr] = useState<{
    name: string;
    code: Wiederkehrcode;
  } | null>(null);
  const basis = useBasisAdresse();

  const holen = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const steuerung = await ladeSteuerung(id, signal);
        setStand({
          phase: "fertig",
          steuerung,
          versatz: Date.parse(steuerung.jetzt) - Date.now(),
        });
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

  async function handeln(aktion: () => Promise<Steuerung | void>): Promise<boolean> {
    setFehler("");
    try {
      const neu = await aktion();
      if (neu)
        setStand({
          phase: "fertig",
          steuerung: neu,
          versatz: Date.parse(neu.jetzt) - Date.now(),
        });
      else await holen();
      return true;
    } catch (grund) {
      setFehler(meldung(grund));
      return false;
    }
  }

  const tu = (aktion: Aktion) => void handeln(() => steuere(id, aktion));

  if (stand.phase === "laedt") {
    return (
      <div className={stil.dashboard} role="status" aria-label="Runde wird geladen">
        <Platzhalter hoehe="3rem" />
        <div className={stil.dashboardRaster}>
          <Platzhalter hoehe="100%" />
          <Platzhalter hoehe="100%" />
          <Platzhalter hoehe="100%" />
        </div>
      </div>
    );
  }
  if (stand.phase === "fehler") {
    return (
      <div className={stil.formular}>
        <Hinweis ton="fehler" dringend>
          {stand.nachricht}
        </Hinweis>
        <div>
          <Knopf auspraegung="sekundaer" onClick={zurueck}>
            Zurück
          </Knopf>
        </div>
      </div>
    );
  }

  const s = stand.steuerung;
  const { runde, frage } = s;
  const beendet = runde.status === "beendet";
  const index = frage ? s.fragen.findIndex((f) => f.id === frage.id) : -1;
  const naechste =
    s.fragen.find((f, i) => i > index && !s.beantwortet.includes(f.id)) ??
    s.fragen[index + 1];
  const tafel = `/modul/quiz/tafel?code=${runde.code}`;

  return (
    <div className={stil.dashboard}>
      {/* ---------------------------------------------------------- Kopfleiste */}
      <header className={stil.leiste}>
        <div className={stil.leisteTitel}>
          <h1 className={stil.leisteName}>{runde.katalog_titel}</h1>
          <span className={stil.codeChip} aria-label={`Rundencode ${runde.code}`}>
            {runde.code}
          </span>
          <span className={stil.leisteZahl}>
            <Symbol name="spieler" /> {s.spieler.length}
          </span>
          <span className={stil.phasePunkt} data-phase={s.phase}>
            {beendet ? "Beendet" : PHASEWORT[s.phase]}
          </span>
        </div>
        <nav className={stil.leisteKnoepfe} aria-label="Werkzeuge der Leitung">
          <SymbolKnopf
            symbol="qr"
            name="QR-Code zum Mitspielen"
            onClick={() => setFenster("qr")}
          />
          <a
            className={stil.symbolknopf}
            href={tafel}
            target="_blank"
            rel="noopener"
            aria-label="Anzeigetafel öffnen"
            title="Anzeigetafel öffnen"
          >
            <Symbol name="tafel" />
          </a>
          <SymbolKnopf
            symbol="teams"
            name="Teams einteilen"
            aktiv={s.teams.length > 0}
            onClick={() => setFenster("teams")}
          />
          {!beendet && (
            <SymbolKnopf
              symbol={runde.beitritt_offen ? "offen" : "schloss"}
              name={runde.beitritt_offen ? "Beitritt schließen" : "Beitritt öffnen"}
              aktiv={!runde.beitritt_offen}
              onClick={() => tu({ art: "beitritt", offen: !runde.beitritt_offen })}
            />
          )}
          <SymbolKnopf
            symbol="auswertung"
            name="Auswertung"
            onClick={() => setFenster("auswertung")}
          />
          <SymbolKnopf
            symbol="schluessel"
            name="Moderatorcode"
            onClick={() => setFenster("code")}
          />
          <SymbolKnopf
            symbol="mehr"
            name="Runde beenden oder löschen"
            onClick={() => setFenster("ende")}
          />
        </nav>
      </header>

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <div className={stil.dashboardRaster}>
        {/* ---------------------------------------------------- Fragen */}
        <section className={stil.spalte} aria-label="Fragen">
          <h2 className={stil.spaltenKopf}>
            Fragen{" "}
            <span className={stil.nebensache}>
              {s.beantwortet.length}/{s.fragen.length}
            </span>
          </h2>
          <ol className={stil.fragenleiste}>
            {s.fragen.map((f, i) => {
              const aktuell = f.id === frage?.id;
              const gespielt = s.beantwortet.includes(f.id);
              return (
                <li key={f.id}>
                  <button
                    type="button"
                    className={stil.fragenknopf}
                    aria-current={aktuell ? "true" : undefined}
                    data-gespielt={gespielt || undefined}
                    disabled={beendet || aktuell}
                    onClick={() => tu({ art: "frage", frage_id: f.id })}
                    aria-label={`Frage ${i + 1} wählen: ${f.text}`}
                  >
                    <span className={stil.fragennummer}>
                      {gespielt ? <Symbol name="haken" /> : i + 1}
                    </span>
                    <span className={stil.fragenzeile}>
                      <span className={stil.fragenkurz}>{f.text}</span>
                      <span className={stil.nebensache}>{TYPWORT[f.daten.typ]}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>

        {/* ---------------------------------------------------- Bühne */}
        <section className={stil.buehne} aria-label="Aktuelle Frage">
          {frage ? (
            <Buehne
              s={s}
              frage={frage}
              index={index}
              versatz={stand.versatz}
              timer={timer}
              setTimer={setTimer}
              naechste={naechste}
              beendet={beendet}
              tu={tu}
              rundeId={id}
              bewerten={(antwort, punkte) =>
                void handeln(() => bewerteAntwort(id, antwort.id, punkte))
              }
            />
          ) : (
            <div className={stil.buehneLeer}>
              {!beendet && (
                <>
                  <p className={stil.kapitaelchen}>Mitspielen mit dem Code</p>
                  <p className={stil.buehnenCode}>{runde.code}</p>
                </>
              )}
              <p className={stil.buehneHinweis}>
                {beendet
                  ? "Die Runde ist beendet. Die Auswertung steht oben rechts."
                  : "Die Spieler treten gerade bei. Wähle links eine Frage - sie bleibt verdeckt, bis du sie zeigst."}
              </p>
              {!beendet && s.fragen[0] && (
                <button
                  type="button"
                  className={stil.hauptknopf}
                  onClick={() => tu({ art: "frage", frage_id: s.fragen[0]!.id })}
                >
                  <Symbol name="start" gefuellt /> Mit Frage 1 beginnen
                </button>
              )}
            </div>
          )}
        </section>

        {/* ---------------------------------------------------- Spieler */}
        <section className={stil.spalte} aria-label="Spieler">
          <h2 className={stil.spaltenKopf}>
            Spieler{" "}
            <span className={stil.nebensache}>
              {s.spieler.filter((x) => x.verbunden).length} verbunden
            </span>
          </h2>
          {s.teams.length > 0 && (
            <ol className={stil.teamstand} aria-label="Teams">
              {s.teams.map((t) => (
                <li key={t.id}>
                  <span>{t.name}</span>
                  <strong>{t.punkte}</strong>
                </li>
              ))}
            </ol>
          )}
          {s.spieler.length === 0 ? (
            <p className={stil.nebensache}>
              Noch niemand da. Zeig den QR-Code <Symbol name="qr" /> oder den Code{" "}
              {runde.code}.
            </p>
          ) : (
            <ol className={stil.spielerleiste}>
              {s.spieler.map((wer) => (
                <li key={wer.id}>
                  <button
                    type="button"
                    className={stil.spielerknopf}
                    onClick={() => setFenster({ spieler: wer })}
                    aria-label={`${wer.name}, Platz ${wer.rang}, ${wer.punkte} Punkte - Aktionen`}
                  >
                    <span className={stil.rang}>{wer.rang}</span>
                    <span className={stil.verbindung} data-verbunden={wer.verbunden} />
                    <span className={stil.platzname}>
                      {wer.name}
                      {wer.team_id && (
                        <span className={stil.nebensache}>
                          {" "}
                          · {s.teams.find((t) => t.id === wer.team_id)?.name}
                        </span>
                      )}
                    </span>
                    <span className={stil.platzpunkte}>{wer.punkte}</span>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      {/* ---------------------------------------------------- Dialoge */}
      <Dialog
        titel="Mitspielen"
        offen={fenster === "qr"}
        schliessen={() => setFenster(null)}
      >
        <div className={stil.dialogMitte}>
          <QrKarte url={basis === null ? null : beitrittsAdresse(basis, runde.code)} />
          <p className={stil.grosserCode}>{runde.code}</p>
          {!runde.beitritt_offen && (
            <Hinweis>
              Der Beitritt ist geschlossen - nur Rückkehrer kommen hinein.
            </Hinweis>
          )}
        </div>
      </Dialog>

      <Dialog
        titel="Teams"
        offen={fenster === "teams"}
        schliessen={() => setFenster(null)}
        breit
      >
        <TeamDialog
          teams={s.teams}
          spieler={s.spieler}
          darf={!beendet}
          anlegen={(name) => handeln(() => legeTeamAn(id, name))}
          aufloesen={(team) => void handeln(() => loescheTeam(id, team.id))}
          zuordnen={(wer, team) => void handeln(() => weiseTeamZu(id, wer.id, team))}
        />
      </Dialog>

      <Dialog
        titel="Auswertung"
        offen={fenster === "auswertung"}
        schliessen={() => setFenster(null)}
        breit
      >
        <Auswertung rundeId={id} />
      </Dialog>

      <Dialog
        titel="Moderatorcode"
        offen={fenster === "code"}
        schliessen={() => {
          setFenster(null);
          setCode(null);
        }}
      >
        <div className={stil.dialogMitte}>
          {code ? (
            <>
              <QrKarte url={basis === null ? null : leitungsAdresse(basis, code)} />
              <p className={stil.grosserCode}>{code}</p>
              <p className={stil.nebensache}>
                Damit übernimmt ein anderes Gerät die Leitung. Der vorige Code gilt nicht
                mehr.
              </p>
            </>
          ) : (
            <>
              <p>
                Der Moderatorcode wird nur einmal angezeigt und nirgends im Klartext
                gespeichert. Brauchst du ihn für ein anderes Gerät, stell einen neuen aus.
              </p>
              <Knopf
                onClick={() =>
                  void handeln(async () => {
                    setCode((await neuerModeratorcode(id)).moderatorcode);
                  })
                }
              >
                Neuen Moderatorcode ausstellen
              </Knopf>
            </>
          )}
        </div>
      </Dialog>

      <Dialog
        titel="Runde"
        offen={fenster === "ende"}
        schliessen={() => setFenster(null)}
      >
        <div className={stil.formular}>
          {!beendet && (
            <Knopf
              auspraegung="sekundaer"
              onClick={() => {
                setFenster(null);
                tu({ art: "beenden" });
              }}
            >
              Runde beenden - danach tritt niemand mehr bei
            </Knopf>
          )}
          <Knopf
            auspraegung="leise"
            onClick={() =>
              void handeln(async () => {
                await loescheRunde(id);
                zurueck();
              })
            }
          >
            Runde mit allen Punkten löschen
          </Knopf>
        </div>
      </Dialog>

      <Dialog
        titel={typeof fenster === "object" && fenster ? fenster.spieler.name : ""}
        offen={typeof fenster === "object" && fenster !== null}
        schliessen={() => {
          setFenster(null);
          setWiederkehr(null);
        }}
      >
        {typeof fenster === "object" && fenster && (
          <SpielerDialog
            wer={s.spieler.find((x) => x.id === fenster.spieler.id) ?? fenster.spieler}
            wiederkehr={
              wiederkehr?.name === fenster.spieler.name ? wiederkehr.code : null
            }
            korrigieren={(punkte) =>
              void handeln(() => korrigiere(id, fenster.spieler.id, punkte))
            }
            codeAusstellen={() =>
              void handeln(async () => {
                setWiederkehr({
                  name: fenster.spieler.name,
                  code: await stelleWiederkehrAus(id, fenster.spieler.id),
                });
              })
            }
            entfernen={() => {
              setFenster(null);
              void handeln(() => entferneSpieler(id, fenster.spieler.id));
            }}
          />
        )}
      </Dialog>

      <p className="nur-vorlesen" aria-live="polite">
        {s.spieler.length} Spieler, {beendet ? "Beendet" : PHASEWORT[s.phase]}
      </p>
    </div>
  );
}

// ================================================================ Bühne

function Buehne({
  s,
  frage,
  index,
  versatz,
  timer,
  setTimer,
  naechste,
  beendet,
  tu,
  rundeId,
  bewerten,
}: {
  s: Steuerung;
  frage: Frage;
  index: number;
  versatz: number;
  timer: boolean;
  setTimer: (an: boolean) => void;
  naechste: Frage | undefined;
  beendet: boolean;
  tu: (aktion: Aktion) => void;
  rundeId: string;
  bewerten: (antwort: AntwortSicht, punkte: number) => void;
}) {
  const buzzer = frage.daten.typ === "buzzer";
  const offenOderZu = s.phase === "offen" || s.phase === "gesperrt";
  // Haben alle geantwortet, gibt es nichts mehr zu sperren - dann ist das
  // Auflösen dran.
  const alleDa = s.spieler.length > 0 && s.antworten.length >= s.spieler.length;

  /* Die eine Handlung, die jetzt dran ist - groß. Alles andere klein daneben. */
  let haupt: {
    wort: string;
    symbol: "start" | "pause" | "auge" | "weiter";
    aktion: Aktion;
  } | null = null;
  if (!beendet) {
    if (s.phase === "bereit")
      haupt = { wort: "Frage zeigen", symbol: "start", aktion: { art: "zeigen", timer } };
    else if (s.phase === "offen" && !buzzer && !alleDa)
      haupt = { wort: "Eingabe sperren", symbol: "pause", aktion: { art: "sperren" } };
    else if (offenOderZu)
      haupt = { wort: "Auflösen", symbol: "auge", aktion: { art: "aufloesen" } };
    else if (s.phase === "aufgeloest" && naechste)
      haupt = {
        wort: "Nächste Frage",
        symbol: "weiter",
        aktion: { art: "frage", frage_id: naechste.id },
      };
  }

  return (
    <>
      <div className={stil.buehnenKopf}>
        <span className={stil.fragemeta}>
          <span>
            Frage {index + 1} von {s.fragen.length}
          </span>
          <Etikett>{TYPWORT[frage.daten.typ]}</Etikett>
          <Etikett ton="akzent">{frage.punkte} P.</Etikett>
        </span>
        {s.frist && s.phase === "offen" && (
          <Countdown frist={s.frist} versatz={versatz} />
        )}
      </div>
      <h2 className={stil.buehnenFrage}>{frage.text}</h2>
      <p className={stil.loesungszeile}>
        <Symbol name="haken" /> {loesungstext(frage)}
      </p>

      <div className={stil.steuerzeile}>
        {haupt && (
          <button
            type="button"
            className={stil.hauptknopf}
            onClick={() => tu(haupt.aktion)}
          >
            <Symbol name={haupt.symbol} gefuellt={haupt.symbol === "start"} />
            {haupt.wort}
          </button>
        )}
        {!beendet && s.phase === "bereit" && frage.zeitlimit !== null && (
          <SymbolKnopf
            symbol="pause"
            name={
              timer
                ? `Ohne Timer zeigen (sonst ${frage.zeitlimit} s)`
                : `Mit Timer ${frage.zeitlimit} s zeigen`
            }
            aktiv={!timer}
            onClick={() => setTimer(!timer)}
          />
        )}
        {haupt?.aktion.art === "sperren" && (
          <SymbolKnopf
            symbol="auge"
            name="Sofort auflösen"
            onClick={() => tu({ art: "aufloesen" })}
          />
        )}
        {!beendet && s.phase === "gesperrt" && (
          <SymbolKnopf
            symbol="start"
            name="Eingabe wieder öffnen"
            onClick={() => tu({ art: "oeffnen" })}
          />
        )}
        {frage.hat_bild && s.phase !== "bereit" && !beendet && (
          <SymbolKnopf
            symbol={s.bild_sichtbar ? "verborgen" : "bild"}
            name={s.bild_sichtbar ? "Bild verbergen" : "Bild zeigen"}
            onClick={() => tu({ art: "bild", sichtbar: !s.bild_sichtbar })}
          />
        )}
        {frage.medien.includes("ton") && (
          <audio
            controls
            src={leitungsmediumAdresse(rundeId, "ton", frage.id)}
            className={stil.ton}
            aria-label="Ton zur Frage"
          />
        )}
      </div>

      <div className={stil.buehnenInhalt}>
        {buzzer ? (
          <BuzzerReihe s={s} darf={!beendet && offenOderZu} tu={tu} />
        ) : (
          <Antworten
            antworten={s.antworten}
            anzahlSpieler={s.spieler.length}
            aufgeloest={s.phase === "aufgeloest"}
            bewerten={bewerten}
          />
        )}
      </div>
    </>
  );
}

function BuzzerReihe({
  s,
  darf,
  tu,
}: {
  s: Steuerung;
  darf: boolean;
  tu: (aktion: Aktion) => void;
}) {
  const dran = s.buzzer.find((b) => b.urteil === "wartet");
  return (
    <div className={stil.buzzerpult}>
      <p className={stil.buzzerDran} role="status">
        {dran ? (
          <>
            <strong>{dran.spieler}</strong> ist dran
          </>
        ) : s.phase === "offen" ? (
          "Warte auf den ersten Druck …"
        ) : (
          "Zeig die Frage, dann gilt der Buzzer."
        )}
      </p>
      {darf && (
        <div className={stil.steuerzeile}>
          <button
            type="button"
            className={stil.hauptknopf}
            data-ton="gut"
            disabled={!dran}
            onClick={() => tu({ art: "buzzer", richtig: true })}
          >
            <Symbol name="haken" /> Richtig
          </button>
          <button
            type="button"
            className={stil.hauptknopf}
            data-ton="fehler"
            disabled={!dran}
            onClick={() => tu({ art: "buzzer", richtig: false })}
          >
            <Symbol name="kreuz" /> Falsch - nächster
          </button>
          <SymbolKnopf
            symbol="zurueck"
            name="Buzzer freigeben"
            onClick={() => tu({ art: "buzzer/zuruecksetzen" })}
          />
        </div>
      )}
      {s.buzzer.length > 0 && (
        <ol className={stil.buzzerliste}>
          {s.buzzer.map((b) => (
            <li key={b.spieler_id} data-urteil={b.urteil}>
              <span className={stil.rang}>{b.position}</span>
              <span className={stil.platzname}>{b.spieler}</span>
              <span className={stil.nebensache}>{b.urteil}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Antworten({
  antworten,
  anzahlSpieler,
  aufgeloest,
  bewerten,
}: {
  antworten: AntwortSicht[];
  anzahlSpieler: number;
  aufgeloest: boolean;
  bewerten: (antwort: AntwortSicht, punkte: number) => void;
}) {
  const anteil = anzahlSpieler ? antworten.length / anzahlSpieler : 0;
  return (
    <div className={stil.antwortbereich}>
      <div
        className={stil.fortschritt}
        aria-label={`${antworten.length} von ${anzahlSpieler} haben geantwortet`}
      >
        <span>
          {antworten.length} / {anzahlSpieler} Antworten
        </span>
        <span className={stil.fortschrittsbalken}>
          <span style={{ width: `${Math.round(anteil * 100)}%` }} />
        </span>
      </div>
      {antworten.length === 0 ? (
        <p className={stil.nebensache}>Noch keine Antwort.</p>
      ) : (
        <ul className={stil.antwortgitter}>
          {antworten.map((antwort) => (
            <li
              key={antwort.id}
              className={stil.antwortkarte}
              data-richtig={antwort.richtig === null ? undefined : antwort.richtig}
            >
              <span className={stil.antwortname}>
                {antwort.spieler}
                {!antwort.eingeloggt && <span className={stil.nebensache}> · tippt</span>}
              </span>
              <span className={stil.antworttext}>{antwort.anzeige}</span>
              {aufgeloest && <PunkteFeld antwort={antwort} bewerten={bewerten} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PunkteFeld({
  antwort,
  bewerten,
}: {
  antwort: AntwortSicht;
  bewerten: (antwort: AntwortSicht, punkte: number) => void;
}) {
  const [wert, setWert] = useState(String(antwort.punkte ?? ""));
  useEffect(() => setWert(String(antwort.punkte ?? "")), [antwort.punkte]);
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
      <button
        type="submit"
        className={stil.symbolknopf}
        aria-label={`Punkte für ${antwort.spieler} speichern`}
        title="Speichern"
      >
        <Symbol name="haken" />
      </button>
    </form>
  );
}

// ================================================================ Dialoge

function SpielerDialog({
  wer,
  wiederkehr,
  korrigieren,
  codeAusstellen,
  entfernen,
}: {
  wer: SpielerSicht;
  wiederkehr: Wiederkehrcode | null;
  korrigieren: (punkte: number) => void;
  codeAusstellen: () => void;
  entfernen: () => void;
}) {
  return (
    <div className={stil.formular}>
      <p className={stil.dialogZahl}>
        {wer.punkte} <span className={stil.nebensache}>Punkte · Platz {wer.rang}</span>
      </p>
      <div className={stil.steuerzeile}>
        <Knopf
          auspraegung="sekundaer"
          onClick={() => korrigieren(1)}
          aria-label={`${wer.name} einen Punkt geben`}
        >
          <Symbol name="plus" /> 1 Punkt
        </Knopf>
        <Knopf
          auspraegung="sekundaer"
          onClick={() => korrigieren(-1)}
          aria-label={`${wer.name} einen Punkt abziehen`}
        >
          <Symbol name="minus" /> 1 Punkt
        </Knopf>
      </div>
      {wiederkehr ? (
        <Hinweis ton="gut">
          Wiederkehrcode: <strong className={stil.code}>{wiederkehr.code}</strong> - gilt
          15 Minuten und einmal. Unter „Ich war schon dabei“ mit dem Namen eingeben.
        </Hinweis>
      ) : (
        <Knopf auspraegung="leise" onClick={codeAusstellen}>
          <Symbol name="schluessel" /> Wiederkehrcode für ein neues Gerät
        </Knopf>
      )}
      <Knopf auspraegung="leise" onClick={entfernen}>
        <Symbol name="kreuz" /> {wer.name} aus der Runde entfernen
      </Knopf>
    </div>
  );
}

function TeamDialog({
  teams,
  spieler,
  darf,
  anlegen,
  aufloesen,
  zuordnen,
}: {
  teams: TeamPlatz[];
  spieler: SpielerSicht[];
  darf: boolean;
  anlegen: (name: string) => Promise<boolean>;
  aufloesen: (team: TeamPlatz) => void;
  zuordnen: (wer: SpielerSicht, team: string | null) => void;
}) {
  const [name, setName] = useState("");

  async function absenden(e: FormEvent) {
    e.preventDefault();
    if (await anlegen(name)) setName("");
  }

  return (
    <div className={stil.teamdialog}>
      <div className={stil.formular}>
        <p className={stil.nebensache}>
          Ohne Teams spielt jeder für sich. Mit Teams wählen neue Spieler beim Beitritt
          eines, die Punkte der Mitglieder zählen zusammen, und je Team gilt ein Buzzer.
        </p>
        {darf && (
          <form className={stil.eroeffnen} onSubmit={(e) => void absenden(e)}>
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
        <ul className={stil.liste}>
          {teams.map((team) => (
            <li key={team.id} className={stil.listenzeile}>
              <span className={stil.zeilentext}>
                {team.name}{" "}
                <span className={stil.nebensache}>
                  · {team.mitglieder} · {team.punkte} P.
                </span>
              </span>
              {darf && (
                <SymbolKnopf
                  symbol="kreuz"
                  name={`Team ${team.name} auflösen`}
                  onClick={() => aufloesen(team)}
                />
              )}
            </li>
          ))}
        </ul>
      </div>
      {teams.length > 0 && (
        <ul className={stil.liste} aria-label="Einteilung">
          {spieler.map((wer) => (
            <li key={wer.id} className={stil.listenzeile}>
              <span className={stil.zeilentext}>{wer.name}</span>
              <label className={stil.auswahl}>
                <span className="nur-vorlesen">Team von {wer.name}</span>
                <select
                  value={wer.team_id ?? ""}
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Rueckblick =
  | { phase: "laedt" }
  | { phase: "fertig"; fragen: FrageAuswertung[] }
  | { phase: "fehler"; nachricht: string };

function Auswertung({ rundeId }: { rundeId: string }) {
  const [rueckblick, setRueckblick] = useState<Rueckblick>({ phase: "laedt" });

  useEffect(() => {
    const controller = new AbortController();
    ladeAuswertung(rundeId, controller.signal)
      .then((fragen) => setRueckblick({ phase: "fertig", fragen }))
      .catch((grund: unknown) => {
        if (!controller.signal.aborted)
          setRueckblick({ phase: "fehler", nachricht: meldung(grund) });
      });
    return () => controller.abort();
  }, [rundeId]);

  return (
    <div className={stil.auswertung}>
      <a className={stil.verweis} href={ergebnisAdresse(rundeId)} download>
        Ergebnis als CSV herunterladen
      </a>
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
          rueckblick.fragen.map((f) => (
            <section key={f.frage_id} className={stil.auswertungsfrage}>
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
                      ton={a.richtig === null ? "warnung" : a.richtig ? "gut" : "neutral"}
                    >
                      {a.punkte ?? "?"} P.
                    </Etikett>
                  </li>
                ))}
              </ul>
            </section>
          ))
        ))}
    </div>
  );
}
