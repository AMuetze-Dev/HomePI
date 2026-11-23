import { describe, expect, it } from "vitest";

import { ABTASTRATE, alsWav, angleichen, stilleKuerzen, zuMono } from "./audio";

function rms(werte: Float32Array): number {
  let summe = 0;
  for (const wert of werte) summe += wert * wert;
  return Math.sqrt(summe / werte.length);
}

function spitze(werte: Float32Array): number {
  let groesste = 0;
  for (const wert of werte) groesste = Math.max(groesste, Math.abs(wert));
  return groesste;
}

describe("zuMono", () => {
  it("mittelt die Kanäle", () => {
    const links = Float32Array.from([1, 0, -1]);
    const rechts = Float32Array.from([0, 0, 1]);

    expect(Array.from(zuMono([links, rechts]))).toEqual([0.5, 0, 0]);
  });

  it("lässt einen einzelnen Kanal, wie er ist", () => {
    const kanal = Float32Array.from([0.1, 0.2]);

    expect(zuMono([kanal])).toBe(kanal);
  });
});

describe("stilleKuerzen", () => {
  it("schneidet Stille vorn und hinten ab und lässt einen kleinen Rand", () => {
    // 1 s Stille, 1 s Ton, 1 s Stille bei 1000 Hz Abtastrate
    const rate = 1000;
    const werte = new Float32Array(3000);
    werte.fill(0.5, 1000, 2000);

    const gekuerzt = stilleKuerzen(werte, rate, { randMs: 50 });

    expect(gekuerzt.length).toBe(1000 + 2 * 50);
    expect(gekuerzt[0]).toBe(0);
    expect(gekuerzt[50]).toBe(0.5);
  });

  it("gibt bei reiner Stille nichts zurück", () => {
    expect(stilleKuerzen(new Float32Array(500), 1000).length).toBe(0);
  });

  it("geht am Rand nicht über die Aufnahme hinaus", () => {
    const werte = Float32Array.from([0.5, 0.5, 0.5]);

    expect(stilleKuerzen(werte, 1000, { randMs: 80 }).length).toBe(3);
  });
});

describe("angleichen", () => {
  it("bringt eine leise Aufnahme auf die Ziellautheit", () => {
    const leise = new Float32Array(1000).map((_, i) => 0.01 * Math.sin(i / 5));

    const laut = angleichen(leise, { zielRms: 0.1, hoechsteSpitze: 0.95 });

    expect(rms(laut)).toBeCloseTo(0.1, 2);
  });

  it("übersteuert nie, auch wenn die Lautheit dann nicht erreicht wird", () => {
    // Ein einzelnes Knacken in Stille: viel Spitze, wenig Lautheit.
    const knacken = new Float32Array(1000);
    knacken[500] = 0.5;

    const ergebnis = angleichen(knacken, { zielRms: 0.1, hoechsteSpitze: 0.9 });

    expect(spitze(ergebnis)).toBeCloseTo(0.9, 5);
  });

  it("lässt Stille in Ruhe, statt durch null zu teilen", () => {
    const stille = new Float32Array(10);

    expect(Array.from(angleichen(stille))).toEqual(Array.from(stille));
  });
});

describe("alsWav", () => {
  it("schreibt einen WAV-Kopf mit mono, 16 Bit und der Abtastrate", () => {
    const wav = alsWav(Float32Array.from([0, 1, -1]), ABTASTRATE);
    const kopf = new DataView(wav.buffer);
    const text = (von: number) => String.fromCharCode(...wav.slice(von, von + 4));

    expect(text(0)).toBe("RIFF");
    expect(text(8)).toBe("WAVE");
    expect(kopf.getUint16(20, true)).toBe(1); // PCM
    expect(kopf.getUint16(22, true)).toBe(1); // mono
    expect(kopf.getUint32(24, true)).toBe(22050);
    expect(kopf.getUint16(34, true)).toBe(16);
    expect(kopf.getUint32(40, true)).toBe(6);
    expect(wav.length).toBe(44 + 6);
  });

  it("begrenzt Werte jenseits von ±1, statt sie umklappen zu lassen", () => {
    const wav = alsWav(Float32Array.from([2, -2, 0.5]), ABTASTRATE);
    const daten = new DataView(wav.buffer, 44);

    expect(daten.getInt16(0, true)).toBe(32767);
    expect(daten.getInt16(2, true)).toBe(-32768);
    expect(daten.getInt16(4, true)).toBe(16384);
  });
});
