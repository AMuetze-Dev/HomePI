import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { meldung } from "../../api/client";
import {
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Tafel,
} from "../../ui";
import { codeAusEingabe, useRundenstand } from "./abruf";
import {
  antworte,
  buzzere,
  rundenbildAdresse,
  trittBei,
  type Rundenstand,
  rundenmediumAdresse,
  wechsleTeam,
  type TeamPlatz,
} from "./api";
import { Countdown } from "./Countdown";
import { Eingabe } from "./Eingabe";
import {
  alsEingabe,
  entwurfAus,
  leererEntwurf,
  vollstaendig,
  type Entwurf,
} from "./entwurf";
import { Rangliste } from "./Rangliste";
import stil from "./Quiz.module.css";

/**
 * Die Fläche für Mitspieler - ohne Konto.
 *
 * Drei Schritte, jeder mit eigener Adresse über `?code=`: Code eintippen,
 * Namen wählen, spielen. Wer die Seite neu lädt, landet wieder im Spiel: der
 * Code steht in der Adresse, das Token im Cookie.
 */
export function SpielerTafel() {
  const [suche, setSuche] = useSearchParams();
  const code = suche.get("code") ? codeAusEingabe(suche.get("code") ?? "") : null;

  if (code === null) {
    return (
      <Tafel titel="Mitspielen">
        <CodeFormular weiter={(neu) => setSuche({ code: neu })} />
      </Tafel>
    );
  }
  return <Runde code={code} zurueck={() => setSuche({})} />;
}

function CodeFormular({ weiter }: { weiter: (code: string) => void }) {
  const [eingabe, setEingabe] = useState("");
  const code = codeAusEingabe(eingabe);

  function absenden(ereignis: FormEvent) {
    ereignis.preventDefault();
    if (code.length === 6) weiter(code);
  }

  return (
    <Karte>
      <form className={stil.formular} onSubmit={absenden}>
        <p>
          Die Spielleitung zeigt einen Code aus sechs Zeichen - am Beamer oder als
          QR-Code. Ein Konto brauchst du nicht.
        </p>
        <Feld
          beschriftung="Rundencode"
          value={eingabe}
          onChange={(e) => setEingabe(e.target.value)}
          autoComplete="off"
          autoCapitalize="characters"
          maxLength={9}
          className={stil.codefeld}
        />
        <Knopf type="submit" disabled={code.length !== 6}>
          Weiter
        </Knopf>
      </form>
    </Karte>
  );
}

function Runde({ code, zurueck }: { code: string; zurueck: () => void }) {
  const { abruf, uebernehmen } = useRundenstand(code);

  if (abruf.phase === "laedt") {
    return (
      <Tafel titel="Mitspielen">
        <div className={stil.laden} role="status" aria-label="Runde wird geladen">
          <Platzhalter breite="60%" hoehe="1.5rem" />
          <Platzhalter hoehe="10rem" />
        </div>
      </Tafel>
    );
  }

  if (abruf.phase === "fehler") {
    return (
      <Tafel titel="Mitspielen">
        <Hinweis ton="fehler" dringend>
          {abruf.nachricht}
        </Hinweis>
        <div>
          <Knopf auspraegung="sekundaer" onClick={zurueck}>
            Anderen Code eingeben
          </Knopf>
        </div>
      </Tafel>
    );
  }

  const { stand, versatz } = abruf;
  if (stand.ich === null) {
    return (
      <Tafel titel={stand.titel} beiwort={`Runde ${stand.code}`}>
        {stand.status === "beendet" ? (
          <>
            <Leerzustand titel="Diese Runde ist vorbei">
              Hier tritt niemand mehr bei. Der Endstand steht darunter.
            </Leerzustand>
            <Rangliste plaetze={stand.rangliste} />
          </>
        ) : (
          <NamensFormular
            code={code}
            teams={stand.teams}
            offen={stand.beitritt_offen}
            uebernehmen={uebernehmen}
          />
        )}
      </Tafel>
    );
  }

  return (
    <Tafel
      titel={stand.titel}
      beiwort={
        <>
          {stand.ich.name}
          {stand.ich.team ? ` (${stand.ich.team})` : ""} · {stand.ich.punkte}{" "}
          {stand.ich.punkte === 1 ? "Punkt" : "Punkte"} · Platz {stand.ich.rang}
        </>
      }
    >
      <Spiel stand={stand} versatz={versatz} uebernehmen={uebernehmen} />
    </Tafel>
  );
}

function NamensFormular({
  code,
  teams,
  offen,
  uebernehmen,
}: {
  code: string;
  teams: TeamPlatz[];
  offen: boolean;
  uebernehmen: (stand: Rundenstand) => void;
}) {
  const [name, setName] = useState("");
  const [team, setTeam] = useState("");
  // Ist der Beitritt zu, bleibt nur der Weg zurueck - also gleich dorthin.
  const [wiederkehr, setWiederkehr] = useState(!offen);
  const [wiederkehrcode, setWiederkehrcode] = useState("");
  const [fehler, setFehler] = useState("");
  const [sendet, setSendet] = useState(false);

  async function absenden(ereignis: FormEvent) {
    ereignis.preventDefault();
    setFehler("");
    setSendet(true);
    try {
      uebernehmen(
        await trittBei(
          code,
          name,
          wiederkehr ? wiederkehrcode : undefined,
          wiederkehr ? undefined : team || undefined,
        ),
      );
    } catch (grund) {
      // Die Eingabe bleibt stehen - wer "Anna" tippt und hört, dass es Anna
      // schon gibt, ändert einen Buchstaben und tippt nicht alles neu.
      setFehler(meldung(grund));
    } finally {
      setSendet(false);
    }
  }

  return (
    <Karte>
      <form className={stil.formular} onSubmit={(e) => void absenden(e)}>
        {offen ? (
          <p>
            Wähle deinen Namen für diese Runde. Er gehört dann dir: Nur dieses Gerät kann
            unter ihm antworten.
          </p>
        ) : (
          <Hinweis>
            Die Spielleitung hat den Beitritt geschlossen. Wer schon dabei war, kommt mit
            seinem Wiederkehrcode zurück.
          </Hinweis>
        )}
        <Feld
          beschriftung="Dein Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={24}
          autoComplete="nickname"
          required
        />
        {!wiederkehr && teams.length > 0 && (
          <Teamwahl teams={teams} gewaehlt={team} waehlen={setTeam} />
        )}
        {wiederkehr && (
          <Feld
            beschriftung="Wiederkehrcode"
            hinweis="Bekommst du von der Spielleitung, wenn dein altes Gerät weg ist."
            value={wiederkehrcode}
            onChange={(e) => setWiederkehrcode(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            required
          />
        )}
        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}
        <div className={stil.knopfzeile}>
          <Knopf
            type="submit"
            disabled={
              sendet ||
              name.trim() === "" ||
              (!wiederkehr && teams.length > 0 && team === "")
            }
          >
            {wiederkehr ? "Zurück ins Spiel" : "Mitspielen"}
          </Knopf>
          {offen && (
            <Knopf
              auspraegung="leise"
              type="button"
              onClick={() => setWiederkehr(!wiederkehr)}
            >
              {wiederkehr ? "Neu beitreten" : "Ich war schon dabei"}
            </Knopf>
          )}
        </div>
      </form>
    </Karte>
  );
}

function Teamwahl({
  teams,
  gewaehlt,
  waehlen,
  gesperrt = false,
}: {
  teams: TeamPlatz[];
  gewaehlt: string;
  waehlen: (team: string) => void;
  gesperrt?: boolean;
}) {
  return (
    <fieldset className={stil.optionen} disabled={gesperrt}>
      <legend className={stil.nebensache}>Dein Team</legend>
      {teams.map((t) => (
        <label key={t.id} className={stil.option} data-gewaehlt={gewaehlt === t.id}>
          <input
            type="radio"
            name="team"
            checked={gewaehlt === t.id}
            onChange={() => waehlen(t.id)}
          />
          <span>
            {t.name}
            <span className={stil.nebensache}>
              {" "}
              · {t.mitglieder} {t.mitglieder === 1 ? "Person" : "Personen"}
            </span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}

function Spiel({
  stand,
  versatz,
  uebernehmen,
}: {
  stand: Rundenstand;
  versatz: number;
  uebernehmen: (stand: Rundenstand) => void;
}) {
  const { frage, ich } = stand;
  const [entwurf, setEntwurf] = useState<Entwurf | null>(null);
  const [fehler, setFehler] = useState("");
  const [sendet, setSendet] = useState(false);
  const schluessel = frage ? `${frage.nummer}:${frage.text ?? ""}` : "";

  // Neue Frage, neuer Entwurf - aus der gespeicherten Antwort, falls es eine
  // gibt. Am Schlüssel und nicht an jedem Abruf, sonst überschriebe der
  // Takt das Tippen.
  useEffect(() => {
    setFehler("");
    if (!frage || frage.text === null) {
      setEntwurf(null);
      return;
    }
    setEntwurf(ich?.antwort ? entwurfAus(frage, ich.antwort.wert) : leererEntwurf(frage));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schluessel]);

  async function handeln(aktion: () => Promise<Rundenstand>) {
    setFehler("");
    setSendet(true);
    try {
      uebernehmen(await aktion());
    } catch (grund) {
      setFehler(meldung(grund));
    } finally {
      setSendet(false);
    }
  }

  if (stand.status === "beendet") {
    return (
      <>
        <Hinweis ton="gut">Die Runde ist vorbei - danke fürs Mitspielen!</Hinweis>
        <Rangliste plaetze={stand.rangliste} hervorheben={ich?.name} />
      </>
    );
  }

  if (!frage || frage.text === null) {
    const meinTeam = stand.teams.find((t) => t.name === ich?.team)?.id ?? "";
    return (
      <>
        {stand.status === "lobby" && stand.teams.length > 0 && (
          <Teamwahl
            teams={stand.teams}
            gewaehlt={meinTeam}
            gesperrt={sendet}
            waehlen={(team) => void handeln(() => wechsleTeam(stand.code, team))}
          />
        )}
        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}
        <Leerzustand
          titel={frage ? `Frage ${frage.nummer} kommt gleich` : "Gleich geht es los"}
        >
          {frage?.kategorie
            ? `Kategorie: ${frage.kategorie}. Die Frage erscheint hier von selbst.`
            : "Die Spielleitung startet die nächste Frage. Sie erscheint hier von selbst."}
        </Leerzustand>
        <Rangliste plaetze={stand.rangliste} hervorheben={ich?.name} />
      </>
    );
  }

  const offen = stand.phase === "offen";
  const bild =
    stand.bild_sichtbar && frage.hat_bild
      ? rundenbildAdresse(stand.code, frage.nummer)
      : null;
  const abgegeben = ich?.antwort?.eingeloggt ?? false;

  return (
    <div className={stil.spiel}>
      <FrageKopf stand={stand} versatz={versatz} />
      {bild && frage.typ !== "hotspot" && (
        <img src={bild} alt="Bild zur Frage" className={stil.bild} />
      )}

      {stand.phase === "aufgeloest" ? (
        <Ergebnis stand={stand} />
      ) : frage.typ === "buzzer" ? (
        <Buzzer
          stand={stand}
          sendet={sendet}
          druecken={() => void handeln(() => buzzere(stand.code))}
        />
      ) : (
        entwurf && (
          <form
            className={stil.formular}
            onSubmit={(e) => {
              e.preventDefault();
              void handeln(() => antworte(stand.code, alsEingabe(frage, entwurf)));
            }}
          >
            <Eingabe
              frage={frage}
              entwurf={entwurf}
              aendern={setEntwurf}
              bildAdresse={bild}
              gesperrt={!offen}
              medienAdresse={(schluessel) =>
                rundenmediumAdresse(stand.code, schluessel, frage.nummer)
              }
            />
            <div className={stil.knopfzeile}>
              <Knopf
                type="submit"
                disabled={!offen || sendet || !vollstaendig(frage, entwurf)}
              >
                {abgegeben ? "Antwort ändern" : "Antwort abgeben"}
              </Knopf>
              {abgegeben && <Etikett ton="gut">Abgegeben</Etikett>}
              {!offen && <Etikett ton="warnung">Eingabe gesperrt</Etikett>}
            </div>
          </form>
        )
      )}

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}
    </div>
  );
}

export function FrageKopf({ stand, versatz }: { stand: Rundenstand; versatz: number }) {
  const { frage } = stand;
  if (!frage) return null;
  return (
    <div className={stil.fragekopf}>
      <div className={stil.fragemeta}>
        <span>
          Frage {frage.nummer} von {frage.anzahl}
        </span>
        {frage.kategorie && <Etikett>{frage.kategorie}</Etikett>}
        <Etikett ton="akzent">
          {frage.punkte} {frage.punkte === 1 ? "Punkt" : "Punkte"}
        </Etikett>
        {stand.frist && stand.phase === "offen" && (
          <Countdown frist={stand.frist} versatz={versatz} />
        )}
      </div>
      <h2 className={stil.fragetext}>{frage.text}</h2>
    </div>
  );
}

function Buzzer({
  stand,
  sendet,
  druecken,
}: {
  stand: Rundenstand;
  sendet: boolean;
  druecken: () => void;
}) {
  const ich = stand.ich;
  const position = ich?.buzzer_position ?? null;
  let status = "Wer zuerst drückt, antwortet.";
  if (position !== null) {
    status =
      ich?.buzzer_urteil === "falsch"
        ? "Leider falsch."
        : stand.buzzer === ich?.name
          ? "Du bist dran - antworte laut!"
          : `Du bist auf Platz ${position} in der Reihe.`;
  } else if (stand.buzzer) {
    status = `${stand.buzzer} ist dran. Du kannst noch drücken, falls es falsch ist.`;
  }

  return (
    <div className={stil.buzzerbereich}>
      <button
        type="button"
        className={stil.buzzer}
        onClick={druecken}
        disabled={sendet || position !== null || stand.phase !== "offen"}
      >
        Buzzer
      </button>
      <p role="status" className={stil.buzzerstatus}>
        {stand.phase === "offen" ? status : "Der Buzzer ist gesperrt."}
      </p>
    </div>
  );
}

function Ergebnis({ stand }: { stand: Rundenstand }) {
  const { frage, ich } = stand;
  const antwort = ich?.antwort;
  let urteil = <Hinweis>Du hast bei dieser Frage nicht geantwortet.</Hinweis>;
  if (frage?.typ === "buzzer") {
    urteil =
      ich?.buzzer_urteil === "richtig" ? (
        <Hinweis ton="gut">Richtig - die Punkte gehören dir.</Hinweis>
      ) : (
        <Hinweis>Diese Frage ist entschieden.</Hinweis>
      );
  } else if (antwort) {
    if (antwort.richtig === null) {
      urteil = <Hinweis>Die Spielleitung bewertet deine Antwort.</Hinweis>;
    } else if (antwort.richtig) {
      urteil = <Hinweis ton="gut">Richtig! +{antwort.punkte ?? 0}</Hinweis>;
    } else {
      urteil = (
        <Hinweis ton={antwort.punkte ? "neutral" : "fehler"}>
          {antwort.punkte ? `Teilweise richtig: +${antwort.punkte}` : "Leider daneben."}
        </Hinweis>
      );
    }
  }
  return (
    <div className={stil.ergebnis}>
      {frage?.loesung && (
        <p className={stil.loesung}>
          <span className={stil.nebensache}>Lösung</span>
          <strong>{frage.loesung.anzeige}</strong>
        </p>
      )}
      {urteil}
      <Rangliste plaetze={stand.rangliste} hervorheben={ich?.name} />
    </div>
  );
}
