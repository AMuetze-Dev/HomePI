import { useEffect, useState } from "react";

import { Feld, Hinweis, Karte, Knopf, Platzhalter } from "../../ui";
import { type ZugangStand, ladeZugang, loescheZugang, speichereZugang } from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/**
 * Die Anmeldedaten, mit denen der Prüfdienst nach DFBnet geht.
 *
 * Das Passwort wird verschlüsselt abgelegt und kommt **nie** zurück — auch
 * nicht in dieses Formular. Wer es ändern will, tippt es neu; wer nur den
 * Benutzernamen sehen will, liest ihn oben.
 *
 * Fehlt der Schlüssel in der Umgebung, sagt die Karte das, bevor jemand
 * tippt. Gespeichert würde dann nämlich nichts.
 */
export function ZugangKarte() {
  const [stand, setStand] = useState<ZugangStand | null>(null);
  const [benutzer, setBenutzer] = useState("");
  const [passwort, setPasswort] = useState("");
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    ladeZugang(controller.signal)
      .then((s) => {
        setStand(s);
        setBenutzer(s.benutzer);
      })
      .catch((f: unknown) => {
        if (!controller.signal.aborted) setFehler(meldung(f));
      });
    return () => controller.abort();
  }, []);

  async function auffrischen() {
    const frisch = await ladeZugang();
    setStand(frisch);
    // Den Benutzernamen **nicht** aus der Antwort übernehmen: im Feld steht,
    // was der Staffelleiter gerade tippt. Nur nach dem Löschen wird es
    // ausdrücklich geleert.
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    setFehler("");
    setGespeichert(false);
    try {
      await speichereZugang(benutzer, passwort);
      // Das Passwortfeld leeren: was dort stünde, wäre ab jetzt eine Kopie
      // von etwas, das nirgends mehr im Klartext liegt.
      setPasswort("");
      setGespeichert(true);
      await auffrischen();
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  async function entfernen() {
    setFehler("");
    setGespeichert(false);
    try {
      await loescheZugang();
      setBenutzer("");
      setPasswort("");
      await auffrischen();
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  if (stand === null && !fehler) {
    // Erst laden, dann tippen lassen. Vorher stand das Formular schon da, und
    // die Antwort des Servers setzte den Benutzernamen auf den gespeicherten
    // Wert zurück — bei einer frischen Installation also auf leer. Wer schnell
    // war, tippte seinen Namen ins Nichts und fand danach einen Knopf, der
    // sich nicht drücken ließ.
    return (
      <div role="status" aria-label="DFBnet-Zugang wird geladen">
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  return (
    <Karte>
      <form className={stil.formular} onSubmit={(e) => void absenden(e)}>
        <h2 className={stil.formularTitel}>DFBnet-Zugang</h2>

        <p className={stil.vorgangHinweis}>
          Damit meldet sich der Prüfdienst an. Das Passwort wird verschlüsselt abgelegt
          und kommt nie wieder heraus — auch nicht in dieses Formular.
        </p>

        {stand !== null && !stand.schluessel_vorhanden && (
          <Hinweis ton="warnung" dringend>
            Es ist kein Schlüssel hinterlegt (<code>STAFFELPILOT_SCHLUESSEL</code>). Ohne
            ihn wird hier nichts gespeichert — lieber gar nicht als im Klartext.
          </Hinweis>
        )}

        {stand?.gespeichert && (
          <Hinweis ton="neutral">
            Hinterlegt für <strong>{stand.benutzer}</strong>.
          </Hinweis>
        )}

        <Feld
          beschriftung="DFBnet-Benutzername"
          value={benutzer}
          autoComplete="off"
          onChange={(e) => {
            setBenutzer(e.target.value);
            setGespeichert(false);
          }}
        />
        <Feld
          beschriftung="DFBnet-Passwort"
          type="password"
          value={passwort}
          autoComplete="new-password"
          hinweis={
            stand?.gespeichert ? "Leer lassen ändert nichts am Passwort." : undefined
          }
          onChange={(e) => {
            setPasswort(e.target.value);
            setGespeichert(false);
          }}
        />

        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}
        {gespeichert && !fehler && <Hinweis ton="neutral">Zugang hinterlegt.</Hinweis>}

        <div className={stil.knoepfe}>
          <Knopf
            type="submit"
            disabled={!benutzer || !passwort || stand?.schluessel_vorhanden === false}
          >
            Zugang hinterlegen
          </Knopf>
          {stand?.gespeichert && (
            <Knopf auspraegung="leise" onClick={() => void entfernen()}>
              Entfernen
            </Knopf>
          )}
        </div>
      </form>
    </Karte>
  );
}
