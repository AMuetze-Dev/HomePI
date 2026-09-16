import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchModule, type ModulEintrag } from "../api/client";
import { GenerischeAnsicht } from "../module/GenerischeAnsicht";
import { oberflaecheFuer } from "../module/register";

type Zustand =
  | { phase: "laedt" }
  | { phase: "gefunden"; modul: ModulEintrag }
  | { phase: "unbekannt" }
  | { phase: "fehler"; nachricht: string };

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

  if (zustand.phase === "laedt") return <p role="status">Wird geladen …</p>;

  if (zustand.phase === "fehler") return <p role="alert">{zustand.nachricht}</p>;

  if (zustand.phase === "unbekannt") {
    return (
      <main>
        <h1>Unbekanntes Artefakt</h1>
        <p role="alert">
          Das Gateway kennt kein Modul mit der Kennung <code>{id}</code>.
        </p>
        <Link to="/">Zur Startseite</Link>
      </main>
    );
  }

  const { modul } = zustand;
  const eigene = oberflaecheFuer(modul.id);

  return (
    <main>
      <nav>
        <Link to="/">Zurück</Link>
      </nav>
      <h1>{modul.titel}</h1>
      {eigene ? <eigene.Komponente modul={modul} /> : <GenerischeAnsicht modul={modul} />}
    </main>
  );
}
