import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import { ladeDashboard, type Dashboard, type Spiel } from "./api";
import { erlaubnisFragen, geweckte, melden, tonVorbereiten, umschalten } from "./glocke";
import { PlanGrafik } from "./PlanGrafik";
import stil from "./TischtennisSeite.module.css";
import { seit, uhrzeit } from "./zeit";

/** Alle fünf Sekunden. Ein Ballwechsel dauert länger. */
const TAKT = 5000;

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Dashboard }
  | { phase: "fehler"; nachricht: string };

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

function istGeweckt(spiel: Spiel, glocken: string[]): boolean {
  return [spiel.heim_id, spiel.gast_id].some((id) => id !== null && glocken.includes(id));
}

/**
 * Die öffentliche Ansicht. Ohne Anmeldung erreichbar.
 *
 * Sie fragt im Takt nach, statt auf eine Verbindung zu warten: ein
 * Server-Sent-Event-Strom wäre sparsamer und bräuchte eine Verbindung je
 * Zuschauer, die über den Reverse Proxy und den Schlafmodus eines Handys
 * hinweg offen bleiben müsste. Bei zwanzig Zuschauern und einem Abruf alle
 * fünf Sekunden sind das vier Anfragen pro Sekunde - das merkt ein Pi 5
 * nicht.
 */
export function DashboardTafel({ turnierId }: { turnierId?: string | undefined }) {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  const [glocken, setGlocken] = useState<string[]>(() => geweckte());
  const [erlaubnis, setErlaubnis] = useState(false);
  // Je Spiel nur einmal läuten - sonst klingelt es im Fünf-Sekunden-Takt
  // weiter, solange das Spiel vor dem eigenen läuft.
  const gemeldet = useRef<Set<string>>(new Set());

  const holen = useCallback(
    async (signal: AbortSignal) => {
      try {
        const daten = await ladeDashboard(turnierId, signal);
        setZustand({ phase: "fertig", daten });
      } catch (fehler) {
        if (signal.aborted) return;
        // Eine abgerissene Abfrage darf eine stehende Anzeige nicht gegen
        // eine Fehlerseite tauschen: im Saal ist das WLAN mal weg, und der
        // Spielstand von vor fünf Sekunden ist besser als nichts.
        setZustand((vorher) =>
          vorher.phase === "fertig"
            ? vorher
            : { phase: "fehler", nachricht: meldung(fehler) },
        );
      }
    },
    [turnierId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void holen(controller.signal);
    const uhr = window.setInterval(() => void holen(controller.signal), TAKT);
    return () => {
      controller.abort();
      window.clearInterval(uhr);
    };
  }, [holen]);

  // useMemo, damit der Effekt darunter an neuen Daten haengt und nicht an
  // jedem Rendern: sonst lief er im Sekundentakt ohne neuen Anlass.
  const faellig = useMemo(
    () =>
      zustand.phase === "fertig"
        ? zustand.daten.naechste.filter(
            (spiel) => spiel.gleich_dran && istGeweckt(spiel, glocken),
          )
        : [],
    [zustand, glocken],
  );

  useEffect(() => {
    faellig.forEach((spiel) => {
      if (gemeldet.current.has(spiel.id)) return;
      gemeldet.current.add(spiel.id);
      melden(
        "Gleich bist du dran",
        `${spiel.heim ?? "?"} gegen ${spiel.gast ?? "?"} an Tisch ${spiel.tisch ?? "?"}`,
      );
    });
  }, [faellig]);

  async function glockeUmschalten(wer: string) {
    // Im Klick, nicht beim Laden: nur so lässt der Browser später Ton zu.
    tonVorbereiten();
    const neu = umschalten(glocken, wer);
    setGlocken(neu);
    if (neu.includes(wer)) setErlaubnis(await erlaubnisFragen());
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Turnierstand wird geladen">
        <Platzhalter breite="100%" hoehe="9rem" />
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

  const { daten } = zustand;

  if (daten.turnier === null) {
    return (
      <Leerzustand titel="Gerade läuft kein Turnier">
        Sobald der Spielplan ausgewürfelt ist, steht hier, wer an welchem Tisch spielt und
        wer als nächstes dran ist.
      </Leerzustand>
    );
  }

  return (
    <div className={stil.dashboard}>
      <section aria-labelledby="tische">
        <div className={stil.abschnittskopf}>
          <h2 id="tische" className={stil.abschnittstitel}>
            An den Tischen
          </h2>
        </div>
        <div className={stil.tische}>
          {daten.tische.map((tisch) => (
            <Karte key={tisch.tisch}>
              <div className={stil.tischkopf}>
                <span className={stil.tischname}>Tisch {tisch.tisch}</span>
                {tisch.laeuft ? (
                  <Etikett ton="gut">läuft</Etikett>
                ) : (
                  <Etikett ton="neutral">frei</Etikett>
                )}
              </div>

              {tisch.laeuft ? (
                <div className={stil.laufend}>
                  <div className={stil.paarung}>
                    <span className={stil.spielername}>{tisch.laeuft.heim}</span>
                    <span className={stil.gegen}>gegen</span>
                    <span className={stil.spielername}>{tisch.laeuft.gast}</span>
                  </div>
                  <p className={stil.nebensache}>
                    {tisch.laeuft.bezeichnung}
                    {seit(tisch.laeuft.begonnen_am) !== null &&
                      ` · läuft seit ${seit(tisch.laeuft.begonnen_am)} min`}
                  </p>
                </div>
              ) : (
                <p className={stil.nebensache}>Kein Spiel angepfiffen.</p>
              )}

              {/* Die Warteschlange dieses Tisches. Eine zweite, globale
                  Liste „Als nächstes“ stand hier früher darunter und sagte
                  bei einem Tisch genau dasselbe - zweimal dieselbe Auskunft
                  ist eine zu viel, und sie kostete einen halben Bildschirm. */}
              {tisch.danach.length > 0 && (
                <ol className={stil.danach}>
                  {tisch.danach.map((spiel) => (
                    <li key={spiel.id}>
                      <span className={stil.paarungZeile}>
                        {spiel.heim ?? spiel.heim_herkunft} gegen{" "}
                        {spiel.gast ?? spiel.gast_herkunft}
                        {istGeweckt(spiel, glocken) && (
                          <span aria-label="Glocke an" title="Glocke an">
                            {" "}
                            🔔
                          </span>
                        )}
                      </span>
                      <span className={stil.nebensache}>
                        {spiel.gleich_dran
                          ? "gleich dran"
                          : `ab ${uhrzeit(spiel.erwartet_ab)}`}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Karte>
          ))}
        </div>
      </section>

      <PlanGrafik tabellen={daten.tabellen} spiele={daten.spiele} />

      {/* Zugeklappt, weil beides Nachschlagewerk ist: man braucht es, wenn
          man es braucht, und sonst nimmt es Platz vor dem weg, was gerade
          passiert. */}
      <details className={stil.klappe}>
        <summary className={stil.klappengriff}>
          Glocke
          <span className={stil.nebensache}>
            {glocken.length > 0
              ? ` · ${glocken.length} aktiv`
              : " · benachrichtigt werden"}
          </span>
        </summary>
        <div className={stil.klappeninhalt}>
          <p className={stil.nebensache}>
            Tippe deinen Namen an. Sobald das Spiel vor deinem beginnt, meldet sich dieses
            Gerät – mit Ton und, wenn du es erlaubst, als Benachrichtigung. Das gilt nur
            hier und nur, solange diese Seite geöffnet ist.
          </p>
          <ul className={stil.glocken}>
            {daten.teilnehmer.map((wer) => (
              <li key={wer.id}>
                <Knopf
                  groesse="sm"
                  auspraegung={glocken.includes(wer.id) ? "primaer" : "sekundaer"}
                  aria-pressed={glocken.includes(wer.id)}
                  onClick={() => void glockeUmschalten(wer.id)}
                >
                  {glocken.includes(wer.id) ? `🔔 ${wer.name}` : wer.name}
                </Knopf>
              </li>
            ))}
          </ul>
          {glocken.length > 0 && !erlaubnis && (
            <p className={stil.nebensache}>
              Ohne erteilte Erlaubnis erscheint die Meldung nur auf dieser Seite.
            </p>
          )}
        </div>
      </details>

      {daten.letzte.length > 0 && (
        <details className={stil.klappe}>
          <summary className={stil.klappengriff}>
            Zuletzt gespielt
            <span className={stil.nebensache}>
              {` · ${daten.letzte.length} ${daten.letzte.length === 1 ? "Ergebnis" : "Ergebnisse"}`}
            </span>
          </summary>
          <ol className={stil.liste}>
            {daten.letzte.map((spiel) => (
              <li key={spiel.id} className={stil.zeile}>
                <span
                  className={spiel.sieger_id === spiel.heim_id ? stil.sieger : undefined}
                >
                  {spiel.heim}
                </span>
                <span className={stil.gegen}>gegen</span>
                <span
                  className={spiel.sieger_id === spiel.gast_id ? stil.sieger : undefined}
                >
                  {spiel.gast}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}

      <p className={stil.stand}>
        Stand {uhrzeit(daten.stand)} · aktualisiert sich alle {TAKT / 1000} Sekunden
      </p>
    </div>
  );
}
