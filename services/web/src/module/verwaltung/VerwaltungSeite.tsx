import { useCallback, useEffect, useState } from "react";

import { useAnmeldung } from "../../anmeldung/kontext";
import {
  Abschnitt,
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Reihe,
  Tabelle,
  Tafel,
  Zelle,
} from "../../ui";
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
import { meldung } from "../../api/client";

type Daten = { konten: Konto[]; artefakte: Artefakt[] };

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

const ROLLEN: Rolle[] = ["leser", "nutzer", "verwalter"];

//: "kein Recht" ist ein eigener Wert im Auswahlfeld, nicht die leere Auswahl -
//: sonst sähe es aus, als wäre nur noch nichts gewählt worden.
const OHNE = "-";

export function VerwaltungSeite() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  // Getrennt vom Ladezustand: ein misslungener Klick darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState("");
  // Welche Zeile aufgeklappt ist - und ob das Anlegeformular dasteht. Beides
  // war vorher dauernd sichtbar: drei Knoepfe je Konto und ein Formular
  // darunter, auch wenn man nur nachsehen wollte, wer was darf.
  const [offenesKonto, setOffenesKonto] = useState<string | null>(null);
  const [anlegen, setAnlegen] = useState(false);
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
      <Tafel titel="Verwaltung">
        <div className={stil.laden} role="status" aria-label="Konten werden geladen">
          <Platzhalter breite="100%" hoehe="4rem" />
          <Platzhalter breite="100%" hoehe="14rem" />
        </div>
      </Tafel>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <Tafel titel="Verwaltung">
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { konten, artefakte } = zustand.daten;
  const verwalter = konten.filter((k) => k.verwalter).length;
  const gesperrt = konten.filter((k) => !k.aktiv).length;

  return (
    <Tafel
      titel="Verwaltung"
      beiwort={[
        `${konten.length} ${konten.length === 1 ? "Konto" : "Konten"}`,
        `${verwalter} ${verwalter === 1 ? "Verwalter" : "Verwalter"}`,
        ...(gesperrt > 0 ? [`${gesperrt} gesperrt`] : []),
      ].join(" · ")}
      aktionen={
        konten.length > 0 && (
          <Knopf groesse="sm" auspraegung="primaer" onClick={() => setAnlegen(true)}>
            Konto anlegen
          </Knopf>
        )
      }
    >
      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {start && (
        <Startpasswort name={start.name} wert={start.wert} onWeg={() => setStart(null)} />
      )}

      {konten.length === 0 ? (
        <Leerzustand titel="Noch kein Konto">
          Lege das erste an — ohne Konto kommt niemand an ein Artefakt.
          <p className={stil.leerknopf}>
            <Knopf auspraegung="primaer" onClick={() => setAnlegen(true)}>
              Konto anlegen
            </Knopf>
          </p>
        </Leerzustand>
      ) : (
        <Tabelle
          beschriftung="Konten"
          raster="1.6fr 1.1fr 1fr"
          spalten={["Konto", "Zustand", "Rechte"]}
        >
          {konten.map((konto) => (
            <Kontoreihe
              key={konto.id}
              konto={konto}
              artefakte={artefakte}
              ichSelbst={konto.id === benutzer?.id}
              offen={offenesKonto === konto.id}
              onKlick={() => setOffenesKonto(offenesKonto === konto.id ? null : konto.id)}
              aufAktion={mitFehlerbehandlung}
              aufStartpasswort={setStart}
            />
          ))}
        </Tabelle>
      )}

      {anlegen && (
        <Anlegen
          onAbbrechen={() => setAnlegen(false)}
          onAnlegen={async (daten) =>
            mitFehlerbehandlung(async () => {
              const neu = await legeKontoAn(daten);
              setStart({ name: neu.name, wert: neu.startpasswort });
              setAnlegen(false);
            })
          }
        />
      )}
    </Tafel>
  );
}

function Kontoreihe({
  konto,
  artefakte,
  ichSelbst,
  offen,
  onKlick,
  aufAktion,
  aufStartpasswort,
}: {
  konto: Konto;
  artefakte: Artefakt[];
  ichSelbst: boolean;
  offen: boolean;
  onKlick: () => void;
  aufAktion: (aktion: () => Promise<unknown>) => Promise<boolean>;
  aufStartpasswort: (start: { name: string; wert: string }) => void;
}) {
  const anzahl = Object.keys(konto.rechte).length;

  return (
    <Reihe
      leise={!konto.aktiv}
      onKlick={onKlick}
      offen={offen}
      ausklappung={
        <div className={stil.ausklappung}>
          {ichSelbst && (
            <p className={stil.selbsthinweis}>
              Am eigenen Konto sind Sperren und Löschen abgeschaltet — ein Fehlgriff ließe
              sich nicht zurücknehmen.
            </p>
          )}

          {konto.passwort_wechseln && !ichSelbst && (
            <p className={stil.selbsthinweis}>
              Benutzt noch das vergebene Startpasswort. Bis es ersetzt ist, kommt dieses
              Konto an kein Artefakt.
            </p>
          )}

          <Abschnitt titel="Rechte" id={`rechte-${konto.id}`}>
            <Rechte
              konto={konto}
              artefakte={artefakte}
              ichSelbst={ichSelbst}
              aufAktion={aufAktion}
            />
          </Abschnitt>

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
              onClick={() => void aufAktion(() => loescheKonto(konto.id))}
              disabled={ichSelbst}
              aria-label={`${konto.name} löschen`}
            >
              Löschen
            </Knopf>
          </div>
        </div>
      }
    >
      <Zelle>
        {konto.anzeigename}
        <span className={stil.benutzername}>{konto.name}</span>
      </Zelle>
      <Zelle>
        <span className={stil.etiketten}>
          {ichSelbst && <Etikett>Du</Etikett>}
          {konto.verwalter && <Etikett ton="gut">Verwalter</Etikett>}
          {konto.passwort_wechseln && <Etikett ton="warnung">Startpasswort</Etikett>}
          {!konto.aktiv && <Etikett ton="warnung">Gesperrt</Etikett>}
        </span>
      </Zelle>
      <Zelle leise>
        {anzahl === 0
          ? "kein Recht"
          : `${anzahl} ${anzahl === 1 ? "Artefakt" : "Artefakte"}`}
      </Zelle>
    </Reihe>
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
  onAbbrechen,
}: {
  onAnlegen: (daten: { name: string; anzeigename?: string }) => Promise<boolean>;
  onAbbrechen: () => void;
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
    <Abschnitt titel="Konto anlegen" id="anlegen" regel>
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

          <div className={stil.formularfuss}>
            <Knopf type="button" auspraegung="leise" onClick={onAbbrechen}>
              Abbrechen
            </Knopf>
            <Knopf type="submit" auspraegung="primaer" disabled={!vollstaendig || laeuft}>
              {laeuft ? "Einen Moment …" : "Anlegen"}
            </Knopf>
          </div>
        </form>
      </Karte>
    </Abschnitt>
  );
}
