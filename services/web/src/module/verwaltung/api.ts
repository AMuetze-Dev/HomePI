import type { Rolle } from "../../api/anmeldung";
import { schnittstelle } from "../../api/schnittstelle";

const API = schnittstelle("/verwaltung");

export type { Rolle };

export interface Konto {
  id: string;
  name: string;
  anzeigename: string;
  aktiv: boolean;
  /** Artefakt → Rolle. */
  rechte: Record<string, Rolle>;
  angelegt: string | null;
  /** Darf dieses Konto die Verwaltung? Blendet Knöpfe aus - geprüft wird im Backend. */
  verwalter: boolean;
  /** True, solange das Passwort von jemand anderem gesetzt wurde. */
  passwort_wechseln: boolean;
}

/** Die Antwort aufs Anlegen - einmalig mit dem Startpasswort. */
export interface KontoAngelegt extends Konto {
  /** Nur hier. Danach ist es nicht mehr abrufbar. */
  startpasswort: string;
}

export interface Artefakt {
  id: string;
  titel: string;
  zugang: string;
}

export interface NeuesKonto {
  name: string;
  anzeigename?: string;
}

const { anfrage } = API;

export function ladeKonten(signal?: AbortSignal): Promise<Konto[]> {
  return anfrage<Konto[]>("/benutzer", {}, signal);
}

export function ladeArtefakte(signal?: AbortSignal): Promise<Artefakt[]> {
  return anfrage<Artefakt[]>("/artefakte", {}, signal);
}

export function legeKontoAn(daten: NeuesKonto): Promise<KontoAngelegt> {
  return anfrage<KontoAngelegt>("/benutzer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}

export function setzeAktiv(id: string, aktiv: boolean): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aktiv }),
  });
}

export function setzeAnzeigename(id: string, anzeigename: string): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ anzeigename }),
  });
}

/**
 * Setzt das Passwort zurück. Der Dienst erzeugt ein Startpasswort und gibt es
 * einmalig zurück; der Benutzer ersetzt es beim nächsten Anmelden.
 *
 * Ohne Körper, und das ist der Punkt: ein Passwort vorzugeben ist hier nicht
 * vorgesehen. Was ein Verwalter tippt, kennt er auch.
 */
export function setzePasswort(id: string): Promise<{ startpasswort: string }> {
  return anfrage<{ startpasswort: string }>(`/benutzer/${id}/passwort`, {
    method: "PUT",
  });
}

export function loescheKonto(id: string): Promise<void> {
  return anfrage<void>(`/benutzer/${id}`, { method: "DELETE" });
}

export function setzeRecht(id: string, artefakt: string, rolle: Rolle): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}/rechte/${artefakt}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rolle }),
  });
}

export function entzieheRecht(id: string, artefakt: string): Promise<Konto> {
  return anfrage<Konto>(`/benutzer/${id}/rechte/${artefakt}`, { method: "DELETE" });
}
