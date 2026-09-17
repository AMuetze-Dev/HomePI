import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import * as api from "../api/anmeldung";
import type { Benutzer, Rolle } from "../api/anmeldung";
import { AnmeldungKontext, RANG, type Anmeldung } from "./kontext";

/** Fragt beim Start einmal, wer angemeldet ist, und hält die Antwort. */
export function AnmeldungProvider({ children }: { children: ReactNode }) {
  const [benutzer, setBenutzer] = useState<Benutzer | null>(null);
  const [laedt, setLaedt] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    api
      .holeIch(controller.signal)
      .then(setBenutzer)
      .catch(() => {
        // Ein nicht erreichbares Gateway ist etwas anderes als "nicht
        // angemeldet" - für diese Ansicht bleibt das Ergebnis dasselbe.
        setBenutzer(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLaedt(false);
      });

    return () => controller.abort();
  }, []);

  const anmelden = useCallback(async (name: string, passwort: string) => {
    setBenutzer(await api.anmelden(name, passwort));
  }, []);

  const abmelden = useCallback(async () => {
    try {
      await api.abmelden();
    } catch {
      // Bewusst geschluckt. Scheitert der Aufruf, bleibt die Sitzung auf dem
      // Server bis zum Ablauf bestehen - dagegen kann das Frontend nichts
      // ausrichten. Angemeldet zu bleiben, weil das Netz kurz weg war, wäre
      // aber das schlechtere von beiden.
    }
    setBenutzer(null);
  }, []);

  const darf = useCallback(
    (artefakt: string, benoetigt: Rolle = "leser") => {
      const vorhanden = benutzer?.rechte[artefakt];
      return vorhanden !== undefined && RANG[vorhanden] >= RANG[benoetigt];
    },
    [benutzer],
  );

  const wert: Anmeldung = {
    zustand: laedt ? "laedt" : benutzer ? "angemeldet" : "abgemeldet",
    benutzer,
    anmelden,
    abmelden,
    darf,
  };

  return <AnmeldungKontext.Provider value={wert}>{children}</AnmeldungKontext.Provider>;
}
