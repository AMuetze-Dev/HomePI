/**
 * Aus einer Aufnahme wird, was der ESP32 ohne Decoder abspielen kann.
 *
 * Der Pi nimmt nur WAV, mono, 16 Bit, 22 050 Hz. Umgerechnet wird hier im
 * Browser und nicht auf dem Pi: Der Browser kann jedes Format lesen, das er
 * selbst aufnimmt (webm auf Android, mp4 auf dem iPhone), und das Gateway
 * braucht dafür kein ffmpeg.
 *
 * Zwei Schritte über die Umrechnung hinaus, beide für das Kind:
 *
 * - **Stille abschneiden.** Sonst kommt der Klang eine halbe Sekunde nach
 *   dem Druck auf den Knopf - und ein Baby verbindet beides nicht mehr.
 * - **Lautheit angleichen.** Sonst ist Omas Aufnahme doppelt so laut wie
 *   eure, und die Lautstärkegrenze am Gerät schützt nur vor der lauteren.
 */

export const ABTASTRATE = 22050;
export const HOECHSTDAUER_S = 30;

export function zuMono(kanaele: readonly Float32Array[]): Float32Array {
  const [erster] = kanaele;
  if (kanaele.length === 1 && erster) return erster;
  const laenge = Math.min(...kanaele.map((k) => k.length));
  const mono = new Float32Array(laenge);
  for (const kanal of kanaele) {
    for (let i = 0; i < laenge; i++)
      mono[i] = (mono[i] ?? 0) + (kanal[i] ?? 0) / kanaele.length;
  }
  return mono;
}

export function stilleKuerzen(
  werte: Float32Array,
  rate: number,
  { schwelle = 0.02, randMs = 80 }: { schwelle?: number; randMs?: number } = {},
): Float32Array {
  const laut = (i: number) => Math.abs(werte[i] ?? 0) > schwelle;
  let anfang = 0;
  while (anfang < werte.length && !laut(anfang)) anfang++;
  if (anfang === werte.length) return new Float32Array(0);
  let ende = werte.length - 1;
  while (ende > anfang && !laut(ende)) ende--;

  const rand = Math.round((randMs / 1000) * rate);
  return werte.slice(Math.max(0, anfang - rand), Math.min(werte.length, ende + 1 + rand));
}

export function angleichen(
  werte: Float32Array,
  {
    zielRms = 0.1,
    hoechsteSpitze = 0.89,
  }: { zielRms?: number; hoechsteSpitze?: number } = {},
): Float32Array {
  let summe = 0;
  let spitze = 0;
  for (const wert of werte) {
    summe += wert * wert;
    spitze = Math.max(spitze, Math.abs(wert));
  }
  if (spitze === 0) return werte;
  const rms = Math.sqrt(summe / werte.length);
  // Die Lautheit ist das Ziel, die Spitze die Grenze: lieber etwas leiser als
  // übersteuert. Ein verzerrter Klang klingt für ein Baby wie ein Fehler.
  const faktor = Math.min(zielRms / rms, hoechsteSpitze / spitze);
  return werte.map((wert) => wert * faktor);
}

export function alsWav(werte: Float32Array, rate: number): Uint8Array {
  const datenBytes = werte.length * 2;
  const wav = new Uint8Array(44 + datenBytes);
  const sicht = new DataView(wav.buffer);
  const text = (stelle: number, wort: string) => {
    for (let i = 0; i < wort.length; i++) sicht.setUint8(stelle + i, wort.charCodeAt(i));
  };

  text(0, "RIFF");
  sicht.setUint32(4, 36 + datenBytes, true);
  text(8, "WAVE");
  text(12, "fmt ");
  sicht.setUint32(16, 16, true);
  sicht.setUint16(20, 1, true); // PCM
  sicht.setUint16(22, 1, true); // mono
  sicht.setUint32(24, rate, true);
  sicht.setUint32(28, rate * 2, true);
  sicht.setUint16(32, 2, true);
  sicht.setUint16(34, 16, true);
  text(36, "data");
  sicht.setUint32(40, datenBytes, true);

  werte.forEach((wert, i) => {
    const begrenzt = Math.max(-1, Math.min(1, wert));
    const ganz = Math.round(begrenzt < 0 ? begrenzt * 0x8000 : begrenzt * 0x7fff);
    sicht.setInt16(44 + i * 2, ganz, true);
  });
  return wav;
}

/**
 * Der ganze Weg von einer Aufnahme oder Datei zur WAV für den Pi.
 *
 * Wirft mit einem Satz für Menschen, wenn nichts zu hören ist oder die
 * Aufnahme zu lang wird.
 */
export async function bereiteAuf(roh: Blob): Promise<Blob> {
  const kontext = new AudioContext();
  let gelesen: AudioBuffer;
  try {
    gelesen = await kontext.decodeAudioData(await roh.arrayBuffer());
  } catch {
    throw new Error("Diese Datei kann der Browser nicht als Ton lesen.");
  } finally {
    void kontext.close();
  }

  // Ein Offline-Kontext mit einem Kanal und der Zielrate rechnet um und
  // mischt dabei auf mono - in der Qualität des Browsers, nicht in der einer
  // selbstgeschriebenen Interpolation.
  const laenge = Math.ceil(gelesen.duration * ABTASTRATE);
  const offline = new OfflineAudioContext(1, Math.max(1, laenge), ABTASTRATE);
  const quelle = offline.createBufferSource();
  quelle.buffer = gelesen;
  quelle.connect(offline.destination);
  quelle.start();
  const umgerechnet = await offline.startRendering();

  const werte = angleichen(stilleKuerzen(umgerechnet.getChannelData(0), ABTASTRATE));
  if (werte.length === 0) throw new Error("In der Aufnahme ist nichts zu hören.");
  const sekunden = werte.length / ABTASTRATE;
  if (sekunden > HOECHSTDAUER_S) {
    throw new Error(
      `Die Aufnahme ist ${Math.round(sekunden)} Sekunden lang, höchstens ${HOECHSTDAUER_S} passen.`,
    );
  }
  return new Blob([alsWav(werte, ABTASTRATE)], { type: "audio/wav" });
}
