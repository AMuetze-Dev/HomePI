import { useState } from "react";

import { einrichten } from "../api/einrichtung";
import { useAnmeldung } from "../anmeldung/kontext";
import { Feld, Hinweis, Karte, Knopf } from "../ui";
import stil from "./Einrichtungsmaske.module.css";

interface Props {
  /** Wird gerufen, wenn der erste Verwalter steht. */
  onFertig: () => void;
}

/**
 * Das erste Konto dieser Installation.
 *
 * Verlangt neben Name und Passwort das **Einrichtungstoken**. Das steht im Log
 * des Gateways, gleich nach dem Start - lesen kann es also nur, wer ohnehin
 * Zugriff auf die Maschine hat. Ohne diese Bedingung würde derjenige die
 * Installation übernehmen, der als Erster an die frische Adresse kommt.
 *
 * Geprüft wird beides im Backend, bei jedem Aufruf. Dass diese Maske
 * erscheint, ist nur die Einladung - nicht die Erlaubnis.
 */
export function Einrichtungsmaske({ onFertig }: Props) {
  const { uebernimm } = useAnmeldung();
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [anzeigename, setAnzeigename] = useState("");
  const [passwort, setPasswort] = useState("");
  const [wiederholung, setWiederholung] = useState("");
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const passwoerterGleich = passwort === wiederholung;
  const vollstaendig =
    token.trim() !== "" && name.trim() !== "" && passwort !== "" && passwoerterGleich;

  function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    void versuchen();
  }

  async function versuchen() {
    setFehler("");
    setLaeuft(true);
    try {
      const benutzer = await einrichten({
        token: token.trim(),
        name: name.trim(),
        passwort,
        ...(anzeigename.trim() ? { anzeigename: anzeigename.trim() } : {}),
      });
      uebernimm(benutzer);
      onFertig();
    } catch (problem) {
      setFehler(
        problem instanceof Error ? problem.message : "Einrichtung fehlgeschlagen",
      );
      // Nur die Passwörter leeren. Token und Name stehen zu lassen spart nach
      // einem Tippfehler das erneute Abtippen eines 43-Zeichen-Tokens.
      setPasswort("");
      setWiederholung("");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <Karte className={stil.karte}>
      <form className={stil.formular} onSubmit={absenden}>
        <div className={stil.kopf}>
          <h1 className={stil.titel}>Ersteinrichtung</h1>
          <p className={stil.beschreibung}>
            Diese Installation hat noch kein Konto. Lege das erste an — es darf
            anschließend Benutzer und Rechte verwalten.
          </p>
        </div>

        <Feld
          beschriftung="Einrichtungstoken"
          name="token"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={token}
          hinweis="Steht im Log des Gateways, gleich nach dem Start: docker compose logs gateway"
          onChange={(e) => setToken(e.target.value)}
        />

        <Feld
          beschriftung="Benutzername"
          name="benutzername"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={name}
          hinweis="Klein, 3 bis 32 Zeichen. Damit meldest du dich künftig an."
          onChange={(e) => setName(e.target.value)}
        />

        <Feld
          beschriftung="Anzeigename"
          name="anzeigename"
          autoComplete="name"
          value={anzeigename}
          hinweis="Optional. Steht später oben rechts."
          onChange={(e) => setAnzeigename(e.target.value)}
        />

        <Feld
          beschriftung="Passwort"
          name="passwort"
          type="password"
          autoComplete="new-password"
          required
          value={passwort}
          hinweis="Mindestens 12 Zeichen. Länge zählt, nicht Sonderzeichen."
          onChange={(e) => setPasswort(e.target.value)}
        />

        <Feld
          beschriftung="Passwort wiederholen"
          name="wiederholung"
          type="password"
          autoComplete="new-password"
          required
          value={wiederholung}
          onChange={(e) => setWiederholung(e.target.value)}
        />

        {wiederholung !== "" && !passwoerterGleich && (
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
          {laeuft ? "Einen Moment …" : "Einrichten"}
        </Knopf>

        <p className={stil.fuss}>
          Lieber über die Kommandozeile?{" "}
          <code>
            homepi benutzer anlegen &lt;name&gt; --artefakt verwaltung --rolle verwalter
          </code>{" "}
          tut dasselbe. Danach schließt sich diese Maske von selbst.
        </p>
      </form>
    </Karte>
  );
}
