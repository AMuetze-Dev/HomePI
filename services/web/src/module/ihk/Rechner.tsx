import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Etikett, Feld, Hinweis, Karte, Tafel } from "../../ui";
import * as api from "./api";
import { Lade } from "./IhkSeite";
import stil from "./IhkSeite.module.css";
import { meldung, note, punkte } from "./zeit";

/** Wartet kurz, bis nicht mehr getippt wird - eine Anfrage je Zahl, nicht je Ziffer. */
const PAUSE_MS = 250;

function alsZahl(text: string): number | null {
  return text.trim() === "" ? null : Number(text);
}

/**
 * Rechnet, ohne dass ein Prüfling dafür angelegt werden muss: im Ausschuss,
 * wenn jemand fragt „was wäre, wenn“, oder beim Gegenlesen eines Bogens.
 *
 * Gerechnet wird im Backend wie überall - hier steht nur die Eingabe.
 */
export function RechnerTafel() {
  const [katalog, setKatalog] = useState<api.Katalog | null>(null);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const steuerung = new AbortController();
    api
      .ladeKatalog(steuerung.signal)
      .then(setKatalog)
      .catch((e: unknown) => {
        if (!steuerung.signal.aborted) setFehler(meldung(e));
      });
    return () => steuerung.abort();
  }, []);

  if (fehler) {
    return (
      <Tafel titel="Notenrechner">
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      </Tafel>
    );
  }
  if (!katalog) return <Lade titel="Notenrechner" />;

  return (
    <Tafel titel="Notenrechner" beiwort="rechnet nur - es wird nichts gespeichert">
      <Link to="?" className={stil.zurueck}>
        ← Prüfungstage
      </Link>
      <PunkteZuNote />
      <Gesamtrechner katalog={katalog} />
    </Tafel>
  );
}

function Stufe({ stufe }: { stufe: api.Notenstufe }) {
  return (
    <div className={stil.stufe}>
      <span className={stil.grossnote}>{note(stufe.note)}</span>
      <span className={stil.leise}>
        {stufe.punkte} P · ganze Note {stufe.ganze_note}
      </span>
      {stufe.grenzfall && <Etikett ton="warnung">Grenzfall</Etikett>}
      <span className={stil.leise}>
        {stufe.bessere_note !== null && `${stufe.fehlen} P bis zur ${stufe.bessere_note}`}
        {stufe.bessere_note !== null && stufe.ganze_note < 6 && " · "}
        {stufe.ganze_note < 6 &&
          (stufe.puffer === 0
            ? "ein Punkt weniger, und die Note sinkt"
            : `${stufe.puffer} P Puffer nach unten`)}
      </span>
    </div>
  );
}

function PunkteZuNote() {
  const [eingabe, setEingabe] = useState("");
  const [stufe, setStufe] = useState<api.Notenstufe | null>(null);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const wert = alsZahl(eingabe);
    if (wert === null) {
      setStufe(null);
      setFehler("");
      return;
    }
    const steuerung = new AbortController();
    const uhr = window.setTimeout(() => {
      api
        .ladeNotenstufe(wert, steuerung.signal)
        .then((s) => {
          setStufe(s);
          setFehler("");
        })
        .catch((e: unknown) => {
          if (steuerung.signal.aborted) return;
          setStufe(null);
          setFehler(meldung(e));
        });
    }, PAUSE_MS);
    return () => {
      window.clearTimeout(uhr);
      steuerung.abort();
    };
  }, [eingabe]);

  return (
    <Karte>
      <section aria-labelledby="punkte-note" className={stil.sektion}>
        <h2 id="punkte-note" className={stil.sektionstitel}>
          Punkte → Note
        </h2>
        <div className={stil.rechnerzeile}>
          <Feld
            beschriftung="Punkte"
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            value={eingabe}
            onChange={(e) => setEingabe(e.target.value)}
          />
          {stufe && <Stufe stufe={stufe} />}
        </div>
        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}
      </section>
    </Karte>
  );
}

type Feldname =
  "teil1" | "planen_softwareprodukt" | "algorithmen" | "wiso" | "doku" | "praesentation";

const LEER: Record<Feldname, string> = {
  teil1: "",
  planen_softwareprodukt: "",
  algorithmen: "",
  wiso: "",
  doku: "",
  praesentation: "",
};

function Gesamtrechner({ katalog }: { katalog: api.Katalog }) {
  const [felder, setFelder] = useState(LEER);
  const [mepBereich, setMepBereich] = useState<api.MepBereich | "">("");
  const [mepPunkte, setMepPunkte] = useState("");
  const [ergebnis, setErgebnis] = useState<api.RechnerErgebnis | null>(null);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    // Leer gibt es nichts zu rechnen - und keine Anfrage.
    if (Object.values(felder).every((w) => w.trim() === "") && !mepBereich) {
      setErgebnis(null);
      setFehler("");
      return;
    }
    const steuerung = new AbortController();
    const uhr = window.setTimeout(() => {
      api
        .rechne(
          {
            teil1: alsZahl(felder.teil1),
            planen_softwareprodukt: alsZahl(felder.planen_softwareprodukt),
            algorithmen: alsZahl(felder.algorithmen),
            wiso: alsZahl(felder.wiso),
            doku: alsZahl(felder.doku),
            praesentation: alsZahl(felder.praesentation),
            mep: mepBereich
              ? { bereich: mepBereich, punkte: alsZahl(mepPunkte) ?? 0 }
              : null,
          },
          steuerung.signal,
        )
        .then((e) => {
          setErgebnis(e);
          setFehler("");
        })
        .catch((e: unknown) => {
          if (!steuerung.signal.aborted) setFehler(meldung(e));
        });
    }, PAUSE_MS);
    return () => {
      window.clearTimeout(uhr);
      steuerung.abort();
    };
  }, [felder, mepBereich, mepPunkte]);

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

  return (
    <Karte>
      <section aria-labelledby="gesamtrechner" className={stil.sektion}>
        <h2 id="gesamtrechner" className={stil.sektionstitel}>
          Gesamtergebnis
        </h2>
        <div className={stil.rechnerspalten}>
          <div className={stil.sektion}>
            {zahlfeld("teil1", katalog.teil1_label)}
            {katalog.bereiche.map((b) => zahlfeld(b.id, b.label))}
            {zahlfeld("doku", "Dokumentation")}
            {zahlfeld("praesentation", "Präsentation und Fachgespräch")}
            <div className={stil.zeilenformular}>
              <label className={stil.auswahlgruppe}>
                <span className={stil.beschriftung}>Ergänzungsprüfung in</span>
                <select
                  className={stil.auswahl}
                  value={mepBereich}
                  onChange={(e) => setMepBereich(e.target.value as api.MepBereich | "")}
                >
                  <option value="">keinem Bereich</option>
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
          </div>

          <div className={stil.sektion} aria-live="polite">
            {fehler && (
              <Hinweis ton="fehler" dringend>
                {fehler}
              </Hinweis>
            )}
            {ergebnis && (
              <>
                <Ergebnisblock
                  titel="Ohne Ergänzungsprüfung"
                  ergebnis={ergebnis.ohne_mep}
                  stufe={ergebnis.stufe_ohne_mep}
                  projekt={katalog.projekt_label}
                />
                {ergebnis.mit_mep && (
                  <Ergebnisblock
                    titel="Mit Ergänzungsprüfung"
                    ergebnis={ergebnis.mit_mep}
                    stufe={ergebnis.stufe_mit_mep}
                    projekt={katalog.projekt_label}
                  />
                )}
                {(ergebnis.stufe_doku || ergebnis.stufe_praesentation) && (
                  <dl className={stil.ergebnisliste}>
                    {ergebnis.stufe_doku && (
                      <div className={stil.ergebniszeile}>
                        <dt>Dokumentation</dt>
                        <dd>
                          {ergebnis.stufe_doku.punkte} P ·{" "}
                          {note(ergebnis.stufe_doku.note)}
                          {ergebnis.stufe_doku.grenzfall && " · Grenzfall"}
                        </dd>
                      </div>
                    )}
                    {ergebnis.stufe_praesentation && (
                      <div className={stil.ergebniszeile}>
                        <dt>Präsentation</dt>
                        <dd>
                          {ergebnis.stufe_praesentation.punkte} P ·{" "}
                          {note(ergebnis.stufe_praesentation.note)}
                          {ergebnis.stufe_praesentation.grenzfall && " · Grenzfall"}
                        </dd>
                      </div>
                    )}
                  </dl>
                )}
              </>
            )}
          </div>
        </div>
      </section>
    </Karte>
  );
}

function Ergebnisblock({
  titel,
  ergebnis,
  stufe,
  projekt,
}: {
  titel: string;
  ergebnis: api.GesamtErgebnis;
  stufe: api.Notenstufe | null;
  projekt: string;
}) {
  return (
    <section aria-label={titel} className={stil.sektion}>
      <h3 className={stil.beschriftung}>{titel}</h3>
      <dl className={stil.ergebnisliste}>
        <div className={stil.ergebniszeile}>
          <dt>{projekt}</dt>
          <dd>{punkte(ergebnis.projekt)} P</dd>
        </div>
        {ergebnis.bereiche
          .filter((b) => b.muendlich !== null)
          .map((b) => (
            <div key={b.id} className={stil.ergebniszeile}>
              <dt>{b.label} mit mündlich</dt>
              <dd>{punkte(b.wert)} P</dd>
            </div>
          ))}
      </dl>
      <p className={stil.summenzahl}>
        Teil 2: {punkte(ergebnis.teil2)} P · Gesamt: {punkte(ergebnis.gesamt)} P
      </p>
      {stufe ? (
        <Stufe stufe={stufe} />
      ) : (
        <p className={stil.leise}>Es fehlen noch Teilergebnisse.</p>
      )}
    </section>
  );
}
