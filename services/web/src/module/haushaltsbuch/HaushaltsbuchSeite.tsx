import { useCallback, useEffect, useState } from "react";

import { Hinweis, Platzhalter } from "../../ui";
import type { ModulProps } from "../typen";
import {
  ladeFlussbild,
  ladeKategorien,
  ladeKonten,
  ladePersonen,
  ladePosten,
  ladeUebersicht,
} from "./api";
import { dieserMonat, verschiebe, type Daten, type Zeitraum } from "./daten";
import { FlussTafel } from "./FlussTafel";
import stil from "./HaushaltsbuchSeite.module.css";
import { PostenTafel } from "./PostenTafel";
import { StammdatenTafel } from "./StammdatenTafel";
import { UebersichtTafel } from "./UebersichtTafel";

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

export function HaushaltsbuchSeite({ unterseite }: ModulProps) {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  const [zeitraum, setZeitraum] = useState<Zeitraum>(dieserMonat);
  // Getrennt vom Ladezustand: ein Fehler beim Anlegen darf die ganze Seite
  // nicht gegen eine Fehlermeldung austauschen.
  const [aktionsfehler, setAktionsfehler] = useState("");

  const laden = useCallback(async (fuer: Zeitraum, signal?: AbortSignal) => {
    try {
      const [uebersicht, flussbild, personen, konten, kategorien, posten] =
        await Promise.all([
          ladeUebersicht(fuer, signal),
          ladeFlussbild(signal),
          ladePersonen(signal),
          ladeKonten(signal),
          ladeKategorien(signal),
          ladePosten(signal),
        ]);
      setZustand({
        phase: "fertig",
        daten: { uebersicht, flussbild, personen, konten, kategorien, posten },
      });
    } catch (fehler) {
      if (signal?.aborted) return;
      setZustand({ phase: "fehler", nachricht: meldung(fehler) });
    }
  }, []);

  useEffect(() => {
    const abbruch = new AbortController();
    void laden(zeitraum, abbruch.signal);
    return () => abbruch.abort();
  }, [laden, zeitraum]);

  /** true, wenn die Aktion geklappt hat - der Aufrufer leert sein Formular nur dann. */
  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden(zeitraum);
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Haushaltsbuch wird geladen">
        <Platzhalter breite="100%" hoehe="4rem" />
        <Platzhalter breite="100%" hoehe="14rem" />
        <Platzhalter breite="100%" hoehe="8rem" />
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

  return (
    <>
      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      {unterseite === "fluss" && <FlussTafel bild={daten.flussbild} />}

      {unterseite === "posten" && (
        <PostenTafel daten={daten} aktion={mitFehlerbehandlung} />
      )}

      {unterseite === "stammdaten" && (
        <StammdatenTafel daten={daten} aktion={mitFehlerbehandlung} />
      )}

      {(unterseite === undefined || unterseite === "uebersicht") && (
        <UebersichtTafel
          daten={daten}
          zeitraum={zeitraum}
          onZeitraum={(schritte) => setZeitraum((alt) => verschiebe(alt, schritte))}
          onHeute={() => setZeitraum(dieserMonat())}
        />
      )}
    </>
  );
}
