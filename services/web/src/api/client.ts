/**
 * Zugriff auf das Backend.
 *
 * VITE_API_URL wird zur BUILD-Zeit in das Bundle geschrieben, nicht zur
 * Laufzeit gelesen. Ein Image, das gegen api.home.example.com gebaut wurde,
 * spricht auch nur mit dieser Adresse.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type HealthStatus = "ok" | "degraded" | "down";

export interface Health {
  status: HealthStatus;
  version: string;
  checks: Record<string, boolean>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isHealth(value: unknown): value is Health {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.status === "string" &&
    typeof candidate.version === "string" &&
    typeof candidate.checks === "object" &&
    candidate.checks !== null
  );
}

/**
 * Holt den Gesundheitszustand.
 *
 * Wichtig: Auch 503 liefert einen gueltigen Bericht - genau dann will die
 * Oberflaeche ja wissen, was kaputt ist. Nur andere Fehlercodes werfen.
 */
export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch(`${BASE_URL}/health`, {
    signal: signal ?? null,
    headers: { Accept: "application/json" },
  });

  if (!response.ok && response.status !== 503) {
    throw new ApiError(`Unerwartete Antwort ${response.status}`, response.status);
  }

  const body: unknown = await response.json();
  if (!isHealth(body)) {
    throw new ApiError("Antwort hat nicht die erwartete Form", response.status);
  }
  return body;
}
