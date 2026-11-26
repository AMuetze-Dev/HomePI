import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter, Tafel } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { PrueflingTafel } from "./PrueflingTafel";
import { datum, meldung, note, punkte } from "./zeit";

/**
 * Prüfungstage → Prüflinge → Prüfling, wie im ExamManager.
 *
 * Wo man ist, steht in der Adresse (`?tag=…`, `?pruefling=…`), nicht im
 * Zustand: Ein Neuladen mitten in der Prüfung landet wieder beim Prüfling,
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

function TageTafel() {
  const { zustand, laden } = useLaden(api.ladeTage);
  const [fehler, setFehler] = useState("");

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
  return (
    <Tafel
      titel="Prüfungstage"
      beiwort={`${tage.length} ${tage.length === 1 ? "Tag" : "Tage"} · IHK Fachinformatiker Anwendungsentwicklung`}
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
        <Karte blank>
          <ul className={stil.liste}>
            {tage.map((t) => (
              <li key={t.id}>
                <Link to={`?tag=${encodeURIComponent(t.id)}`} className={stil.zeile}>
                  <span className={stil.zeilentitel}>{datum(t.datum)}</span>
                  <span className={stil.leise}>
                    {[t.ort, t.korrektor].filter(Boolean).join(" · ")}
                  </span>
                  <span className={stil.rechts}>
                    {t.anzahl_prueflinge}{" "}
                    {t.anzahl_prueflinge === 1 ? "Prüfling" : "Prüflinge"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Karte>
      )}

      <TagAnlegen
        onAnlegen={async (daten) => {
          setFehler("");
          try {
            await api.legeTagAn(daten);
            await laden();
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

// ── Ein Prüfungstag ──────────────────────────────────────────────────────────

const STATUS_WORT: Record<keyof api.Status, string> = {
  runtergeladen: "Doku geladen",
  kontrolliert: "Kontrolliert",
  abgestimmt: "Abgestimmt",
  hochgeladen: "Hochgeladen",
};

function TagTafel({ tagId }: { tagId: string }) {
  const holen = useCallback(
    (signal?: AbortSignal) => api.ladeTag(tagId, signal),
    [tagId],
  );
  const { zustand, laden } = useLaden(holen);
  const [fehler, setFehler] = useState("");
  const navigiere = useNavigate();

  if (zustand.phase === "laedt") return <Lade titel="Prüfungstag" />;
  if (zustand.phase === "fehler") {
    return (
      <Tafel titel="Prüfungstag">
        <Link to="?" className={stil.zurueck}>
          ← Alle Prüfungstage
        </Link>
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { tag, prueflinge } = zustand.daten;

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
      titel={datum(tag.datum)}
      beiwort={[tag.ort, tag.korrektor].filter(Boolean).join(" · ") || undefined}
      aktionen={
        <Knopf groesse="sm" auspraegung="leise" onClick={() => void entfernen()}>
          Tag entfernen
        </Knopf>
      }
    >
      <Link to="?" className={stil.zurueck}>
        ← Alle Prüfungstage
      </Link>
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {prueflinge.length === 0 ? (
        <Leerzustand titel="Noch keine Prüflinge">
          Trage unten die Prüflinge dieses Tages in der Reihenfolge ein, in der sie
          geprüft werden.
        </Leerzustand>
      ) : (
        <Karte blank>
          <ul className={stil.liste}>
            {prueflinge.map((p) => {
              const erledigt = (Object.keys(STATUS_WORT) as (keyof api.Status)[]).filter(
                (k) => p.status[k],
              );
              return (
                <li key={p.id}>
                  <Link
                    to={`?pruefling=${encodeURIComponent(p.id)}`}
                    className={stil.zeile}
                  >
                    <span className={stil.zeilentitel}>
                      {p.reihenfolge}. {p.name}
                    </span>
                    <span className={stil.leise}>
                      {[p.ident, p.korrekturart, ...erledigt.map((k) => STATUS_WORT[k])]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    <span className={stil.rechts}>
                      Doku {punkte(p.doku_punkte)} P ({note(p.doku_note)}) · Präs.{" "}
                      {punkte(p.praesi_punkte)} P ({note(p.praesi_note)})
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Karte>
      )}

      <PrueflingAnlegen
        onAnlegen={async (name) => {
          setFehler("");
          try {
            await api.legePrueflingAn(tag.id, name);
            await laden();
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
