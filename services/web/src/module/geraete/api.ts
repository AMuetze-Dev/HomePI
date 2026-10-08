import { schnittstelle } from "../../api/schnittstelle";

const API = schnittstelle("/geraete");

export type GeraetZustand = "bereit" | "wartung";

export interface Geraet {
  id: string;
  name: string;
  raum: string;
  zustand: GeraetZustand;
  eingeschaltet: boolean;
}

export interface Zusammenfassung {
  anzahl: number;
  eingeschaltet: number;
  in_wartung: number;
  raeume: Record<string, number>;
}

export interface NeuesGeraet {
  name: string;
  raum: string;
  zustand?: GeraetZustand;
}

const { anfrage } = API;

export function ladeGeraete(signal?: AbortSignal): Promise<Geraet[]> {
  return anfrage<Geraet[]>("/", {}, signal);
}

export function ladeZusammenfassung(signal?: AbortSignal): Promise<Zusammenfassung> {
  return anfrage<Zusammenfassung>("/zusammenfassung", {}, signal);
}

export function legeGeraetAn(daten: NeuesGeraet): Promise<Geraet> {
  return anfrage<Geraet>("/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(daten),
  });
}

export function schalteGeraet(id: string, eingeschaltet: boolean): Promise<Geraet> {
  return anfrage<Geraet>(`/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ eingeschaltet }),
  });
}

export function entferneGeraet(id: string): Promise<void> {
  return anfrage<void>(`/${id}`, { method: "DELETE" });
}
