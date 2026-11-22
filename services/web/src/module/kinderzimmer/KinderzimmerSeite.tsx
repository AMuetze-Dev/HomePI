import { useCallback, useEffect, useState } from "react";

import { meldung } from "../../api/client";
import { useAnmeldung } from "../../anmeldung/kontext";
import { Hinweis, Knopf, Platzhalter, Tafel } from "../../ui";
import type { ModulProps } from "../typen";
import {
  aendereAufnahme,
  aendereFigur,
  entferneAufnahme,
  entferneFigur,
  entferneGeraet,
  entferneTagebuch,
  ladeAufnahmeHoch,
  ladeAufnahmen,
  ladeEinstellungen,
  ladeFiguren,
  ladeGeraete,
  ladeProtokoll,
  ladeTagebuch,
  ladeUebersicht,
  ladeUnbekannte,
  legeFigurAn,
  legeGeraetAn,
  schreibeTagebuch,
  speichereEinstellungen,
  stelleTokenAus,
  type Aufnahme,
  type Einstellungen,
  type Ereignis,
  type Figur,
  type FigurEingabe,
  type Geraet,
  type GeraetMitToken,
  type Tagebucheintrag,
  type Uebersicht,
  type UnbekannteFigur,
} from "./api";
import { AufnahmenTafel } from "./AufnahmenTafel";
import { EinstellungenTafel } from "./EinstellungenTafel";
import { FigurenTafel } from "./FigurenTafel";
import { GeraeteTafel } from "./GeraeteTafel";
import stil from "./KinderzimmerSeite.module.css";
import { SpieleTafel } from "./SpieleTafel";
import { TagebuchTafel } from "./TagebuchTafel";
import { LEERE_FIGUR } from "./texte";

interface Daten {
  uebersicht: Uebersicht;
  einstellungen: Einstellungen;
  figuren: Figur[];
  unbekannte: UnbekannteFigur[];
  aufnahmen: Aufnahme[];
  geraete: Geraet[];
  protokoll: Ereignis[];
  tagebuch: Tagebucheintrag[];
}

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

/** Die Wörter stehen ein zweites Mal im Register - die Fläche braucht ihren
 *  Titel schon, solange sie lädt. */
const TITEL: Record<string, string> = {
  spiele: "Spiele",
  figuren: "Figuren",
  aufnahmen: "Aufnahmen",
  tagebuch: "Tagebuch",
  einstellungen: "Einstellungen",
  geraete: "Geräte",
};

async function ladeAlles(signal?: AbortSignal): Promise<Daten> {
  const [
    uebersicht,
    einstellungen,
    figuren,
    unbekannte,
    aufnahmen,
    geraete,
    protokoll,
    tagebuch,
  ] = await Promise.all([
    ladeUebersicht(signal),
    ladeEinstellungen(signal),
    ladeFiguren(signal),
    ladeUnbekannte(signal),
    ladeAufnahmen(signal),
    ladeGeraete(signal),
    ladeProtokoll(signal),
    ladeTagebuch(signal),
  ]);
  return {
    uebersicht,
    einstellungen,
    figuren,
    unbekannte,
    aufnahmen,
    geraete,
    protokoll,
    tagebuch,
  };
}

/**
 * Die Redaktion für das Spielgerät im Kinderzimmer.
 *
 * Das Gerät spielt allein; hier wird gepflegt, was es beim nächsten
 * Abgleich holt, und gelesen, was es gemeldet hat. Alle Bereiche teilen
 * dieselben Daten - eine Aufnahme, die hier entsteht, steht im nächsten
 * Moment bei den Figuren zur Wahl. Deshalb wird einmal alles geladen und
 * nicht je Bereich.
 */
export function KinderzimmerSeite({ unterseite = "spiele" }: ModulProps) {
  const { darf } = useAnmeldung();
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  // Getrennt vom Ladezustand: ein Fehler bei einer Aktion darf die Liste
  // nicht gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState("");

  const [figurFormular, setFigurFormular] = useState<FigurEingabe | null>(null);
  const [figurBearbeitet, setFigurBearbeitet] = useState<Figur | null>(null);
  const [aufnahmeOffen, setAufnahmeOffen] = useState(false);
  const [geraetOffen, setGeraetOffen] = useState(false);
  const [neuesToken, setNeuesToken] = useState<GeraetMitToken | null>(null);
  const [notizOffen, setNotizOffen] = useState(false);

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      setZustand({ phase: "fertig", daten: await ladeAlles(signal) });
    } catch (fehler) {
      if (signal?.aborted) return;
      setZustand({ phase: "fehler", nachricht: meldung(fehler) });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(controller.signal);
    return () => controller.abort();
  }, [laden]);

  // Ein Bereichswechsel schließt offene Formulare und die alte Meldung.
  useEffect(() => {
    setAktionsfehler("");
    setFigurFormular(null);
    setAufnahmeOffen(false);
    setGeraetOffen(false);
    setNotizOffen(false);
  }, [unterseite]);

  /** true, wenn es geklappt hat - der Aufrufer entscheidet damit, ob er
   *  sein Formular schließen darf. */
  async function aktion(was: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await was();
      await laden();
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  const titel = TITEL[unterseite] ?? "Kinderzimmer";
  const darfAendern = darf("kinderzimmer", "nutzer");
  const darfVerwalten = darf("kinderzimmer", "verwalter");

  if (zustand.phase === "laedt") {
    return (
      <Tafel titel={titel}>
        <div className={stil.laden} role="status" aria-label="Kinderzimmer wird geladen">
          <Platzhalter breite="100%" hoehe="3rem" />
          <Platzhalter breite="100%" hoehe="12rem" />
        </div>
      </Tafel>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <Tafel titel={titel}>
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  const { daten } = zustand;
  const fehlerband = aktionsfehler && (
    <Hinweis ton="fehler" dringend>
      {aktionsfehler}
    </Hinweis>
  );

  if (unterseite === "figuren") {
    return (
      <Tafel
        titel={titel}
        beiwort={`${daten.figuren.length} angelegt`}
        aktionen={
          darfAendern &&
          figurFormular === null && (
            <Knopf
              auspraegung="primaer"
              onClick={() => {
                setFigurBearbeitet(null);
                setFigurFormular(LEERE_FIGUR);
              }}
            >
              Figur anlegen
            </Knopf>
          )
        }
      >
        {fehlerband}
        <FigurenTafel
          figuren={daten.figuren}
          unbekannte={daten.unbekannte}
          aufnahmen={daten.aufnahmen}
          darfAendern={darfAendern}
          formular={figurFormular}
          bearbeitet={figurBearbeitet}
          onFormular={(werte, figur = null) => {
            setAktionsfehler("");
            setFigurBearbeitet(figur);
            setFigurFormular(werte);
          }}
          onSpeichern={async (werte, id) => {
            const geklappt = await aktion(() =>
              id === null ? legeFigurAn(werte) : aendereFigur(id, werte),
            );
            if (geklappt) setFigurFormular(null);
            return geklappt;
          }}
          onEntfernen={(figur) => void aktion(() => entferneFigur(figur.id))}
        />
      </Tafel>
    );
  }

  if (unterseite === "aufnahmen") {
    return (
      <Tafel
        titel={titel}
        beiwort={`${daten.aufnahmen.length} gespeichert`}
        aktionen={
          darfAendern &&
          !aufnahmeOffen && (
            <Knopf auspraegung="primaer" onClick={() => setAufnahmeOffen(true)}>
              Neue Aufnahme
            </Knopf>
          )
        }
      >
        {fehlerband}
        <AufnahmenTafel
          aufnahmen={daten.aufnahmen}
          figuren={daten.figuren}
          knoepfe={daten.einstellungen.knoepfe}
          darfAendern={darfAendern}
          formularOffen={aufnahmeOffen}
          onFormular={setAufnahmeOffen}
          onHochladen={(titelText, art, wav) =>
            aktion(() => ladeAufnahmeHoch(titelText, art, wav))
          }
          onAendern={(id, titelText, art) =>
            aktion(() => aendereAufnahme(id, { titel: titelText, art }))
          }
          onEntfernen={(aufnahme) => void aktion(() => entferneAufnahme(aufnahme.id))}
        />
      </Tafel>
    );
  }

  if (unterseite === "einstellungen") {
    return (
      <Tafel titel={titel} beiwort={`Stand ${daten.uebersicht.stand}`}>
        {fehlerband}
        <EinstellungenTafel
          einstellungen={daten.einstellungen}
          spiele={daten.uebersicht.spiele}
          aufnahmen={daten.aufnahmen}
          darfAendern={darfAendern}
          onSpeichern={(werte) => aktion(() => speichereEinstellungen(werte))}
        />
      </Tafel>
    );
  }

  if (unterseite === "geraete") {
    return (
      <Tafel
        titel={titel}
        aktionen={
          darfVerwalten &&
          !geraetOffen && (
            <Knopf auspraegung="primaer" onClick={() => setGeraetOffen(true)}>
              Gerät anlegen
            </Knopf>
          )
        }
      >
        {fehlerband}
        <GeraeteTafel
          geraete={daten.geraete}
          darfVerwalten={darfVerwalten}
          formularOffen={geraetOffen}
          neuesToken={neuesToken}
          onFormular={setGeraetOffen}
          onAnlegen={async (name) => {
            const geklappt = await aktion(async () =>
              setNeuesToken(await legeGeraetAn(name)),
            );
            if (geklappt) setGeraetOffen(false);
            return geklappt;
          }}
          onNeuesToken={(geraet) =>
            void aktion(async () => setNeuesToken(await stelleTokenAus(geraet.id)))
          }
          onEntfernen={(geraet) => void aktion(() => entferneGeraet(geraet.id))}
          onTokenGelesen={() => setNeuesToken(null)}
        />
      </Tafel>
    );
  }

  if (unterseite === "tagebuch") {
    return (
      <Tafel
        titel={titel}
        aktionen={
          darfAendern &&
          !notizOffen && (
            <Knopf auspraegung="primaer" onClick={() => setNotizOffen(true)}>
              Notiz schreiben
            </Knopf>
          )
        }
      >
        {fehlerband}
        <TagebuchTafel
          eintraege={daten.tagebuch}
          protokoll={daten.protokoll}
          darfAendern={darfAendern}
          formularOffen={notizOffen}
          onFormular={setNotizOffen}
          onSchreiben={(werte) => aktion(() => schreibeTagebuch(werte))}
          onEntfernen={(eintrag) => void aktion(() => entferneTagebuch(eintrag.id))}
        />
      </Tafel>
    );
  }

  const { spiele, phasen } = daten.uebersicht;
  const bereit = spiele.filter((s) => s.bereit).length;
  return (
    <Tafel
      titel={TITEL.spiele ?? "Spiele"}
      beiwort={
        <>
          {bereit} von {spiele.length} am Gerät
          <span className={stil.beiwortTrenner} aria-hidden="true">
            ·
          </span>
          die übrigen sind geplant
        </>
      }
    >
      {fehlerband}
      <SpieleTafel phasen={phasen} spiele={spiele} />
    </Tafel>
  );
}
