import { useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand } from "../../ui";
import type { Satz, Spiel, Turnier } from "./api";
import stil from "./TischtennisSeite.module.css";
import { uhrzeit } from "./zeit";

interface Props {
  turnier: Turnier;
  spiele: Spiel[];
  onBeginnen: (id: string) => void;
  onErgebnis: (id: string, saetze: Satz[]) => Promise<boolean>;
  onZuruecknehmen: (id: string) => void;
  onNaechsteRunde: () => void;
}

const ZUSTANDSWORT: Record<Spiel["zustand"], string> = {
  geplant: "geplant",
  laeuft: "läuft",
  beendet: "gewertet",
};

const ZUSTANDSTON: Record<Spiel["zustand"], "neutral" | "warnung" | "gut"> = {
  geplant: "neutral",
  laeuft: "warnung",
  beendet: "gut",
};

/**
 * Der Spielplan, wie ihn der Turnierleiter braucht.
 *
 * Eine Zeile je Spiel, aufgeklappt wird nur das, an dem gerade gearbeitet
 * wird. Die Zeile bleibt dabei an ihrem Platz: eine Liste, die beim Öffnen
 * eines Formulars umspringt, kostet an einem Turnierabend mehr Zeit als jeder
 * Mausweg.
 */
export function SpielplanTafel({
  turnier,
  spiele,
  onBeginnen,
  onErgebnis,
  onZuruecknehmen,
  onNaechsteRunde,
}: Props) {
  const [offen, setOffen] = useState<string | null>(null);

  if (spiele.length === 0) {
    return (
      <Leerzustand titel="Noch kein Spielplan">
        Unter „Auswürfeln“ entsteht er – aus den eingetragenen Teilnehmern.
      </Leerzustand>
    );
  }

  const naechsteRundeFaellig =
    turnier.offene_spiele === 0 && turnier.zustand !== "beendet";

  return (
    <>
      {naechsteRundeFaellig && (
        <Hinweis ton="warnung">
          Alle Spiele sind gewertet.{" "}
          {turnier.modus === "gruppen_ko" && !turnier.ko_steht
            ? "Jetzt kann das KO-Raster aus den Gruppentabellen gesetzt werden."
            : "Die nächste Runde kann angesetzt werden."}{" "}
          <Knopf groesse="sm" auspraegung="primaer" onClick={onNaechsteRunde}>
            Ansetzen
          </Knopf>
        </Hinweis>
      )}

      {turnier.zustand === "beendet" && (
        <Hinweis>Das Turnier ist durch – alle Spiele sind gewertet.</Hinweis>
      )}

      <Karte blank>
        <ul className={stil.liste}>
          {spiele.map((spiel) => (
            <li key={spiel.id} className={stil.spielzeile}>
              <div className={stil.spielkopf}>
                <span className={stil.spielnummer}>#{spiel.nummer}</span>
                <span className={stil.name}>
                  {spiel.heim ?? spiel.heim_herkunft} gegen{" "}
                  {spiel.gast ?? spiel.gast_herkunft}
                </span>
                <span className={stil.nebensache}>
                  {spiel.bezeichnung}
                  {spiel.tisch !== null && ` · Tisch ${spiel.tisch}`}
                  {spiel.zustand === "geplant" &&
                    spiel.erwartet_ab !== null &&
                    ` · ab ${uhrzeit(spiel.erwartet_ab)}`}
                </span>
                <span className={stil.zeilenaktionen}>
                  {spiel.saetze.length > 0 && (
                    <span className={stil.satzstandKlein}>
                      {spiel.saetze_heim}:{spiel.saetze_gast}
                    </span>
                  )}
                  {spiel.freilos ? (
                    <Etikett ton="neutral">Freilos</Etikett>
                  ) : (
                    <Etikett ton={ZUSTANDSTON[spiel.zustand]}>
                      {ZUSTANDSWORT[spiel.zustand]}
                    </Etikett>
                  )}
                </span>
              </div>

              {!spiel.freilos && spiel.heim_id !== null && spiel.gast_id !== null && (
                <div className={stil.zeilenaktionen}>
                  {spiel.zustand === "geplant" && (
                    <Knopf
                      groesse="sm"
                      auspraegung="sekundaer"
                      onClick={() => onBeginnen(spiel.id)}
                      aria-label={`Spiel ${spiel.nummer} beginnen`}
                    >
                      Beginnen
                    </Knopf>
                  )}
                  <Knopf
                    groesse="sm"
                    auspraegung={spiel.zustand === "laeuft" ? "primaer" : "leise"}
                    onClick={() => setOffen(offen === spiel.id ? null : spiel.id)}
                    aria-expanded={offen === spiel.id}
                    aria-label={`Ergebnis für Spiel ${spiel.nummer} eintragen`}
                  >
                    {spiel.saetze.length > 0 ? "Ergebnis ändern" : "Ergebnis eintragen"}
                  </Knopf>
                  {spiel.zustand !== "geplant" && (
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => onZuruecknehmen(spiel.id)}
                      aria-label={`Ergebnis von Spiel ${spiel.nummer} zurücknehmen`}
                    >
                      Zurücknehmen
                    </Knopf>
                  )}
                </div>
              )}

              {offen === spiel.id && (
                <ErgebnisFormular
                  spiel={spiel}
                  bestOf={turnier.best_of}
                  onSpeichern={async (saetze) => {
                    const geklappt = await onErgebnis(spiel.id, saetze);
                    if (geklappt) setOffen(null);
                    return geklappt;
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      </Karte>
    </>
  );
}

/**
 * Satz für Satz, alle Felder auf einmal.
 *
 * Leere Zeilen am Ende werden weggelassen: wer nach drei Sätzen fertig ist,
 * soll nicht zwei Nullen eintragen müssen. Satz drei auszufüllen und Satz
 * zwei leer zu lassen lehnt das Backend ab – und sagt auch, warum.
 */
function ErgebnisFormular({
  spiel,
  bestOf,
  onSpeichern,
}: {
  spiel: Spiel;
  bestOf: number;
  onSpeichern: (saetze: Satz[]) => Promise<boolean>;
}) {
  const [felder, setFelder] = useState<string[][]>(() =>
    Array.from({ length: bestOf }, (_, stelle) => [
      spiel.saetze[stelle] ? String(spiel.saetze[stelle].heim) : "",
      spiel.saetze[stelle] ? String(spiel.saetze[stelle].gast) : "",
    ]),
  );
  const [laeuft, setLaeuft] = useState(false);

  function setzen(satz: number, seite: number, wert: string) {
    setFelder((vorher) =>
      vorher.map((zeile, stelle) =>
        stelle === satz
          ? zeile.map((alt, index) => (index === seite ? wert : alt))
          : zeile,
      ),
    );
  }

  const gefuellt = felder
    .map(([heim, gast]) => ({
      heim: Number(heim),
      gast: Number(gast),
      leer: heim === "" || gast === "",
    }))
    .filter((satz) => !satz.leer)
    .map(({ heim, gast }) => ({ heim, gast }));

  return (
    <form
      className={stil.ergebnis}
      onSubmit={(ereignis) => {
        ereignis.preventDefault();
        setLaeuft(true);
        void onSpeichern(gefuellt).finally(() => setLaeuft(false));
      }}
    >
      <fieldset className={stil.saetze}>
        <legend className={stil.nebensache}>
          Sätze – {spiel.heim} zuerst. Best of {bestOf}.
        </legend>
        {felder.map(([heim, gast], satz) => (
          <div key={satz} className={stil.satzzeile}>
            <Feld
              beschriftung={`Satz ${satz + 1}, ${spiel.heim ?? "Heim"}`}
              type="number"
              min={0}
              max={99}
              inputMode="numeric"
              value={heim}
              onChange={(e) => setzen(satz, 0, e.target.value)}
            />
            <Feld
              beschriftung={`Satz ${satz + 1}, ${spiel.gast ?? "Gast"}`}
              type="number"
              min={0}
              max={99}
              inputMode="numeric"
              value={gast}
              onChange={(e) => setzen(satz, 1, e.target.value)}
            />
          </div>
        ))}
      </fieldset>
      <Knopf
        type="submit"
        auspraegung="primaer"
        disabled={laeuft || gefuellt.length === 0}
      >
        {laeuft ? "Wird gespeichert …" : "Speichern"}
      </Knopf>
    </form>
  );
}
