import { useState } from "react";

import { Abschnitt, Hinweis, Knopf, Schalter } from "../../ui";
import type { Aufnahme, Einstellungen, Spiel } from "./api";
import { Auswahl, Regler } from "./bausteine";
import stil from "./KinderzimmerSeite.module.css";

interface Props {
  einstellungen: Einstellungen;
  spiele: readonly Spiel[];
  aufnahmen: readonly Aufnahme[];
  darfAendern: boolean;
  onSpeichern: (werte: Einstellungen) => Promise<boolean>;
}

const OHNE = "";

/** Eine Farbe, die auf dem Gerät gut leuchtet und nicht blendet. */
const FARBVORSCHLAEGE = [
  "#FFB000",
  "#2F80ED",
  "#27AE60",
  "#EB5757",
  "#9B51E0",
  "#F2994A",
];

/**
 * Was das Gerät beim nächsten Abgleich übernimmt.
 *
 * Die Grenzen stehen oben, weil sie die wichtigsten sind: Lautstärke und
 * Helligkeit sind Obergrenzen, über die das Gerät nie hinausgeht - auch
 * nicht, wenn jemand am Gerät selbst dreht.
 */
export function EinstellungenTafel({
  einstellungen,
  spiele,
  aufnahmen,
  darfAendern,
  onSpeichern,
}: Props) {
  const [werte, setWerte] = useState<Einstellungen>(einstellungen);
  const [laeuft, setLaeuft] = useState(false);
  const [gespeichert, setGespeichert] = useState(false);

  const bereit = spiele.filter((s) => s.bereit);
  const titel = new Map(spiele.map((s) => [s.id, s.titel]));

  function setze<F extends keyof Einstellungen>(feld: F, wert: Einstellungen[F]) {
    setGespeichert(false);
    setWerte((vorher) => ({ ...vorher, [feld]: wert }));
  }

  function schalte(spielId: string, an: boolean) {
    const aktiv = an
      ? [...werte.spiele_aktiv, spielId]
      : werte.spiele_aktiv.filter((id) => id !== spielId);
    // Das Startspiel muss eingeschaltet sein. Wird es ausgeschaltet, rückt
    // das erste übrige nach, statt das Speichern scheitern zu lassen.
    const startspiel = aktiv.includes(werte.startspiel)
      ? werte.startspiel
      : (aktiv[0] ?? werte.startspiel);
    setGespeichert(false);
    setWerte((vorher) => ({ ...vorher, spiele_aktiv: aktiv, startspiel }));
  }

  function aendereKnopf(
    nummer: number,
    aenderung: Partial<Einstellungen["knoepfe"][number]>,
  ) {
    setze(
      "knoepfe",
      werte.knoepfe.map((k) => (k.nummer === nummer ? { ...k, ...aenderung } : k)),
    );
  }

  function knopfDazu() {
    const belegt = new Set(werte.knoepfe.map((k) => k.nummer));
    const nummer = [1, 2, 3, 4, 5, 6, 7, 8].find((n) => !belegt.has(n));
    if (nummer === undefined) return;
    const farbe =
      FARBVORSCHLAEGE[werte.knoepfe.length % FARBVORSCHLAEGE.length] ?? "#FFB000";
    setze("knoepfe", [...werte.knoepfe, { nummer, farbe, klang: null }]);
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (laeuft) return;
    setLaeuft(true);
    const geklappt = await onSpeichern(werte);
    setLaeuft(false);
    setGespeichert(geklappt);
  }

  const klaenge: (readonly [string, string])[] = [
    [OHNE, "Kein Klang, nur Licht"],
    ...aufnahmen.map((a) => [a.id, a.titel] as const),
  ];

  return (
    <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
      {!darfAendern && (
        <Hinweis>
          Ansehen geht, ändern darf nur, wer hier mindestens „nutzer“ ist.
        </Hinweis>
      )}

      <Abschnitt titel="Grenzen" regel>
        <div className={stil.formular}>
          <Regler
            beschriftung="Höchste Lautstärke"
            wert={werte.lautstaerke_max}
            min={5}
            max={100}
            einheit="%"
            hinweis="Kinderohren sind nah dran. Das Gerät wird nie lauter, auch nicht über seine eigenen Knöpfe. Fangt niedrig an."
            beiWechsel={(w) => setze("lautstaerke_max", w)}
            disabled={!darfAendern}
          />
          <Regler
            beschriftung="Höchste Helligkeit"
            wert={werte.helligkeit_max}
            min={5}
            max={100}
            einheit="%"
            hinweis="Das Licht blendet sanft über und blinkt nie."
            beiWechsel={(w) => setze("helligkeit_max", w)}
            disabled={!darfAendern}
          />
          <Regler
            beschriftung="Still nach"
            wert={werte.ruhe_nach_min}
            min={1}
            max={60}
            einheit="Min."
            hinweis="So lange ohne Knopfdruck oder Figur, dann wird das Gerät still. Es ruft nie von sich aus zum Spielen."
            beiWechsel={(w) => setze("ruhe_nach_min", w)}
            disabled={!darfAendern}
          />
        </div>
      </Abschnitt>

      <Abschnitt titel="Spiele am Gerät" regel>
        <div className={stil.formular}>
          <p className={stil.nebensache}>
            Was eingeschaltet ist, könnt ihr am Display auswählen. Spiele, die das Gerät
            noch nicht kann, stehen unter „Spiele“ als geplant.
          </p>
          {bereit.map((spiel) => (
            // Der Schalter nennt sich nur dem Screenreader - fürs Auge steht
            // der Name daneben.
            <div key={spiel.id} className={stil.schalterzeile}>
              <span aria-hidden="true">{spiel.titel}</span>
              <Schalter
                beschriftung={spiel.titel}
                an={werte.spiele_aktiv.includes(spiel.id)}
                beiWechsel={(an) => darfAendern && schalte(spiel.id, an)}
              />
            </div>
          ))}
          <Auswahl
            beschriftung="Startet mit"
            wert={werte.startspiel}
            optionen={werte.spiele_aktiv.map((id) => [id, titel.get(id) ?? id] as const)}
            beiWahl={(w) => setze("startspiel", w)}
            disabled={!darfAendern}
          />
        </div>
      </Abschnitt>

      <Abschnitt titel="Knöpfe" beiwort="für „Licht und Klang“" regel>
        <div className={stil.formular}>
          <p className={stil.nebensache}>
            Jeder Knopf hat immer dieselbe Farbe und denselben Klang. Fangt mit einem an.
          </p>
          <ul className={stil.knoepfe} aria-label="Knöpfe">
            {werte.knoepfe.map((knopf) => (
              <li key={knopf.nummer} className={stil.knopfzeile}>
                <span className={stil.knopfname}>Knopf {knopf.nummer}</span>
                <label className={stil.farbfeld}>
                  Farbe
                  <input
                    type="color"
                    value={knopf.farbe.toLowerCase()}
                    disabled={!darfAendern}
                    onChange={(e) =>
                      aendereKnopf(knopf.nummer, { farbe: e.target.value.toUpperCase() })
                    }
                  />
                </label>
                <Auswahl
                  beschriftung={`Klang für Knopf ${knopf.nummer}`}
                  wert={knopf.klang ?? OHNE}
                  optionen={klaenge}
                  beiWahl={(w) =>
                    aendereKnopf(knopf.nummer, { klang: w === OHNE ? null : w })
                  }
                  disabled={!darfAendern}
                />
                {darfAendern && werte.knoepfe.length > 1 && (
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    aria-label={`Knopf ${knopf.nummer} entfernen`}
                    onClick={() =>
                      setze(
                        "knoepfe",
                        werte.knoepfe.filter((k) => k.nummer !== knopf.nummer),
                      )
                    }
                  >
                    Entfernen
                  </Knopf>
                )}
              </li>
            ))}
          </ul>
          {darfAendern && werte.knoepfe.length < 8 && (
            <div>
              <Knopf groesse="sm" onClick={knopfDazu}>
                Knopf hinzufügen
              </Knopf>
            </div>
          )}
        </div>
      </Abschnitt>

      {darfAendern && (
        <div className={stil.formularfuss}>
          {gespeichert && (
            <span className={stil.nebensache} role="status">
              Gespeichert. Das Gerät übernimmt es, sobald gerade niemand spielt.
            </span>
          )}
          <Knopf type="submit" auspraegung="primaer" disabled={laeuft}>
            {laeuft ? "Wird gespeichert …" : "Einstellungen speichern"}
          </Knopf>
        </div>
      )}
    </form>
  );
}
