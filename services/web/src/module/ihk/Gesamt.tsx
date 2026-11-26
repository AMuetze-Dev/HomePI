import { useEffect, useState, type FormEvent } from "react";

import { Etikett, Karte, Knopf } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import type { Aendern } from "./PrueflingTafel";
import { note, punkte } from "./zeit";

type Feldname = "teil1" | api.MepBereich;

function alsText(wert: number | null): string {
  return wert === null ? "" : String(wert);
}

function alsZahl(text: string): number | null {
  return text.trim() === "" ? null : Number(text);
}

function Ergebnis({
  titel,
  ergebnis,
  projektLabel,
}: {
  titel: string;
  ergebnis: api.GesamtErgebnis;
  projektLabel: string;
}) {
  return (
    <Karte>
      <section aria-label={titel} className={stil.sektion}>
        <h3 className={stil.sektionstitel}>{titel}</h3>
        <dl className={stil.ergebnisliste}>
          <div className={stil.ergebniszeile}>
            <dt>{projektLabel}</dt>
            <dd>{punkte(ergebnis.projekt)} P</dd>
          </div>
          {ergebnis.bereiche.map((b) => (
            <div key={b.id} className={stil.ergebniszeile}>
              <dt>
                {b.label}
                {b.muendlich !== null && (
                  <span className={stil.leise}>
                    {" "}
                    (schriftlich {b.schriftlich}, mündlich {b.muendlich})
                  </span>
                )}
              </dt>
              <dd>{punkte(b.wert)} P</dd>
            </div>
          ))}
        </dl>
        <div className={stil.summe}>
          <span className={stil.summenzahl}>
            Teil 2: {punkte(ergebnis.teil2)} P · Gesamt: {punkte(ergebnis.gesamt)} P
          </span>
          <span className={stil.note}>Note {note(ergebnis.note)}</span>
          {ergebnis.grenzfall && <Etikett ton="warnung">Grenzfall</Etikett>}
        </div>
        {ergebnis.fehlend.length > 0 && (
          <p className={stil.leise}>
            Es fehlen noch Teilergebnisse - kein Gesamtergebnis.
          </p>
        )}
      </section>
    </Karte>
  );
}

export function GesamtFormular({
  katalog,
  pruefling: p,
  aendern,
}: {
  katalog: api.Katalog;
  pruefling: api.Pruefling;
  aendern: Aendern;
}) {
  const t = p.teilnoten;
  const [felder, setFelder] = useState<Record<Feldname, string>>(() => ({
    teil1: alsText(t.teil1),
    planen_softwareprodukt: alsText(t.planen_softwareprodukt),
    algorithmen: alsText(t.algorithmen),
    wiso: alsText(t.wiso),
  }));
  const [mepBereich, setMepBereich] = useState<api.MepBereich | "">(t.mep?.bereich ?? "");
  const [mepPunkte, setMepPunkte] = useState(t.mep ? String(t.mep.punkte) : "");
  const [laeuft, setLaeuft] = useState(false);

  // Nach dem Speichern übernimmt das Formular, was das Backend zurückgibt.
  useEffect(() => {
    setFelder({
      teil1: alsText(t.teil1),
      planen_softwareprodukt: alsText(t.planen_softwareprodukt),
      algorithmen: alsText(t.algorithmen),
      wiso: alsText(t.wiso),
    });
    setMepBereich(t.mep?.bereich ?? "");
    setMepPunkte(t.mep ? String(t.mep.punkte) : "");
  }, [t]);

  async function absenden(e: FormEvent) {
    e.preventDefault();
    setLaeuft(true);
    // Schlägt es fehl, bleibt die Eingabe stehen: Der Zustand oben ändert
    // sich nur bei Erfolg, und nur dann zieht der Effekt neu.
    await aendern(() =>
      api.setzeTeilnoten(p.id, {
        teil1: alsZahl(felder.teil1),
        planen_softwareprodukt: alsZahl(felder.planen_softwareprodukt),
        algorithmen: alsZahl(felder.algorithmen),
        wiso: alsZahl(felder.wiso),
        mep: mepBereich ? { bereich: mepBereich, punkte: alsZahl(mepPunkte) ?? 0 } : null,
      }),
    );
    setLaeuft(false);
  }

  const zahlfeld = (name: Feldname, beschriftung: string) => (
    <label key={name} className={stil.zahlzeile}>
      <span>{beschriftung}</span>
      <input
        className={stil.zahlfeld}
        type="number"
        inputMode="numeric"
        min={0}
        max={100}
        value={felder[name]}
        onChange={(e) => setFelder({ ...felder, [name]: e.target.value })}
      />
    </label>
  );

  const { doku, praesentation, gesamt_ohne_mep, gesamt_mit_mep } = p.auswertung;

  return (
    <>
      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.sektion}>
          <h3 className={stil.sektionstitel}>Teil 1</h3>
          {zahlfeld("teil1", katalog.teil1_label)}
          <h3 className={stil.sektionstitel}>Teil 2 - schriftliche Prüfungsbereiche</h3>
          {katalog.bereiche.map((b) => zahlfeld(b.id, b.label))}
          <p className={stil.leise}>
            Dokumentation {punkte(doku.gesamt)} P und Präsentation{" "}
            {punkte(praesentation.gesamt)} P fließen als „{katalog.projekt_label}“ ein.
          </p>

          <h3 className={stil.sektionstitel}>Mündliche Ergänzungsprüfung</h3>
          <div className={stil.zeilenformular}>
            <label className={stil.auswahlgruppe}>
              <span className={stil.beschriftung}>Bereich der Ergänzungsprüfung</span>
              <select
                className={stil.auswahl}
                value={mepBereich}
                onChange={(e) => setMepBereich(e.target.value as api.MepBereich | "")}
              >
                <option value="">keine</option>
                {katalog.bereiche.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.label}
                  </option>
                ))}
              </select>
            </label>
            <label className={stil.auswahlgruppe}>
              <span className={stil.beschriftung}>Punkte mündlich</span>
              <input
                className={stil.zahlfeld}
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                disabled={!mepBereich}
                value={mepPunkte}
                onChange={(e) => setMepPunkte(e.target.value)}
              />
            </label>
          </div>
          <p className={stil.leise}>
            Schriftlich zählt doppelt, mündlich einfach: (2 × schriftlich + mündlich) / 3.
          </p>
          <div className={stil.knopfreihe}>
            <Knopf type="submit" auspraegung="primaer" disabled={laeuft}>
              {laeuft ? "Wird gespeichert …" : "Teilnoten speichern"}
            </Knopf>
          </div>
        </form>
      </Karte>

      <Ergebnis
        titel="Ergebnis ohne Ergänzungsprüfung"
        ergebnis={gesamt_ohne_mep}
        projektLabel={katalog.projekt_label}
      />
      {gesamt_mit_mep && (
        <Ergebnis
          titel="Ergebnis mit Ergänzungsprüfung"
          ergebnis={gesamt_mit_mep}
          projektLabel={katalog.projekt_label}
        />
      )}
    </>
  );
}
