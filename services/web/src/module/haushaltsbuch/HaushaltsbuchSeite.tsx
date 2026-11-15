import { useCallback, useEffect, useState } from "react";

import { Hinweis, Knopf, Platzhalter, Tafel } from "../../ui";
import type { ModulProps } from "../typen";
import {
  ladeFlussbild,
  ladeKategorien,
  ladeKonten,
  ladePersonen,
  ladePosten,
  ladeUebersicht,
} from "./api";
import {
  bereichstitel,
  dieserMonat,
  verschiebe,
  type Daten,
  type Zeitraum,
} from "./daten";
import { FlussTafel } from "./FlussTafel";
import { monatswort } from "./geld";
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

  // Der Monatsplan ist die Startfläche: ohne Bereich landet man hier.
  const aufMonatsplan = unterseite === undefined || unterseite === "uebersicht";

  /* Der Monat gehört in die Titelzeile und nicht in eine eigene Leiste
     darunter: Er sagt, WELCHEN Monatsplan man sieht, und das ist eine Angabe
     zum Titel. Er steht auch schon da, solange geladen wird - der Zeitraum
     ist hier bekannt, und so rückt beim Eintreffen der Daten nichts. */
  const kopf = {
    titel: bereichstitel(unterseite),
    beiwort: aufMonatsplan ? `${monatswort(zeitraum.monat)} ${zeitraum.jahr}` : undefined,
    aktionen: aufMonatsplan ? (
      <Monatswaehler
        onZeitraum={(schritte) => setZeitraum((alt) => verschiebe(alt, schritte))}
        onHeute={() => setZeitraum(dieserMonat())}
      />
    ) : undefined,
  };

  if (zustand.phase === "laedt") {
    return (
      <Tafel {...kopf}>
        <div className={stil.laden} role="status" aria-label="Haushaltsbuch wird geladen">
          <Platzhalter breite="100%" hoehe="4rem" />
          <Platzhalter breite="100%" hoehe="14rem" />
          <Platzhalter breite="100%" hoehe="8rem" />
        </div>
      </Tafel>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <Tafel {...kopf}>
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { daten } = zustand;

  return (
    <Tafel {...kopf} beiwort={kopf.beiwort ?? zahlen(unterseite, daten)}>
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

      {aufMonatsplan && <UebersichtTafel daten={daten} />}
    </Tafel>
  );
}

/**
 * Die Zahl neben dem Titel: wie viel auf dieser Fläche steht.
 *
 * Auf dem Monatsplan steht dort der Monat - zwei Angaben in derselben Zeile
 * wären eine zu viel. Das Flussbild sagt seine Zahl im Bild selbst.
 */
function zahlen(unterseite: string | undefined, daten: Daten): string | undefined {
  if (unterseite === "posten") {
    const pausiert = daten.posten.filter((posten) => !posten.aktiv).length;
    const teile = [`${daten.posten.length} Posten`];
    if (pausiert > 0) teile.push(`${pausiert} pausiert`);
    return teile.join(" · ");
  }

  if (unterseite === "stammdaten") {
    return [
      mengenwort(daten.personen.length, "Person", "Personen"),
      mengenwort(daten.konten.length, "Konto", "Konten"),
      mengenwort(daten.kategorien.length, "Kategorie", "Kategorien"),
    ].join(" · ");
  }

  return undefined;
}

function mengenwort(anzahl: number, eines: string, mehrere: string): string {
  return `${anzahl} ${anzahl === 1 ? eines : mehrere}`;
}

/**
 * Einen Monat vor, zurück, oder wieder in diesen.
 *
 * Steht in der Titelzeile der Fläche und nicht als eigene Leiste darüber:
 * Der Zeitraum gehört zum Titel "Monatsplan", und eine zweite Leiste war
 * genau die Zeile, die auf jeder Unterseite anders weit vom Inhalt entfernt
 * stand.
 */
function Monatswaehler({
  onZeitraum,
  onHeute,
}: {
  onZeitraum: (schritte: number) => void;
  onHeute: () => void;
}) {
  return (
    <div className={stil.monatswaehler}>
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={() => onZeitraum(-1)}
        aria-label="Einen Monat zurück"
      >
        ←
      </Knopf>
      <Knopf groesse="sm" auspraegung="leise" onClick={onHeute}>
        Heute
      </Knopf>
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={() => onZeitraum(1)}
        aria-label="Einen Monat vor"
      >
        →
      </Knopf>
    </div>
  );
}
