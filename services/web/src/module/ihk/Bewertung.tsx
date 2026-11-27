import { useCallback, useEffect, useRef, useState } from "react";

import { Etikett, Karte, Knopf } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import type { Aendern } from "./PrueflingTafel";
import { FragenListe } from "./Fachgespraech";
import { Zeitmessung } from "./Zeitmessung";
import { useZitat } from "./Zitat";
import { note, punkte } from "./zeit";

interface Props {
  katalog: api.Katalog;
  pruefling: api.Pruefling;
  aendern: Aendern;
}

function blaetter(knoten: api.Knoten | api.Sektion): api.Knoten[] {
  if ("art" in knoten && knoten.kinder.length === 0)
    return knoten.art === "group" ? [] : [knoten];
  return knoten.kinder.flatMap(blaetter);
}

function knotenIn(sektion: api.Sektion): Map<string, api.Knoten> {
  const alle = new Map<string, api.Knoten>();
  const sammle = (k: api.Knoten) => {
    alle.set(k.id, k);
    k.kinder.forEach(sammle);
  };
  sektion.kinder.forEach(sammle);
  return alle;
}

/** Ganze Punkte, bei den Mängeln von -2 bis 0. */
function optionen(knoten: api.Knoten): number[] {
  const max = knoten.max ?? 0;
  return max < 0
    ? Array.from({ length: -max + 1 }, (_, i) => max + i)
    : Array.from({ length: max + 1 }, (_, i) => i);
}

function Summe({
  ergebnis,
  titel,
  anzahl,
  aktion,
}: {
  ergebnis: api.TeilErgebnis;
  titel: string;
  anzahl: string;
  aktion?: React.ReactNode;
}) {
  return (
    <Karte>
      <div className={stil.summe}>
        <span className={stil.summenzahl}>
          {titel}: {punkte(ergebnis.gesamt)} / 100 P
        </span>
        <span className={stil.note}>Note {note(ergebnis.note)}</span>
        {ergebnis.grenzfall && <Etikett ton="warnung">Grenzfall beachten</Etikett>}
        {aktion && <span className={stil.summeaktion}>{aktion}</span>}
      </div>
      {ergebnis.fehlend.length > 0 && <p className={stil.leise}>{anzahl}</p>}
    </Karte>
  );
}

/**
 * Ein Bemerkungsfeld, das beim Verlassen speichert und zwischendurch nach
 * einer Pause - ein Absturz mitten in der Prüfung kostet so höchstens den
 * letzten Satz.
 */
export function Bemerkung({
  wert,
  beschriftung,
  zeilen = 2,
  onSpeichern,
}: {
  wert: string;
  beschriftung: string;
  zeilen?: number;
  onSpeichern: (text: string) => void;
}) {
  const [entwurf, setEntwurf] = useState(wert);
  const geaendert = useRef(false);
  const feld = useRef<HTMLTextAreaElement>(null);
  const zitat = useZitat();

  // Fügt an der Schreibmarke ein - auf eigener Zeile, wenn dort schon Text steht.
  const einfuegen = useCallback((text: string) => {
    const el = feld.current;
    if (!el) return;
    const pos = el.selectionStart ?? el.value.length;
    const davor = el.value.slice(0, pos);
    const zusatz = davor !== "" && !davor.endsWith("\n") ? `\n${text}` : text;
    const neu = davor + zusatz + el.value.slice(pos);
    geaendert.current = true;
    setEntwurf(neu);
    el.focus();
    window.requestAnimationFrame(() => {
      el.selectionStart = el.selectionEnd = pos + zusatz.length;
    });
  }, []);

  // Abmelden erst, wenn das Feld verschwindet. An setzeZiel und nicht am
  // ganzen Kontext gehängt: Der ändert sich mit jeder Anmeldung, und das Feld
  // meldete sich sonst im selben Augenblick wieder ab.
  const setzeZiel = zitat?.setzeZiel;
  useEffect(() => {
    if (!setzeZiel) return;
    return () => setzeZiel(null, einfuegen);
  }, [setzeZiel, einfuegen]);

  useEffect(() => {
    if (!geaendert.current) setEntwurf(wert);
  }, [wert]);

  useEffect(() => {
    if (!geaendert.current) return;
    const uhr = window.setTimeout(() => {
      geaendert.current = false;
      onSpeichern(entwurf);
    }, 500);
    return () => window.clearTimeout(uhr);
  }, [entwurf, onSpeichern]);

  return (
    <textarea
      ref={feld}
      className={stil.textfeld}
      aria-label={beschriftung}
      onFocus={() => zitat?.setzeZiel(einfuegen)}
      placeholder={beschriftung}
      rows={zeilen}
      value={entwurf}
      onChange={(e) => {
        geaendert.current = true;
        setEntwurf(e.target.value);
      }}
      onBlur={() => {
        if (geaendert.current) {
          geaendert.current = false;
          onSpeichern(entwurf);
        }
      }}
    />
  );
}

/** Welche Sektionen zugeklappt sind - je Reiter, nicht gespeichert. */
function useEinklappen(ids: string[]) {
  const [zu, setZu] = useState<Set<string>>(new Set());
  const alleZu = ids.every((id) => zu.has(id));
  return {
    offen: (id: string) => !zu.has(id),
    umschalten: (id: string) =>
      setZu((alt) => {
        const neu = new Set(alt);
        if (neu.has(id)) neu.delete(id);
        else neu.add(id);
        return neu;
      }),
    knopf: (
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={() => setZu(alleZu ? new Set() : new Set(ids))}
      >
        {alleZu ? "Alle aufklappen" : "Alle einklappen"}
      </Knopf>
    ),
  };
}

/**
 * Eine Sektion des Rasters. Zugeklappt bleibt der Kopf mit der Summe stehen -
 * eine fertige Sektion braucht man nicht mehr in ganzer Länge, ihre Punkte aber
 * schon.
 */
function SektionKarte({
  id,
  titel,
  summe,
  offen,
  onUmschalten,
  children,
}: {
  id: string;
  titel: string;
  summe: string;
  offen: boolean;
  onUmschalten: () => void;
  children: React.ReactNode;
}) {
  return (
    <Karte>
      <section aria-labelledby={`k-${id}`} className={stil.sektion}>
        <h3 id={`k-${id}`} className={stil.sektionstitel}>
          <button
            type="button"
            className={stil.sektionskopf}
            aria-expanded={offen}
            aria-controls={`inhalt-${id}`}
            onClick={onUmschalten}
          >
            <span>
              <span className={stil.pfeil} aria-hidden="true">
                {offen ? "▾" : "▸"}{" "}
              </span>
              {titel}
            </span>
            <span className={stil.sektionssumme}>{summe}</span>
          </button>
        </h3>
        {offen && (
          <div id={`inhalt-${id}`} className={stil.sektion}>
            {children}
          </div>
        )}
      </section>
    </Karte>
  );
}

function Punktwahl({
  knoten,
  wert,
  onWahl,
  eingerueckt,
}: {
  knoten: api.Knoten;
  wert: number | undefined;
  onWahl: (wert: number | null) => void;
  eingerueckt: boolean;
}) {
  return (
    <div
      className={eingerueckt ? `${stil.kriterium} ${stil.eingerueckt}` : stil.kriterium}
    >
      <div className={stil.kriteriumtext}>
        <span>{knoten.label}</span>
        <span className={stil.leise}> ({knoten.max} P)</span>
        {knoten.hinweis && <span className={stil.hinweistext}>{knoten.hinweis}</span>}
      </div>
      <div
        role="group"
        aria-label={`${knoten.label} (${knoten.max} P)`}
        className={stil.punkte}
      >
        {optionen(knoten).map((o) => (
          <button
            key={o}
            type="button"
            className={stil.punkt}
            aria-pressed={wert === o}
            onClick={() => onWahl(wert === o ? null : o)}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DokuFormular({ katalog, pruefling: p, aendern }: Props) {
  const ergebnis = p.auswertung.doku;
  const anzahl = katalog.doku.flatMap(blaetter).length;
  const setze = (doku: Record<string, number | null>) =>
    void aendern(() => api.aendereBewertung(p.id, { doku }));
  const bemerke = (id: string, text: string) =>
    void aendern(() => api.aendereBewertung(p.id, { doku_bemerkungen: { [id]: text } }));
  const klappen = useEinklappen(katalog.doku.map((s) => s.id));

  return (
    <>
      <Summe
        ergebnis={ergebnis}
        titel="Dokumentation"
        aktion={klappen.knopf}
        anzahl={`${ergebnis.fehlend.length} von ${anzahl} Kriterien offen - noch keine Gesamtpunktzahl.`}
      />
      {katalog.doku.map((sektion) => {
        const s = ergebnis.sektionen.find((e) => e.id === sektion.id);
        const knoten = knotenIn(sektion);
        return (
          <SektionKarte
            key={sektion.id}
            id={sektion.id}
            titel={`${sektion.nr}. ${sektion.label}`}
            summe={`${punkte(s?.wert ?? null)} / ${sektion.max} P`}
            offen={klappen.offen(sektion.id)}
            onUmschalten={() => klappen.umschalten(sektion.id)}
          >
            {/* Ein Bemerkungsfeld je Block - dieselbe Aufteilung wie der Bogen. */}
            {sektion.bloecke.map((block) => {
              const erster = block.knoten[0] ? knoten.get(block.knoten[0]) : undefined;
              const verschachtelt = erster?.art === "group";
              return (
                <div key={block.id} className={stil.block}>
                  {block.knoten.map((kid) => {
                    const k = knoten.get(kid);
                    if (!k) return null;
                    if (k.art === "group") {
                      return (
                        <p key={k.id} className={stil.gruppe}>
                          {k.label} <span className={stil.leise}>({k.max} P)</span>
                        </p>
                      );
                    }
                    return (
                      <Punktwahl
                        key={k.id}
                        knoten={k}
                        wert={p.bewertung.doku[k.id]}
                        eingerueckt={verschachtelt}
                        onWahl={(w) => setze({ [k.id]: w })}
                      />
                    );
                  })}
                  <Bemerkung
                    wert={p.bewertung.doku_bemerkungen[block.id] ?? ""}
                    beschriftung={`Bemerkung zu ${erster ? erster.label : sektion.label}`}
                    onSpeichern={(text) => bemerke(block.id, text)}
                  />
                </div>
              );
            })}
          </SektionKarte>
        );
      })}
    </>
  );
}

/** Prozent statt Brüchen: "75 %" liest man im Vorbeigehen, "¾" muss man
 *  erst übersetzen - und das während der Prüfling spricht. */
function prozent(stufe: number): string {
  return `${Math.round(stufe * 100)} %`;
}

function SektionsPunkte({
  sektion,
  wert,
  vorschlag,
  onSetzen,
}: {
  sektion: api.Sektion;
  wert: number | undefined;
  vorschlag: number | null;
  onSetzen: (wert: number | null) => void;
}) {
  const [entwurf, setEntwurf] = useState(wert === undefined ? "" : String(wert));
  useEffect(() => setEntwurf(wert === undefined ? "" : String(wert)), [wert]);

  function uebernehmen() {
    const neu = entwurf.trim() === "" ? null : Number(entwurf);
    if (neu !== (wert ?? null)) onSetzen(neu);
  }

  return (
    <div className={stil.zeilenformular}>
      <label className={stil.auswahlgruppe}>
        <span className={stil.beschriftung}>Punkte (0 bis {sektion.max})</span>
        <input
          className={stil.zahlfeld}
          type="number"
          inputMode="numeric"
          min={0}
          max={sektion.max}
          value={entwurf}
          onChange={(e) => setEntwurf(e.target.value)}
          onBlur={uebernehmen}
          onKeyDown={(e) => e.key === "Enter" && uebernehmen()}
        />
      </label>
      <Knopf
        groesse="sm"
        disabled={vorschlag === null}
        onClick={() => vorschlag !== null && onSetzen(vorschlag)}
      >
        {`Vorschlag ${punkte(vorschlag)} übernehmen`}
      </Knopf>
    </div>
  );
}

export function PraesiFormular({ katalog, pruefling: p, aendern }: Props) {
  const ergebnis = p.auswertung.praesentation;
  const b = p.bewertung;
  const setze = (aenderung: api.BewertungAenderung) =>
    void aendern(() => api.aendereBewertung(p.id, aenderung));
  const klappen = useEinklappen(katalog.praesentation.map((s) => s.id));

  return (
    <>
      <Zeitmessung katalog={katalog} pruefling={p} aendern={aendern} />
      <Summe
        ergebnis={ergebnis}
        titel="Präsentation und Fachgespräch"
        aktion={klappen.knopf}
        anzahl={`${ergebnis.fehlend.length} von ${katalog.praesentation.length} Sektionen ohne Punktzahl - noch keine Gesamtpunktzahl.`}
      />
      {katalog.praesentation.map((sektion) => {
        const s = ergebnis.sektionen.find((e) => e.id === sektion.id);
        return (
          <SektionKarte
            key={sektion.id}
            id={sektion.id}
            titel={`${sektion.nr}. ${sektion.label}`}
            summe={`${punkte(s?.wert ?? null)} / ${sektion.max} P`}
            offen={klappen.offen(sektion.id)}
            onUmschalten={() => klappen.umschalten(sektion.id)}
          >
            {sektion.fragen && (
              <FragenListe
                fragen={b.fg_fragen}
                skala={katalog.skala}
                onAendern={(neu) => setze({ fg_fragen: neu })}
              />
            )}
            {sektion.kinder.map((k) => (
              <div key={k.id} className={stil.kriterium}>
                <div className={stil.kriteriumtext}>{k.label}</div>
                <div role="group" aria-label={k.label} className={stil.punkte}>
                  {katalog.skala.map((stufe) => {
                    const gewaehlt = b.praesi_skala[k.id] === stufe;
                    return (
                      <button
                        key={stufe}
                        type="button"
                        className={stil.punkt}
                        aria-pressed={gewaehlt}
                        onClick={() =>
                          setze({ praesi_skala: { [k.id]: gewaehlt ? null : stufe } })
                        }
                      >
                        {prozent(stufe)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            <SektionsPunkte
              sektion={sektion}
              wert={b.praesi_punkte[sektion.id]}
              vorschlag={s?.vorschlag ?? null}
              onSetzen={(w) => setze({ praesi_punkte: { [sektion.id]: w } })}
            />
            <Bemerkung
              wert={b.praesi_bemerkungen[sektion.id] ?? ""}
              beschriftung={`Bemerkung zu ${sektion.label}`}
              onSpeichern={(text) =>
                setze({ praesi_bemerkungen: { [sektion.id]: text } })
              }
            />
          </SektionKarte>
        );
      })}
      <Karte>
        <section aria-labelledby="notizen" className={stil.sektion}>
          <h3 id="notizen" className={stil.sektionstitel}>
            Notizen <span className={stil.leise}>(werden nicht gedruckt)</span>
          </h3>
          <Bemerkung
            wert={b.notizen}
            zeilen={4}
            beschriftung="Notizen"
            onSpeichern={(text) => setze({ notizen: text })}
          />
        </section>
      </Karte>
    </>
  );
}
