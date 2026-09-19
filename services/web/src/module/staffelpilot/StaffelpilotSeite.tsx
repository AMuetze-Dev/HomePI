import { useCallback, useEffect, useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  entscheide,
  hakeAb,
  ladeSpiel,
  ladeStaffeln,
  legeVorgangAn,
  nimmEntscheidungZurueck,
  ladeWarteschlange,
  ladeZusammenfassung,
  aendereStaffel,
  legeStaffelAn,
  loescheStaffel,
  loeseHaken,
  type Befund,
  type Schwere,
  type Spiel,
  type SpielZeile,
  type Staffel,
  type Zusammenfassung,
} from "./api";
import { alsDatum } from "./datum";
import { EinstellungenTafel } from "./EinstellungenTafel";
import { ErgebnisseTafel } from "./ErgebnisseTafel";
import { PrueflaufTafel } from "./PrueflaufTafel";
import { StaffelnTafel } from "./StaffelnTafel";
import { UebersichtTafel } from "./UebersichtTafel";
import { ZugangKarte } from "./ZugangKarte";
import { RegelnTafel } from "./RegelnTafel";
import { VorgaengeTafel } from "./VorgaengeTafel";
import stil from "./StaffelpilotSeite.module.css";

type Daten = { staffeln: Staffel[]; spiele: SpielZeile[]; uebersicht: Zusammenfassung };

/**
 * Vier Flaechen, und die erste ist die taegliche Arbeit.
 *
 * Reiter und keine Unterseiten: ein Staffelleiter springt zwischen Befund und
 * Entwurf hin und her, und jeder Seitenwechsel waere ein neuer Ladevorgang
 * samt verlorener Stelle in der Liste.
 */
const REITER = [
  ["uebersicht", "Übersicht"],
  ["spiele", "Spielprüfung"],
  ["prueflauf", "Prüflauf"],
  ["ergebnisse", "Ergebnisse"],
  ["staffeln", "Staffeln"],
  ["vorgaenge", "Vorgänge"],
  ["regeln", "Regeln"],
  ["einstellungen", "Einstellungen"],
  ["zugang", "DFBnet-Zugang"],
] as const;

type ReiterId = (typeof REITER)[number][0];

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
  const [reiter, setReiter] = useState<ReiterId>("uebersicht");
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  const [staffelFilter, setStaffelFilter] = useState<string>("");
  // Der haeufigste Handgriff am Montag: was ist seit dem Wochenende faellig.
  const [nurFaellig, setNurFaellig] = useState(false);
  const [offenesSpiel, setOffenesSpiel] = useState<Spiel | null>(null);
  // Getrennt vom Ladezustand: ein Fehler beim Abhaken darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState<string>("");

  const laden = useCallback(
    async (staffelId: string, faellig: boolean, signal?: AbortSignal) => {
      try {
        const [staffeln, spiele, uebersicht] = await Promise.all([
          ladeStaffeln(signal),
          ladeWarteschlange(staffelId || undefined, signal, faellig),
          ladeZusammenfassung(signal),
        ]);
        setZustand({ phase: "fertig", daten: { staffeln, spiele, uebersicht } });
      } catch (fehler) {
        if (signal?.aborted) return;
        setZustand({ phase: "fehler", nachricht: meldung(fehler) });
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    void laden(staffelFilter, nurFaellig, controller.signal);
    return () => controller.abort();
  }, [laden, staffelFilter, nurFaellig]);

  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden(staffelFilter, nurFaellig);
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

  const leiste = (
    <div className={stil.reiter} role="tablist" aria-label="Bereiche">
      {REITER.map(([id, wort]) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={reiter === id}
          className={reiter === id ? stil.reiterAktiv : stil.reiterKnopf}
          onClick={() => setReiter(id)}
        >
          {wort}
        </button>
      ))}
    </div>
  );

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

  const { staffeln, spiele } = zustand.daten;

  if (reiter === "uebersicht") {
    return (
      <>
        {leiste}
        <UebersichtTafel onWechsel={(ziel) => setReiter(ziel as ReiterId)} />
      </>
    );
  }

  if (reiter === "einstellungen") {
    return (
      <>
        {leiste}
        <EinstellungenTafel />
      </>
    );
  }

  if (reiter === "zugang") {
    return (
      <>
        {leiste}
        <ZugangKarte />
      </>
    );
  }

  if (reiter === "staffeln") {
    return (
      <>
        {leiste}
        {aktionsfehler && (
          <Hinweis ton="fehler" dringend>
            {aktionsfehler}
          </Hinweis>
        )}
        <StaffelnTafel
          staffeln={staffeln}
          onAnlegen={(daten) => mitFehlerbehandlung(() => legeStaffelAn(daten))}
          onAendern={(id, daten) => mitFehlerbehandlung(() => aendereStaffel(id, daten))}
          onLoeschen={(id) => mitFehlerbehandlung(() => loescheStaffel(id))}
        />
      </>
    );
  }

  if (reiter === "ergebnisse") {
    return (
      <>
        {leiste}
        <ErgebnisseTafel staffeln={staffeln} />
      </>
    );
  }

  if (reiter === "prueflauf") {
    return (
      <>
        {leiste}
        <PrueflaufTafel
          staffeln={staffeln}
          onFertig={() => void laden(staffelFilter, nurFaellig)}
        />
      </>
    );
  }

  if (reiter === "regeln") {
    return (
      <>
        {leiste}
        <RegelnTafel />
      </>
    );
  }

  if (reiter === "vorgaenge") {
    return (
      <>
        {leiste}
        <VorgaengeTafel />
      </>
    );
  }

  return (
    <>
      {leiste}

      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {staffeln.length === 0 ? (
        <Leerzustand
          titel="Noch keine Staffel angelegt"
          aktion={<Knopf onClick={() => setReiter("staffeln")}>Staffeln verwalten</Knopf>}
        >
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

          <div className={stil.filterZeile}>
            <Knopf
              groesse="sm"
              auspraegung={nurFaellig ? "primaer" : "leise"}
              aria-pressed={nurFaellig}
              onClick={() => {
                setOffenesSpiel(null);
                setNurFaellig(!nurFaellig);
              }}
            >
              Nur fällige
            </Knopf>
          </div>

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
                    onEntwurf={(befundId) =>
                      nachAktion(zeile.id, () => legeVorgangAn(befundId))
                    }
                    onZuruecknehmen={(befundId) =>
                      nachAktion(zeile.id, () => nimmEntscheidungZurueck(befundId))
                    }
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
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
  onEntwurf,
  onZuruecknehmen,
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
  onEntwurf: (befundId: string) => Promise<boolean>;
  onZuruecknehmen: (befundId: string) => Promise<boolean>;
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
          {!zeile.faellig && !zeile.abgehakt && (
            <Etikett>außerhalb des Prüfzeitraums</Etikett>
          )}
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
                  <BefundZeile
                    befund={b}
                    onEntscheiden={onEntscheiden}
                    onEntwurf={onEntwurf}
                    onZuruecknehmen={onZuruecknehmen}
                  />
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

const WEG_WORT = {
  mahnung: "Mahnung entwerfen",
  sportgericht: "Antrag entwerfen",
} as const;

function BefundZeile({
  befund,
  onEntscheiden,
  onEntwurf,
  onZuruecknehmen,
}: {
  befund: Befund;
  onEntscheiden: (
    befundId: string,
    art: "kenntnis" | "verworfen",
    grund: string,
  ) => Promise<boolean>;
  onEntwurf: (befundId: string) => Promise<boolean>;
  onZuruecknehmen: (befundId: string) => Promise<boolean>;
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
          <div className={stil.entschieden}>
            <p className={stil.erledigt}>
              {befund.entscheidung === "kenntnis" ? "Zur Kenntnis genommen" : "Verworfen"}
              {befund.grund && `: ${befund.grund}`}
            </p>
            {/* Wer sich vertippt hat, soll das geradeziehen können, ohne den
                Bericht neu einzuspielen. Der Haken fällt dabei mit. */}
            <Knopf
              groesse="sm"
              auspraegung="leise"
              onClick={() => void onZuruecknehmen(befund.id)}
            >
              Zurücknehmen
            </Knopf>
          </div>
        )}

        {befund.weg !== "kein" &&
          (befund.vorgang_id === null ? (
            <div className={stil.knoepfe}>
              <Knopf
                groesse="sm"
                auspraegung="sekundaer"
                onClick={() => void onEntwurf(befund.id)}
              >
                {WEG_WORT[befund.weg]}
              </Knopf>
            </div>
          ) : (
            <p className={stil.erledigt}>
              Entwurf angelegt — steht unter „Vorgänge". Verschickt wird er dort nicht,
              sondern von Hand.
            </p>
          ))}
      </div>
    </Karte>
  );
}
