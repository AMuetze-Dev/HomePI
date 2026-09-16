import { useEffect, useState } from "react";

import { fetchHealth, type Health } from "../api/client";

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; health: Health }
  | { phase: "fehler"; nachricht: string };

const BESCHRIFTUNG: Record<Health["status"], string> = {
  ok: "Alle Systeme laufen",
  degraded: "Eingeschränkt",
  down: "Ausfall",
};

export function SystemStatus() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });

  useEffect(() => {
    const controller = new AbortController();

    fetchHealth(controller.signal)
      .then((health) => setZustand({ phase: "fertig", health }))
      .catch((fehler: unknown) => {
        if (controller.signal.aborted) return;
        const nachricht = fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
        setZustand({ phase: "fehler", nachricht });
      });

    return () => controller.abort();
  }, []);

  if (zustand.phase === "laedt") {
    return <p role="status">Status wird geladen …</p>;
  }

  if (zustand.phase === "fehler") {
    return <p role="alert">Backend nicht erreichbar: {zustand.nachricht}</p>;
  }

  const { health } = zustand;
  return (
    <section aria-labelledby="status-titel">
      <h2 id="status-titel">{BESCHRIFTUNG[health.status]}</h2>
      <p>Version {health.version}</p>
      <ul>
        {Object.entries(health.checks).map(([name, gesund]) => (
          <li key={name}>
            {name}: {gesund ? "in Ordnung" : "gestört"}
          </li>
        ))}
      </ul>
    </section>
  );
}
