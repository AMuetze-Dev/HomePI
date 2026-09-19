import { useCallback, useEffect, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import { type BefundZeile, type Schwere, type Staffel, ladeAlleBefunde } from "./api";
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
export function BefundeTafel({ staffeln }: { staffeln: Staffel[] }) {
  const [zeilen, setZeilen] = useState<BefundZeile[] | null>(null);
  const [staffelId, setStaffelId] = useState("");
  const [nurOffen, setNurOffen] = useState(false);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(
    async (gewaehlt: string, offen: boolean, signal?: AbortSignal) => {
      try {
        setZeilen(
          await ladeAlleBefunde(
            { staffelId: gewaehlt || undefined, nurOffen: offen },
            signal,
          ),
        );
      } catch (f) {
        if (signal?.aborted) return;
        setFehler(meldung(f));
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    void laden(staffelId, nurOffen, controller.signal);
    return () => controller.abort();
  }, [laden, staffelId, nurOffen]);

  if (fehler && zeilen === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {fehler}
      </Hinweis>
    );
  }

  if (zeilen === null) {
    return (
      <div role="status" aria-label="Befunde werden geladen">
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  return (
    <>
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

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {zeilen.length === 0 ? (
        <Leerzustand titel={nurOffen ? "Nichts offen" : "Keine Befunde"}>
          {nurOffen
            ? "Zu jedem Befund liegt eine Entscheidung vor."
            : "Sobald ein Prüflauf Befunde einspielt, stehen sie hier — jeder einzeln, über alle Spiele hinweg."}
        </Leerzustand>
      ) : (
        <>
          <p className={stil.vorgangHinweis}>
            {zeilen.length} {zeilen.length === 1 ? "Befund" : "Befunde"}
          </p>
          <ul className={stil.liste} aria-label="Befunde">
            {zeilen.map((z) => (
              <li key={z.id}>
                <Karte>
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
        </>
      )}
    </>
  );
}
