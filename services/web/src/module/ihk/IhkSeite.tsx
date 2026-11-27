import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter, Tafel } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { PrueflingTafel } from "./PrueflingTafel";
import { datum, meldung, note, punkte } from "./zeit";

/**
 * Prüfungstage (mit allen Prüflingen) → Prüfling; ein Tag wird auf eigener
 * Fläche bearbeitet.
 *
 * Wo man ist, steht in der Adresse (`?pruefling=…`, `?tag=…`, `?offen=…`),
 * nicht im Zustand: Ein Neuladen mitten in der Prüfung landet wieder beim Prüfling,
 * und der Zurück-Knopf des Browsers führt eine Ebene hinauf.
 */
export function IhkSeite() {
  const [suche] = useSearchParams();
  const prueflingId = suche.get("pruefling");
  const tagId = suche.get("tag");

  if (prueflingId) return <PrueflingTafel key={prueflingId} prueflingId={prueflingId} />;
  if (tagId) return <TagTafel key={tagId} tagId={tagId} />;
  return <TageTafel />;
}

const heute = () => new Date().toISOString().slice(0, 10);

type Laden<T> =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: T }
  | { phase: "fehler"; nachricht: string };

function useLaden<T>(holen: (signal?: AbortSignal) => Promise<T>) {
  const [zustand, setZustand] = useState<Laden<T>>({ phase: "laedt" });
  const laden = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setZustand({ phase: "fertig", daten: await holen(signal) });
      } catch (fehler) {
        if (signal?.aborted) return;
        setZustand({ phase: "fehler", nachricht: meldung(fehler) });
      }
    },
    [holen],
  );
  useEffect(() => {
    const steuerung = new AbortController();
    void laden(steuerung.signal);
    return () => steuerung.abort();
  }, [laden]);
  return { zustand, laden };
}

export function Lade({ titel }: { titel: string }) {
  return (
    <Tafel titel={titel}>
      <div role="status" aria-label="Wird geladen" className={stil.stapel}>
        <Platzhalter hoehe="3.5rem" />
        <Platzhalter hoehe="3.5rem" />
        <Platzhalter hoehe="12rem" />
      </div>
    </Tafel>
  );
}

// ── Alle Prüfungstage ────────────────────────────────────────────────────────

function sucheIn(p: api.PrueflingKurz, begriff: string): boolean {
  return `${p.name} ${p.ident}`.toLowerCase().includes(begriff);
}

/**
 * Alle Tage auf einer Fläche, jeder mit seinen Prüflingen zum Aufklappen.
 *
 * Vorher führte der Weg zum Prüfling über den Tag in eine zweite Liste. Wer
 * einen Namen sucht, weiß selten den Tag - deshalb stehen hier alle, und das
 * Suchfeld geht über alle Tage. Bearbeitet wird ein Tag auf eigener Fläche.
 */
function TageTafel() {
  const { zustand, laden } = useLaden(api.ladeTage);
  const [suchparameter] = useSearchParams();
  const [fehler, setFehler] = useState("");
  // null heißt: noch nichts angetippt, es gilt die Voreinstellung.
  const [offen, setOffen] = useState<Set<string> | null>(null);
  const [begriff, setBegriff] = useState("");

  if (zustand.phase === "laedt") return <Lade titel="Prüfungstage" />;
  if (zustand.phase === "fehler") {
    return (
      <Tafel titel="Prüfungstage">
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const tage = zustand.daten;
  // Zurück vom Prüfling ist sein Tag offen, sonst der jüngste.
  const vorgabe = suchparameter.get("offen") ?? tage[0]?.tag.id;
  const aufgeklappt = offen ?? new Set(vorgabe ? [vorgabe] : []);
  const gesucht = begriff.trim().toLowerCase();
  const sichtbar = gesucht
    ? tage
        .map((t) => ({
          ...t,
          prueflinge: t.prueflinge.filter((p) => sucheIn(p, gesucht)),
        }))
        .filter((t) => t.prueflinge.length > 0)
    : tage;
  const alleOffen = tage.length > 0 && tage.every((t) => aufgeklappt.has(t.tag.id));
  const anzahl = tage.reduce((summe, t) => summe + t.prueflinge.length, 0);

  function umschalten(id: string) {
    const neu = new Set(aufgeklappt);
    if (neu.has(id)) neu.delete(id);
    else neu.add(id);
    setOffen(neu);
  }

  return (
    <Tafel
      titel="Prüfungstage"
      beiwort={`${tage.length} ${tage.length === 1 ? "Tag" : "Tage"} · ${anzahl} ${anzahl === 1 ? "Prüfling" : "Prüflinge"}`}
    >
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {tage.length === 0 ? (
        <Leerzustand titel="Noch kein Prüfungstag">
          Lege unten einen Prüfungstag an. Darin trägst du die Prüflinge ein und bewertest
          Dokumentation, Präsentation und Fachgespräch.
        </Leerzustand>
      ) : (
        <>
          <div className={stil.werkzeuge}>
            <Feld
              beschriftung="Prüfling suchen"
              type="search"
              placeholder="Name oder Ident"
              value={begriff}
              onChange={(e) => setBegriff(e.target.value)}
              autoComplete="off"
            />
            <Knopf
              groesse="sm"
              auspraegung="leise"
              onClick={() =>
                setOffen(alleOffen ? new Set() : new Set(tage.map((t) => t.tag.id)))
              }
            >
              {alleOffen ? "Alle zuklappen" : "Alle aufklappen"}
            </Knopf>
          </div>

          {sichtbar.length === 0 && (
            <p className={stil.leise}>Kein Prüfling passt zu „{begriff.trim()}“.</p>
          )}

          {sichtbar.map(({ tag: t, prueflinge }) => {
            // Bei einer Suche ist jeder Treffer sichtbar - aufgeklappt wird
            // dann nicht mehr von Hand.
            const istOffen = gesucht !== "" || aufgeklappt.has(t.id);
            const listeId = `tag-${t.id}`;
            return (
              <Karte key={t.id} blank>
                <div className={stil.tagkopf}>
                  <button
                    type="button"
                    className={stil.aufklapper}
                    aria-expanded={istOffen}
                    aria-controls={listeId}
                    onClick={() => umschalten(t.id)}
                  >
                    <span className={stil.pfeil} aria-hidden="true">
                      {istOffen ? "▾" : "▸"}
                    </span>
                    <span className={stil.zeilentitel}>{datum(t.datum)}</span>
                    <span className={stil.leise}>
                      {[t.ort, t.korrektor].filter(Boolean).join(" · ")}
                    </span>
                    <span className={stil.rechts}>
                      {t.anzahl_prueflinge}{" "}
                      {t.anzahl_prueflinge === 1 ? "Prüfling" : "Prüflinge"}
                    </span>
                  </button>
                  <Link
                    to={`?tag=${encodeURIComponent(t.id)}`}
                    className={stil.bearbeiten}
                    aria-label={`Bearbeiten: ${datum(t.datum)}`}
                  >
                    Bearbeiten
                  </Link>
                </div>
                {istOffen && (
                  <div id={listeId}>
                    {prueflinge.length === 0 ? (
                      <p className={`${stil.leise} ${stil.innen}`}>
                        Noch keine Prüflinge - über „Bearbeiten“ eintragen.
                      </p>
                    ) : (
                      <ul className={stil.liste}>
                        {prueflinge.map((p) => (
                          <li key={p.id}>
                            <PrueflingZeile pruefling={p} />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </Karte>
            );
          })}
        </>
      )}

      <TagAnlegen
        onAnlegen={async (daten) => {
          setFehler("");
          try {
            const neu = await api.legeTagAn(daten);
            await laden();
            setOffen(new Set([...aufgeklappt, neu.id]));
            return true;
          } catch (e) {
            setFehler(meldung(e));
            return false;
          }
        }}
      />
    </Tafel>
  );
}

/** Was über einen Prüfling ohne Öffnen zu sagen ist. Ob die Doku vorliegt,
 *  ergibt sich aus dem hinterlegten PDF - abgehakt wird nur, was niemand
 *  sonst wissen kann. */
function zustandText(p: api.PrueflingKurz): string {
  return [
    p.ident,
    p.korrekturart,
    p.dokumente > 0 ? "Doku hinterlegt" : "keine Doku",
    p.status.kontrolliert ? "Kontrolliert" : "",
    p.status.abgestimmt ? "Abgestimmt" : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function PrueflingZeile({ pruefling: p }: { pruefling: api.PrueflingKurz }) {
  return (
    <Link to={`?pruefling=${encodeURIComponent(p.id)}`} className={stil.zeile}>
      <span className={stil.zeilentitel}>
        {p.reihenfolge}. {p.name}
      </span>
      <span className={stil.leise}>{zustandText(p)}</span>
      <span className={stil.rechts}>
        Doku {punkte(p.doku_punkte)} P ({note(p.doku_note)}) · Präs.{" "}
        {punkte(p.praesi_punkte)} P ({note(p.praesi_note)})
      </span>
    </Link>
  );
}

function TagAnlegen({ onAnlegen }: { onAnlegen: (d: api.NeuerTag) => Promise<boolean> }) {
  const [daten, setDaten] = useState<api.NeuerTag>({
    datum: heute(),
    ort: "",
    korrektor: "",
  });
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(e: FormEvent) {
    e.preventDefault();
    if (laeuft) return;
    setLaeuft(true);
    const geklappt = await onAnlegen({
      ...daten,
      ort: daten.ort.trim(),
      korrektor: daten.korrektor.trim(),
    });
    setLaeuft(false);
    // Nur leeren, wenn es geklappt hat - sonst tippt man alles neu. Der
    // Korrektor bleibt stehen: Er ist an jedem Tag derselbe.
    if (geklappt) setDaten((alt) => ({ ...alt, ort: "" }));
  }

  return (
    <section aria-labelledby="tag-anlegen" className={stil.stapel}>
      <h2 id="tag-anlegen" className={stil.abschnittstitel}>
        Prüfungstag anlegen
      </h2>
      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Datum"
            type="date"
            value={daten.datum}
            onChange={(e) => setDaten({ ...daten, datum: e.target.value })}
            required
          />
          <Feld
            beschriftung="Ort"
            value={daten.ort}
            onChange={(e) => setDaten({ ...daten, ort: e.target.value })}
            autoComplete="off"
          />
          <Feld
            beschriftung="Korrektor"
            value={daten.korrektor}
            onChange={(e) => setDaten({ ...daten, korrektor: e.target.value })}
            autoComplete="name"
          />
          <Knopf type="submit" auspraegung="primaer" disabled={laeuft || !daten.datum}>
            {laeuft ? "Wird angelegt …" : "Tag anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}

// ── Einen Prüfungstag bearbeiten ─────────────────────────────────────────────

function TagTafel({ tagId }: { tagId: string }) {
  const holen = useCallback(
    (signal?: AbortSignal) => api.ladeTag(tagId, signal),
    [tagId],
  );
  const { zustand, laden } = useLaden(holen);
  const [fehler, setFehler] = useState("");
  const navigiere = useNavigate();
  const zurueck = `?offen=${encodeURIComponent(tagId)}`;

  if (zustand.phase === "laedt") return <Lade titel="Prüfungstag" />;
  if (zustand.phase === "fehler") {
    return (
      <Tafel titel="Prüfungstag">
        <Link to="?" className={stil.zurueck}>
          ← Prüfungstage
        </Link>
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { tag, prueflinge } = zustand.daten;

  async function mitFehler(aktion: () => Promise<unknown>): Promise<boolean> {
    setFehler("");
    try {
      await aktion();
      await laden();
      return true;
    } catch (e) {
      setFehler(meldung(e));
      return false;
    }
  }

  async function entfernen() {
    if (
      !window.confirm(
        `Prüfungstag ${datum(tag.datum)} mit allen Prüflingen und Bewertungen entfernen?`,
      )
    ) {
      return;
    }
    setFehler("");
    try {
      await api.entferneTag(tag.id);
      void navigiere("?");
    } catch (e) {
      setFehler(meldung(e));
    }
  }

  return (
    <Tafel
      titel={`Prüfungstag ${datum(tag.datum)}`}
      beiwort={[tag.ort, tag.korrektor].filter(Boolean).join(" · ") || undefined}
      aktionen={
        <Knopf groesse="sm" auspraegung="leise" onClick={() => void entfernen()}>
          Tag entfernen
        </Knopf>
      }
    >
      <Link to={zurueck} className={stil.zurueck}>
        ← Prüfungstage
      </Link>
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <TagBearbeiten
        key={`${tag.datum}|${tag.ort}|${tag.korrektor}`}
        tag={tag}
        onSpeichern={(daten) => mitFehler(() => api.aendereTag(tag.id, daten))}
      />

      <section aria-labelledby="prueflinge" className={stil.stapel}>
        <h2 id="prueflinge" className={stil.abschnittstitel}>
          Prüflinge
        </h2>
        {prueflinge.length === 0 ? (
          <Leerzustand titel="Noch keine Prüflinge">
            Trage unten die Prüflinge dieses Tages in der Reihenfolge ein, in der sie
            geprüft werden.
          </Leerzustand>
        ) : (
          <Karte blank>
            <ul className={stil.liste}>
              {prueflinge.map((p) => (
                <li key={p.id} className={stil.mitaktion}>
                  <PrueflingZeile pruefling={p} />
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    aria-label={`${p.name} entfernen`}
                    onClick={() => {
                      if (
                        window.confirm(
                          `${p.name} mit Bewertung und Dokumenten entfernen?`,
                        )
                      ) {
                        void mitFehler(() => api.entfernePruefling(p.id));
                      }
                    }}
                  >
                    Entfernen
                  </Knopf>
                </li>
              ))}
            </ul>
          </Karte>
        )}
      </section>

      <PrueflingAnlegen
        onAnlegen={(name) => mitFehler(() => api.legePrueflingAn(tag.id, name))}
      />
    </Tafel>
  );
}

function TagBearbeiten({
  tag,
  onSpeichern,
}: {
  tag: api.Tag;
  onSpeichern: (daten: api.NeuerTag) => Promise<boolean>;
}) {
  const [daten, setDaten] = useState<api.NeuerTag>({
    datum: tag.datum,
    ort: tag.ort,
    korrektor: tag.korrektor,
  });
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(e: FormEvent) {
    e.preventDefault();
    setLaeuft(true);
    await onSpeichern({
      ...daten,
      ort: daten.ort.trim(),
      korrektor: daten.korrektor.trim(),
    });
    setLaeuft(false);
  }

  return (
    <Karte>
      <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
        <Feld
          beschriftung="Datum"
          type="date"
          value={daten.datum}
          onChange={(e) => setDaten({ ...daten, datum: e.target.value })}
          required
        />
        <Feld
          beschriftung="Ort"
          value={daten.ort}
          onChange={(e) => setDaten({ ...daten, ort: e.target.value })}
          autoComplete="off"
        />
        <Feld
          beschriftung="Korrektor"
          value={daten.korrektor}
          onChange={(e) => setDaten({ ...daten, korrektor: e.target.value })}
          autoComplete="name"
        />
        <Knopf type="submit" auspraegung="primaer" disabled={laeuft || !daten.datum}>
          {laeuft ? "Wird gespeichert …" : "Speichern"}
        </Knopf>
      </form>
    </Karte>
  );
}

function PrueflingAnlegen({
  onAnlegen,
}: {
  onAnlegen: (name: string) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || laeuft) return;
    setLaeuft(true);
    const geklappt = await onAnlegen(name.trim());
    setLaeuft(false);
    if (geklappt) setName("");
  }

  return (
    <section aria-labelledby="pruefling-anlegen" className={stil.stapel}>
      <h2 id="pruefling-anlegen" className={stil.abschnittstitel}>
        Prüfling anlegen
      </h2>
      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            placeholder="Nachname, Vorname"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
            required
          />
          <Knopf type="submit" auspraegung="primaer" disabled={!name.trim() || laeuft}>
            {laeuft ? "Wird angelegt …" : "Prüfling anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}
