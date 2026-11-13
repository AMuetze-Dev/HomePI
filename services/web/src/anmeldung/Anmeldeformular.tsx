import { useState } from "react";

import { Feld, Hinweis, Knopf, Marke, Regel } from "../ui";
import { useAnmeldung } from "./kontext";
import stil from "./Anmeldeformular.module.css";

interface Props {
  titel?: string;
  beschreibung?: string;
}

/**
 * Das Anmeldeformular.
 *
 * Eine Spalte auf dem nackten Grund, keine Karte: Eine Karte setzt einen
 * Rahmen um etwas, das sich von seiner Umgebung abheben soll - hier ist
 * aber nichts drumherum, von dem es sich abheben könnte. Übrig blieb ein
 * Kasten, der auf einer leeren Seite schwebte.
 *
 * Bewusst ohne „Konto anlegen": es gibt keinen Registrierungs-Endpunkt.
 * Konten legt jemand an, der ohnehin Zugriff auf die Maschine hat - ein
 * offenes Anmeldeformular wäre auf einem selbst gehosteten Dienst die erste
 * Tür, die jemand eintritt.
 */
export function Anmeldeformular({
  titel = "Anmelden",
  beschreibung = "Diese Installation zeigt nur, wofür du berechtigt bist.",
}: Props) {
  const { anmelden } = useAnmeldung();
  const [name, setName] = useState("");
  const [passwort, setPasswort] = useState("");
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    void versuchen();
  }

  async function versuchen() {
    setFehler("");
    setLaeuft(true);
    try {
      await anmelden(name.trim(), passwort);
    } catch (problem) {
      setFehler(problem instanceof Error ? problem.message : "Anmeldung fehlgeschlagen");
      // Nur das Passwort leeren. Den Namen stehen zu lassen, spart bei einem
      // Tippfehler im Passwort das erneute Eintippen.
      setPasswort("");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <div className={stil.buehne}>
      <div className={stil.schein} aria-hidden="true" />

      <div className={stil.saeule}>
        <span className={stil.zeichen}>
          <Marke gross />
        </span>

        <h1 className={stil.titel}>{titel}</h1>
        <p className={stil.beschreibung}>{beschreibung}</p>

        <form className={stil.formular} onSubmit={absenden}>
          <Feld
            beschriftung="Benutzername"
            name="benutzername"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Feld
            beschriftung="Passwort"
            name="passwort"
            type="password"
            autoComplete="current-password"
            required
            value={passwort}
            onChange={(e) => setPasswort(e.target.value)}
          />

          {fehler && (
            <Hinweis ton="fehler" dringend>
              {fehler}
            </Hinweis>
          )}

          <Knopf
            type="submit"
            auspraegung="primaer"
            className={stil.knopf}
            disabled={laeuft || name.trim() === "" || passwort === ""}
          >
            {laeuft ? "Einen Moment …" : "Anmelden"}
          </Knopf>
        </form>

        <Regel kurz className={stil.trenner} />

        <p className={stil.fuss}>
          Kein Konto? Es gibt keine Selbstregistrierung. Konten legt der Betreiber dieser
          Installation an.
        </p>
      </div>
    </div>
  );
}
