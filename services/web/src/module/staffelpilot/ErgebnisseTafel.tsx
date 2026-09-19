import { useCallback, useEffect, useState } from "react";

import { Hinweis, Karte, Leerzustand, Platzhalter } from "../../ui";
import { type Auswertung, type Posten, type Staffel, ladeErgebnisse } from "./api";
import { BefundeListe } from "./BefundeTafel";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

const SCHWERE_WORT: Record<string, string> = {
  kritisch: "kritisch",
  warnung: "Warnung",
  hinweis: "Hinweis",
};

const MONATE = [
  "Januar",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
];

/** "2026-09" → "September 2026". Die Zahl allein liest niemand als Monat. */
function alsMonat(wert: string): string {
  const [jahr, monat] = wert.split("-");
  const name = MONATE[Number(monat) - 1];
  return name ? `${name} ${jahr}` : wert;
}

/**
 * Was in dieser Saison aufgelaufen ist — gezählt, nicht aufgelistet.
 *
 * Die Spielprüfung beantwortet „was ist als Nächstes zu tun". Das hier ist
 * die Frage am Saisonende und die, die ein Verein am Telefon stellt: wie
 * oft, wer, welche Regel, wann.
 */
export function ErgebnisseTafel({ staffeln }: { staffeln: Staffel[] }) {
  const [werte, setWerte] = useState<Auswertung | null>(null);
  const [staffelId, setStaffelId] = useState("");
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async (gewaehlt: string, signal?: AbortSignal) => {
    try {
      setWerte(await ladeErgebnisse(gewaehlt || undefined, signal));
    } catch (f) {
      if (signal?.aborted) return;
      setFehler(meldung(f));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(staffelId, controller.signal);
    return () => controller.abort();
  }, [laden, staffelId]);

  if (fehler && werte === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  if (werte === null) {
    return (
      <div role="status" aria-label="Ergebnisse werden geladen">
        <Platzhalter breite="100%" hoehe="14rem" />
      </div>
    );
  }

  return (
    <>
      {staffeln.length > 1 && (
        <Karte>
          <label className={stil.wahl}>
            <span className={stil.wahlName}>Staffel</span>
            <select
              className={stil.auswahl}
              value={staffelId}
              onChange={(e) => setStaffelId(e.target.value)}
            >
              <option value="">Alle Staffeln</option>
              {staffeln.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </Karte>
      )}

      <ul className={stil.kennzahlen} aria-label="Bilanz">
        <li className={stil.kennzahl}>
          <span className={stil.zahl}>{werte.spiele}</span>
          <span className={stil.zahlName}>Spiele</span>
        </li>
        <li className={stil.kennzahl}>
          <span className={stil.zahl}>{werte.abgehakt}</span>
          <span className={stil.zahlName}>abgehakt</span>
        </li>
        <li className={stil.kennzahl}>
          <span className={stil.zahl}>{werte.befunde}</span>
          <span className={stil.zahlName}>Befunde</span>
        </li>
        <li className={stil.kennzahl}>
          <span className={werte.offen > 0 ? stil.zahlWarnend : stil.zahl}>
            {werte.offen}
          </span>
          <span className={stil.zahlName}>noch offen</span>
        </li>
      </ul>

      {werte.befunde === 0 ? (
        <Leerzustand titel="Noch nichts ausgewertet">
          Sobald ein Prüflauf Befunde einspielt, steht hier, wie oft was vorgekommen ist —
          nach Schwere, Regel, Mannschaft und Monat.
        </Leerzustand>
      ) : (
        <>
          <Gruppe
            titel="Nach Schwere"
            posten={werte.nach_schwere}
            beschriften={SCHWERE_WORT}
          />
          <Gruppe titel="Nach Regel" posten={werte.nach_regel} />
          <Gruppe titel="Nach Mannschaft" posten={werte.nach_mannschaft} />
          <Gruppe titel="Im Verlauf" posten={werte.nach_monat} beschriften={alsMonat} />

          {/* Die Zahlen sagen „wie oft"; wer wissen will „welche", klappt
              die Liste auf. Beides auf einer Fläche, weil es dieselbe Frage
              in zwei Auflösungen ist. */}
          <BefundeListe staffelId={staffelId || undefined} />
        </>
      )}
    </>
  );
}

function Gruppe({
  titel,
  posten,
  beschriften,
}: {
  titel: string;
  posten: Posten[];
  beschriften?: Record<string, string> | ((wert: string) => string);
}) {
  if (posten.length === 0) return null;

  // Der längste Balken ist voll, der Rest im Verhältnis dazu. Gegen die
  // Gesamtzahl wäre bei zwanzig Regeln jeder Balken ein Strich.
  const groesster = Math.max(...posten.map((p) => p.anzahl), 1);

  function name(wert: string): string {
    if (typeof beschriften === "function") return beschriften(wert);
    return beschriften?.[wert] ?? wert;
  }

  return (
    <Karte>
      <h2 className={stil.formularTitel}>{titel}</h2>
      <ul className={stil.auswertung} aria-label={titel}>
        {posten.map((p) => (
          <li key={p.name} className={stil.auswertungZeile}>
            <span className={stil.auswertungName}>{name(p.name)}</span>
            {/* Zahl und Balken: ein Balken allein sagt nicht, wie viele. */}
            <span className={stil.auswertungZahl}>
              {p.anzahl}
              {p.offen > 0 && (
                <span className={stil.auswertungOffen}> ({p.offen} offen)</span>
              )}
            </span>
            <span
              className={stil.auswertungBalken}
              style={{ width: `${(p.anzahl / groesster) * 100}%` }}
              aria-hidden="true"
            />
          </li>
        ))}
      </ul>
    </Karte>
  );
}
