import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import { ladeDashboard, type Dashboard, type Spiel } from "./api";
import { erlaubnisFragen, geweckte, melden, tonVorbereiten, umschalten } from "./glocke";
import { TabellenTafel } from "./TabellenTafel";
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
      {faellig.length > 0 && (
        <Hinweis ton="warnung" dringend>
          Gleich dran:{" "}
          {faellig
            .map((spiel) => `${spiel.heim} gegen ${spiel.gast} an Tisch ${spiel.tisch}`)
            .join(" · ")}
        </Hinweis>
      )}

      <section aria-labelledby="tische">
        <h2 id="tische" className={stil.abschnittstitel}>
          An den Tischen
        </h2>
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
                    <span className={stil.satzstand}>
                      {tisch.laeuft.saetze_heim}:{tisch.laeuft.saetze_gast}
                    </span>
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

              {tisch.danach.length > 0 && (
                <ol className={stil.danach}>
                  {tisch.danach.map((spiel) => (
                    <li key={spiel.id}>
                      <span>
                        {spiel.heim ?? spiel.heim_herkunft} gegen{" "}
                        {spiel.gast ?? spiel.gast_herkunft}
                      </span>
                      <span className={stil.nebensache}>
                        ab {uhrzeit(spiel.erwartet_ab)}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Karte>
          ))}
        </div>
      </section>

      <div className={stil.spalten}>
        <section aria-labelledby="naechste">
          <h2 id="naechste" className={stil.abschnittstitel}>
            Als nächstes
          </h2>
          {daten.naechste.length === 0 ? (
            <Leerzustand titel="Nichts mehr offen">
              {daten.fertig
                ? "Das Turnier ist durch."
                : "Die nächste Runde ist noch nicht angesetzt."}
            </Leerzustand>
          ) : (
            <Karte blank>
              <ol className={stil.liste}>
                {daten.naechste.map((spiel) => (
                  <li key={spiel.id} className={stil.zeile}>
                    <div>
                      <div className={stil.paarungZeile}>
                        {spiel.heim ?? spiel.heim_herkunft} gegen{" "}
                        {spiel.gast ?? spiel.gast_herkunft}
                        {istGeweckt(spiel, glocken) && (
                          <span aria-label="Glocke an" title="Glocke an">
                            {" "}
                            🔔
                          </span>
                        )}
                      </div>
                      <div className={stil.nebensache}>
                        {spiel.bezeichnung} · Tisch {spiel.tisch} · ab{" "}
                        {uhrzeit(spiel.erwartet_ab)}
                      </div>
                    </div>
                    {spiel.gleich_dran && <Etikett ton="warnung">gleich dran</Etikett>}
                  </li>
                ))}
              </ol>
            </Karte>
          )}
        </section>

        <section aria-labelledby="letzte">
          <h2 id="letzte" className={stil.abschnittstitel}>
            Zuletzt gespielt
          </h2>
          {daten.letzte.length === 0 ? (
            <Leerzustand titel="Noch kein Ergebnis">
              Hier stehen die Spiele, sobald das erste gewertet ist.
            </Leerzustand>
          ) : (
            <Karte blank>
              <ol className={stil.liste}>
                {daten.letzte.map((spiel) => (
                  <li key={spiel.id} className={stil.zeile}>
                    <span
                      className={
                        spiel.sieger_id === spiel.heim_id ? stil.sieger : undefined
                      }
                    >
                      {spiel.heim}
                    </span>
                    <span className={stil.satzstandKlein}>
                      {spiel.saetze_heim}:{spiel.saetze_gast}
                    </span>
                    <span
                      className={
                        spiel.sieger_id === spiel.gast_id ? stil.sieger : undefined
                      }
                    >
                      {spiel.gast}
                    </span>
                  </li>
                ))}
              </ol>
            </Karte>
          )}
        </section>
      </div>

      <section aria-labelledby="glocke">
        <h2 id="glocke" className={stil.abschnittstitel}>
          Glocke
        </h2>
        <Karte>
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
        </Karte>
      </section>

      {daten.tabellen.length > 0 && <TabellenTafel tabellen={daten.tabellen} />}

      <p className={stil.stand}>
        Stand {uhrzeit(daten.stand)} · aktualisiert sich alle {TAKT / 1000} Sekunden
      </p>
    </div>
  );
}
