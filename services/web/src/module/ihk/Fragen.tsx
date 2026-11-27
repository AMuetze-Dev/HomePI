import { useCallback, useEffect, useId, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Feld, Hinweis, Karte, Knopf, Leerzustand, Tafel } from "../../ui";
import * as api from "./api";
import { Lade } from "./IhkSeite";
import stil from "./IhkSeite.module.css";
import { meldung, themenAus } from "./zeit";

const OHNE_THEMA = "Ohne Thema";

/**
 * Die Fragensammlung fürs Fachgespräch. Gepflegt wird sie hier, gezogen wird
 * im Fachgespräch - zufällig, auf Wunsch aus einem Thema.
 */
export function FragenTafel() {
  const [fragen, setFragen] = useState<api.Frage[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [suche, setSuche] = useState("");
  const listeId = useId();

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      setFragen(await api.ladeFragen(signal));
    } catch (e) {
      if (!signal?.aborted) setFehler(meldung(e));
    }
  }, []);

  useEffect(() => {
    const steuerung = new AbortController();
    void laden(steuerung.signal);
    return () => steuerung.abort();
  }, [laden]);

  async function mitFehler<T>(tun: () => Promise<T>): Promise<T | null> {
    setFehler("");
    try {
      return await tun();
    } catch (e) {
      setFehler(meldung(e));
      return null;
    }
  }

  const themen = useMemo(() => themenAus(fragen ?? []), [fragen]);
  const gruppen = useMemo(() => {
    const s = suche.trim().toLocaleLowerCase("de");
    const passend = (fragen ?? []).filter(
      (f) =>
        !s ||
        f.text.toLocaleLowerCase("de").includes(s) ||
        f.thema.toLocaleLowerCase("de").includes(s),
    );
    const nach = new Map<string, api.Frage[]>();
    for (const f of passend) {
      const t = f.thema || OHNE_THEMA;
      nach.set(t, [...(nach.get(t) ?? []), f]);
    }
    const namen = [...themen.filter((t) => nach.has(t))];
    if (nach.has(OHNE_THEMA)) namen.push(OHNE_THEMA);
    return namen.map((t) => ({ thema: t, fragen: nach.get(t)! }));
  }, [fragen, suche, themen]);

  if (fragen === null && !fehler) return <Lade titel="Fragensammlung" />;
  const anzahl = fragen?.length ?? 0;

  return (
    <Tafel
      titel="Fragensammlung"
      beiwort={`${anzahl} ${anzahl === 1 ? "Frage" : "Fragen"} · im Fachgespräch zufällig ziehen`}
    >
      <Link to="?" className={stil.zurueck}>
        ← Prüfungstage
      </Link>
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <datalist id={listeId}>
        {themen.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>

      <FrageAufnehmen
        themenliste={listeId}
        onAufnehmen={async (daten) => {
          const neu = await mitFehler(() => api.legeFrageAn(daten));
          if (neu) setFragen((alt) => [...(alt ?? []), neu]);
          return neu !== null;
        }}
        onStapel={async (daten) => {
          const ergebnis = await mitFehler(() => api.legeFragenAn(daten));
          if (ergebnis) await laden();
          return ergebnis;
        }}
      />

      {anzahl === 0 ? (
        <Leerzustand titel="Noch keine Fragen">
          Nimm Fragen auf, einzeln oder viele auf einmal. Im Fachgespräch ziehst du sie
          dann zufällig, auf Wunsch nach Thema.
        </Leerzustand>
      ) : (
        <>
          <input
            type="search"
            className={stil.eingabezeile}
            aria-label="Fragen durchsuchen"
            placeholder="Fragen durchsuchen …"
            value={suche}
            onChange={(e) => setSuche(e.target.value)}
          />
          {gruppen.length === 0 && (
            <p className={stil.leise}>Keine Frage passt zur Suche.</p>
          )}
          {gruppen.map(({ thema, fragen: inThema }) => (
            <ThemaGruppe
              key={thema}
              thema={thema}
              fragen={inThema}
              themenliste={listeId}
              onAendern={async (frage, daten) => {
                const neu = await mitFehler(() => api.aendereFrage(frage.id, daten));
                if (neu)
                  setFragen((alt) => (alt ?? []).map((f) => (f.id === neu.id ? neu : f)));
                return neu !== null;
              }}
              onEntfernen={async (frage) => {
                if (!window.confirm(`Frage „${frage.text}“ aus der Sammlung entfernen?`))
                  return;
                const ok = await mitFehler(() => api.entferneFrage(frage.id));
                if (ok !== null)
                  setFragen((alt) => (alt ?? []).filter((f) => f.id !== frage.id));
              }}
            />
          ))}
        </>
      )}
    </Tafel>
  );
}

function FrageAufnehmen({
  themenliste,
  onAufnehmen,
  onStapel,
}: {
  themenliste: string;
  onAufnehmen: (daten: Omit<api.Frage, "id">) => Promise<boolean>;
  onStapel: (daten: {
    thema: string;
    texte: string;
  }) => Promise<{ angelegt: number; doppelt: number } | null>;
}) {
  const [text, setText] = useState("");
  const [thema, setThema] = useState("");
  const [stapelOffen, setStapelOffen] = useState(false);
  const [stapel, setStapel] = useState("");
  const [ergebnis, setErgebnis] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const textId = useId();
  const stapelId = useId();

  async function einzeln(e: FormEvent) {
    e.preventDefault();
    if (!text.trim() || laeuft) return;
    setLaeuft(true);
    // Das Thema bleibt stehen: Meist kommen mehrere Fragen zum selben.
    if (await onAufnehmen({ text: text.trim(), thema: thema.trim() })) setText("");
    setLaeuft(false);
  }

  async function viele(e: FormEvent) {
    e.preventDefault();
    if (!stapel.trim() || laeuft) return;
    setLaeuft(true);
    const neu = await onStapel({ thema: thema.trim(), texte: stapel });
    setLaeuft(false);
    if (!neu) return;
    setStapel("");
    setErgebnis(
      neu.doppelt
        ? `${neu.angelegt} aufgenommen, ${neu.doppelt} gab es schon.`
        : `${neu.angelegt} aufgenommen.`,
    );
  }

  return (
    <Karte>
      <div className={stil.stapel}>
        <form
          onSubmit={(e) => void (stapelOffen ? viele(e) : einzeln(e))}
          className={stil.stapel}
        >
          {stapelOffen ? (
            <div className={stil.auswahlgruppe}>
              <label htmlFor={stapelId} className={stil.beschriftung}>
                Eine Frage je Zeile
              </label>
              <textarea
                id={stapelId}
                className={stil.textfeld}
                rows={8}
                value={stapel}
                onChange={(e) => setStapel(e.target.value)}
              />
            </div>
          ) : (
            <div className={stil.auswahlgruppe}>
              <label htmlFor={textId} className={stil.beschriftung}>
                Frage
              </label>
              <textarea
                id={textId}
                className={stil.textfeld}
                rows={2}
                maxLength={500}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  // Enter nimmt auf, Umschalt+Enter bricht um.
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.form?.requestSubmit();
                  }
                }}
              />
            </div>
          )}
          <div className={stil.formular}>
            <Feld
              beschriftung="Thema"
              list={themenliste}
              placeholder="z. B. Datenbanken"
              maxLength={60}
              value={thema}
              onChange={(e) => setThema(e.target.value)}
              autoComplete="off"
            />
            <Knopf
              type="submit"
              auspraegung="primaer"
              disabled={laeuft || !(stapelOffen ? stapel : text).trim()}
            >
              {stapelOffen ? "Alle aufnehmen" : "Aufnehmen"}
            </Knopf>
          </div>
        </form>
        <div className={stil.knopfreihe}>
          <Knopf
            groesse="sm"
            auspraegung="leise"
            aria-expanded={stapelOffen}
            onClick={() => {
              setStapelOffen(!stapelOffen);
              setErgebnis("");
            }}
          >
            {stapelOffen ? "Einzeln aufnehmen" : "Mehrere auf einmal"}
          </Knopf>
        </div>
        {ergebnis && <Hinweis ton="gut">{ergebnis}</Hinweis>}
      </div>
    </Karte>
  );
}

function ThemaGruppe({
  thema,
  fragen,
  themenliste,
  onAendern,
  onEntfernen,
}: {
  thema: string;
  fragen: api.Frage[];
  themenliste: string;
  onAendern: (frage: api.Frage, daten: Omit<api.Frage, "id">) => Promise<boolean>;
  onEntfernen: (frage: api.Frage) => Promise<void>;
}) {
  const kopf = useId();
  const [bearbeitet, setBearbeitet] = useState<string | null>(null);

  return (
    <section aria-labelledby={kopf} className={stil.stapel}>
      <h2 id={kopf} className={stil.abschnittstitel}>
        {thema}{" "}
        <span className={stil.leise} aria-hidden="true">
          {fragen.length}
        </span>
      </h2>
      <Karte>
        <ul className={stil.liste}>
          {fragen.map((f) =>
            bearbeitet === f.id ? (
              <li key={f.id} className={stil.fragenposten}>
                <FrageBearbeiten
                  frage={f}
                  themenliste={themenliste}
                  onSpeichern={async (daten) => {
                    if (await onAendern(f, daten)) setBearbeitet(null);
                  }}
                  onAbbrechen={() => setBearbeitet(null)}
                />
              </li>
            ) : (
              <li key={f.id} className={`${stil.fragenposten} ${stil.kriterium}`}>
                <span className={stil.kriteriumtext}>{f.text}</span>
                <span className={stil.knopfreihe}>
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    aria-label={`„${f.text}“ ändern`}
                    onClick={() => setBearbeitet(f.id)}
                  >
                    Ändern
                  </Knopf>
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    aria-label={`„${f.text}“ entfernen`}
                    onClick={() => void onEntfernen(f)}
                  >
                    Entfernen
                  </Knopf>
                </span>
              </li>
            ),
          )}
        </ul>
      </Karte>
    </section>
  );
}

function FrageBearbeiten({
  frage,
  themenliste,
  onSpeichern,
  onAbbrechen,
}: {
  frage: api.Frage;
  themenliste: string;
  onSpeichern: (daten: Omit<api.Frage, "id">) => Promise<void>;
  onAbbrechen: () => void;
}) {
  const [text, setText] = useState(frage.text);
  const [thema, setThema] = useState(frage.thema);
  const textId = useId();

  return (
    <form
      className={stil.stapel}
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) void onSpeichern({ text: text.trim(), thema: thema.trim() });
      }}
    >
      <div className={stil.auswahlgruppe}>
        <label htmlFor={textId} className={stil.beschriftung}>
          Text der Frage
        </label>
        <textarea
          id={textId}
          className={stil.textfeld}
          rows={2}
          maxLength={500}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div className={stil.formular}>
        <Feld
          beschriftung="Thema der Frage"
          list={themenliste}
          maxLength={60}
          value={thema}
          onChange={(e) => setThema(e.target.value)}
          autoComplete="off"
        />
        <Knopf type="submit" auspraegung="primaer" disabled={!text.trim()}>
          Speichern
        </Knopf>
        <Knopf auspraegung="leise" onClick={onAbbrechen}>
          Abbrechen
        </Knopf>
      </div>
    </form>
  );
}
