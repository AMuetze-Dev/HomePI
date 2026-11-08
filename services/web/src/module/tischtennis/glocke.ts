/**
 * Die Glocke: „sag mir, wenn ich als nächster dran bin".
 *
 * Sie lebt vollständig im Gerät. Wer auf dem Dashboard seinen Namen antippt,
 * schreibt das in den `localStorage` dieses Browsers - und sonst nirgendwohin.
 * Das ist nicht nur sparsam, sondern die richtige Stelle: der Server müsste
 * sonst wissen, welches Handy zu welchem Kollegen gehört, und niemand müsste
 * ihm das sagen.
 *
 * Der Preis steht im Vertrag mit dem Benutzer und wird in der Oberfläche auch
 * so gesagt: es wirkt, solange die Seite offen ist. Echtes Web-Push bräuchte
 * einen Service Worker, VAPID-Schlüssel im Gateway und ein gültiges
 * Zertifikat auf dem Pi.
 *
 * Jeder Zugriff auf `localStorage` ist eingepackt: im privaten Fenster und
 * bei gesperrten Website-Daten wirft er, und eine Seite, die daran scheitert,
 * zeigt das Turnier nicht mehr an.
 */

const SCHLUESSEL = "homepi.tischtennis.glocke";

export function geweckte(): string[] {
  try {
    const gespeichert = window.localStorage.getItem(SCHLUESSEL);
    const gelesen: unknown = gespeichert ? JSON.parse(gespeichert) : [];
    return Array.isArray(gelesen)
      ? gelesen.filter((e): e is string => typeof e === "string")
      : [];
  } catch {
    return [];
  }
}

export function merken(kennungen: string[]): void {
  try {
    window.localStorage.setItem(SCHLUESSEL, JSON.stringify(kennungen));
  } catch {
    /* Privates Fenster oder gesperrte Website-Daten: die Glocke gilt dann
       nur für diese Sitzung. Besser als keine Glocke. */
  }
}

export function umschalten(kennungen: string[], wer: string): string[] {
  const neu = kennungen.includes(wer)
    ? kennungen.filter((e) => e !== wer)
    : [...kennungen, wer];
  merken(neu);
  return neu;
}

let klang: AudioContext | null = null;

/**
 * Den Ton vorbereiten - im Klick, mit dem die Glocke angeht.
 *
 * Browser lassen Ton nur nach einer Benutzerinteraktion zu. Ohne diese Zeile
 * im Klick bleibt die erste Benachrichtigung stumm, und genau die ist die,
 * auf die jemand gewartet hat.
 */
export function tonVorbereiten(): void {
  try {
    klang ??= new AudioContext();
    void klang.resume();
  } catch {
    /* Kein Ton in dieser Umgebung - das Banner kommt trotzdem. */
  }
}

/** Zwei kurze Töne. Kein Tondatei-Anhang, nur ein Oszillator. */
export function laeuten(): void {
  if (klang === null) return;
  try {
    [0, 0.25].forEach((versatz) => {
      const ton = klang!.createOscillator();
      const lautstaerke = klang!.createGain();
      ton.type = "sine";
      ton.frequency.value = 880;
      lautstaerke.gain.setValueAtTime(0.0001, klang!.currentTime + versatz);
      lautstaerke.gain.exponentialRampToValueAtTime(
        0.3,
        klang!.currentTime + versatz + 0.02,
      );
      lautstaerke.gain.exponentialRampToValueAtTime(
        0.0001,
        klang!.currentTime + versatz + 0.18,
      );
      ton.connect(lautstaerke).connect(klang!.destination);
      ton.start(klang!.currentTime + versatz);
      ton.stop(klang!.currentTime + versatz + 0.2);
    });
  } catch {
    /* Ton gescheitert - das Banner bleibt. */
  }
}

export function ruettele(): void {
  try {
    navigator.vibrate?.([200, 100, 200]);
  } catch {
    /* Geräte ohne Vibration, und alle Rechner. */
  }
}

/**
 * Fragt die Erlaubnis für eine Browser-Benachrichtigung.
 *
 * Nur auf Knopfdruck gefragt und nie beim Laden der Seite: eine Nachfrage,
 * die ungefragt aufpoppt, wird weggeklickt - und dann ist sie für diese
 * Adresse dauerhaft verweigert.
 */
export async function erlaubnisFragen(): Promise<boolean> {
  try {
    if (!("Notification" in window)) return false;
    if (Notification.permission === "granted") return true;
    if (Notification.permission === "denied") return false;
    return (await Notification.requestPermission()) === "granted";
  } catch {
    return false;
  }
}

export function benachrichtigen(titel: string, text: string): void {
  try {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(titel, { body: text, tag: "tischtennis-glocke" });
    }
  } catch {
    /* Auch ohne Benachrichtigung bleibt Banner, Ton und Vibration. */
  }
}

/** Alles zusammen: Ton, Vibration, Benachrichtigung. Das Banner macht die Seite. */
export function melden(titel: string, text: string): void {
  laeuten();
  ruettele();
  benachrichtigen(titel, text);
}
