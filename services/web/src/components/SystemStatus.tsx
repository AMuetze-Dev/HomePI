import { useEffect, useState } from "react";

import { fetchHealth, type Health } from "../api/client";
import { Platzhalter, Statuspunkt, type Ton } from "../ui";
import stil from "./SystemStatus.module.css";

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; health: Health }
  | { phase: "fehler"; nachricht: string };

const BESCHRIFTUNG: Record<Health["status"], string> = {
  ok: "Alle Systeme betriebsbereit",
  degraded: "Eingeschränkt betriebsbereit",
  down: "Störung",
};

const TON: Record<Health["status"], Ton> = {
  ok: "gut",
  degraded: "warnung",
  down: "fehler",
};

/**
 * Eine Zeile, die den Gesamtzustand zusammenfasst.
 *
 * Bewusst knapp: im Normalfall soll sie beruhigen, nicht informieren. Erst
 * wenn etwas nicht stimmt, nennt sie die betroffene Abhängigkeit beim Namen.
 */
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
    return (
      <div className={stil.status} role="status">
        <Statuspunkt ton="neutral" laedt />
        <Platzhalter breite="11rem" hoehe="0.875rem" />
      </div>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <p className={stil.status} role="alert">
        <Statuspunkt ton="fehler" />
        <span className={stil.text}>Backend nicht erreichbar</span>
        <span className={stil.detail}>{zustand.nachricht}</span>
      </p>
    );
  }

  const { health } = zustand;
  const gestoert = Object.entries(health.checks)
    .filter(([, gesund]) => !gesund)
    .map(([name]) => name);

  return (
    <p className={stil.status}>
      <Statuspunkt ton={TON[health.status]} />
      <span className={stil.text}>{BESCHRIFTUNG[health.status]}</span>
      {gestoert.length > 0 && (
        <span className={stil.detail}>gestört: {gestoert.join(", ")}</span>
      )}
      <span className={stil.version}>v{health.version}</span>
    </p>
  );
}
