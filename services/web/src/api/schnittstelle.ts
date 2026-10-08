/**
 * Der eine Weg, mit dem eine Oberfläche ihr Artefakt anspricht.
 *
 * Bis hierher brachte jedes Artefakt seine eigene Kopie derselben dreißig
 * Zeilen mit - sechs Stück, fast gleich. Die Vorlage für neue Artefakte war
 * die siebte, und ihr fehlte `credentials: "include"`: Ein frisch angelegtes
 * Artefakt bekam auf jede Anfrage 401, obwohl jemand angemeldet war.
 *
 * Was hier steht, gilt für jedes Artefakt gleich: Sitzungscookie mitsenden,
 * JSON hin und zurück, Fehler aus problem+json (RFC 9457) als Satz für
 * Menschen. Ein Artefakt beschreibt nur noch seine Pfade und Typen.
 */
import { ApiError } from "./client";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

type Methode = "POST" | "PUT" | "PATCH" | "DELETE";

/** Fehlerformat des Backends (RFC 9457), wie homepi-core es schickt. */
interface Problem {
  title?: string;
  detail?: string;
  fehler?: { feld?: string; problem?: string }[];
}

export interface Schnittstelle {
  // Als Eigenschaften, nicht als Methoden: Sie hängen an keinem `this`, und
  // `const { anfrage } = schnittstelle(...)` ist der gedachte Gebrauch.

  /** Freie Anfrage relativ zum Artefakt. */
  anfrage: <T>(pfad: string, init?: RequestInit, signal?: AbortSignal) => Promise<T>;
  /** Schreibende Anfrage; `daten` gehen als JSON hinaus. */
  sende: <T>(methode: Methode, pfad: string, daten?: unknown) => Promise<T>;
  /** Volle Adresse, für alles, was der Browser selbst lädt - ein PDF etwa. */
  adresse: (pfad: string) => string;
}

/**
 * Die Felder, die das Backend abgelehnt hat - ohne "body."/"query.", denn
 * das ist Aufbau der Anfrage, nicht Wortschatz des Benutzers.
 */
function felder(problem: Problem): string {
  const namen = (problem.fehler ?? [])
    .map((f) => f.feld?.split(".").slice(1).join(".") || f.feld)
    .filter((n): n is string => Boolean(n));
  return namen.length > 0 ? ` (${[...new Set(namen)].join(", ")})` : "";
}

async function meldung(antwort: Response): Promise<string> {
  try {
    const problem = (await antwort.json()) as Problem;
    const satz = problem.detail ?? problem.title;
    if (satz) return satz + felder(problem);
  } catch {
    /* Antwort ohne JSON-Körper - etwa von einem Proxy davor */
  }
  return `Fehler ${antwort.status}`;
}

/**
 * Schnittstelle zu einem Artefakt, etwa `schnittstelle("/geraete")`.
 *
 * `basis` ist der Pfad, unter dem das Gateway das Artefakt einhängt - also
 * `/` + seine id.
 */
export function schnittstelle(basis: string): Schnittstelle {
  async function anfrage<T>(
    pfad: string,
    init: RequestInit = {},
    signal?: AbortSignal,
  ): Promise<T> {
    const antwort = await fetch(`${BASE_URL}${basis}${pfad}`, {
      ...init,
      signal: signal ?? init.signal ?? null,
      // Das Sitzungscookie ist httponly. Ohne diese Zeile antwortet das
      // Gateway so, als wäre niemand angemeldet.
      credentials: "include",
      headers: { Accept: "application/json", ...init.headers },
    });

    if (!antwort.ok) throw new ApiError(await meldung(antwort), antwort.status);
    if (antwort.status === 204) return undefined as T;
    return (await antwort.json()) as T;
  }

  function sende<T>(methode: Methode, pfad: string, daten?: unknown): Promise<T> {
    if (daten === undefined) return anfrage<T>(pfad, { method: methode });
    return anfrage<T>(pfad, {
      method: methode,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(daten),
    });
  }

  return { anfrage, sende, adresse: (pfad) => `${BASE_URL}${basis}${pfad}` };
}
