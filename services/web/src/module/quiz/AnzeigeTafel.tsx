import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { QrKarte } from "../../seiten/QrKarte";
import { Feld, Hinweis, Karte, Knopf, Platzhalter, Tafel } from "../../ui";
import { codeAusEingabe, restSekunden, useRundenstand } from "./abruf";
import { beitrittsAdresse, useBasisAdresse } from "./adresse";
import {
  rundenbildAdresse,
  rundenmediumAdresse,
  type Platz,
  type Rundenstand,
  type TeamPlatz,
} from "./api";
import { Symbol } from "./Symbol";
import stil from "./Quiz.module.css";

const BUCHSTABEN = "ABCDEFGH";

/**
 * Die Anzeigetafel für den Beamer - aus fünf Metern lesbar.
 *
 * Kein Bedienelement, keine Kästen: Die Frage ist das Größte im Raum, die
 * Rangliste das Zweitgrößte, und alles andere tritt zurück. Ohne Konto
 * erreichbar, wie das Dashboard beim Tischtennis - sie zeigt nur, was jeder
 * Mitspieler ohnehin sieht.
 */
export function AnzeigeTafel() {
  const [suche, setSuche] = useSearchParams();
  const code = suche.get("code") ? codeAusEingabe(suche.get("code") ?? "") : null;
  const [eingabe, setEingabe] = useState("");

  if (code === null) {
    const absenden = (ereignis: FormEvent) => {
      ereignis.preventDefault();
      setSuche({ code: codeAusEingabe(eingabe) });
    };
    return (
      <Tafel titel="Anzeigetafel">
        <Karte>
          <form className={stil.formular} onSubmit={absenden}>
            <p>
              Für den Beamer: Frage, Countdown und Rangliste einer Runde - groß und ohne
              Bedienelemente. Die Leitung öffnet sie über das Bildschirm-Symbol.
            </p>
            <Feld
              beschriftung="Rundencode"
              value={eingabe}
              onChange={(e) => setEingabe(e.target.value)}
              autoComplete="off"
              className={stil.codefeld}
            />
            <Knopf type="submit" disabled={codeAusEingabe(eingabe).length !== 6}>
              Anzeigen
            </Knopf>
          </form>
        </Karte>
      </Tafel>
    );
  }
  return <Anzeige code={code} />;
}

function Anzeige({ code }: { code: string }) {
  const { abruf } = useRundenstand(code);
  const basis = useBasisAdresse();

  if (abruf.phase === "laedt") {
    return (
      <div className={stil.buehnenbild} role="status" aria-label="Runde wird geladen">
        <Platzhalter breite="40%" hoehe="2rem" />
        <Platzhalter hoehe="20rem" />
      </div>
    );
  }
  if (abruf.phase === "fehler") {
    return (
      <Tafel titel="Anzeigetafel">
        <Hinweis ton="fehler" dringend>
          {abruf.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { stand, versatz } = abruf;
  const adresse = basis === null ? null : beitrittsAdresse(basis, stand.code);
  const lobby = !stand.frage && stand.status !== "beendet";

  return (
    <div className={stil.buehnenbild}>
      <header className={stil.tafelkopf}>
        <h1 className={stil.tafeltitel}>{stand.titel}</h1>
        <span className={stil.tafelcode}>
          <span className={stil.kapitaelchen}>Code</span> {stand.code}
        </span>
      </header>

      {stand.status === "beendet" ? (
        <Siegerehrung stand={stand} />
      ) : lobby ? (
        <Lobby stand={stand} adresse={adresse} />
      ) : (
        <div className={stil.tafelraster}>
          <section className={stil.tafelhaupt} aria-label="Aktuelle Frage">
            <Fragefeld stand={stand} versatz={versatz} />
          </section>
          <aside className={stil.tafelseite}>
            {stand.teams.length > 0 && <TeamRangliste teams={stand.teams} />}
            <Bestenliste plaetze={stand.rangliste} />
            {stand.beitritt_offen && (
              <div className={stil.tafelqr}>
                <QrKarte url={adresse} />
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

// ================================================================ Lobby

function Lobby({ stand, adresse }: { stand: Rundenstand; adresse: string | null }) {
  const anzahl = stand.rangliste.length;
  return (
    <div className={stil.lobby}>
      <section className={stil.lobbyText}>
        <p className={stil.kapitaelchen}>Mitspielen mit dem Code</p>
        <p className={stil.lobbyCode} aria-label={`Code ${stand.code}`}>
          {stand.code.split("").map((zeichen, i) => (
            <span key={i} aria-hidden="true">
              {zeichen}
            </span>
          ))}
        </p>
        {adresse && (
          <p className={stil.lobbyAdresse}>{adresse.replace(/^https?:\/\//, "")}</p>
        )}
        <p className={stil.lobbyZahl}>
          <strong>{anzahl}</strong> {anzahl === 1 ? "Person ist" : "Personen sind"} dabei
        </p>
        {anzahl > 0 && (
          <ul className={stil.lobbyNamen} aria-label="Mitspieler">
            {stand.rangliste.map((p) => (
              <li key={p.name}>{p.name}</li>
            ))}
          </ul>
        )}
        {!stand.beitritt_offen && (
          <p className={stil.nebensache}>Der Beitritt ist geschlossen.</p>
        )}
      </section>
      {stand.beitritt_offen && (
        <div className={stil.lobbyQr}>
          <QrKarte url={adresse} />
        </div>
      )}
    </div>
  );
}

// ================================================================ Frage

function Fragefeld({ stand, versatz }: { stand: Rundenstand; versatz: number }) {
  const frage = stand.frage!;
  if (frage.text === null) {
    return (
      <div className={stil.gleich}>
        <p className={stil.kapitaelchen}>
          Frage {frage.nummer} von {frage.anzahl}
          {frage.kategorie && ` · ${frage.kategorie}`}
        </p>
        <p className={stil.gleichText}>Gleich geht es los …</p>
      </div>
    );
  }

  const loesung = frage.loesung;
  return (
    <div className={stil.fragebuehne}>
      <div className={stil.fragezeileOben}>
        <p className={stil.kapitaelchen}>
          Frage {frage.nummer} von {frage.anzahl}
          {frage.kategorie && ` · ${frage.kategorie}`}
          {` · ${frage.punkte} ${frage.punkte === 1 ? "Punkt" : "Punkte"}`}
        </p>
        {stand.frist && stand.phase === "offen" && (
          <Zeitring frist={stand.frist} versatz={versatz} />
        )}
      </div>

      <h2 className={stil.tafelfrage}>{frage.text}</h2>

      {frage.hat_ton && (
        <audio
          controls
          src={rundenmediumAdresse(stand.code, "ton", frage.nummer)}
          className={stil.ton}
          aria-label="Ton zur Frage"
        />
      )}

      {stand.bild_sichtbar && frage.hat_bild && (
        <div className={stil.hotspot}>
          <img
            src={rundenbildAdresse(stand.code, frage.nummer)}
            alt="Bild zur Frage"
            className={stil.tafelbild}
          />
          {loesung?.ziele.map((ziel, index) => (
            <span
              key={index}
              className={stil.zielkreis}
              style={{
                left: `${ziel.x}%`,
                top: `${ziel.y}%`,
                width: `${ziel.radius * 2}%`,
              }}
              aria-hidden="true"
            />
          ))}
        </div>
      )}

      {frage.optionen.length > 0 && (
        <ol className={stil.tafeloptionen}>
          {frage.optionen.map((option, index) => (
            <li
              key={index}
              data-richtig={loesung ? loesung.optionen.includes(index) : undefined}
            >
              <span className={stil.optionsbuchstabe} aria-hidden="true">
                {BUCHSTABEN[index]}
              </span>
              <span className={stil.optionstext}>{option}</span>
              {loesung?.optionen.includes(index) && <Symbol name="haken" />}
            </li>
          ))}
        </ol>
      )}

      {frage.bildoptionen.length > 0 && (
        <ol className={stil.anzeigeBilder}>
          {frage.bildoptionen.map((text, index) => (
            <li
              key={index}
              data-richtig={loesung ? loesung.optionen.includes(index) : undefined}
            >
              <span className={stil.optionsbuchstabe} aria-hidden="true">
                {BUCHSTABEN[index]}
              </span>
              <img
                src={rundenmediumAdresse(stand.code, `option-${index}`, frage.nummer)}
                alt={text || `Bild ${index + 1}`}
                className={stil.optionsbild}
              />
            </li>
          ))}
        </ol>
      )}

      {frage.links.length > 0 && !loesung && (
        <div className={stil.anzeigeZuordnen}>
          <ul className={stil.tafeloptionen} aria-label="Links">
            {frage.links.map((text, i) => (
              <li key={text}>
                <span className={stil.optionsbuchstabe} aria-hidden="true">
                  {i + 1}
                </span>
                <span className={stil.optionstext}>{text}</span>
              </li>
            ))}
          </ul>
          <ul className={stil.tafeloptionen} aria-label="Rechts">
            {frage.rechts.map((element, i) => (
              <li key={element.kennung}>
                <span className={stil.optionsbuchstabe} aria-hidden="true">
                  {BUCHSTABEN[i]}
                </span>
                <span className={stil.optionstext}>{element.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {frage.elemente.length > 0 && !loesung && (
        <ul className={stil.tafeloptionen}>
          {frage.elemente.map((element) => (
            <li key={element.kennung}>
              <span className={stil.optionstext}>{element.text}</span>
            </li>
          ))}
        </ul>
      )}

      <footer className={stil.tafelfuss}>
        {loesung ? (
          <p className={stil.tafelloesung}>
            <span className={stil.kapitaelchen}>Lösung</span>
            <strong>{loesung.anzeige}</strong>
          </p>
        ) : frage.typ === "buzzer" ? (
          <p className={stil.tafelbuzzer} role="status">
            {stand.buzzer ? `${stand.buzzer} ist dran!` : "Wer weiß es? Buzzer drücken!"}
          </p>
        ) : (
          <Fortschritt
            antworten={stand.anzahl_antworten}
            gesamt={stand.rangliste.length}
            gesperrt={stand.phase === "gesperrt"}
          />
        )}
      </footer>
    </div>
  );
}

function Fortschritt({
  antworten,
  gesamt,
  gesperrt,
}: {
  antworten: number;
  gesamt: number;
  gesperrt: boolean;
}) {
  const anteil = gesamt ? Math.min(1, antworten / gesamt) : 0;
  return (
    <div className={stil.tafelfortschritt} role="status">
      <span>
        {antworten} von {gesamt} haben geantwortet
        {gesperrt ? " - Eingabe geschlossen" : ""}
      </span>
      <span className={stil.fortschrittsbalken} aria-hidden="true">
        <span style={{ width: `${Math.round(anteil * 100)}%` }} />
      </span>
    </div>
  );
}

/**
 * Die Restzeit als Ring. Die Gesamtzeit kennt die Tafel nicht - sie nimmt
 * die Restzeit beim ersten Blick auf diese Frist, und das ist beim Zeigen
 * der Frage die ganze.
 */
function Zeitring({ frist, versatz }: { frist: string; versatz: number }) {
  const [rest, setRest] = useState(() => restSekunden(frist, versatz));
  const gesamt = useRef(Math.max(1, rest));

  useEffect(() => {
    gesamt.current = Math.max(1, restSekunden(frist, versatz));
    setRest(restSekunden(frist, versatz));
    const uhr = window.setInterval(() => setRest(restSekunden(frist, versatz)), 250);
    return () => window.clearInterval(uhr);
  }, [frist, versatz]);

  const umfang = 2 * Math.PI * 26;
  const anteil = Math.max(0, Math.min(1, rest / gesamt.current));
  return (
    <div
      className={stil.zeitring}
      data-knapp={rest <= 5}
      role="timer"
      aria-label={`Noch ${rest} Sekunden`}
    >
      <svg viewBox="0 0 60 60" aria-hidden="true">
        <circle cx="30" cy="30" r="26" className={stil.zeitringSpur} />
        <circle
          cx="30"
          cy="30"
          r="26"
          className={stil.zeitringRest}
          strokeDasharray={umfang}
          strokeDashoffset={umfang * (1 - anteil)}
        />
      </svg>
      <span>{rest}</span>
    </div>
  );
}

// ================================================================ Ranglisten

function Bestenliste({ plaetze }: { plaetze: Platz[] }) {
  if (plaetze.length === 0) {
    return <p className={stil.nebensache}>Noch spielt niemand mit.</p>;
  }
  const spitze = Math.max(1, ...plaetze.map((p) => p.punkte));
  return (
    <ol className={stil.bestenliste} aria-label="Rangliste">
      {plaetze.slice(0, 10).map((p) => (
        <li key={p.name} data-rang={p.rang <= 3 ? p.rang : undefined}>
          <span className={stil.bestenrang}>{p.rang}</span>
          <span className={stil.bestenname}>
            {p.name}
            <span className={stil.bestenbalken} aria-hidden="true">
              <span
                style={{
                  width: `${Math.round((Math.max(0, p.punkte) / spitze) * 100)}%`,
                }}
              />
            </span>
          </span>
          <span className={stil.bestenpunkte}>{p.punkte}</span>
        </li>
      ))}
    </ol>
  );
}

function TeamRangliste({ teams }: { teams: TeamPlatz[] }) {
  return (
    <ol className={stil.bestenliste} data-teams="true" aria-label="Teams">
      {teams.map((team) => (
        <li key={team.id} data-rang={team.rang === 1 ? 1 : undefined}>
          <span className={stil.bestenrang}>{team.rang}</span>
          <span className={stil.bestenname}>
            {team.name}
            <span className={stil.nebensache}> · {team.mitglieder}</span>
          </span>
          <span className={stil.bestenpunkte}>{team.punkte}</span>
        </li>
      ))}
    </ol>
  );
}

// ================================================================ Ende

/**
 * Das Ende der Runde: drei Stufen, die erste in der Mitte und am höchsten.
 * Geteilte Plätze stehen zusammen auf einer Stufe.
 */
export function Siegerehrung({ stand }: { stand: Rundenstand }) {
  const stufen = [2, 1, 3]
    .map((rang) => ({ rang, namen: stand.rangliste.filter((p) => p.rang === rang) }))
    .filter((stufe) => stufe.namen.length > 0);
  if (stufen.length === 0) {
    return (
      <div className={stil.gleich}>
        <p className={stil.kapitaelchen}>Endstand</p>
        <p className={stil.gleichText}>Diese Runde ist vorbei - ohne Mitspieler.</p>
      </div>
    );
  }
  const sieger = stand.teams[0];
  const weitere = stand.rangliste.filter((p) => p.rang > 3);
  return (
    <div className={stil.siegerehrung}>
      <h2 className={stil.kapitaelchen}>Endstand</h2>
      {sieger && sieger.punkte > 0 && (
        <p className={stil.siegerteam}>
          Bestes Team: <strong>{sieger.name}</strong> mit {sieger.punkte} Punkten
        </p>
      )}
      <ol className={stil.podest} aria-label="Siegerpodest">
        {stufen.map((stufe) => (
          <li key={stufe.rang} className={stil.stufe} data-rang={stufe.rang}>
            {stufe.rang === 1 && (
              <span className={stil.krone}>
                <Symbol name="pokal" />
              </span>
            )}
            <span className={stil.stufenname}>
              {stufe.namen.map((p) => p.name).join(" & ")}
            </span>
            <span className={stil.stufenpunkte}>{stufe.namen[0]!.punkte} Punkte</span>
            <span className={stil.stufenblock} aria-label={`Platz ${stufe.rang}`}>
              {stufe.rang}
            </span>
          </li>
        ))}
      </ol>
      {weitere.length > 0 && (
        <div className={stil.weitere}>
          <Bestenliste plaetze={weitere} />
        </div>
      )}
    </div>
  );
}
