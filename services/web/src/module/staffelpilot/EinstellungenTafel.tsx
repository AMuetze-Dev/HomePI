import { useEffect, useState } from "react";

import { Feld, Hinweis, Karte, Knopf, Platzhalter } from "../../ui";
import { type Einstellungen, ladeEinstellungen, speichereEinstellungen } from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/**
 * Was in jedem Schreiben steht und wie lange eine Frist läuft.
 *
 * Eine Seite mit fünf Feldern, einem Schalter und einem Knopf: sie wird
 * einmal im Jahr angefasst. Alles, was sie aufwendiger macht, zahlt sich nie
 * zurück.
 */
export function EinstellungenTafel() {
  const [werte, setWerte] = useState<Einstellungen | null>(null);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    ladeEinstellungen(controller.signal)
      .then(setWerte)
      .catch((f: unknown) => {
        if (!controller.signal.aborted) setFehler(meldung(f));
      });
    return () => controller.abort();
  }, []);

  if (fehler && werte === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  if (werte === null) {
    return (
      <div role="status" aria-label="Einstellungen werden geladen">
        <Platzhalter breite="100%" hoehe="14rem" />
      </div>
    );
  }

  function aendern<K extends keyof Einstellungen>(feld: K, wert: Einstellungen[K]) {
    setWerte((alt) => (alt === null ? alt : { ...alt, [feld]: wert }));
    setGespeichert(false);
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (werte === null) return;
    setLaeuft(true);
    setFehler("");
    try {
      // Die Antwort und nicht die Eingabe übernehmen: das Backend trimmt und
      // setzt Vorgaben ein, und was dort steht, ist der Stand.
      setWerte(await speichereEinstellungen(werte));
      setGespeichert(true);
    } catch (f) {
      setFehler(meldung(f));
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <Karte>
      <form className={stil.formular} onSubmit={(e) => void absenden(e)}>
        <h2 className={stil.formularTitel}>Einstellungen</h2>

        <Feld
          beschriftung="Staffelleiter"
          hinweis="Steht unter jedem Schreiben."
          value={werte.staffelleiter}
          onChange={(e) => aendern("staffelleiter", e.target.value)}
        />
        <Feld
          beschriftung="Verband"
          hinweis="Zeile unter der Unterschrift. Darf leer bleiben."
          value={werte.verband}
          onChange={(e) => aendern("verband", e.target.value)}
        />
        <Feld
          beschriftung="Absenderadresse"
          hinweis="Vorschlag für den Empfänger eines neuen Entwurfs."
          value={werte.absender}
          onChange={(e) => aendern("absender", e.target.value)}
        />
        <Feld
          beschriftung="Prüfzeitraum (Tage)"
          hinweis="Wie weit zurück ein Spiel noch geprüft wird."
          type="number"
          min={1}
          max={365}
          value={String(werte.pruefzeitraum_tage)}
          onChange={(e) => aendern("pruefzeitraum_tage", Number(e.target.value))}
        />
        <Feld
          beschriftung="Frist (Tage)"
          hinweis="Wie lange ein Verein Zeit bekommt zu antworten."
          type="number"
          min={1}
          max={90}
          value={String(werte.frist_tage)}
          onChange={(e) => aendern("frist_tage", Number(e.target.value))}
        />

        <label className={stil.schalter}>
          <input
            type="checkbox"
            className={stil.schalterKasten}
            checked={werte.browser_sichtbar}
            onChange={(e) => aendern("browser_sichtbar", e.target.checked)}
          />
          <span className={stil.schalterText}>
            <span>Beim Prüfen zusehen</span>
            <span className={stil.wahlName}>
              Der Prüfdienst zeigt sein Browserfenster, statt im Verborgenen zu arbeiten.
              Zum Zusehen schön, beim Arbeiten im Weg — das Fenster nimmt den Vordergrund.
              Läuft der Dienst im Container, wo es keinen Bildschirm gibt, prüft er weiter
              unsichtbar und schreibt das ins Protokoll.
            </span>
          </span>
        </label>

        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}
        {gespeichert && !fehler && <Hinweis ton="neutral">Gespeichert.</Hinweis>}

        <Knopf type="submit" disabled={laeuft}>
          {laeuft ? "Speichert …" : "Speichern"}
        </Knopf>
      </form>
    </Karte>
  );
}
