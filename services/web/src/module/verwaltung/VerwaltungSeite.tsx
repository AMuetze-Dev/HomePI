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
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <Anlegen onAnlegen={(daten) => mitFehlerbehandlung(() => legeKontoAn(daten))} />
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
}: {
  konto: Konto;
  artefakte: Artefakt[];
  ichSelbst: boolean;
  aufAktion: (aktion: () => Promise<unknown>) => Promise<boolean>;
}) {
  const [passwort, setPasswort] = useState("");
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

      {offen && (
        <>
          <Rechte
            konto={konto}
            artefakte={artefakte}
            ichSelbst={ichSelbst}
            aufAktion={aufAktion}
          />

          <div className={stil.passwortzeile}>
            <Feld
              beschriftung={`Neues Passwort für ${konto.name}`}
              type="password"
              autoComplete="new-password"
              value={passwort}
              className={stil.passwortfeld}
              hinweis="Beendet alle Sitzungen dieses Kontos."
              onChange={(e) => setPasswort(e.target.value)}
            />
            <Knopf
              groesse="sm"
              disabled={passwort === ""}
              onClick={() => {
                void aufAktion(() => setzePasswort(konto.id, passwort)).then((ok) => {
                  if (ok) setPasswort("");
                });
              }}
            >
              Setzen
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
  onAnlegen: (daten: {
    name: string;
    passwort: string;
    anzeigename?: string;
  }) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [anzeigename, setAnzeigename] = useState("");
  const [passwort, setPasswort] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const vollstaendig = name.trim() !== "" && passwort !== "";

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (!vollstaendig || laeuft) return;

    setLaeuft(true);
    const geklappt = await onAnlegen({
      name: name.trim(),
      passwort,
      ...(anzeigename.trim() ? { anzeigename: anzeigename.trim() } : {}),
    });
    setLaeuft(false);

    // Nur leeren, wenn es geklappt hat. Sonst tippt man nach einem vergebenen
    // Namen alles neu - der Fehler steht oben, die Eingabe bleibt stehen.
    if (geklappt) {
      setName("");
      setAnzeigename("");
      setPasswort("");
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
            <Feld
              beschriftung="Passwort"
              type="password"
              autoComplete="new-password"
              value={passwort}
              onChange={(e) => setPasswort(e.target.value)}
            />
          </div>

          <p className={stil.leerhinweis}>
            Ein neues Konto hat zunächst keine Rechte. Was es darf, vergibst du danach
            einzeln.
          </p>

          <Knopf type="submit" auspraegung="primaer" disabled={!vollstaendig || laeuft}>
            {laeuft ? "Einen Moment …" : "Anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}
