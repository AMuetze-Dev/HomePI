import { useState } from "react";

import { aenderePasswort, holeIch } from "../api/anmeldung";
import { Feld, Hinweis, Karte, Knopf } from "../ui";
import { useAnmeldung } from "./kontext";
import stil from "./Anmeldeformular.module.css";

/**
 * Der erzwungene erste Passwortwechsel.
 *
 * Ein neues Konto bekommt sein Startpasswort von jemand anderem. Bis es
 * ersetzt ist, weist das Backend dieses Konto an **jedem** Artefakt ab - diese
 * Maske ist die Führung dorthin, nicht die Sicherung.
 *
 * Die laufende Sitzung bleibt bestehen; nach dem Wechsel geht es ohne erneutes
 * Anmelden weiter.
 */
export function Passwortwechsel() {
  const { benutzer, uebernimm, abmelden } = useAnmeldung();
  const [altes, setAltes] = useState("");
  const [neues, setNeues] = useState("");
  const [wiederholung, setWiederholung] = useState("");
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const gleich = neues === wiederholung;
  const vollstaendig = altes !== "" && neues !== "" && gleich;

  function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    void versuchen();
  }

  async function versuchen() {
    setFehler("");
    setLaeuft(true);
    try {
      await aenderePasswort(altes, neues);
      // Nicht raten, sondern nachfragen: das Backend entscheidet, ob der
      // Wechsel damit erledigt ist.
      const aktuell = await holeIch();
      if (aktuell) uebernimm(aktuell);
    } catch (problem) {
      setFehler(problem instanceof Error ? problem.message : "Wechsel fehlgeschlagen");
      setNeues("");
      setWiederholung("");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <Karte className={stil.karte}>
      <form className={stil.formular} onSubmit={absenden}>
        <div className={stil.kopf}>
          <h1 className={stil.titel}>Eigenes Passwort wählen</h1>
          <p className={stil.beschreibung}>
            Dein Konto benutzt noch das Startpasswort, das jemand anders vergeben hat.
            Wähle ein eigenes — danach geht es weiter, ohne dass du dich neu anmelden
            musst.
          </p>
        </div>

        <Feld
          beschriftung="Startpasswort"
          name="altes"
          type="password"
          autoComplete="current-password"
          required
          value={altes}
          hinweis="Das, mit dem du dich gerade angemeldet hast."
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

        <Knopf
          type="submit"
          auspraegung="primaer"
          className={stil.knopf}
          disabled={laeuft || !vollstaendig}
        >
          {laeuft ? "Einen Moment …" : "Passwort setzen"}
        </Knopf>

        <p className={stil.fuss}>
          Angemeldet als <strong>{benutzer?.name}</strong>. Falsches Konto?{" "}
          <button type="button" className={stil.abmelden} onClick={() => void abmelden()}>
            Abmelden
          </button>
        </p>
      </form>
    </Karte>
  );
}
