import { useId, useState } from "react";

import { Hinweis, Karte, Knopf, Feld } from "../../ui";
import type { Einstellungen, Modus, Turnier } from "./api";
import stil from "./TischtennisSeite.module.css";
import { dauer } from "./zeit";

interface Props {
  turnier: Turnier | null;
  onAnlegen: (name: string, einstellungen: Einstellungen) => Promise<boolean>;
  onAendern: (einstellungen: Einstellungen) => Promise<boolean>;
  onBeenden: () => void;
  onLoeschen: () => void;
}

const VORGABE: Einstellungen = {
  modus: "gruppen_ko",
  tische: 2,
  best_of: 3,
  minuten_pro_spiel: 12,
  anzahl_gruppen: 2,
  weiter_pro_gruppe: 2,
  runden: 4,
};

interface Moduswahl {
  wert: Modus;
  wort: string;
  erklaerung: string;
}

/** Eigene Konstante, damit der Rückfall unten keinen Indexzugriff braucht. */
const GRUPPEN_KO: Moduswahl = {
  wert: "gruppen_ko",
  wort: "Gruppen und KO-Raster",
  erklaerung:
    "Erst jeder gegen jeden in der Gruppe, dann ein Raster aus den Besten. Mit einer Gruppe und einem Weiterkommenden ist es „alle gegen alle, eine Tabelle“.",
};

const MODI: Moduswahl[] = [
  GRUPPEN_KO,
  {
    wert: "ko",
    wort: "KO-Raster",
    erklaerung:
      "Verlierer ist raus. Der kürzeste Modus – bei acht Leuten sieben Spiele, und die Hälfte hat nach einem Spiel Schluss.",
  },
  {
    wert: "schweizer",
    wort: "Schweizer System",
    erklaerung:
      "Feste Rundenzahl, jede Runde paart Punktgleiche. Zeitlich genau planbar, und niemand ist früh draußen.",
  },
];

/**
 * Die Regeln des Turniers – und der Ort, an dem es entsteht.
 *
 * Nach dem Auswürfeln sind die meisten Felder gesperrt. Das sagt die Fläche
 * selbst und nicht erst das Backend: ein Formular, das sich abschicken lässt
 * und dann abgelehnt wird, ist eine Falle.
 */
export function EinstellungenTafel({
  turnier,
  onAnlegen,
  onAendern,
  onBeenden,
  onLoeschen,
}: Props) {
  const [name, setName] = useState("");
  const [werte, setWerte] = useState<Einstellungen>(turnier ?? VORGABE);
  const [laeuft, setLaeuft] = useState(false);

  const planung = turnier === null || turnier.zustand === "planung";
  const modus = MODI.find((eintrag) => eintrag.wert === werte.modus) ?? GRUPPEN_KO;

  function setze<Feldname extends keyof Einstellungen>(
    feld: Feldname,
    wert: Einstellungen[Feldname],
  ) {
    setWerte((vorher) => ({ ...vorher, [feld]: wert }));
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (laeuft) return;
    setLaeuft(true);
    const geklappt =
      turnier === null ? await onAnlegen(name.trim(), werte) : await onAendern(werte);
    setLaeuft(false);
    if (geklappt && turnier === null) setName("");
  }

  const spieleGeschaetzt = schaetzung(werte, turnier?.anzahl_teilnehmer ?? 0);

  return (
    <>
      <Karte>
        <h2 className={stil.abschnittstitel}>
          {turnier === null ? "Turnier anlegen" : "Einstellungen"}
        </h2>

        {!planung && (
          <Hinweis>
            Der Spielplan steht. Tischzahl und geschätzte Spieldauer gehen weiter – alles,
            woran der Plan hängt, erst wieder nach dem Zurücksetzen.
          </Hinweis>
        )}

        <form onSubmit={(e) => void absenden(e)} className={stil.einstellungen}>
          {turnier === null && (
            <Feld
              beschriftung="Name des Turniers"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="off"
              required
            />
          )}

          <Auswahl
            beschriftung="Spielmodus"
            hinweis={modus.erklaerung}
            value={werte.modus}
            disabled={!planung}
            onChange={(wert) => setze("modus", wert as Modus)}
            optionen={MODI.map((eintrag) => ({ wert: eintrag.wert, wort: eintrag.wort }))}
          />

          <div className={stil.zweispaltig}>
            <Feld
              beschriftung="Tische"
              hinweis="Wie viele gleichzeitig bespielt werden"
              type="number"
              min={1}
              max={12}
              value={werte.tische}
              onChange={(e) => setze("tische", Number(e.target.value))}
            />
            <Feld
              beschriftung="Minuten je Spiel"
              hinweis="Nur die Schätzung für den Zeitplan"
              type="number"
              min={1}
              max={120}
              value={werte.minuten_pro_spiel}
              onChange={(e) => setze("minuten_pro_spiel", Number(e.target.value))}
            />
          </div>

          <Auswahl
            beschriftung="Gewinnsätze"
            hinweis="Sagt nur, wie lange gespielt wird – eingetragen wird allein der Sieger"
            value={String(werte.best_of)}
            onChange={(wert) => setze("best_of", Number(wert))}
            optionen={[
              { wert: "1", wort: "Ein Satz" },
              { wert: "3", wort: "Best of 3" },
              { wert: "5", wort: "Best of 5" },
              { wert: "7", wort: "Best of 7" },
            ]}
          />

          {werte.modus === "gruppen_ko" && (
            <div className={stil.zweispaltig}>
              <Feld
                beschriftung="Gruppen"
                hinweis={
                  (turnier?.anzahl_teilnehmer ?? 0) > 0
                    ? `Vorschlag für ${turnier?.anzahl_teilnehmer} Teilnehmer: ${vorschlag(turnier?.anzahl_teilnehmer ?? 0)}`
                    : "Vierergruppen sind das übliche Maß"
                }
                type="number"
                min={1}
                max={16}
                value={werte.anzahl_gruppen}
                disabled={!planung}
                onChange={(e) => setze("anzahl_gruppen", Number(e.target.value))}
              />
              <Feld
                beschriftung="Je Gruppe weiter"
                hinweis="1 bedeutet: der Gruppensieger ist durch"
                type="number"
                min={1}
                max={8}
                value={werte.weiter_pro_gruppe}
                disabled={!planung}
                onChange={(e) => setze("weiter_pro_gruppe", Number(e.target.value))}
              />
            </div>
          )}

          {werte.modus === "schweizer" && (
            <Feld
              beschriftung="Runden"
              hinweis="Die Zahl, mit der sich der Abend planen lässt"
              type="number"
              min={1}
              max={20}
              value={werte.runden}
              disabled={!planung}
              onChange={(e) => setze("runden", Number(e.target.value))}
            />
          )}

          {spieleGeschaetzt !== null && (
            <Hinweis>
              {/* Ein Satz, ein Textknoten: so steht er auch im Test als ein
                  Satz da und nicht als vier Bruchstuecke. */}
              {`Ergibt etwa ${spieleGeschaetzt.spiele} Spiele, geschätzt ` +
                `${dauer(spieleGeschaetzt.minuten)} auf ${werte.tische} ` +
                `${werte.tische === 1 ? "Tisch" : "Tischen"}.`}
            </Hinweis>
          )}

          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={laeuft || (turnier === null && name.trim() === "")}
          >
            {turnier === null ? "Turnier anlegen" : "Einstellungen speichern"}
          </Knopf>
        </form>
      </Karte>

      {turnier !== null && (
        <Karte>
          <h2 className={stil.abschnittstitel}>Turnier abschließen</h2>
          <p className={stil.nebensache}>
            Beenden lässt den Spielplan stehen und nimmt das Turnier aus der
            Dashboard-Ansicht. Löschen entfernt Teilnehmer, Spiele und Ergebnisse.
          </p>
          <div className={stil.aktionen}>
            <Knopf auspraegung="sekundaer" onClick={onBeenden}>
              Beenden
            </Knopf>
            <Knopf auspraegung="leise" onClick={onLoeschen}>
              Löschen
            </Knopf>
          </div>
        </Karte>
      )}
    </>
  );
}

function vorschlag(anzahl: number): number {
  return Math.max(1, Math.min(Math.floor(anzahl / 2), Math.round(anzahl / 4)));
}

/**
 * Wie viele Spiele dabei herauskommen - dieselbe Rechnung wie im Backend.
 *
 * Hier ist sie eine Schätzung im Formular und nicht die Wahrheit: die steht
 * in der Vorschau des Loses, die das Backend rechnet. Deshalb ist diese
 * Dopplung in Ordnung - sie entscheidet nichts.
 */
function schaetzung(
  werte: Einstellungen,
  teilnehmer: number,
): { spiele: number; minuten: number } | null {
  if (teilnehmer < 2) return null;

  let spiele = 0;
  if (werte.modus === "gruppen_ko") {
    const je = Math.floor(teilnehmer / werte.anzahl_gruppen);
    spiele = werte.anzahl_gruppen * ((je * (je - 1)) / 2);
    const weiter = Math.min(teilnehmer, werte.anzahl_gruppen * werte.weiter_pro_gruppe);
    spiele += Math.max(0, weiter - 1);
  } else if (werte.modus === "ko") {
    spiele = teilnehmer - 1;
  } else {
    spiele = Math.floor(teilnehmer / 2) * werte.runden;
  }

  const durchgaenge = Math.ceil(spiele / Math.max(1, werte.tische));
  return { spiele, minuten: durchgaenge * werte.minuten_pro_spiel };
}

/**
 * Ein Auswahlfeld im Stil von `Feld`.
 *
 * Die Bausteine in src/ui haben keines - und eines dort zu ergänzen, wäre
 * eine Änderung am Designsystem für ein einzelnes Artefakt. Bleibt es hier,
 * bis ein zweites Artefakt es braucht.
 */
function Auswahl({
  beschriftung,
  hinweis,
  value,
  optionen,
  disabled,
  onChange,
}: {
  beschriftung: string;
  hinweis?: string;
  value: string;
  optionen: { wert: string; wort: string }[];
  disabled?: boolean;
  onChange: (wert: string) => void;
}) {
  const kennung = useId();

  return (
    <div className={stil.auswahl}>
      <label htmlFor={kennung}>{beschriftung}</label>
      <select
        id={kennung}
        value={value}
        disabled={disabled}
        onChange={(ereignis) => onChange(ereignis.target.value)}
      >
        {optionen.map((eintrag) => (
          <option key={eintrag.wert} value={eintrag.wert}>
            {eintrag.wort}
          </option>
        ))}
      </select>
      {hinweis && <p className={stil.nebensache}>{hinweis}</p>}
    </div>
  );
}
