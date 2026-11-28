import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { QrKarte } from "../../seiten/QrKarte";
import { Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter, Tafel } from "../../ui";
import { codeAusEingabe, useRundenstand } from "./abruf";
import { beitrittsAdresse, useBasisAdresse } from "./adresse";
import {
  rundenbildAdresse,
  type Rundenstand,
  rundenmediumAdresse,
  type TeamPlatz,
} from "./api";
import { Rangliste } from "./Rangliste";
import { FrageKopf } from "./SpielerTafel";
import stil from "./Quiz.module.css";

/**
 * Die Anzeigetafel für den Beamer. Ohne Konto, wie das Dashboard beim
 * Tischtennis: Sie zeigt nur, was jeder Mitspieler ohnehin sieht.
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
              Für den Beamer: Frage, Countdown und Rangliste einer Runde, groß und ohne
              Bedienelemente. Den Code zeigt die Leitung beim Eröffnen.
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
      <Tafel titel="Anzeigetafel">
        <div className={stil.laden} role="status" aria-label="Runde wird geladen">
          <Platzhalter breite="50%" hoehe="2.5rem" />
          <Platzhalter hoehe="16rem" />
        </div>
      </Tafel>
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
  return (
    <Tafel titel={stand.titel} beiwort={<span className={stil.code}>{stand.code}</span>}>
      <div className={stil.anzeige}>
        <section className={stil.anzeigeHaupt} aria-label="Aktuelle Frage">
          <Fragefeld stand={stand} versatz={versatz} />
        </section>
        <aside className={stil.anzeigeSeite}>
          {stand.status !== "beendet" && stand.beitritt_offen && (
            <QrKarte url={adresse} />
          )}
          {stand.teams.length > 0 && <TeamRangliste teams={stand.teams} />}
          <Rangliste plaetze={stand.rangliste} gross />
        </aside>
      </div>
    </Tafel>
  );
}

function Fragefeld({ stand, versatz }: { stand: Rundenstand; versatz: number }) {
  const { frage } = stand;
  if (stand.status === "beendet") {
    return <Siegerehrung stand={stand} />;
  }
  if (!frage || frage.text === null) {
    return (
      <Leerzustand titel={frage ? `Gleich: Frage ${frage.nummer}` : "Gleich geht es los"}>
        {stand.rangliste.length}{" "}
        {stand.rangliste.length === 1 ? "Person spielt" : "Personen spielen"} mit. Wer
        noch fehlt: QR-Code scannen oder den Code eingeben.
      </Leerzustand>
    );
  }

  const loesung = frage.loesung;
  return (
    <div className={stil.spiel}>
      <FrageKopf stand={stand} versatz={versatz} />
      {stand.bild_sichtbar && frage.hat_bild && (
        <div className={stil.hotspot}>
          <img
            src={rundenbildAdresse(stand.code, frage.nummer)}
            alt="Bild zur Frage"
            className={stil.bild}
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
      {frage.hat_ton && (
        <audio
          controls
          src={rundenmediumAdresse(stand.code, "ton", frage.nummer)}
          className={stil.ton}
          aria-label="Ton zur Frage"
        />
      )}
      {frage.bildoptionen.length > 0 && (
        <ol className={stil.anzeigeBilder}>
          {frage.bildoptionen.map((text, index) => (
            <li
              key={index}
              data-richtig={loesung ? loesung.optionen.includes(index) : undefined}
            >
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
          <ul className={stil.anzeigeOptionen} aria-label="Links">
            {frage.links.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          <ul className={stil.anzeigeOptionen} aria-label="Rechts">
            {frage.rechts.map((element) => (
              <li key={element.kennung}>{element.text}</li>
            ))}
          </ul>
        </div>
      )}
      {frage.optionen.length > 0 && (
        <ol className={stil.anzeigeOptionen}>
          {frage.optionen.map((option, index) => (
            <li
              key={index}
              data-richtig={loesung ? loesung.optionen.includes(index) : undefined}
            >
              {option}
            </li>
          ))}
        </ol>
      )}
      {frage.elemente.length > 0 && !loesung && (
        <ul className={stil.anzeigeOptionen}>
          {frage.elemente.map((element) => (
            <li key={element.kennung}>{element.text}</li>
          ))}
        </ul>
      )}
      {loesung ? (
        <p className={stil.loesung}>
          <span className={stil.nebensache}>Lösung</span>
          <strong>{loesung.anzeige}</strong>
        </p>
      ) : frage.typ === "buzzer" ? (
        <p className={stil.anzeigeStatus} role="status">
          {stand.buzzer ? `${stand.buzzer} ist dran!` : "Wer weiß es? Buzzer drücken!"}
        </p>
      ) : (
        <p className={stil.anzeigeStatus} role="status">
          {stand.anzahl_antworten} von {stand.rangliste.length} haben geantwortet
          {stand.phase === "gesperrt" ? " - Eingabe geschlossen" : ""}
        </p>
      )}
    </div>
  );
}

/**
 * Das Ende der Runde, so wie man es am Beamer sehen will: drei Plaetze,
 * der erste in der Mitte und am hoechsten. Geteilte Plaetze stehen
 * zusammen auf einer Stufe.
 */
export function Siegerehrung({ stand }: { stand: Rundenstand }) {
  const stufen = [2, 1, 3]
    .map((rang) => ({ rang, namen: stand.rangliste.filter((p) => p.rang === rang) }))
    .filter((stufe) => stufe.namen.length > 0);
  if (stufen.length === 0) {
    return (
      <Leerzustand titel="Endstand">
        Diese Runde ist vorbei - ohne Mitspieler.
      </Leerzustand>
    );
  }
  const sieger = stand.teams[0];
  return (
    <div className={stil.siegerehrung}>
      <h2 className={stil.fragetext}>Endstand</h2>
      {sieger && sieger.punkte > 0 && (
        <p className={stil.anzeigeStatus}>
          Bestes Team: <strong>{sieger.name}</strong> mit {sieger.punkte} Punkten
        </p>
      )}
      <ol className={stil.podest} aria-label="Siegerpodest">
        {stufen.map((stufe) => (
          <li key={stufe.rang} className={stil.stufe} data-rang={stufe.rang}>
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
    </div>
  );
}

function TeamRangliste({ teams }: { teams: TeamPlatz[] }) {
  return (
    <ol className={stil.rangliste} data-gross="true" aria-label="Teams">
      {teams.map((team) => (
        <li key={team.id} className={stil.platz}>
          <span className={stil.rang}>{team.rang}.</span>
          <span className={stil.platzname}>
            {team.name}
            <span className={stil.nebensache}> · {team.mitglieder}</span>
          </span>
          <span className={stil.platzpunkte}>{team.punkte}</span>
        </li>
      ))}
    </ol>
  );
}
