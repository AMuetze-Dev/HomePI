import { useCallback, useEffect, useRef, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  type Regeldatei,
  aendereRegeldatei,
  entferneRegeldatei,
  ladeRegeldatei,
  ladeRegeldateien,
  speichereRegeldatei,
} from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/** Was das Gateway als Dateinamen annimmt. Dieselbe Prüfung dort, nicht hier. */
const NAME_MUSTER = /^[0-9A-Za-z_]+\.py$/;

/**
 * Der Quelltext der Prüfungen — hochladen, ändern, entfernen.
 *
 * Bisher lagen die dreißig Prüfungen der Spielordnung nur in einem Band am
 * Prüfdienst. Wer eine ändern wollte, brauchte eine Konsole auf dem Pi.
 *
 * **Das ist ausführbarer Code.** Er läuft im Prüfdienst, in dessen Container,
 * mit dessen Rechten. Schreiben darf nur ein Verwalter; das Gateway weist
 * alles andere ab.
 *
 * Getrennt von der Regelübersicht, und das ist Absicht: dort steht, *was*
 * geprüft wird und ob es gemeldet werden soll — hier steht, *wie* geprüft
 * wird. Das eine ist eine Entscheidung, das andere ein Programm.
 */
export function RegeldateienTafel() {
  const [dateien, setDateien] = useState<Regeldatei[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [offen, setOffen] = useState<string | null>(null);

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      setDateien(await ladeRegeldateien(signal));
    } catch (f) {
      if (signal?.aborted) return;
      setFehler(meldung(f));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(controller.signal);
    return () => controller.abort();
  }, [laden]);

  async function handeln(tun: () => Promise<unknown>) {
    setFehler("");
    try {
      await tun();
      await laden();
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  if (fehler && dateien === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  if (dateien === null) {
    return (
      <div role="status" aria-label="Regeldateien werden geladen">
        <Platzhalter breite="100%" hoehe="10rem" />
      </div>
    );
  }

  return (
    <>
      <Karte>
        <h2 className={stil.formularTitel}>Regeldateien</h2>
        <p className={stil.vorgangHinweis}>
          Der Quelltext der Prüfungen. Er wird im Prüfdienst ausgeführt — vor jedem
          Lauf schreibt er sich die Dateien von hier in seinen Ordner. Was hier steht,
          ist die Wahrheit; der Ordner ist die Kopie.
        </p>
        <Hinweis ton="warnung">
          Das ist ausführbarer Code und kein Formular. Eine Datei mit einem Fehler
          darin lässt der Prüfdienst stehen und meldet sie als fehlerhafte Regel — sie
          reißt keinen Lauf um, aber sie prüft auch nichts.
        </Hinweis>
        <Hochladen onFertig={(name, inhalt) => handeln(() => speichereRegeldatei(name, inhalt))} />
      </Karte>

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {dateien.length === 0 ? (
        <Leerzustand titel="Keine eigenen Regeldateien">
          Der Prüfdienst legt beim ersten Lauf seine mitgelieferten Vorlagen an. Was
          hier steht, sind die Dateien, die diese Installation selbst führt — hochgeladen
          oder hier geschrieben.
        </Leerzustand>
      ) : (
        <ul className={stil.liste} aria-label="Regeldateien">
          {dateien.map((d) => (
            <li key={d.id}>
              <DateiKarte
                datei={d}
                offen={offen === d.id}
                onOeffnen={() => setOffen(offen === d.id ? null : d.id)}
                onSpeichern={(inhalt) => handeln(() => aendereRegeldatei(d.id, { inhalt }))}
                onSchalten={() => handeln(() => aendereRegeldatei(d.id, { aktiv: !d.aktiv }))}
                onEntfernen={() => handeln(() => entferneRegeldatei(d.id))}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * Eine Datei vom Rechner holen.
 *
 * Hochladen statt tippen: so kommt eine Regel aus der alten Anwendung ohne
 * Umweg herüber, und niemand muss zweihundert Zeilen in ein Textfeld
 * einfügen.
 */
function Hochladen({
  onFertig,
}: {
  onFertig: (name: string, inhalt: string) => Promise<void>;
}) {
  const feld = useRef<HTMLInputElement>(null);
  const [laeuft, setLaeuft] = useState(false);
  const [abgelehnt, setAbgelehnt] = useState("");

  async function gewaehlt(dateien: FileList | null) {
    const datei = dateien?.[0];
    if (!datei) return;
    setAbgelehnt("");

    if (!NAME_MUSTER.test(datei.name)) {
      // Vor dem Hochladen und nicht erst danach: der Name wird zu einem Pfad
      // im Ordner des Prüfdienstes, und ein Leerzeichen darin wäre eine
      // Datei, die der Lader übersieht.
      setAbgelehnt(
        `„${datei.name}" geht nicht. Erlaubt sind Ziffern, Buchstaben und Unterstrich, ` +
          "dazu die Endung .py — zum Beispiel 90_eigene.py.",
      );
      if (feld.current) feld.current.value = "";
      return;
    }

    setLaeuft(true);
    try {
      await onFertig(datei.name, await datei.text());
    } finally {
      setLaeuft(false);
      if (feld.current) feld.current.value = "";
    }
  }

  return (
    <>
      <label className={stil.textfeldEtikett}>
        Datei hochladen
        <input
          ref={feld}
          type="file"
          accept=".py,text/x-python"
          onChange={(e) => void gewaehlt(e.target.files)}
          disabled={laeuft}
        />
      </label>
      {abgelehnt && <Hinweis ton="warnung">{abgelehnt}</Hinweis>}
    </>
  );
}

function DateiKarte({
  datei,
  offen,
  onOeffnen,
  onSpeichern,
  onSchalten,
  onEntfernen,
}: {
  datei: Regeldatei;
  offen: boolean;
  onOeffnen: () => void;
  onSpeichern: (inhalt: string) => Promise<void>;
  onSchalten: () => Promise<void>;
  onEntfernen: () => Promise<void>;
}) {
  const [inhalt, setInhalt] = useState<string | null>(null);
  const [fragtNach, setFragtNach] = useState(false);

  useEffect(() => {
    if (!offen) return;
    const controller = new AbortController();
    ladeRegeldatei(datei.id, controller.signal)
      .then((d) => setInhalt(d.inhalt))
      .catch(() => {
        // Der Fehler steht schon über der Liste; hier bliebe er zweimal.
      });
    return () => controller.abort();
  }, [offen, datei.id]);

  return (
    <Karte>
      <button type="button" className={stil.kopf} onClick={onOeffnen} aria-expanded={offen}>
        <span className={stil.paarung}>{datei.name}</span>
        <span className={stil.zeile}>
          <Etikett mono>{datei.zeilen} Zeilen</Etikett>
          <Etikett ton={datei.aktiv ? "gut" : "neutral"}>
            {datei.aktiv ? "läuft" : "stillgelegt"}
          </Etikett>
        </span>
      </button>

      {offen && (
        <div className={stil.detail}>
          {inhalt === null ? (
            <Platzhalter breite="100%" hoehe="12rem" />
          ) : (
            <>
              {/* Monospace und Tabulatoren: hier steht Python, und Einrückung
                  ist dort keine Geschmacksfrage. Kein Syntaxhighlighting --
                  das wäre eine Bibliothek für ein Feld, das zweimal im Jahr
                  angefasst wird. */}
              <label className={stil.textfeldEtikett}>
                Quelltext
                <textarea
                  className={stil.quelltext}
                  rows={20}
                  spellCheck={false}
                  value={inhalt}
                  onChange={(e) => setInhalt(e.target.value)}
                />
              </label>

              <div className={stil.knoepfe}>
                <Knopf groesse="sm" onClick={() => void onSpeichern(inhalt)}>
                  Speichern
                </Knopf>
                <Knopf groesse="sm" auspraegung="sekundaer" onClick={() => void onSchalten()}>
                  {datei.aktiv ? "Stilllegen" : "Wieder einschalten"}
                </Knopf>
                {fragtNach ? (
                  <>
                    <Knopf groesse="sm" auspraegung="leise" onClick={() => void onEntfernen()}>
                      Wirklich entfernen
                    </Knopf>
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => setFragtNach(false)}
                    >
                      Abbrechen
                    </Knopf>
                  </>
                ) : (
                  <Knopf groesse="sm" auspraegung="leise" onClick={() => setFragtNach(true)}>
                    Entfernen
                  </Knopf>
                )}
              </div>

              <p className={stil.vorgangHinweis}>
                Gilt ab dem nächsten Prüflauf — der Prüfdienst holt sich die Dateien,
                bevor er anfängt. Befunde aus früheren Läufen bleiben stehen: entfernt
                heißt „wird nicht mehr geprüft" und nicht „ist nie passiert".
              </p>
            </>
          )}
        </div>
      )}
    </Karte>
  );
}
