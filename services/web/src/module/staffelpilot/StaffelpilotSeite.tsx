import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Reihe,
  Segmentwahl,
  Statuspunkt,
  Tabelle,
  Tafel,
  Zelle,
} from "../../ui";
import {
  entscheide,
  hakeAb,
  ladeEinrichtung,
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
  type Einrichtungsstand,
  type Schwere,
  type Spiel,
  type SpielZeile,
  type Staffel,
  type Zusammenfassung,
} from "./api";
import { alsDatum } from "./datum";
import { Einrichtung } from "./Einrichtung";
import { EinstellungenTafel } from "./EinstellungenTafel";
import { ErgebnisseTafel } from "./ErgebnisseTafel";
import { PrueflaufTafel } from "./PrueflaufTafel";
import { StaffelnTafel } from "./StaffelnTafel";
import { UebersichtTafel } from "./UebersichtTafel";
import { ZugangKarte } from "./ZugangKarte";
import { RegeldateienTafel } from "./RegeldateienTafel";
import { RegelnTafel } from "./RegelnTafel";
import { VorgaengeTafel } from "./VorgaengeTafel";
import type { ModulProps } from "../typen";
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

const WELCHE = [
  { wert: "alle", wort: "Alle" },
  { wert: "faellig", wort: "Nur fällige" },
] as const;

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/**
 * Neun Bereiche - und keiner davon eine eigene Seite im alten Sinn.
 *
 * Welche Bereiche es gibt, steht in `src/module/register.ts`; die Huelle
 * navigiert sie. Hierher kommt nur noch, welcher gerade dran ist.
 *
 * Wichtig dabei: Diese Komponente bleibt ueber allen Bereichen montiert.
 * Staffeln, Spielliste und Zusammenfassung werden einmal geladen und
 * ueberstehen jeden Wechsel - ein Staffelleiter springt zwischen Befund
 * und Entwurf hin und her, und ein Ladebalken bei jedem Sprung waere
 * genau das, was diese Ansicht unbrauchbar machte.
 */
export function StaffelpilotSeite({ unterseite = "uebersicht" }: ModulProps) {
  const navigate = useNavigate();
  // Gibt bewusst nichts zurueck: navigate() liefert ein Promise, und das in
  // einem onClick landen zu lassen heisst, einen Fehlschlag stillschweigend
  // zu verlieren.
  const gehe = (ziel: string): void => {
    void navigate(`/modul/staffelpilot/${ziel}`);
  };
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  // `null` heisst "weiss ich noch nicht" und nicht "alles in Ordnung": solange
  // der Stand nicht da ist, wird niemand irgendwohin geschickt.
  const [einrichtung, setEinrichtung] = useState<Einrichtungsstand | null>(null);
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

  // Ohne DFBnet-Zugang und ohne Staffel bleibt jede Liste leer -- vorher stand
  // dort "keine Spielberichte" und gemeint war "nicht eingerichtet". Deshalb
  // einmal fragen, wo die Einrichtung steht.
  useEffect(() => {
    const controller = new AbortController();
    ladeEinrichtung(controller.signal)
      .then(setEinrichtung)
      .catch(() => {
        // Stumm: eine frisch eingerichtete Anlage soll an einem Fehler dieses
        // Abrufs nicht scheitern. Fehlt die Antwort, fuehrt eben niemand.
      });
    return () => controller.abort();
  }, []);

  // Nur von der Startflaeche aus und nur einmal: wer einen Bereich ansteuert,
  // wollte dorthin. Ein Weg, der jeden Aufruf abfaengt, ist eine Falle.
  useEffect(() => {
    if (einrichtung === null || einrichtung.schritt === "fertig") return;
    if (unterseite !== "uebersicht") return;
    void navigate("/modul/staffelpilot/einrichten", { replace: true });
  }, [einrichtung, unterseite, navigate]);

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

  if (unterseite === "einrichten") {
    return (
      <Einrichtung
        onFertig={() => {
          setEinrichtung((vorher) =>
            vorher === null ? vorher : { ...vorher, erledigt: true, schritt: "fertig" },
          );
          void laden(staffelFilter, nurFaellig);
          gehe("spiele");
        }}
      />
    );
  }

  if (unterseite === "uebersicht") {
    return <UebersichtTafel onWechsel={gehe} />;
  }

  if (unterseite === "einstellungen") {
    return <EinstellungenTafel />;
  }

  if (unterseite === "zugang") {
    return <ZugangKarte />;
  }

  if (unterseite === "staffeln") {
    return (
      <>
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

  if (unterseite === "ergebnisse") {
    return <ErgebnisseTafel staffeln={staffeln} />;
  }

  if (unterseite === "prueflauf") {
    return (
      <PrueflaufTafel
        staffeln={staffeln}
        onFertig={() => void laden(staffelFilter, nurFaellig)}
      />
    );
  }

  if (unterseite === "regeldateien") {
    return <RegeldateienTafel />;
  }

  if (unterseite === "regeln") {
    return <RegelnTafel />;
  }

  if (unterseite === "vorgaenge") {
    return <VorgaengeTafel />;
  }

  if (staffeln.length === 0) {
    return (
      <Tafel titel="Spielprüfung">
        <Leerzustand
          titel="Noch keine Staffel angelegt"
          aktion={<Knopf onClick={() => gehe("staffeln")}>Staffeln verwalten</Knopf>}
        >
          Eine Staffel ist der Ort, an dem Spielberichte ankommen. Leg die erste an — Name
          und Spielklasse genau so, wie sie in DFBnet heißen.
        </Leerzustand>
      </Tafel>
    );
  }

  const wartend = spiele.filter((s) => !s.abgehakt).length;
  const faellige = spiele.filter((s) => s.faellig && !s.abgehakt).length;

  return (
    <Tafel
      titel="Spielprüfung"
      beiwort={
        spiele.length === 0
          ? undefined
          : `${wartend} ${wartend === 1 ? "Bericht wartet" : "Berichte warten"} · ${faellige} fällig`
      }
      aktionen={
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

          {/* Eine Auswahl, kein Schalter.
              "Nur fällige" stand hier einmal allein und war im Aus-Zustand
              von Fliesstext nicht zu unterscheiden -- man sah ihm weder an,
              dass man ihn druecken kann, noch ob er an ist. Danach standen
              hier zwei Knoepfe mit `aria-pressed`, was dasselbe meinte wie
              die Segmentwahl der Einstellungen, es aber von Hand nachbaute:
              ohne Pfeiltasten, ohne Gruppenansage. Jetzt dasselbe Bauteil. */}
          <Segmentwahl
            beschriftung="Welche Spiele"
            optionen={WELCHE}
            wert={nurFaellig ? "faellig" : "alle"}
            beiWahl={(wahl) => {
              setOffenesSpiel(null);
              setNurFaellig(wahl === "faellig");
            }}
          />
        </>
      }
    >
      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {spiele.length === 0 ? (
        <Leerzustand titel="Keine Spielberichte">
          Geprüfte Spielberichte kommen über <code>POST /staffelpilot/import</code>{" "}
          herein. Die DFBnet-Automation läuft als eigener Dienst und schiebt sie dorthin.
        </Leerzustand>
      ) : (
        <Tabelle
          beschriftung="Spielberichte"
          raster="1.7fr 0.6fr 1.2fr 0.8fr 0.7fr"
          spalten={["Paarung", "Ergebnis", "Befunde", "Angesetzt", "Stand"]}
          rechtsBuendig
        >
          {spiele.map((zeile) => (
            <SpielReihe
              key={zeile.id}
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
          ))}
        </Tabelle>
      )}
    </Tafel>
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
  // Keine Karte mehr drumherum: Der Filter gehoert in die Titelzeile, zu den
  // anderen Filtern. Als eigene Karte darueber war er eine Flaeche fuer ein
  // Auswahlfeld - und stand dabei zwischen Titel und Liste.
  return (
    <label className={stil.wahl}>
      <span className="nur-vorlesen">Staffel</span>
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
  );
}

/**
 * Eine Zeile der Spielprüfung — und darunter, aufgeklappt, der Bericht.
 *
 * Aufklappen und nicht wegnavigieren: Ein Staffelleiter arbeitet die Liste
 * von oben nach unten ab, und jeder Sprung auf eine eigene Seite kostet den
 * Platz in der Liste. Dass die Reihe dabei schmal bleibt und der Bericht
 * darunter aufgeht, ist der Unterschied zu einer Karte je Zeile: Zwanzig
 * zugeklappte Karten sind zwanzig Kästen, zwanzig zugeklappte Reihen sind
 * eine Liste.
 */
function SpielReihe({
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
    <Reihe
      betont={zeile.faellig && !zeile.abgehakt}
      leise={zeile.abgehakt || !zeile.faellig}
      onKlick={onOeffnen}
      offen={!!offen}
      ausklappung={
        <div className={stil.detail}>
          {offen?.befunde.length === 0 ? (
            <p className={stil.sauber}>
              Keine Befunde — alle Prüfschritte sind sauber gelaufen.
            </p>
          ) : (
            <ul className={stil.befunde} aria-label="Befunde">
              {offen?.befunde.map((b) => (
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
      }
    >
      <Zelle>
        {zeile.heim} – {zeile.gast}
      </Zelle>

      <Zelle leise>{zeile.ergebnis}</Zelle>

      {/* Schwere UND Stand, beides nebeneinander.
          Zwischendurch stand hier nur das eine von beiden: bei einem
          kritischen Befund verschwand damit die Auskunft, ob er schon
          entschieden ist - und das ist genau die Frage, mit der man die
          Zeile ansieht. Die Zahl steht jeweils im Text und nicht nur in der
          Farbe: "2 offen" sagt auch dann etwas, wenn weder Punkt noch
          Etikett ankommt. */}
      <Zelle>
        {zeile.kritische_befunde > 0 && (
          <Etikett ton="fehler">{`${zeile.kritische_befunde} kritisch`}</Etikett>
        )}
        {zeile.offene_befunde > 0 && (
          <>
            <Statuspunkt ton="akzent" />
            {`${zeile.offene_befunde} offen`}
          </>
        )}
        {zeile.kritische_befunde === 0 && zeile.offene_befunde === 0 && (
          <span className={stil.ohneBefund}>ohne Befund</span>
        )}
      </Zelle>

      <Zelle leise>{alsDatum(zeile.datum)}</Zelle>

      <Zelle rechts>
        {zeile.abgehakt ? (
          <span className={stil.standLeise}>abgehakt</span>
        ) : zeile.faellig ? (
          <span className={stil.standFaellig}>fällig</span>
        ) : (
          /* Sichtbar ein Wort, vorgelesen der ganze Satz. "außerhalb des
             Prüfzeitraums" ist in einer Spalte von 80 px entweder abgeschnitten
             oder dreizeilig; "außerhalb" allein sagt einem Screenreader
             dagegen nicht, wovon. Beides getrennt kostet nichts. */
          <span className={stil.standLeise} title="außerhalb des Prüfzeitraums">
            <span aria-hidden="true">außerhalb</span>
            <span className="nur-vorlesen">außerhalb des Prüfzeitraums</span>
          </span>
        )}
      </Zelle>
    </Reihe>
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
              Entwurf angelegt — steht unter „Vorgänge“. Verschickt wird er dort nicht,
              sondern von Hand.
            </p>
          ))}
      </div>
    </Karte>
  );
}
