import { type FormEvent, useEffect, useState } from "react";

import {
  Abschnitt,
  Etikett,
  Feld,
  Hinweis,
  Knopf,
  Leerzustand,
  Platzhalter,
  Regel as Linie,
  Schalter,
  Segmentwahl,
  Tafel,
} from "../../ui";
import {
  type Parameter,
  type Regel,
  type Staffel,
  formuliereRegel,
  ladeRegeln,
  schalteRegel,
  stelleRegelEin,
  uebernimmFreieStaffeln,
} from "./api";
import {
  anzeigename,
  aufzaehlung,
  eingabenAus,
  feldname,
  fristsatz,
  nachThemen,
} from "./regelsatz";
import eigen from "./RegelnTafel.module.css";
import stil from "./StaffelpilotSeite.module.css";
import { meldung } from "../../api/client";

const SCHWERE_WORT = {
  kritisch: "kritisch",
  warnung: "Warnung",
  hinweis: "Hinweis",
} as const;

const SCHWERE_TON = {
  kritisch: "fehler",
  warnung: "warnung",
  hinweis: "neutral",
} as const;

const WEG_WORT = {
  kein: "",
  mahnung: "führt zur Mahnung",
  sportgericht: "führt vors Sportgericht",
} as const;

/** Wonach sich die Liste einschränken lässt. */
const FILTER = {
  alle: "Alle",
  aktiv: "An",
  aus: "Aus",
  angepasst: "Angepasst",
} as const;

type Filter = keyof typeof FILTER;

/**
 * Ob eine Regel bei dieser Einschränkung sichtbar bleibt.
 *
 * Als eigene Funktion, nicht als Kette im JSX: so steht die Bedeutung der
 * vier Fälle an einer Stelle.
 */
function passt(regel: Regel, filter: Filter, suche: string): boolean {
  const wort = suche.trim().toLowerCase();
  if (wort) {
    const heuhaufen =
      `${regel.name} ${regel.beschreibung} ${regel.schluessel}`.toLowerCase();
    if (!heuhaufen.includes(wort)) return false;
  }
  if (filter === "aktiv") return regel.aktiv;
  if (filter === "aus") return !regel.aktiv;
  if (filter === "angepasst") return regel.angepasst;
  return true;
}

const FILTERWAHL = (Object.keys(FILTER) as Filter[]).map((wert) => ({
  wert,
  wort: FILTER[wert],
}));

const KEINE_STAFFELN: readonly Staffel[] = [];

/**
 * Der eigene Regelsatz: was geprüft wird, und wie streng.
 *
 * Der Katalog kommt vom Prüfdienst; dieses Artefakt kennt die Spielordnung
 * nicht. Schalter und Werte gehören dem, der hier angemeldet ist, und gelten
 * für die Staffeln, die er leitet.
 *
 * In der Zeile steht, wonach man sucht, und der eine Handgriff, den man im
 * Durchgehen braucht: der Schalter. Alles andere — Erklärung, Werte, Sätze —
 * steht in der Ausklappung. Vierzig Regeln mit offenen Feldern wären ein
 * Formular, durch das sich niemand arbeitet.
 */
export function RegelnTafel({
  staffeln = KEINE_STAFFELN,
  onStaffelnGeaendert,
}: {
  staffeln?: readonly Staffel[];
  onStaffelnGeaendert?: () => void;
}) {
  const [regeln, setRegeln] = useState<Regel[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [filter, setFilter] = useState<Filter>("alle");
  const [suche, setSuche] = useState("");
  const [offen, setOffen] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    ladeRegeln(controller.signal)
      .then(setRegeln)
      .catch((f: unknown) => {
        if (!controller.signal.aborted) setFehler(meldung(f));
      });
    return () => controller.abort();
  }, []);

  function ersetzen(danach: Regel) {
    setRegeln((alt) => alt?.map((r) => (r.id === danach.id ? danach : r)) ?? alt);
  }

  async function umschalten(regel: Regel) {
    setFehler("");
    try {
      ersetzen(await schalteRegel(regel.id, !regel.aktiv));
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  async function uebernehmen() {
    setFehler("");
    try {
      await uebernimmFreieStaffeln();
      onStaffelnGeaendert?.();
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  if (fehler && regeln === null) {
    return (
      <Tafel titel="Regeln">
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      </Tafel>
    );
  }

  if (regeln === null) {
    return (
      <Tafel titel="Regeln">
        <div role="status" aria-label="Regeln werden geladen">
          <Platzhalter breite="100%" hoehe="12rem" />
        </div>
      </Tafel>
    );
  }

  if (regeln.length === 0) {
    return (
      <Tafel titel="Regeln">
        <Leerzustand titel="Noch keine Regeln">
          Was geprüft wird, meldet der Prüfdienst beim ersten Prüflauf. Starte einen unter
          „Prüflauf“, danach stehen hier alle Regeln zum Ein- und Ausschalten.
        </Leerzustand>
      </Tafel>
    );
  }

  const sichtbar = regeln.filter((r) => passt(r, filter, suche));
  const an = regeln.filter((r) => r.aktiv).length;
  const angepasst = regeln.filter((r) => r.angepasst).length;

  return (
    <Tafel
      titel="Regeln"
      beiwort={
        `${an} von ${regeln.length} an` +
        (angepasst > 0 ? ` · ${angepasst} angepasst` : "")
      }
      aktionen={
        <Segmentwahl
          beschriftung="Regeln einschränken"
          optionen={FILTERWAHL}
          wert={filter}
          beiWahl={setFilter}
        />
      }
    >
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <Geltung staffeln={staffeln} onUebernehmen={() => void uebernehmen()} />

      <div className={stil.werkzeugleiste}>
        <input
          type="search"
          className={stil.suchfeld}
          aria-label="Suchen"
          placeholder="Regel suchen"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
        />
        {sichtbar.length < regeln.length && (
          <span className={eigen.satz} role="status">
            {sichtbar.length} von {regeln.length} Regeln zu sehen
          </span>
        )}
      </div>

      {sichtbar.length === 0 && (
        <Leerzustand titel="Keine Regel passt dazu">
          Die Einschränkung oben nimmt alle weg. Mit „Alle“ und leerer Suche stehen wieder
          alle {regeln.length} da.
        </Leerzustand>
      )}

      {nachThemen(sichtbar).map((gruppe) => (
        <Abschnitt key={gruppe.thema} titel={gruppe.thema} regel>
          <ul className={eigen.liste} aria-label={gruppe.thema}>
            {gruppe.regeln.map((r) => (
              <Zeile
                key={r.id}
                regel={r}
                offen={offen === r.id}
                onKlappen={() => setOffen(offen === r.id ? null : r.id)}
                onSchalten={() => void umschalten(r)}
                onGespeichert={ersetzen}
              />
            ))}
          </ul>
        </Abschnitt>
      ))}
    </Tafel>
  );
}

/**
 * Für welche Staffeln der Regelsatz gilt.
 *
 * Ohne diese Zeile schaltet jemand, wundert sich, dass sich nichts ändert, und
 * sucht den Fehler im Prüfdienst. Stillgelegte Staffeln zählen nicht: sie
 * werden nicht geprüft.
 */
function Geltung({
  staffeln,
  onUebernehmen,
}: {
  staffeln: readonly Staffel[];
  onUebernehmen: () => void;
}) {
  const aktive = staffeln.filter((s) => s.aktiv);
  if (aktive.length === 0) return null;

  const meine = aktive.filter((s) => s.leite_ich).map((s) => s.name);
  const freie = aktive.filter((s) => s.staffelleiter === "").map((s) => s.name);

  return (
    <>
      <p className={eigen.geltung}>
        {meine.length > 0
          ? `Dein Regelsatz prüft ${aufzaehlung(meine)}. Andere Staffelleiter haben ihren eigenen. Änderungen gelten ab dem nächsten Prüflauf.`
          : "Du leitest noch keine Staffel. Was du hier einstellst, gilt erst, wenn du eine übernimmst."}
      </p>
      {freie.length > 0 && (
        <Hinweis ton="warnung">
          <span className={eigen.freie}>
            <span>
              Ohne Staffelleiter und deshalb mit den Vorgaben geprüft:{" "}
              {aufzaehlung(freie)}.
            </span>
            <Knopf groesse="sm" onClick={onUebernehmen}>
              {freie.length === 1 ? "Übernehmen" : `Alle ${freie.length} übernehmen`}
            </Knopf>
          </span>
        </Hinweis>
      )}
    </>
  );
}

function Zeile({
  regel,
  offen,
  onKlappen,
  onSchalten,
  onGespeichert,
}: {
  regel: Regel;
  offen: boolean;
  onKlappen: () => void;
  onSchalten: () => void;
  onGespeichert: (r: Regel) => void;
}) {
  const name = anzeigename(regel.name);
  // Nur bei einer verstellten Frist. Bei den übrigen wäre der Satz vierzigmal
  // dieselbe Vorgabe -- und beim Aufklappen steht er ohnehin da.
  const verstellt = regel.parameter.some((p) => p.wert !== null);
  const satz =
    verstellt && !offen ? fristsatz(regel.parameter, eingabenAus(regel.parameter)) : "";

  return (
    <li>
      <div className={eigen.zeile}>
        <button
          type="button"
          className={[eigen.kopf, regel.aktiv ? undefined : eigen.aus]
            .filter(Boolean)
            .join(" ")}
          aria-expanded={offen}
          onClick={onKlappen}
        >
          <span aria-hidden="true" className={eigen.pfeil}>
            ▸
          </span>
          <span className={eigen.namen}>
            <span className={eigen.namenzeile}>
              <span>{name}</span>
              {regel.schwere !== "hinweis" && (
                <Etikett ton={SCHWERE_TON[regel.schwere]}>
                  {SCHWERE_WORT[regel.schwere]}
                </Etikett>
              )}
              {regel.angepasst && <Etikett>angepasst</Etikett>}
            </span>
            {satz && <span className={eigen.satz}>{satz}</span>}
          </span>
        </button>
        <Schalter
          beschriftung={`${name} prüfen`}
          an={regel.aktiv}
          beiWechsel={onSchalten}
        />
      </div>

      {offen && (
        <div className={eigen.ausklappung}>
          {regel.beschreibung && (
            <p className={stil.vorgangHinweis}>{regel.beschreibung}</p>
          )}
          {regel.parameter.length > 0 && (
            <Werte regel={regel} onGespeichert={onGespeichert} />
          )}
          <span className={eigen.etiketten}>
            {regel.weg !== "kein" && <Etikett>{WEG_WORT[regel.weg]}</Etikett>}
            <Etikett mono>{regel.schluessel}</Etikett>
          </span>
          {regel.weg !== "kein" && <Saetze regel={regel} onGespeichert={onGespeichert} />}
        </div>
      )}
      <Linie />
    </li>
  );
}

/**
 * Was an einer Regel einstellbar ist.
 *
 * Im Feld steht der Wert, der **gilt** — auch, wenn es die Vorgabe ist. Anders
 * als bei den Sätzen friert das nichts ein: Das Artefakt speichert nur, was
 * von der Vorgabe abweicht.
 */
function Werte({
  regel,
  onGespeichert,
}: {
  regel: Regel;
  onGespeichert: (r: Regel) => void;
}) {
  const stand = eingabenAus(regel.parameter);
  const [eingaben, setEingaben] = useState(stand);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState("");

  const geaendert = regel.parameter.some(
    (p) => eingaben[p.schluessel] !== stand[p.schluessel],
  );
  const verstellt = regel.parameter.some((p) => p.wert !== null);

  async function speichern(werte: Record<string, string>) {
    setLaeuft(true);
    setFehler("");
    try {
      const danach = await stelleRegelEin(regel.id, werte);
      onGespeichert(danach);
      setEingaben(eingabenAus(danach.parameter));
    } catch (f) {
      setFehler(meldung(f));
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <form
      className={eigen.werte}
      // Die Grenzen prüft das Backend und sagt sie in einem Satz. Die Blase
      // des Browsers wäre die zweite Meldung zum selben Fehler.
      noValidate
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void speichern(eingaben);
      }}
    >
      <div className={eigen.felder}>
        {regel.parameter.map((p) => (
          <Feld
            key={p.schluessel}
            beschriftung={feldname(p)}
            hinweis={[p.erklaerung, `Vorgabe: ${p.vorgabe}.`].filter(Boolean).join(" ")}
            {...feldart(p)}
            value={eingaben[p.schluessel] ?? ""}
            onChange={(e) =>
              setEingaben((alt) => ({ ...alt, [p.schluessel]: e.target.value }))
            }
          />
        ))}
      </div>

      <p className={eigen.satz}>{fristsatz(regel.parameter, eingaben)}</p>

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <div className={eigen.knoepfe}>
        <Knopf type="submit" groesse="sm" disabled={!geaendert || laeuft}>
          {laeuft ? "Speichert" : "Werte speichern"}
        </Knopf>
        {verstellt && (
          <Knopf
            groesse="sm"
            auspraegung="leise"
            disabled={laeuft}
            onClick={() => void speichern({})}
          >
            Auf Vorgabe zurücksetzen
          </Knopf>
        )}
      </div>
    </form>
  );
}

function feldart(p: Parameter) {
  if (p.art === "uhrzeit") return { type: "time" };
  return {
    type: "number",
    inputMode: "numeric" as const,
    step: 1,
    ...(p.kleinst === null ? {} : { min: p.kleinst }),
    ...(p.groesst === null ? {} : { max: p.groesst }),
  };
}

/**
 * Die beiden Sätze, die aus einem Befund ein Schreiben machen.
 *
 * Nur bei Regeln, aus denen überhaupt eines entsteht — bei den übrigen wäre es
 * ein Feld, das nie irgendwo auftaucht.
 *
 * **Leer heißt: der mitgelieferte Satz gilt.** Er steht als Platzhalter im
 * Feld und wird nicht hineingeschrieben: sonst hielte der erste Klick auf
 * Speichern den heutigen Wortlaut fest, samt Paragraf — und eine spätere
 * Korrektur käme nie an.
 */
function Saetze({
  regel,
  onGespeichert,
}: {
  regel: Regel;
  onGespeichert: (r: Regel) => void;
}) {
  const [sachverhalt, setSachverhalt] = useState(regel.sachverhalt);
  const [hinweis, setHinweis] = useState(regel.hinweis);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState("");

  const geaendert = sachverhalt !== regel.sachverhalt || hinweis !== regel.hinweis;

  async function speichern() {
    setLaeuft(true);
    setFehler("");
    try {
      onGespeichert(await formuliereRegel(regel.id, { sachverhalt, hinweis }));
    } catch (f) {
      setFehler(meldung(f));
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <details className={stil.saetze}>
      <summary className={stil.saetzeKopf}>
        {/* Ein eigenes Zeichen statt des Browser-Dreiecks: das ist je nach
            Browser mal da, mal nicht, und ohne irgendeines sah die Zeile wie
            Fliesstext aus -- niemand haette sie angeklickt. */}
        <span aria-hidden="true" className={stil.saetzePfeil}>
          ▸
        </span>
        Text fürs Schreiben
        {(regel.sachverhalt || regel.hinweis) && <Etikett>eigener</Etikett>}
      </summary>

      <p className={stil.vorgangHinweis}>
        Der Sachverhalt folgt auf „Im Spiel … am … “. Platzhalter in geschweiften Klammern
        werden eingesetzt ({"{person}"}, {"{verein}"}); was in eckigen Klammern steht,
        fällt weg, wenn sein Wert fehlt. Leer lassen heißt: der mitgelieferte Satz gilt.
      </p>

      <label className={stil.textfeldEtikett}>
        Sachverhalt
        <textarea
          className={stil.satzfeld}
          rows={3}
          value={sachverhalt}
          placeholder={regel.vorgabe_sachverhalt}
          onChange={(e) => setSachverhalt(e.target.value)}
        />
      </label>

      <label className={stil.textfeldEtikett}>
        Hinweis
        <textarea
          className={stil.satzfeld}
          rows={4}
          value={hinweis}
          placeholder={regel.vorgabe_hinweis}
          onChange={(e) => setHinweis(e.target.value)}
        />
      </label>

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <div className={stil.knoepfe}>
        <Knopf
          groesse="sm"
          onClick={() => void speichern()}
          disabled={!geaendert || laeuft}
        >
          {laeuft ? "Speichert" : "Speichern"}
        </Knopf>
        {geaendert && (
          <Knopf
            groesse="sm"
            auspraegung="sekundaer"
            onClick={() => {
              setSachverhalt(regel.sachverhalt);
              setHinweis(regel.hinweis);
            }}
          >
            Verwerfen
          </Knopf>
        )}
      </div>

      <p className={stil.vorgangHinweis}>
        Gilt ab dem nächsten Schreiben und für alle Staffelleiter. Schon erstellte
        Entwürfe ändern sich nicht — ihr Text liegt am Vorgang.
      </p>
    </details>
  );
}
