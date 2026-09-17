import { useEffect, useState } from "react";

import { Etikett, Hinweis, Karte, Leerzustand, Platzhalter } from "../../ui";
import { type Regel, ladeRegeln, schalteRegel } from "./api";
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
 * Was ihm gehört, ist der Schalter: eine abgeschaltete Regel meldet nichts
 * mehr. Geprüft wird das im Prüfdienst, der hier nachliest.
 */
export function RegelnTafel() {
  const [regeln, setRegeln] = useState<Regel[] | null>(null);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    ladeRegeln(controller.signal)
      .then(setRegeln)
      .catch((f: unknown) => {
        if (!controller.signal.aborted) setFehler(meldung(f));
      });
    return () => controller.abort();
  }, []);

  async function umschalten(regel: Regel) {
    setFehler("");
    try {
      const danach = await schalteRegel(regel.id, !regel.aktiv);
      setRegeln((alt) => alt?.map((r) => (r.id === danach.id ? danach : r)) ?? alt);
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

      <ul className={stil.liste} aria-label="Regeln">
        {regeln.map((r) => (
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
            </Karte>
          </li>
        ))}
      </ul>
    </>
  );
}
