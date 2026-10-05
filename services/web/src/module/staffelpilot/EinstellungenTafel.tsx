import { useEffect, useState } from "react";

import { Feld, Hinweis, Karte, Knopf, Platzhalter } from "../../ui";
import {
  type Beispieldatenstand,
  type Einstellungen,
  entferneBeispieldaten,
  ladeBeispieldaten,
  ladeEinstellungen,
  speichereEinstellungen,
} from "./api";
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

        <Beispieldaten
          an={werte.beispieldaten}
          onSchalten={(an) => aendern("beispieldaten", an)}
        />

        <label className={stil.textfeldEtikett}>
          Folgesatz unter jeder Mahnung
          <textarea
            className={stil.satzfeld}
            rows={3}
            value={werte.folgesatz}
            placeholder={werte.vorgabe_folgesatz}
            onChange={(e) => aendern("folgesatz", e.target.value)}
          />
        </label>
        <p className={stil.vorgangHinweis}>
          Er macht aus der Mahnung eine Mahnung — ein späterer Antrag ans Sportgericht
          beruft sich auf ihn. Leer lassen heißt: der mitgelieferte Satz gilt, und eine
          spätere Korrektur daran kommt an.
        </p>

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

/**
 * Der Schalter für erfundene Spiele — und der Besen dahinter.
 *
 * Der Anlass war echt: drei Spiele der Attrappe standen zwischen
 * einunddreißig Spielen aus DFBnet, weil der Prüfdienst mit der Attrappe als
 * Leser lief. Aus einer solchen Liste entstehen Mahnungen.
 *
 * Darum stehen hier zwei Dinge zusammen: der Schalter, der sie künftig
 * abweist, und die Zahl derer, die schon drin sind. Die Zahl zeigt sich **nur
 * wenn es welche gibt** — eine dauerhafte Null wäre eine Zeile, die jeden Tag
 * mitliest und nie etwas sagt.
 */
function Beispieldaten({
  an,
  onSchalten,
}: {
  an: boolean;
  onSchalten: (an: boolean) => void;
}) {
  const [stand, setStand] = useState<Beispieldatenstand | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    ladeBeispieldaten(controller.signal)
      .then(setStand)
      .catch(() => {
        // Eine Zugabe. Ohne sie bleibt der Schalter, und der ist die
        // Hauptsache.
      });
    return () => controller.abort();
  }, []);

  async function aufraeumen() {
    setLaeuft(true);
    setFehler("");
    try {
      await entferneBeispieldaten();
      setStand({ anzahl: 0, entfernt: 0 });
    } catch (f) {
      setFehler(f instanceof Error ? f.message : "Unbekannter Fehler");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <>
      <label className={stil.schalter}>
        <input
          type="checkbox"
          className={stil.schalterKasten}
          checked={an}
          onChange={(e) => onSchalten(e.target.checked)}
        />
        <span className={stil.schalterText}>
          <span>Beispieldaten annehmen</span>
          <span className={stil.wahlName}>
            Der Prüfdienst kann zu jeder Staffel Spiele erfinden, statt DFBnet zu
            lesen — zum Durchklicken. Ausgeschaltet weist das Programm einen
            solchen Lauf ganz ab, statt die erfundenen Spiele zwischen die echten
            zu lassen. Aus dieser Liste entstehen Mahnungen.
          </span>
        </span>
      </label>

      {stand !== null && stand.anzahl > 0 && (
        <Hinweis ton="warnung">
          In den Listen stehen {stand.anzahl} erfundene{" "}
          {stand.anzahl === 1 ? "Spiel" : "Spiele"}. Echte Spiele bleiben beim
          Entfernen stehen.
          <div className={stil.knoepfe}>
            <Knopf groesse="sm" onClick={() => void aufraeumen()} disabled={laeuft}>
              {laeuft ? "Entfernt …" : "Beispieldaten entfernen"}
            </Knopf>
          </div>
        </Hinweis>
      )}

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}
    </>
  );
}
