import { useCallback, useEffect, useState } from "react";

import {
  entferneGeraet,
  ladeGeraete,
  ladeZusammenfassung,
  legeGeraetAn,
  schalteGeraet,
  type Geraet,
  type Zusammenfassung,
} from "./api";

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

  if (zustand.phase === "laedt") return <p role="status">Geräte werden geladen …</p>;
  if (zustand.phase === "fehler") return <p role="alert">{zustand.nachricht}</p>;

  const { geraete, uebersicht } = zustand.daten;

  return (
    <>
      <Uebersicht daten={uebersicht} />

      {aktionsfehler && <p role="alert">{aktionsfehler}</p>}

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
    <section aria-labelledby="uebersicht">
      <h2 id="uebersicht">Überblick</h2>
      <p>
        {daten.anzahl} Geräte, davon {daten.eingeschaltet} eingeschaltet
        {daten.in_wartung > 0 && ` und ${daten.in_wartung} in Wartung`}.
      </p>
      {Object.keys(daten.raeume).length > 0 && (
        <ul aria-label="Räume">
          {Object.entries(daten.raeume).map(([raum, anzahl]) => (
            <li key={raum}>
              {raum}: {anzahl}
            </li>
          ))}
        </ul>
      )}
    </section>
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
    return <p>Noch kein Gerät angelegt. Unten kannst du das erste eintragen.</p>;
  }

  return (
    <table>
      <caption>Geräte</caption>
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">Raum</th>
          <th scope="col">Zustand</th>
          <th scope="col">Aktion</th>
        </tr>
      </thead>
      <tbody>
        {geraete.map((geraet) => (
          <tr key={geraet.id}>
            <td>{geraet.name}</td>
            <td>{geraet.raum}</td>
            <td>{geraet.eingeschaltet ? "an" : "aus"}</td>
            <td>
              <button
                type="button"
                onClick={() => onSchalten(geraet)}
                disabled={geraet.zustand === "wartung"}
                aria-label={`${geraet.name} ${geraet.eingeschaltet ? "ausschalten" : "einschalten"}`}
              >
                {geraet.eingeschaltet ? "Ausschalten" : "Einschalten"}
              </button>
              <button
                type="button"
                onClick={() => onEntfernen(geraet)}
                aria-label={`${geraet.name} entfernen`}
              >
                Entfernen
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
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
    <form onSubmit={(e) => void absenden(e)} aria-labelledby="anlegen">
      <h2 id="anlegen">Gerät anlegen</h2>
      <label htmlFor="feld-name">Name</label>
      <input
        id="feld-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <label htmlFor="feld-raum">Raum</label>
      <input
        id="feld-raum"
        value={raum}
        onChange={(e) => setRaum(e.target.value)}
        required
      />
      <button type="submit" disabled={!vollstaendig || laeuft}>
        {laeuft ? "Wird angelegt …" : "Anlegen"}
      </button>
    </form>
  );
}
