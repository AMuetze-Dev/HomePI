import { useCallback, useEffect, useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  entscheide,
  hakeAb,
  ladeSpiel,
  ladeStaffeln,
  ladeWarteschlange,
  ladeZusammenfassung,
  legeStaffelAn,
  loeseHaken,
  type Befund,
  type Schwere,
  type Spiel,
  type SpielZeile,
  type Staffel,
  type Zusammenfassung,
} from "./api";
import { alsDatum } from "./datum";
import stil from "./StaffelpilotSeite.module.css";

type Daten = { staffeln: Staffel[]; spiele: SpielZeile[]; uebersicht: Zusammenfassung };

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

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

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

export function StaffelpilotSeite() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  const [staffelFilter, setStaffelFilter] = useState<string>("");
  const [offenesSpiel, setOffenesSpiel] = useState<Spiel | null>(null);
  // Getrennt vom Ladezustand: ein Fehler beim Abhaken darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState<string>("");

  const laden = useCallback(async (staffelId: string, signal?: AbortSignal) => {
    try {
      const [staffeln, spiele, uebersicht] = await Promise.all([
        ladeStaffeln(signal),
        ladeWarteschlange(staffelId || undefined, signal),
        ladeZusammenfassung(signal),
      ]);
      setZustand({ phase: "fertig", daten: { staffeln, spiele, uebersicht } });
    } catch (fehler) {
      if (signal?.aborted) return;
      setZustand({ phase: "fehler", nachricht: meldung(fehler) });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(staffelFilter, controller.signal);
    return () => controller.abort();
  }, [laden, staffelFilter]);

  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden(staffelFilter);
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  async function oeffnen(zeile: SpielZeile) {
    if (offenesSpiel?.id === zeile.id) {
      setOffenesSpiel(null);
      return;
    }
    setAktionsfehler("");
    try {
      setOffenesSpiel(await ladeSpiel(zeile.id));
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
    }
  }

  async function nachAktion(spielId: string, aktion: () => Promise<unknown>) {
    const geklappt = await mitFehlerbehandlung(aktion);
    // Auch wenn es schiefging: der Stand kann sich geaendert haben, und ein
    // veralteter Befund ist schlimmer als ein zweiter Ladevorgang.
    try {
      setOffenesSpiel(await ladeSpiel(spielId));
    } catch {
      setOffenesSpiel(null);
    }
    return geklappt;
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Spielberichte werden geladen">
        <Platzhalter breite="100%" hoehe="5rem" />
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

  const { staffeln, spiele, uebersicht } = zustand.daten;

  return (
    <>
      <Uebersicht daten={uebersicht} />

      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {staffeln.length === 0 ? (
        <Leerzustand titel="Noch keine Staffel angelegt">
          Eine Staffel ist der Ort, an dem Spielberichte ankommen. Leg die erste an — Name
          und Spielklasse genau so, wie sie in DFBnet heißen.
        </Leerzustand>
      ) : (
        <>
          {staffeln.length > 1 && (
            <StaffelWahl
              staffeln={staffeln}
              gewaehlt={staffelFilter}
              onWahl={(id) => {
                setOffenesSpiel(null);
                setStaffelFilter(id);
              }}
            />
          )}

          {spiele.length === 0 ? (
            <Leerzustand titel="Keine Spielberichte">
              Geprüfte Spielberichte kommen über <code>POST /staffelpilot/import</code>{" "}
              herein. Die DFBnet-Automation läuft als eigener Dienst und schiebt sie
              dorthin.
            </Leerzustand>
          ) : (
            <ul className={stil.liste} aria-label="Spielberichte">
              {spiele.map((zeile) => (
                <li key={zeile.id}>
                  <SpielKarte
                    zeile={zeile}
                    offen={offenesSpiel?.id === zeile.id ? offenesSpiel : null}
                    onOeffnen={() => void oeffnen(zeile)}
                    onEntscheiden={(befundId, art, grund) =>
                      nachAktion(zeile.id, () => entscheide(befundId, art, grund))
                    }
                    onAbhaken={() =>
                      void nachAktion(zeile.id, () =>
                        zeile.abgehakt ? loeseHaken(zeile.id) : hakeAb(zeile.id),
                      )
                    }
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <StaffelAnlegen
        onAnlegen={(daten) => mitFehlerbehandlung(() => legeStaffelAn(daten))}
      />
    </>
  );
}

function Uebersicht({ daten }: { daten: Zusammenfassung }) {
  return (
    <ul className={stil.kennzahlen} aria-label="Überblick">
      <Kennzahl wert={daten.offen} name="zu prüfen" />
      <Kennzahl wert={daten.befunde_kritisch} name="kritische Befunde" ton="fehler" />
      <Kennzahl wert={daten.befunde_offen} name="offene Befunde" />
      <Kennzahl wert={daten.abgehakt} name="abgehakt" />
    </ul>
  );
}

function Kennzahl({ wert, name, ton }: { wert: number; name: string; ton?: "fehler" }) {
  return (
    <li className={stil.kennzahl}>
      <span className={ton && wert > 0 ? stil.zahlWarnend : stil.zahl}>{wert}</span>
      <span className={stil.zahlName}>{name}</span>
    </li>
  );
}

function StaffelWahl({
  staffeln,
  gewaehlt,
  onWahl,
}: {
  staffeln: Staffel[];
  gewaehlt: string;
  onWahl: (id: string) => void;
}) {
  return (
    <Karte>
      <label className={stil.wahl}>
        <span className={stil.wahlName}>Staffel</span>
        <select
          className={stil.auswahl}
          value={gewaehlt}
          onChange={(e) => onWahl(e.target.value)}
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
  );
}

function SpielKarte({
  zeile,
  offen,
  onOeffnen,
  onEntscheiden,
  onAbhaken,
}: {
  zeile: SpielZeile;
  offen: Spiel | null;
  onOeffnen: () => void;
  onEntscheiden: (
    befundId: string,
    art: "kenntnis" | "verworfen",
    grund: string,
  ) => Promise<boolean>;
  onAbhaken: () => void;
}) {
  return (
    <Karte>
      <button
        type="button"
        className={stil.kopf}
        onClick={onOeffnen}
        aria-expanded={!!offen}
      >
        <span className={stil.paarung}>
          {zeile.heim} – {zeile.gast}
        </span>
        <span className={stil.zeile}>
          <span className={stil.datum}>{alsDatum(zeile.datum)}</span>
          {zeile.ergebnis && <span className={stil.datum}>{zeile.ergebnis}</span>}
          {zeile.abgehakt && <Etikett ton="gut">abgehakt</Etikett>}
          {zeile.kritische_befunde > 0 && (
            <Etikett ton="fehler">{zeile.kritische_befunde} kritisch</Etikett>
          )}
          {zeile.offene_befunde > 0 && (
            <Etikett ton="warnung">{zeile.offene_befunde} offen</Etikett>
          )}
        </span>
      </button>

      {offen && (
        <div className={stil.detail}>
          {offen.befunde.length === 0 ? (
            <p className={stil.sauber}>
              Keine Befunde — alle Prüfschritte sind sauber gelaufen.
            </p>
          ) : (
            <ul className={stil.befunde} aria-label="Befunde">
              {offen.befunde.map((b) => (
                <li key={b.id}>
                  <BefundZeile befund={b} onEntscheiden={onEntscheiden} />
                </li>
              ))}
            </ul>
          )}

          <div className={stil.entscheidung}>
            <p className={stil.stand}>
              {zeile.offene_befunde > 0
                ? `${zeile.offene_befunde} ${
                    zeile.offene_befunde === 1 ? "Befund braucht" : "Befunde brauchen"
                  } noch eine Entscheidung`
                : zeile.abgehakt
                  ? "Spiel ist abgehakt"
                  : "Alle Befunde entschieden"}
            </p>
            <Knopf auspraegung={zeile.abgehakt ? "leise" : "primaer"} onClick={onAbhaken}>
              {zeile.abgehakt ? "Haken entfernen" : "Abhaken"}
            </Knopf>
          </div>
        </div>
      )}
    </Karte>
  );
}

function BefundZeile({
  befund,
  onEntscheiden,
}: {
  befund: Befund;
  onEntscheiden: (
    befundId: string,
    art: "kenntnis" | "verworfen",
    grund: string,
  ) => Promise<boolean>;
}) {
  const [grund, setGrund] = useState("");
  const [fragtNachGrund, setFragtNachGrund] = useState(false);

  return (
    <Karte blank>
      <div className={stil.befund}>
        <div className={stil.befundKopf}>
          <Etikett ton={TON[befund.schwere]}>{SCHWERE_WORT[befund.schwere]}</Etikett>
          <span className={stil.befundTitel}>{befund.titel}</span>
        </div>
        {befund.text && <p className={stil.befundText}>{befund.text}</p>}
        {(befund.person || befund.mannschaft) && (
          <p className={stil.befundWer}>
            {[befund.person, befund.mannschaft].filter(Boolean).join(" · ")}
          </p>
        )}

        {befund.entscheidung === "offen" ? (
          fragtNachGrund ? (
            <form
              className={stil.grundform}
              onSubmit={(e) => {
                e.preventDefault();
                void onEntscheiden(befund.id, "verworfen", grund).then((geklappt) => {
                  // Ein fehlgeschlagenes Formular behaelt seine Eingabe.
                  if (geklappt) {
                    setGrund("");
                    setFragtNachGrund(false);
                  }
                });
              }}
            >
              <Feld
                beschriftung="Warum ist das kein Verstoß?"
                hinweis="Steht später in der Akte — ein Verein fragt danach."
                value={grund}
                onChange={(e) => setGrund(e.target.value)}
              />
              <div className={stil.knoepfe}>
                <Knopf type="submit" auspraegung="primaer" groesse="sm">
                  Verwerfen
                </Knopf>
                <Knopf
                  groesse="sm"
                  auspraegung="leise"
                  onClick={() => setFragtNachGrund(false)}
                >
                  Abbrechen
                </Knopf>
              </div>
            </form>
          ) : (
            <div className={stil.knoepfe}>
              <Knopf
                groesse="sm"
                onClick={() => void onEntscheiden(befund.id, "kenntnis", "")}
              >
                Zur Kenntnis genommen
              </Knopf>
              <Knopf
                groesse="sm"
                auspraegung="leise"
                onClick={() => setFragtNachGrund(true)}
              >
                Kein Verstoß
              </Knopf>
            </div>
          )
        ) : (
          <p className={stil.erledigt}>
            {befund.entscheidung === "kenntnis" ? "Zur Kenntnis genommen" : "Verworfen"}
            {befund.grund && `: ${befund.grund}`}
          </p>
        )}
      </div>
    </Karte>
  );
}

const ALTERSKLASSEN = [
  ["maenner", "Männer"],
  ["frauen", "Frauen"],
  ["ue32", "Ü32"],
  ["ue35", "Ü35"],
  ["ue40", "Ü40"],
  ["ue50", "Ü50"],
] as const;

function StaffelAnlegen({
  onAnlegen,
}: {
  onAnlegen: (daten: {
    name: string;
    altersklasse: (typeof ALTERSKLASSEN)[number][0];
    spielklasse: string;
    saison: string;
  }) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [spielklasse, setSpielklasse] = useState("");
  const [saison, setSaison] = useState("");
  const [altersklasse, setAltersklasse] =
    useState<(typeof ALTERSKLASSEN)[number][0]>("maenner");

  return (
    <Karte>
      <form
        className={stil.formular}
        onSubmit={(e) => {
          e.preventDefault();
          void onAnlegen({ name, altersklasse, spielklasse, saison }).then((geklappt) => {
            // Nur bei Erfolg leeren - sonst tippt man alles noch einmal.
            if (geklappt) {
              setName("");
              setSpielklasse("");
              setSaison("");
            }
          });
        }}
      >
        <h2 className={stil.formularTitel}>Staffel anlegen</h2>
        <Feld
          beschriftung="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Feld
          beschriftung="Spielklasse"
          hinweis="Genau wie in DFBnet, z. B. „1.Kreisklasse“."
          value={spielklasse}
          onChange={(e) => setSpielklasse(e.target.value)}
          required
        />
        <label className={stil.wahl}>
          <span className={stil.wahlName}>Altersklasse</span>
          <select
            className={stil.auswahl}
            value={altersklasse}
            onChange={(e) =>
              setAltersklasse(e.target.value as (typeof ALTERSKLASSEN)[number][0])
            }
          >
            {ALTERSKLASSEN.map(([wert, name]) => (
              <option key={wert} value={wert}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <Feld
          beschriftung="Saison"
          hinweis="Optional, z. B. 26/27."
          value={saison}
          onChange={(e) => setSaison(e.target.value)}
        />
        <Knopf type="submit" auspraegung="primaer">
          Anlegen
        </Knopf>
      </form>
    </Karte>
  );
}
