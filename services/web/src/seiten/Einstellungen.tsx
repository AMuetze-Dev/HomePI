import { useState, type ReactNode } from "react";

import { aenderePasswort, type Rolle } from "../api/anmeldung";
import { useAnmeldung } from "../anmeldung/kontext";
import { SystemStatus } from "../components/SystemStatus";
import { GRUENDE } from "../huelle/darstellung";
import { useBewegung } from "../huelle/useBewegung";
import { useGrund } from "../huelle/useGrund";
import { useThema, type Thema } from "../huelle/useThema";
import { useModule } from "../module/useModule";
import {
  Etikett,
  Farbwahl,
  Feld,
  Hinweis,
  Knopf,
  Regel,
  Schalter,
  Segmentwahl,
} from "../ui";
import stil from "./Einstellungen.module.css";

const THEMEN = [
  { wert: "system", wort: "System" },
  { wert: "hell", wort: "Hell" },
  { wert: "dunkel", wort: "Dunkel" },
] as const satisfies readonly { wert: Thema; wort: string }[];

const ROLLENWORT: Record<Rolle, string> = {
  leser: "Lesen",
  nutzer: "Schreiben",
  verwalter: "Verwalter",
};

/**
 * Was dieses Konto an dieser Installation einstellen kann.
 *
 * Bewusst eine schmale Spalte und kein Raster aus Karten: Jede Zeile hier
 * ist ein Satz mit einem Schalter am Ende, und Sätze liest man in einer
 * Spalte. Die Breite entscheidet nicht der Monitor, sondern die Zeile.
 *
 * Die Überschrift sagt „für dieses Konto, nicht für die Installation" -
 * weil genau das die Frage ist, die jeder zuerst hat. Was die Installation
 * angeht, steht in der Nutzerverwaltung.
 */
export function Einstellungen() {
  const { benutzer } = useAnmeldung();
  const { thema, setzeThema } = useThema();
  const { reduziert, setzeReduziert } = useBewegung();
  const { grund, setzeGrund } = useGrund();

  return (
    <div className={stil.seite}>
      <h1 className={stil.titel}>Einstellungen</h1>
      <p className={stil.unterzeile}>
        Gilt für dieses Konto, nicht für die Installation.
      </p>

      <Abschnitt titel="Darstellung">
        <Zeile wort="Farbschema" erklaerung="Folgt dem Gerät, bis du es hier festlegst.">
          <Segmentwahl
            beschriftung="Farbschema"
            optionen={THEMEN}
            wert={thema}
            beiWahl={setzeThema}
          />
        </Zeile>

        <Zeile
          wort="Grundfarbe"
          erklaerung="Der Stich des Hintergrunds. Der Akzent bleibt, wie er ist."
        >
          <Farbwahl
            beschriftung="Grundfarbe"
            optionen={GRUENDE}
            wert={grund}
            beiWahl={setzeGrund}
          />
        </Zeile>

        <Zeile
          wort="Bewegung reduzieren"
          erklaerung="Übergänge aus, Zustände wechseln sofort."
        >
          <Schalter
            beschriftung="Bewegung reduzieren"
            an={reduziert}
            beiWechsel={setzeReduziert}
          />
        </Zeile>
      </Abschnitt>

      <Abschnitt titel="Konto">
        <div className={stil.felder}>
          <Feld beschriftung="Anzeigename" value={benutzer?.anzeigename ?? ""} readOnly />
          <Feld
            beschriftung="Benutzername"
            className={stil.kennung}
            value={benutzer?.name ?? ""}
            readOnly
          />
        </div>

        <p className={stil.nachtrag}>
          Beide ändert, wer die Nutzerverwaltung bedienen darf — auch für das eigene
          Konto.
        </p>

        <Passwortzeile />
      </Abschnitt>

      <Abschnitt titel="Rechte">
        <Rechte rechte={benutzer?.rechte ?? {}} />
      </Abschnitt>

      <Abschnitt titel="System">
        <SystemStatus />
      </Abschnitt>
    </div>
  );
}

function Abschnitt({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <section className={stil.abschnitt}>
      <h2 className={stil.abschnittstitel}>{titel}</h2>
      <Regel kurz className={stil.regel} />
      {children}
    </section>
  );
}

function Zeile({
  wort,
  erklaerung,
  children,
}: {
  wort: string;
  erklaerung: string;
  children: ReactNode;
}) {
  return (
    <div className={stil.zeile}>
      <div className={stil.text}>
        <div className={stil.wort}>{wort}</div>
        <div className={stil.erklaerung}>{erklaerung}</div>
      </div>
      {children}
    </div>
  );
}

/**
 * Das eigene Passwort ändern - aufgeklappt, nicht als eigene Seite.
 *
 * Eine eigene Adresse dafür wäre ein Weg, den man einmal im Jahr geht und
 * der trotzdem dauerhaft in der Navigation stünde. Zugeklappt ist hier eine
 * Zeile mit einem Knopf; aufgeklappt steht das Formular an derselben
 * Stelle, an der man es aufgemacht hat.
 */
function Passwortzeile() {
  const [offen, setOffen] = useState(false);
  const [altes, setAltes] = useState("");
  const [neues, setNeues] = useState("");
  const [wiederholung, setWiederholung] = useState("");
  const [fehler, setFehler] = useState("");
  const [fertig, setFertig] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  const gleich = neues === wiederholung;
  const vollstaendig = altes !== "" && neues !== "" && gleich;

  function schliessen() {
    setOffen(false);
    setAltes("");
    setNeues("");
    setWiederholung("");
    setFehler("");
  }

  async function versuchen() {
    setFehler("");
    setLaeuft(true);
    try {
      await aenderePasswort(altes, neues);
      setFertig(true);
      schliessen();
    } catch (problem) {
      setFehler(problem instanceof Error ? problem.message : "Wechsel fehlgeschlagen");
      setNeues("");
      setWiederholung("");
    } finally {
      setLaeuft(false);
    }
  }

  if (!offen) {
    return (
      <>
        <Zeile
          wort="Passwort"
          erklaerung="Die laufende Sitzung bleibt bestehen, alle anderen Geräte fliegen raus."
        >
          <Knopf
            auspraegung="sekundaer"
            onClick={() => {
              setFertig(false);
              setOffen(true);
            }}
          >
            Ändern
          </Knopf>
        </Zeile>
        {fertig && <Hinweis ton="gut">Das Passwort ist gesetzt.</Hinweis>}
      </>
    );
  }

  return (
    <form
      className={stil.passwortformular}
      onSubmit={(e) => {
        e.preventDefault();
        void versuchen();
      }}
    >
      <Feld
        beschriftung="Bisheriges Passwort"
        name="altes"
        type="password"
        autoComplete="current-password"
        required
        value={altes}
        onChange={(e) => setAltes(e.target.value)}
      />
      <Feld
        beschriftung="Neues Passwort"
        name="neues"
        type="password"
        autoComplete="new-password"
        required
        value={neues}
        hinweis="Mindestens 12 Zeichen. Länge zählt, nicht Sonderzeichen."
        onChange={(e) => setNeues(e.target.value)}
      />
      <Feld
        beschriftung="Neues Passwort wiederholen"
        name="wiederholung"
        type="password"
        autoComplete="new-password"
        required
        value={wiederholung}
        onChange={(e) => setWiederholung(e.target.value)}
      />

      {wiederholung !== "" && !gleich && (
        <Hinweis ton="warnung">Die beiden Passwörter stimmen nicht überein.</Hinweis>
      )}

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <div className={stil.knoepfe}>
        <Knopf type="submit" auspraegung="primaer" disabled={laeuft || !vollstaendig}>
          {laeuft ? "Einen Moment …" : "Passwort setzen"}
        </Knopf>
        <Knopf auspraegung="leise" onClick={schliessen}>
          Abbrechen
        </Knopf>
      </div>
    </form>
  );
}

/**
 * Was dieses Konto darf - je Artefakt eine Rolle.
 *
 * Die Namen kommen aus dem Verzeichnis, das die Hülle ohnehin geladen hat.
 * Steht ein Artefakt nicht darin, bleibt die Kennung stehen: Ein Recht an
 * etwas, das gerade nicht läuft, ist kein Grund, die Zeile zu verschweigen.
 */
function Rechte({ rechte }: { rechte: Record<string, Rolle> }) {
  const zustand = useModule();
  const eintraege = Object.entries(rechte);

  if (eintraege.length === 0) {
    return (
      <p className={stil.nachtrag}>
        Für dieses Konto ist noch kein Artefakt freigeschaltet. Wer die Nutzerverwaltung
        bedienen darf, vergibt die Rechte dort.
      </p>
    );
  }

  const titel = (id: string) =>
    (zustand.phase === "fertig" ? zustand.module.find((m) => m.id === id) : undefined)
      ?.titel ?? id;

  return (
    <ul className={stil.rechte} aria-label="Rechte">
      {eintraege.map(([artefakt, rolle]) => (
        <li key={artefakt}>
          <Etikett ton={rolle === "verwalter" ? "akzent" : "neutral"}>
            {titel(artefakt)} · {ROLLENWORT[rolle]}
          </Etikett>
        </li>
      ))}
    </ul>
  );
}
