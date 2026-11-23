import { useState } from "react";

import {
  Abschnitt,
  Feld,
  Karte,
  Knopf,
  Leerzustand,
  Reihe,
  Tabelle,
  Zelle,
} from "../../ui";
import type { Art, Aufnahme, Figur, FigurEingabe, UnbekannteFigur } from "./api";
import { Auswahl } from "./bausteine";
import stil from "./KinderzimmerSeite.module.css";
import { ARTEN, FARBEN, FORMEN, LEERE_FIGUR, uidLesbar, wortFuer, zeit } from "./texte";

interface Props {
  figuren: readonly Figur[];
  unbekannte: readonly UnbekannteFigur[];
  aufnahmen: readonly Aufnahme[];
  darfAendern: boolean;
  /** Von außen gesteuert, damit der Knopf im Tafelkopf das Formular öffnet. */
  formular: FigurEingabe | null;
  bearbeitet: Figur | null;
  onFormular: (werte: FigurEingabe | null, figur?: Figur | null) => void;
  onSpeichern: (werte: FigurEingabe, id: string | null) => Promise<boolean>;
  onEntfernen: (figur: Figur) => void;
}

const OHNE = "";

/**
 * Die Figuren mit ihrem NFC-Tag.
 *
 * Anlernen geht ohne Abtippen: Ein Tag, der aufs Gerät gelegt wird und noch
 * keine Figur ist, steht oben in der Liste „Aufgelegt, aber unbekannt“. Ein
 * Klick, und das Formular hat die UID schon.
 */
export function FigurenTafel({
  figuren,
  unbekannte,
  aufnahmen,
  darfAendern,
  formular,
  bearbeitet,
  onFormular,
  onSpeichern,
  onEntfernen,
}: Props) {
  const [offen, setOffen] = useState<string | null>(null);
  const titel = new Map(aufnahmen.map((a) => [a.id, a.titel]));

  return (
    <>
      {darfAendern && unbekannte.length > 0 && (
        <Abschnitt titel="Aufgelegt, aber unbekannt" beiwort="letzte sieben Tage" regel>
          <ul className={stil.unbekannt} aria-label="Unbekannte Tags">
            {unbekannte.map((u) => (
              <li key={u.uid} className={stil.unbekanntzeile}>
                <span>
                  <span className={stil.mono}>{uidLesbar(u.uid)}</span>
                  <span className={stil.beiwortTrenner} aria-hidden="true">
                    ·
                  </span>
                  <span className={stil.nebensache}>{zeit(u.zuletzt)}</span>
                </span>
                <Knopf
                  groesse="sm"
                  aria-label={`Tag ${uidLesbar(u.uid)} als Figur anlegen`}
                  onClick={() => onFormular({ ...LEERE_FIGUR, uid: u.uid })}
                >
                  Als Figur anlegen
                </Knopf>
              </li>
            ))}
          </ul>
        </Abschnitt>
      )}

      {formular && (
        <Figurformular
          key={bearbeitet?.id ?? formular.uid}
          anfang={formular}
          bearbeitet={bearbeitet}
          aufnahmen={aufnahmen}
          onAbbrechen={() => onFormular(null)}
          onSpeichern={onSpeichern}
        />
      )}

      {figuren.length === 0 ? (
        <Leerzustand titel="Noch keine Figur">
          Legt eine Figur mit Tag aufs Gerät, dann erscheint sie hier oben zum Anlegen.
          Ohne Gerät geht es auch: „Figur anlegen“ und die UID abtippen, die eine NFC-App
          am Handy anzeigt.
        </Leerzustand>
      ) : (
        <Tabelle
          beschriftung="Figuren"
          raster="1.4fr 1fr 1.6fr 1.2fr"
          spalten={["Figur", "Art", "Spielt ab", "UID"]}
        >
          {figuren.map((figur) => {
            const spielt = [figur.stimme, figur.klang]
              .filter((a): a is string => a !== null)
              .map((a) => titel.get(a) ?? "?");
            return (
              <Reihe
                key={figur.id}
                onKlick={() => setOffen(offen === figur.id ? null : figur.id)}
                offen={offen === figur.id}
                ausklappung={
                  darfAendern && (
                    <div className={stil.handlungen}>
                      <Knopf groesse="sm" onClick={() => onFormular(figur, figur)}>
                        „{figur.name}“ ändern
                      </Knopf>
                      <Knopf
                        groesse="sm"
                        auspraegung="leise"
                        onClick={() => onEntfernen(figur)}
                      >
                        „{figur.name}“ entfernen
                      </Knopf>
                    </div>
                  )
                }
              >
                <Zelle>{figur.name}</Zelle>
                <Zelle leise>{wortFuer(ARTEN, figur.art)}</Zelle>
                <Zelle leise>{spielt.length > 0 ? spielt.join(", ") : "nichts"}</Zelle>
                <Zelle leise>
                  <span className={stil.mono}>{uidLesbar(figur.uid)}</span>
                </Zelle>
              </Reihe>
            );
          })}
        </Tabelle>
      )}
    </>
  );
}

function Figurformular({
  anfang,
  bearbeitet,
  aufnahmen,
  onAbbrechen,
  onSpeichern,
}: {
  anfang: FigurEingabe;
  bearbeitet: Figur | null;
  aufnahmen: readonly Aufnahme[];
  onAbbrechen: () => void;
  onSpeichern: (werte: FigurEingabe, id: string | null) => Promise<boolean>;
}) {
  const [werte, setWerte] = useState<FigurEingabe>(anfang);
  const [laeuft, setLaeuft] = useState(false);

  function setze<F extends keyof FigurEingabe>(feld: F, wert: FigurEingabe[F]) {
    setWerte((vorher) => ({ ...vorher, [feld]: wert }));
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (laeuft) return;
    setLaeuft(true);
    // Schlägt es fehl, bleibt das Formular mit allen Eingaben stehen.
    const { uid, name, art, farbe, form, menge, stimme, klang } = werte;
    await onSpeichern(
      { uid, name, art, farbe, form, menge, stimme, klang },
      bearbeitet?.id ?? null,
    );
    setLaeuft(false);
  }

  const auswahl = (art: "stimme" | "klang"): (readonly [string, string])[] => [
    [OHNE, "nichts"],
    ...aufnahmen
      .filter((a) => a.art === art || a.id === werte[art])
      .map((a) => [a.id, a.titel] as const),
  ];
  const leer = werte.name.trim() === "" || werte.uid.trim() === "";

  return (
    <Karte>
      <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
        <div className={stil.zweispaltig}>
          <Feld
            beschriftung="Name"
            value={werte.name}
            onChange={(e) => setze("name", e.target.value)}
            placeholder="Oma"
            autoComplete="off"
          />
          <Feld
            beschriftung="UID des Tags"
            hinweis="Steht nach dem Auflegen oben in der Liste, oder in einer NFC-App am Handy"
            value={werte.uid}
            onChange={(e) => setze("uid", e.target.value)}
            placeholder="04:A1:B2:C3:D4:E5:F6"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className={stil.zweispaltig}>
          <Auswahl
            beschriftung="Art"
            wert={werte.art}
            optionen={ARTEN}
            beiWahl={(w: Art) => setze("art", w)}
          />
          <Auswahl
            beschriftung="Stimme beim Auflegen"
            wert={werte.stimme ?? OHNE}
            optionen={auswahl("stimme")}
            beiWahl={(w) => setze("stimme", w === OHNE ? null : w)}
          />
          <Auswahl
            beschriftung="Klang beim Auflegen"
            wert={werte.klang ?? OHNE}
            optionen={auswahl("klang")}
            beiWahl={(w) => setze("klang", w === OHNE ? null : w)}
          />
        </div>
        <p className={stil.nebensache}>
          Für spätere Spiele: Farbe, Form und Menge der Figur. Für Phase 1 braucht es sie
          noch nicht.
        </p>
        <div className={stil.zweispaltig}>
          <Auswahl
            beschriftung="Farbe"
            wert={werte.farbe ?? OHNE}
            optionen={[[OHNE, "keine"], ...FARBEN]}
            beiWahl={(w) => setze("farbe", w === OHNE ? null : w)}
          />
          <Auswahl
            beschriftung="Form"
            wert={werte.form ?? OHNE}
            optionen={[[OHNE, "keine"], ...FORMEN]}
            beiWahl={(w) => setze("form", w === OHNE ? null : w)}
          />
          <Feld
            beschriftung="Menge (Punkte)"
            type="number"
            min={1}
            max={10}
            value={werte.menge ?? ""}
            onChange={(e) =>
              setze("menge", e.target.value === "" ? null : Number(e.target.value))
            }
          />
        </div>
        <div className={stil.formularfuss}>
          <Knopf auspraegung="leise" onClick={onAbbrechen}>
            Abbrechen
          </Knopf>
          <Knopf type="submit" auspraegung="primaer" disabled={leer || laeuft}>
            {laeuft
              ? "Wird gespeichert …"
              : bearbeitet
                ? "Änderung speichern"
                : "Figur anlegen"}
          </Knopf>
        </div>
      </form>
    </Karte>
  );
}
