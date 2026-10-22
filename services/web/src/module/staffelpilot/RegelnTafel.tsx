import { useEffect, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import { type Regel, formuliereRegel, ladeRegeln, schalteRegel } from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

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

/**
 * Was der Prüfdienst prüft — und was davon hier ankommen soll.
 *
 * Der Katalog kommt von außen; dieses Artefakt kennt die Spielordnung nicht.
 * Was ihm gehört, sind der Schalter und die beiden Sätze: eine abgeschaltete
 * Regel meldet nichts mehr, und wo ein eigener Satz steht, steht er später im
 * Schreiben an den Verein. Geprüft wird im Prüfdienst, der hier nachliest.
 */
/** Wonach sich die Liste einschränken lässt. */
const FILTER = {
  alle: "Alle",
  aktiv: "An",
  aus: "Aus",
  schreiben: "Mit Schreiben",
} as const;

type Filter = keyof typeof FILTER;

/**
 * Ob eine Regel bei dieser Einschränkung sichtbar bleibt.
 *
 * Als eigene Funktion, nicht als Kette im JSX: so steht die Bedeutung der
 * vier Fälle an einer Stelle, und „Mit Schreiben" heißt nachlesbar „aus ihr
 * entsteht eine Mahnung oder ein Antrag".
 */
function passt(regel: Regel, filter: Filter, suche: string): boolean {
  const wort = suche.trim().toLowerCase();
  if (wort) {
    const heuhaufen = `${regel.name} ${regel.beschreibung} ${regel.schluessel}`.toLowerCase();
    if (!heuhaufen.includes(wort)) return false;
  }
  if (filter === "aktiv") return regel.aktiv;
  if (filter === "aus") return !regel.aktiv;
  if (filter === "schreiben") return regel.weg !== "kein";
  return true;
}

export function RegelnTafel() {
  const [regeln, setRegeln] = useState<Regel[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [filter, setFilter] = useState<Filter>("alle");
  const [suche, setSuche] = useState("");

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

  if (fehler && regeln === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  if (regeln === null) {
    return (
      <div role="status" aria-label="Regeln werden geladen">
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  const sichtbar = regeln.filter((r) => passt(r, filter, suche));

  if (regeln.length === 0) {
    return (
      <Leerzustand titel="Kein Regelkatalog">
        Der Prüfdienst meldet über <code>PUT /staffelpilot/regeln</code>, was er prüft.
        Solange er das nicht getan hat, gibt es hier nichts zu schalten.
      </Leerzustand>
    );
  }

  return (
    <>
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {/* Vierundvierzig Regeln als vierundvierzig Karten waren fünf
          Bildschirme ohne jeden Griff: keine Suche, kein Filter, und die
          eine, die man sucht, findet man durch Scrollen. */}
      {/* Alles in einer Zeile. Untereinander waren Filter, Beschriftung,
          Feld, Hinweis und Zaehler zusammen ein Viertel des Bildschirms --
          bevor eine einzige Regel kam. Der Hinweis steckt jetzt im
          Platzhalter, wo man ihn liest, wenn man das Feld ansieht. */}
      <div className={stil.werkzeugleiste}>
        <div className={stil.filterZeile} role="group" aria-label="Regeln einschränken">
          {(Object.keys(FILTER) as Filter[]).map((f) => (
            <Knopf
              key={f}
              groesse="sm"
              auspraegung={filter === f ? "primaer" : "leise"}
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
            >
              {FILTER[f]}
            </Knopf>
          ))}
        </div>

        <input
          type="search"
          className={stil.suchfeld}
          aria-label="Suchen"
          placeholder="Name, Beschreibung oder Kennung"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
        />

        <span className={stil.zaehler}>
          {sichtbar.length === regeln.length
            ? `${regeln.length} Regeln`
            : `${sichtbar.length} von ${regeln.length}`}
        </span>
      </div>

      {sichtbar.length === 0 && (
        <Leerzustand titel="Keine Regel passt dazu">
          Die Einschränkung oben nimmt alle weg. Mit „Alle" und leerer Suche
          stehen wieder alle {regeln.length} da.
        </Leerzustand>
      )}

      <ul className={stil.liste} aria-label="Regeln">
        {sichtbar.map((r) => (
          <li key={r.id}>
            <Karte>
              <label className={stil.ankreuz}>
                <input
                  type="checkbox"
                  checked={r.aktiv}
                  onChange={() => void umschalten(r)}
                />
                <span className={stil.paarung}>{r.name}</span>
              </label>
              <span className={stil.zeile}>
                <Etikett ton={SCHWERE_TON[r.schwere]}>{SCHWERE_WORT[r.schwere]}</Etikett>
                {r.weg !== "kein" && <Etikett>{WEG_WORT[r.weg]}</Etikett>}
                <Etikett mono>{r.schluessel}</Etikett>
              </span>
              {r.beschreibung && <p className={stil.vorgangHinweis}>{r.beschreibung}</p>}
              {!r.aktiv && (
                <p className={stil.vorgangHinweis}>
                  Abgeschaltet — der Prüfdienst meldet dazu nichts mehr.
                </p>
              )}
              {r.weg !== "kein" && <Saetze regel={r} onGespeichert={ersetzen} />}
            </Karte>
          </li>
        ))}
      </ul>
    </>
  );
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
      setFehler(f instanceof Error ? f.message : "Unbekannter Fehler");
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
        Gilt ab dem nächsten Schreiben. Schon erstellte Entwürfe ändern sich nicht — ihr
        Text liegt am Vorgang.
      </p>
    </details>
  );
}
