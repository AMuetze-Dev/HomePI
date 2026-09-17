import { useCallback, useEffect, useState } from "react";

import { useAnmeldung } from "../../anmeldung/kontext";
import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  entzieheRecht,
  ladeArtefakte,
  ladeKonten,
  legeKontoAn,
  loescheKonto,
  setzeAktiv,
  setzePasswort,
  setzeRecht,
  type Artefakt,
  type Konto,
  type Rolle,
} from "./api";
import { Startpasswort } from "./Startpasswort";
import stil from "./VerwaltungSeite.module.css";

type Daten = { konten: Konto[]; artefakte: Artefakt[] };

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

const ROLLEN: Rolle[] = ["leser", "nutzer", "verwalter"];

//: "kein Recht" ist ein eigener Wert im Auswahlfeld, nicht die leere Auswahl -
//: sonst sähe es aus, als wäre nur noch nichts gewählt worden.
const OHNE = "-";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

export function VerwaltungSeite() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  // Getrennt vom Ladezustand: ein misslungener Klick darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState("");
  // Ein Startpasswort ist genau einmal abrufbar. Es steht deshalb hier oben
  // und nicht in der Zeile, die beim naechsten Laden verschwindet.
  const [start, setStart] = useState<{ name: string; wert: string } | null>(null);
  const { benutzer } = useAnmeldung();

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      const [konten, artefakte] = await Promise.all([
        ladeKonten(signal),
        ladeArtefakte(signal),
      ]);
      setZustand({ phase: "fertig", daten: { konten, artefakte } });
    } catch (fehler) {
      if (signal?.aborted) return;
      setZustand({ phase: "fehler", nachricht: meldung(fehler) });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(controller.signal);
    return () => controller.abort();
  }, [laden]);

  /** true, wenn es geklappt hat - der Aufrufer entscheidet danach, ob er sein
   *  Formular leeren darf. */
  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden();
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Konten werden geladen">
        <Platzhalter breite="100%" hoehe="4rem" />
        <Platzhalter breite="100%" hoehe="14rem" />
      </div>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <Hinweis ton="fehler" dringend>
        {zustand.nachricht}
      </Hinweis>
    );
  }

  const { konten, artefakte } = zustand.daten;

  return (
    <>
      <Uebersicht konten={konten} />

      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {start && (
        <Startpasswort name={start.name} wert={start.wert} onWeg={() => setStart(null)} />
      )}

      <section aria-labelledby="konten">
        <h2 id="konten" className={stil.abschnittstitel}>
          Konten
        </h2>

        {konten.length === 0 ? (
          <Leerzustand titel="Noch kein Konto">Lege unten das erste an.</Leerzustand>
        ) : (
          <ul className={stil.liste} aria-label="Konten">
            {konten.map((konto) => (
              <li key={konto.id}>
                <Kontokarte
                  konto={konto}
                  artefakte={artefakte}
                  ichSelbst={konto.id === benutzer?.id}
                  aufAktion={mitFehlerbehandlung}
                  aufStartpasswort={setStart}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <Anlegen
        onAnlegen={async (daten) =>
          mitFehlerbehandlung(async () => {
            const neu = await legeKontoAn(daten);
            setStart({ name: neu.name, wert: neu.startpasswort });
          })
        }
      />
    </>
  );
}

function Uebersicht({ konten }: { konten: Konto[] }) {
  const verwalter = konten.filter((k) => k.verwalter).length;
  const gesperrt = konten.filter((k) => !k.aktiv).length;

  return (
    <ul className={stil.kennzahlen} aria-label="Überblick">
      <Kennzahl wert={konten.length} name="Konten" />
      <Kennzahl wert={verwalter} name="Verwalter" />
      <Kennzahl wert={gesperrt} name="gesperrt" ton="warnung" />
    </ul>
  );
}

function Kennzahl({
  wert,
  name,
  ton = "neutral",
}: {
  wert: number;
  name: string;
  ton?: "neutral" | "warnung";
}) {
  // Eine Null wird nicht eingefärbt: sie ist keine Meldung, sondern die
  // Abwesenheit einer.
  const eingefaerbt = ton !== "neutral" && wert > 0;

  return (
    <li className={stil.kennzahleintrag} aria-label={`${wert} ${name}`}>
      <Karte className={stil.kennzahl}>
        <span
          className={`${stil.wert} ${eingefaerbt ? stil[ton] : ""}`}
          aria-hidden="true"
        >
          {wert}
        </span>
        <span className={stil.kennzahlname} aria-hidden="true">
          {name}
        </span>
      </Karte>
    </li>
  );
}

function Kontokarte({
  konto,
  artefakte,
  ichSelbst,
  aufAktion,
  aufStartpasswort,
}: {
  konto: Konto;
  artefakte: Artefakt[];
  ichSelbst: boolean;
  aufAktion: (aktion: () => Promise<unknown>) => Promise<boolean>;
  aufStartpasswort: (start: { name: string; wert: string }) => void;
}) {
  const [offen, setOffen] = useState(false);

  return (
    <Karte className={stil.konto}>
      <div className={stil.kopfzeile}>
        <div className={stil.namen}>
          <span className={stil.anzeigename}>{konto.anzeigename}</span>
          <span className={stil.benutzername}>{konto.name}</span>
        </div>

        <div className={stil.etiketten}>
          {ichSelbst && <Etikett>Du</Etikett>}
          {konto.verwalter && <Etikett ton="gut">Verwalter</Etikett>}
          {konto.passwort_wechseln && <Etikett ton="warnung">Startpasswort</Etikett>}
          {!konto.aktiv && <Etikett ton="warnung">Gesperrt</Etikett>}
        </div>
      </div>

      <div className={stil.aktionen}>
        <Knopf
          groesse="sm"
          onClick={() => void aufAktion(() => setzeAktiv(konto.id, !konto.aktiv))}
          disabled={ichSelbst}
          aria-label={`${konto.name} ${konto.aktiv ? "sperren" : "entsperren"}`}
        >
          {konto.aktiv ? "Sperren" : "Entsperren"}
        </Knopf>

        <Knopf
          groesse="sm"
          auspraegung="leise"
          onClick={() => setOffen((o) => !o)}
          aria-expanded={offen}
          aria-label={`Rechte von ${konto.name} ${offen ? "schließen" : "bearbeiten"}`}
        >
          Rechte
        </Knopf>

        <Knopf
          groesse="sm"
          auspraegung="leise"
          onClick={() => void aufAktion(() => loescheKonto(konto.id))}
          disabled={ichSelbst}
          aria-label={`${konto.name} löschen`}
        >
          Löschen
        </Knopf>
      </div>

      {ichSelbst && (
        <p className={stil.selbsthinweis}>
          Am eigenen Konto sind Sperren und Löschen abgeschaltet — ein Fehlgriff ließe
          sich nicht zurücknehmen.
        </p>
      )}

      {konto.passwort_wechseln && !ichSelbst && (
        <p className={stil.selbsthinweis}>
          Benutzt noch das vergebene Startpasswort. Bis es ersetzt ist, kommt dieses Konto
          an kein Artefakt.
        </p>
      )}

      {offen && (
        <>
          <Rechte
            konto={konto}
            artefakte={artefakte}
            ichSelbst={ichSelbst}
            aufAktion={aufAktion}
          />

          <div className={stil.passwortzeile}>
            <div className={stil.passworttext}>
              <span className={stil.passworttitel}>Passwort zurücksetzen</span>
              <p className={stil.leerhinweis}>
                Der Dienst erzeugt ein Startpasswort und zeigt es dir einmal. Du gibst es
                weiter, {konto.anzeigename} ersetzt es beim nächsten Anmelden. Ein eigenes
                vorzugeben ist nicht vorgesehen — was du tippst, kennst du auch. Alle
                Sitzungen dieses Kontos enden dabei.
              </p>
            </div>
            <Knopf
              groesse="sm"
              onClick={() =>
                void aufAktion(async () => {
                  const antwort = await setzePasswort(konto.id);
                  aufStartpasswort({ name: konto.name, wert: antwort.startpasswort });
                })
              }
              aria-label={`Passwort von ${konto.name} zurücksetzen`}
            >
              Startpasswort erzeugen
            </Knopf>
          </div>
        </>
      )}
    </Karte>
  );
}

function Rechte({
  konto,
  artefakte,
  ichSelbst,
  aufAktion,
}: {
  konto: Konto;
  artefakte: Artefakt[];
  ichSelbst: boolean;
  aufAktion: (aktion: () => Promise<unknown>) => Promise<boolean>;
}) {
  if (artefakte.length === 0) {
    return (
      <p className={stil.leerhinweis}>Dieses Gateway hat keine Artefakte geladen.</p>
    );
  }

  return (
    <ul className={stil.rechte} aria-label={`Rechte von ${konto.name}`}>
      {artefakte.map((artefakt) => {
        const aktuell = konto.rechte[artefakt.id] ?? OHNE;
        // Sich selbst die Verwaltung zu nehmen lehnt auch das Backend ab -
        // hier steht es nur nicht erst als anklickbare Falle da.
        const gesperrt = ichSelbst && artefakt.id === "verwaltung";
        const feldId = `recht-${konto.id}-${artefakt.id}`;

        return (
          <li key={artefakt.id} className={stil.rechtzeile}>
            <label className={stil.artefaktname} htmlFor={feldId}>
              {artefakt.titel}
              {artefakt.zugang === "oeffentlich" && (
                <span className={stil.offen}> — öffentlich, braucht kein Recht</span>
              )}
            </label>

            <select
              id={feldId}
              className={stil.auswahl}
              value={aktuell}
              disabled={gesperrt}
              onChange={(e) => {
                const gewaehlt = e.target.value;
                void aufAktion(() =>
                  gewaehlt === OHNE
                    ? entzieheRecht(konto.id, artefakt.id)
                    : setzeRecht(konto.id, artefakt.id, gewaehlt as Rolle),
                );
              }}
            >
              <option value={OHNE}>kein Recht</option>
              {ROLLEN.map((rolle) => (
                <option key={rolle} value={rolle}>
                  {rolle}
                </option>
              ))}
            </select>
          </li>
        );
      })}
    </ul>
  );
}

function Anlegen({
  onAnlegen,
}: {
  onAnlegen: (daten: { name: string; anzeigename?: string }) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [anzeigename, setAnzeigename] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  // Der Name genuegt. Das Startpasswort erzeugt der Dienst - ein Passwort,
  // das ein Verwalter tippt, kennt jemand anders.
  const vollstaendig = name.trim() !== "";

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (!vollstaendig || laeuft) return;

    setLaeuft(true);
    const geklappt = await onAnlegen({
      name: name.trim(),
      ...(anzeigename.trim() ? { anzeigename: anzeigename.trim() } : {}),
    });
    setLaeuft(false);

    // Nur leeren, wenn es geklappt hat. Sonst tippt man nach einem vergebenen
    // Namen alles neu - der Fehler steht oben, die Eingabe bleibt stehen.
    if (geklappt) {
      setName("");
      setAnzeigename("");
    }
  }

  return (
    <section aria-labelledby="anlegen">
      <h2 id="anlegen" className={stil.abschnittstitel}>
        Konto anlegen
      </h2>

      <Karte>
        <form className={stil.formular} onSubmit={(e) => void absenden(e)}>
          <div className={stil.felder}>
            <Feld
              beschriftung="Benutzername"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Feld
              beschriftung="Anzeigename"
              autoComplete="off"
              value={anzeigename}
              onChange={(e) => setAnzeigename(e.target.value)}
            />
          </div>

          <p className={stil.leerhinweis}>
            Der Name genügt. Das Startpasswort erzeugt der Dienst; du gibst es weiter, und
            der Benutzer ersetzt es beim ersten Anmelden. Rechte hat ein neues Konto
            zunächst keine — was es darf, vergibst du danach einzeln.
          </p>

          <Knopf type="submit" auspraegung="primaer" disabled={!vollstaendig || laeuft}>
            {laeuft ? "Einen Moment …" : "Anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}
