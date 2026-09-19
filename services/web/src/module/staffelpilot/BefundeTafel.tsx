import { useCallback, useEffect, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Platzhalter } from "../../ui";
import { type BefundZeile, type Schwere, ladeAlleBefunde } from "./api";
import { alsDatum } from "./datum";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

const TON: Record<Schwere, "fehler" | "warnung" | "neutral"> = {
  kritisch: "fehler",
  warnung: "warnung",
  hinweis: "neutral",
};

const SCHWERE_WORT: Record<Schwere, string> = {
  kritisch: "kritisch",
  warnung: "Warnung",
  hinweis: "Hinweis",
};

const ENTSCHEIDUNG_WORT = {
  offen: "offen",
  kenntnis: "zur Kenntnis",
  verworfen: "verworfen",
} as const;

/**
 * Jeder Befund einzeln, über alle Spiele hinweg.
 *
 * Die Warteschlange beantwortet „was ist als Nächstes zu tun". Das hier ist
 * die andere Frage: „was ist in dieser Saison alles aufgelaufen" — beim
 * Jahresbericht, oder wenn ein Verein anruft und wissen will, wie oft.
 */
export function BefundeListe({ staffelId }: { staffelId?: string | undefined }) {
  const [zeilen, setZeilen] = useState<BefundZeile[] | null>(null);
  const [offen, setOffenAufgeklappt] = useState(false);
  const [nurOffen, setNurOffen] = useState(false);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(
    async (gewaehlt: string | undefined, nur: boolean, signal?: AbortSignal) => {
      try {
        setZeilen(await ladeAlleBefunde({ staffelId: gewaehlt, nurOffen: nur }, signal));
      } catch (f) {
        if (signal?.aborted) return;
        setFehler(meldung(f));
      }
    },
    [],
  );

  useEffect(() => {
    if (!offen) return;
    const controller = new AbortController();
    void laden(staffelId, nurOffen, controller.signal);
    return () => controller.abort();
    // Erst laden, wenn jemand hinsieht: bei dreihundert Befunden ist das
    // eine Abfrage, die auf der Ergebnisseite niemand bestellt hat.
  }, [laden, staffelId, nurOffen, offen]);

  return (
    <Karte>
      <button
        type="button"
        className={stil.kopf}
        onClick={() => setOffenAufgeklappt(!offen)}
        aria-expanded={offen}
      >
        <span className={stil.paarung}>Jeder Befund einzeln</span>
        <span className={stil.datum}>{offen ? "zuklappen" : "aufklappen"}</span>
      </button>

      {offen && (
        <div className={stil.detail}>
          <div className={stil.filterZeile}>
            <Knopf
              groesse="sm"
              auspraegung={nurOffen ? "primaer" : "leise"}
              aria-pressed={nurOffen}
              onClick={() => setNurOffen(!nurOffen)}
            >
              Nur offene
            </Knopf>
          </div>

          {fehler && (
            <Hinweis ton="fehler" dringend>
              {fehler}
            </Hinweis>
          )}

          {zeilen === null ? (
            <div role="status" aria-label="Befunde werden geladen">
              <Platzhalter breite="100%" hoehe="8rem" />
            </div>
          ) : zeilen.length === 0 ? (
            <p className={stil.vorgangHinweis}>
              {nurOffen
                ? "Zu jedem Befund liegt eine Entscheidung vor."
                : "Keine Befunde."}
            </p>
          ) : (
            <ul className={stil.liste} aria-label="Befunde">
              {zeilen.map((z) => (
                <li key={z.id}>
                  <Karte blank>
                    <div className={stil.zeile}>
                      <Etikett ton={TON[z.schwere]}>{SCHWERE_WORT[z.schwere]}</Etikett>
                      <span className={stil.paarung}>{z.titel}</span>
                    </div>
                    <p className={stil.befundWer}>
                      {z.heim} – {z.gast} · {alsDatum(z.datum)}
                      {z.person && ` · ${z.person}`}
                    </p>
                    <div className={stil.zeile}>
                      <Etikett ton={z.entscheidung === "offen" ? "warnung" : "gut"}>
                        {ENTSCHEIDUNG_WORT[z.entscheidung]}
                      </Etikett>
                      {z.vorgang_id !== null && <Etikett>Vorgang</Etikett>}
                      <Etikett mono>{z.regel}</Etikett>
                    </div>
                    {z.grund && <p className={stil.vorgangHinweis}>{z.grund}</p>}
                  </Karte>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Karte>
  );
}
