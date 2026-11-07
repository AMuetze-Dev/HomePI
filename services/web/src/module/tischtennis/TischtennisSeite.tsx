import { useCallback, useEffect, useState } from "react";

import { Anmeldeformular } from "../../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../../anmeldung/kontext";
import { Etikett, Hinweis, Karte, Leerzustand, Platzhalter } from "../../ui";
import type { ModulProps } from "../typen";
import {
  aendereTeilnehmer,
  aendereTurnier,
  beendeTurnier,
  beginneSpiel,
  entferneTeilnehmer,
  ladeSpiele,
  ladeTabellen,
  ladeTeilnehmer,
  ladeTurnier,
  ladeTurniere,
  legeTeilnehmerAn,
  legeTurnierAn,
  loescheTurnier,
  loseAus,
  naechsteRunde,
  nimmErgebnisZurueck,
  setzeZurueck,
  trageErgebnisEin,
  wuerfleAus,
  type Einstellungen,
  type NeuerTeilnehmer,
  type Satz,
  type Spiel,
  type Tabelle,
  type Teilnehmer,
  type Turnier,
} from "./api";
import { AuswuerfelnTafel } from "./AuswuerfelnTafel";
import { DashboardTafel } from "./DashboardTafel";
import { EinstellungenTafel } from "./EinstellungenTafel";
import { SpielplanTafel } from "./SpielplanTafel";
import { TabellenTafel } from "./TabellenTafel";
import { TeilnehmerTafel } from "./TeilnehmerTafel";
import stil from "./TischtennisSeite.module.css";

interface Daten {
  turniere: Turnier[];
  turnier: Turnier | null;
  teilnehmer: Teilnehmer[];
  spiele: Spiel[];
  tabellen: Tabelle[];
}

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

const LEER: Daten = {
  turniere: [],
  turnier: null,
  teilnehmer: [],
  spiele: [],
  tabellen: [],
};

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

const ZUSTANDSWORT: Record<Turnier["zustand"], string> = {
  planung: "in Planung",
  laufend: "läuft",
  beendet: "beendet",
};

/**
 * Sechs Bereiche, und einer davon ist der eigentliche Zweck.
 *
 * Welche Bereiche es gibt, steht in `src/module/register.ts`; die Hülle
 * navigiert sie. Hierher kommt nur, welcher gerade dran ist - und die Daten,
 * die alle brauchen.
 *
 * Die Dashboard-Ansicht steht bewusst an erster Stelle und holt ihre Daten
 * selbst: sie ist die einzige Fläche, die auch ohne Anmeldung funktioniert,
 * und ein Besucher ohne Konto soll nicht auf Abrufe warten, die er gar nicht
 * sieht. Alles Schreibende hängt an `darf("tischtennis", …)` - und wird im
 * Backend noch einmal geprüft.
 */
export function TischtennisSeite({ unterseite = "dashboard" }: ModulProps) {
  const { darf, zustand: anmeldung } = useAnmeldung();
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  const [gewaehlt, setGewaehlt] = useState<string>("");
  // Getrennt vom Ladezustand: ein Fehler beim Eintragen darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState("");

  const laden = useCallback(async (id: string, signal?: AbortSignal) => {
    try {
      const turniere = await ladeTurniere(signal);
      const kennung = id || turniere[0]?.id || "";
      if (kennung === "") {
        setZustand({ phase: "fertig", daten: { ...LEER, turniere } });
        return;
      }

      const [turnier, teilnehmer, spiele, tabellen] = await Promise.all([
        ladeTurnier(kennung, signal),
        ladeTeilnehmer(kennung, signal),
        ladeSpiele(kennung, signal),
        ladeTabellen(kennung, signal),
      ]);
      setZustand({
        phase: "fertig",
        daten: { turniere, turnier, teilnehmer, spiele, tabellen },
      });
    } catch (fehler) {
      if (signal?.aborted) return;
      setZustand({ phase: "fehler", nachricht: meldung(fehler) });
    }
  }, []);

  // Die Dashboard-Ansicht holt ihre Daten selbst, in einem Abruf. Hier
  // nichts zu laden ist kein Feinschliff: ein Besucher ohne Konto würde
  // sonst auf Spielplan, Tabellen und Teilnehmerliste warten, die er auf
  // dieser Fläche gar nicht sieht - vier Abfragen für nichts.
  const nurDashboard = unterseite === "dashboard";

  useEffect(() => {
    if (nurDashboard) return;
    const controller = new AbortController();
    void laden(gewaehlt, controller.signal);
    return () => controller.abort();
  }, [laden, gewaehlt, nurDashboard]);

  if (nurDashboard) {
    return <DashboardTafel turnierId={gewaehlt || undefined} />;
  }

  /** true, wenn die Aktion geklappt hat - der Aufrufer entscheidet damit,
   *  ob er sein Formular leeren darf. */
  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden(gewaehlt);
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Turnier wird geladen">
        <Platzhalter breite="14rem" hoehe="1.75rem" />
        <Platzhalter breite="100%" hoehe="12rem" />
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

  const { turniere, turnier, teilnehmer, spiele, tabellen } = zustand.daten;
  const darfSchreiben = darf("tischtennis", "nutzer");
  const darfEinrichten = darf("tischtennis", "verwalter");

  if (!darfSchreiben) {
    return (
      <>
        <Hinweis>
          Diesen Bereich führt die Turnierleitung. Der aktuelle Stand steht unter
          „Dashboard“ – dafür braucht niemand ein Konto.
        </Hinweis>
        {anmeldung === "abgemeldet" && (
          <Anmeldeformular
            titel="Anmeldung nötig"
            beschreibung="Zum Eintragen von Ergebnissen brauchst du ein Recht auf diesem Artefakt."
          />
        )}
      </>
    );
  }

  const kopf = (
    <div className={stil.kopf}>
      {turnier !== null && (
        <>
          <h2 className={stil.turniername}>{turnier.name}</h2>
          <Etikett ton={turnier.zustand === "laufend" ? "gut" : "neutral"}>
            {ZUSTANDSWORT[turnier.zustand]}
          </Etikett>
          <span className={stil.nebensache}>
            {turnier.anzahl_teilnehmer} Teilnehmer · {turnier.anzahl_spiele} Spiele ·{" "}
            {turnier.offene_spiele} offen
          </span>
        </>
      )}
      {turniere.length > 1 && (
        <label className={stil.turnierwahl}>
          Turnier
          <select value={turnier?.id ?? ""} onChange={(e) => setGewaehlt(e.target.value)}>
            {turniere.map((eintrag) => (
              <option key={eintrag.id} value={eintrag.id}>
                {eintrag.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );

  const fehlerband = aktionsfehler && (
    <Hinweis ton="fehler" dringend>
      {aktionsfehler}
    </Hinweis>
  );

  if (turnier === null) {
    return (
      <>
        {fehlerband}
        {darfEinrichten ? (
          <EinstellungenTafel
            turnier={null}
            onAnlegen={(name, einstellungen) =>
              mitFehlerbehandlung(() => legeTurnierAn({ name, ...einstellungen }))
            }
            onAendern={() => Promise.resolve(false)}
            onBeenden={() => undefined}
            onLoeschen={() => undefined}
          />
        ) : (
          <Leerzustand titel="Noch kein Turnier">
            Ein Turnier legt an, wer dieses Artefakt verwaltet.
          </Leerzustand>
        )}
      </>
    );
  }

  if (unterseite === "teilnehmer") {
    return (
      <>
        {kopf}
        {fehlerband}
        <TeilnehmerTafel
          turnier={turnier}
          teilnehmer={teilnehmer}
          onAnlegen={(daten: NeuerTeilnehmer) =>
            mitFehlerbehandlung(() => legeTeilnehmerAn(turnier.id, daten))
          }
          onAendern={(id, daten) =>
            mitFehlerbehandlung(() => aendereTeilnehmer(id, daten))
          }
          onEntfernen={(id) => void mitFehlerbehandlung(() => entferneTeilnehmer(id))}
        />
      </>
    );
  }

  if (unterseite === "auswuerfeln") {
    if (!darfEinrichten) {
      return (
        <Hinweis>
          Auswürfeln darf, wer dieses Artefakt verwaltet – damit nicht mitten im Turnier
          jemand den Spielplan neu zieht.
        </Hinweis>
      );
    }
    return (
      <>
        {kopf}
        {fehlerband}
        <AuswuerfelnTafel
          turnier={turnier}
          onLosen={async (saat) => {
            setAktionsfehler("");
            try {
              return await loseAus(turnier.id, saat);
            } catch (fehler) {
              setAktionsfehler(meldung(fehler));
              return null;
            }
          }}
          onUebernehmen={(saat) =>
            mitFehlerbehandlung(() => wuerfleAus(turnier.id, saat))
          }
          onZuruecksetzen={() => mitFehlerbehandlung(() => setzeZurueck(turnier.id))}
        />
      </>
    );
  }

  if (unterseite === "spielplan") {
    return (
      <>
        {kopf}
        {fehlerband}
        <SpielplanTafel
          turnier={turnier}
          spiele={spiele}
          onBeginnen={(id) => void mitFehlerbehandlung(() => beginneSpiel(id))}
          onErgebnis={(id, saetze: Satz[]) =>
            mitFehlerbehandlung(() => trageErgebnisEin(id, saetze))
          }
          onZuruecknehmen={(id) =>
            void mitFehlerbehandlung(() => nimmErgebnisZurueck(id))
          }
          onNaechsteRunde={() =>
            void mitFehlerbehandlung(() => naechsteRunde(turnier.id))
          }
        />
      </>
    );
  }

  if (unterseite === "tabellen") {
    return (
      <>
        {kopf}
        {fehlerband}
        <TabellenTafel tabellen={tabellen} />
      </>
    );
  }

  return (
    <>
      {kopf}
      {fehlerband}
      {darfEinrichten ? (
        <EinstellungenTafel
          turnier={turnier}
          onAnlegen={(name, einstellungen: Einstellungen) =>
            mitFehlerbehandlung(() => legeTurnierAn({ name, ...einstellungen }))
          }
          onAendern={(einstellungen) =>
            mitFehlerbehandlung(() => aendereTurnier(turnier.id, einstellungen))
          }
          onBeenden={() => void mitFehlerbehandlung(() => beendeTurnier(turnier.id))}
          onLoeschen={() => {
            void mitFehlerbehandlung(() => loescheTurnier(turnier.id));
            setGewaehlt("");
          }}
        />
      ) : (
        <Karte>
          <p className={stil.nebensache}>
            Die Einstellungen ändert, wer dieses Artefakt verwaltet.
          </p>
        </Karte>
      )}
    </>
  );
}
