import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { fetchModule, type ModulEintrag } from "../api/client";
import { GenerischeAnsicht } from "../module/GenerischeAnsicht";
import { oberflaecheFuer } from "../module/register";
import { Etikett, Hinweis, Leerzustand, Platzhalter, Seitenkopf } from "../ui";
import stil from "./ModulSeite.module.css";

type Zustand =
  | { phase: "laedt" }
  | { phase: "gefunden"; modul: ModulEintrag }
  | { phase: "unbekannt" }
  | { phase: "fehler"; nachricht: string };

const ZURUECK = { ziel: "/", text: "Übersicht" };

export function ModulSeite() {
  const { id = "" } = useParams();
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });

  useEffect(() => {
    const controller = new AbortController();
    setZustand({ phase: "laedt" });

    fetchModule(controller.signal)
      .then((module) => {
        const modul = module.find((m) => m.id === id);
        setZustand(modul ? { phase: "gefunden", modul } : { phase: "unbekannt" });
      })
      .catch((fehler: unknown) => {
        if (controller.signal.aborted) return;
        const nachricht = fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
        setZustand({ phase: "fehler", nachricht });
      });

    return () => controller.abort();
  }, [id]);

  if (zustand.phase === "laedt") {
    return (
      <div className={stil.laden} role="status" aria-label="Wird geladen">
        <Platzhalter breite="9rem" hoehe="0.8125rem" />
        <Platzhalter breite="14rem" hoehe="1.75rem" />
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <>
        <Seitenkopf titel="Nicht erreichbar" zurueck={ZURUECK} />
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </>
    );
  }

  if (zustand.phase === "unbekannt") {
    return (
      <>
        <Seitenkopf titel="Unbekanntes Artefakt" zurueck={ZURUECK} />
        <Leerzustand titel={`Kein Modul mit der Kennung „${id}“`}>
          Das Gateway kennt dieses Artefakt nicht. Vermutlich wurde es umbenannt oder ist
          noch nicht ausgerollt.
        </Leerzustand>
      </>
    );
  }

  const { modul } = zustand;
  const eigene = oberflaecheFuer(modul.id);

  return (
    <>
      <Seitenkopf
        titel={modul.titel}
        beschreibung={modul.beschreibung || undefined}
        zurueck={ZURUECK}
        neben={<Etikett mono>v{modul.version}</Etikett>}
      />

      <div className={stil.inhalt}>
        {eigene ? (
          <eigene.Komponente modul={modul} />
        ) : (
          <GenerischeAnsicht modul={modul} />
        )}
      </div>
    </>
  );
}
