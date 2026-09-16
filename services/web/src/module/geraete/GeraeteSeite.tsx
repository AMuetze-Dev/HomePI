import { useCallback, useEffect, useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  entferneGeraet,
  ladeGeraete,
  ladeZusammenfassung,
  legeGeraetAn,
  schalteGeraet,
  type Geraet,
  type Zusammenfassung,
} from "./api";
import stil from "./GeraeteSeite.module.css";

type Daten = { geraete: Geraet[]; uebersicht: Zusammenfassung };

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; daten: Daten }
  | { phase: "fehler"; nachricht: string };

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

export function GeraeteSeite() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });
  // Getrennt vom Ladezustand: ein Fehler beim Schalten darf die Liste nicht
  // gegen eine Fehlerseite austauschen.
  const [aktionsfehler, setAktionsfehler] = useState<string>("");

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      const [geraete, uebersicht] = await Promise.all([
        ladeGeraete(signal),
        ladeZusammenfassung(signal),
      ]);
      setZustand({ phase: "fertig", daten: { geraete, uebersicht } });
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

  /** true, wenn die Aktion geklappt hat - der Aufrufer braucht das, um zu
   *  entscheiden, ob er sein Formular leeren darf. */
  async function mitFehlerbehandlung(aktion: () => Promise<unknown>): Promise<boolean> {
    setAktionsfehler("");
    try {
      await aktion();
      await laden();
      return true;
    } catch (fehler) {
      setAktionsfehler(meldung(fehler));
      return false;
    }
  }

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Geräte werden geladen">
        <Platzhalter breite="100%" hoehe="5rem" />
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

  const { geraete, uebersicht } = zustand.daten;

  return (
    <>
      <Uebersicht daten={uebersicht} />

      {aktionsfehler && (
        <Hinweis ton="fehler" dringend>
          {aktionsfehler}
        </Hinweis>
      )}

      <Liste
        geraete={geraete}
        onSchalten={(g) =>
          void mitFehlerbehandlung(() => schalteGeraet(g.id, !g.eingeschaltet))
        }
        onEntfernen={(g) => void mitFehlerbehandlung(() => entferneGeraet(g.id))}
      />

      <Anlegen onAnlegen={(daten) => mitFehlerbehandlung(() => legeGeraetAn(daten))} />
    </>
  );
}

function Uebersicht({ daten }: { daten: Zusammenfassung }) {
  return (
    <ul className={stil.kennzahlen} aria-label="Überblick">
      <Kennzahl wert={daten.anzahl} name="Geräte" />
      <Kennzahl wert={daten.eingeschaltet} name="eingeschaltet" ton="gut" />
      <Kennzahl wert={daten.in_wartung} name="in Wartung" ton="warnung" />
      <Kennzahl wert={Object.keys(daten.raeume).length} name="Räume" />
    </ul>
  );
}

function Kennzahl({
  wert,
  name,
  ton = "neutral",
}: {
  wert: number;
  name: string;
  ton?: "neutral" | "gut" | "warnung";
}) {
  // Eine Null wird nicht eingefärbt: sie ist keine Meldung, sondern die
  // Abwesenheit einer.
  const eingefaerbt = ton !== "neutral" && wert > 0;

  return (
    // Zahl und Bezeichnung stehen optisch untereinander; aria-label fasst
    // beides zu dem zusammen, was ein Screenreader vorlesen soll - sonst
    // kommt "1" und "Geräte" als zwei zusammenhanglose Fetzen an.
    <li className={stil.eintrag} aria-label={`${wert} ${name}`}>
      <Karte className={stil.kennzahl}>
        <span
          className={`${stil.wert} ${eingefaerbt ? stil[ton] : ""}`}
          aria-hidden="true"
        >
          {wert}
        </span>
        <span className={stil.name} aria-hidden="true">
          {name}
        </span>
      </Karte>
    </li>
  );
}

function Liste({
  geraete,
  onSchalten,
  onEntfernen,
}: {
  geraete: Geraet[];
  onSchalten: (g: Geraet) => void;
  onEntfernen: (g: Geraet) => void;
}) {
  if (geraete.length === 0) {
    return (
      <Leerzustand titel="Noch kein Gerät angelegt">
        Trage unten das erste ein. Danach lässt es sich hier ein- und ausschalten.
      </Leerzustand>
    );
  }

  return (
    <Karte blank>
      <div className={stil.rollbereich}>
        <table className={stil.tabelle} role="table">
          <caption className="nur-vorlesen">Geräte</caption>
          <thead>
            <tr role="row">
              <th scope="col">Name</th>
              <th scope="col">Raum</th>
              <th scope="col">Zustand</th>
              <th scope="col">
                <span className="nur-vorlesen">Aktion</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {geraete.map((geraet) => (
              <tr key={geraet.id} role="row">
                <td className={stil.geraetname} role="cell">
                  {geraet.name}
                </td>
                <td className={stil.raum} role="cell">
                  {geraet.raum}
                </td>
                <td role="cell" className={stil.zustandszelle}>
                  {geraet.zustand === "wartung" ? (
                    <Etikett ton="warnung">Wartung</Etikett>
                  ) : (
                    <Etikett ton={geraet.eingeschaltet ? "gut" : "neutral"}>
                      {geraet.eingeschaltet ? "An" : "Aus"}
                    </Etikett>
                  )}
                </td>
                <td role="cell" className={stil.aktionszelle}>
                  <div className={stil.aktionen}>
                    <Knopf
                      groesse="sm"
                      onClick={() => onSchalten(geraet)}
                      disabled={geraet.zustand === "wartung"}
                      aria-label={`${geraet.name} ${geraet.eingeschaltet ? "ausschalten" : "einschalten"}`}
                    >
                      {geraet.eingeschaltet ? "Ausschalten" : "Einschalten"}
                    </Knopf>
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => onEntfernen(geraet)}
                      aria-label={`${geraet.name} entfernen`}
                    >
                      Entfernen
                    </Knopf>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Karte>
  );
}

function Anlegen({
  onAnlegen,
}: {
  onAnlegen: (daten: { name: string; raum: string }) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [raum, setRaum] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const vollstaendig = name.trim() !== "" && raum.trim() !== "";

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (!vollstaendig || laeuft) return;

    setLaeuft(true);
    const geklappt = await onAnlegen({ name: name.trim(), raum: raum.trim() });
    setLaeuft(false);

    // Nur leeren, wenn es geklappt hat. Sonst tippt man nach einem Tippfehler
    // oder einem doppelten Namen alles neu - der Fehler steht oben, die
    // Eingabe bleibt stehen.
    if (geklappt) {
      setName("");
      setRaum("");
    }
  }

  return (
    <section aria-labelledby="anlegen">
      <h2 id="anlegen" className={stil.abschnittstitel}>
        Gerät anlegen
      </h2>

      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Stehlampe"
            autoComplete="off"
            required
          />
          <Feld
            beschriftung="Raum"
            value={raum}
            onChange={(e) => setRaum(e.target.value)}
            placeholder="Wohnzimmer"
            autoComplete="off"
            required
          />
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={!vollstaendig || laeuft}
            className={stil.absenden}
          >
            {laeuft ? "Wird angelegt …" : "Anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}
