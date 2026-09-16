/**
 * Zugriff auf das Gateway.
 *
 * VITE_API_URL wird zur BUILD-Zeit in das Bundle geschrieben, nicht zur
 * Laufzeit gelesen. Ein Image, das gegen api.home.example.com gebaut wurde,
 * spricht auch nur mit dieser Adresse.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export type HealthStatus = "ok" | "degraded" | "down";
export type ModulStatus = "bereit" | "fehler";

export interface Health {
  status: HealthStatus;
  version: string;
  checks: Record<string, boolean>;
}

/** Ein Eintrag aus `GET /module`. Genau hieraus baut die Startseite ihre Kacheln. */
export interface ModulEintrag {
  id: string;
  titel: string;
  pfad: string;
  beschreibung: string;
  icon: string;
  version: string;
  status: ModulStatus;
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

function istObjekt(wert: unknown): wert is Record<string, unknown> {
  return typeof wert === "object" && wert !== null;
}

function istHealth(wert: unknown): wert is Health {
  if (!istObjekt(wert)) return false;
  return (
    typeof wert.status === "string" &&
    typeof wert.version === "string" &&
    istObjekt(wert.checks)
  );
}

function istModulEintrag(wert: unknown): wert is ModulEintrag {
  if (!istObjekt(wert)) return false;
  return (
    typeof wert.id === "string" &&
    typeof wert.titel === "string" &&
    typeof wert.pfad === "string" &&
    typeof wert.status === "string"
  );
}

async function hole(pfad: string, signal?: AbortSignal): Promise<Response> {
  return fetch(`${BASE_URL}${pfad}`, {
    signal: signal ?? null,
    headers: { Accept: "application/json" },
  });
}

/**
 * Holt den Gesundheitszustand.
 *
 * Auch 503 liefert einen gültigen Bericht - genau dann will die Oberfläche ja
 * wissen, was kaputt ist. Nur andere Fehlercodes werfen.
 */
export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const antwort = await hole("/health", signal);

  if (!antwort.ok && antwort.status !== 503) {
    throw new ApiError(`Unerwartete Antwort ${antwort.status}`, antwort.status);
  }

  const koerper: unknown = await antwort.json();
  if (!istHealth(koerper)) {
    throw new ApiError("Antwort hat nicht die erwartete Form", antwort.status);
  }
  return koerper;
}

/**
 * Holt das Modulmanifest.
 *
 * Ein Dienst ohne Module antwortet mit 404. Das ist kein Fehler, sondern
 * heißt schlicht "hier läuft kein Gateway" - die Startseite zeigt dann eine
 * leere Liste statt einer Fehlermeldung.
 */
export async function fetchModule(signal?: AbortSignal): Promise<ModulEintrag[]> {
  const antwort = await hole("/module", signal);

  if (antwort.status === 404) return [];
  if (!antwort.ok) {
    throw new ApiError(`Unerwartete Antwort ${antwort.status}`, antwort.status);
  }

  const koerper: unknown = await antwort.json();
  if (!Array.isArray(koerper) || !koerper.every(istModulEintrag)) {
    throw new ApiError("Manifest hat nicht die erwartete Form", antwort.status);
  }
  return koerper;
}

interface OpenApiOperation {
  summary?: string;
  description?: string;
  tags?: string[];
}

export interface Endpunkt {
  methode: string;
  pfad: string;
  beschreibung: string;
}

/**
 * Liest die Endpunkte eines Moduls aus dem OpenAPI-Schema.
 *
 * Damit bekommt ein Artefakt ohne eigene Oberfläche trotzdem eine brauchbare
 * Seite: FastAPI erzeugt das Schema von selbst, also ist die Beschreibung
 * immer aktuell - im Gegensatz zu einer von Hand gepflegten Liste.
 */
export async function fetchEndpunkte(
  modulPfad: string,
  signal?: AbortSignal,
): Promise<Endpunkt[]> {
  const antwort = await hole("/openapi.json", signal);
  if (!antwort.ok) return [];

  const schema: unknown = await antwort.json();
  if (!istObjekt(schema) || !istObjekt(schema.paths)) return [];

  const endpunkte: Endpunkt[] = [];
  for (const [pfad, operationen] of Object.entries(schema.paths)) {
    if (!pfad.startsWith(modulPfad) || !istObjekt(operationen)) continue;
    for (const [methode, operation] of Object.entries(operationen)) {
      const op = operation as OpenApiOperation;
      endpunkte.push({
        methode: methode.toUpperCase(),
        pfad,
        beschreibung: op.summary ?? op.description ?? "",
      });
    }
  }
  return endpunkte.sort((a, b) => a.pfad.localeCompare(b.pfad));
}
