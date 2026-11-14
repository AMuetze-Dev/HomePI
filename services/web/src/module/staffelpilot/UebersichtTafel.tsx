import { useCallback, useEffect, useState } from "react";

import {
  Abschnitt,
  Etikett,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Reihe,
  Statuspunkt,
  Tabelle,
  Tafel,
  Zelle,
} from "../../ui";
import {
  type Auftrag,
  type SpielZeile,
  type UebertragungStand,
  type Zusammenfassung,
  ladeOffenenAuftrag,
  ladeUebertragung,
  ladeWarteschlange,
  ladeZusammenfassung,
} from "./api";
import { alsDatum } from "./datum";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/** So viele Spiele stehen auf der Startfläche. Wer mehr will, geht in die
 *  Spielprüfung — das hier ist der Blick, nicht die Arbeit. */
const NAECHSTE = 5;

/**
 * Was jetzt ansteht — die Fläche, die man morgens aufmacht.
 *
 * Sie arbeitet nicht, sie sagt nur: wie viel liegt an, läuft gerade etwas,
 * hängt etwas fest. Jede Zahl ist ein Weg in die Fläche, auf der man damit
 * etwas tut.
 */
export function UebersichtTafel({ onWechsel }: { onWechsel: (reiter: string) => void }) {
  const [werte, setWerte] = useState<Zusammenfassung | null>(null);
  const [naechste, setNaechste] = useState<SpielZeile[]>([]);
  const [auftrag, setAuftrag] = useState<Auftrag | null>(null);
  const [uebertragung, setUebertragung] = useState<UebertragungStand | null>(null);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      const [zahlen, spiele, offen, stand] = await Promise.all([
        ladeZusammenfassung(signal),
        ladeWarteschlange(undefined, signal, true),
        ladeOffenenAuftrag(signal),
        ladeUebertragung(signal),
      ]);
      setWerte(zahlen);
      setNaechste(spiele.filter((s) => !s.abgehakt).slice(0, NAECHSTE));
      setAuftrag(offen);
      setUebertragung(stand);
    } catch (f) {
      if (signal?.aborted) return;
      setFehler(meldung(f));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(controller.signal);
    return () => controller.abort();
  }, [laden]);

  if (fehler && werte === null) {
    return (
      <Tafel titel="Übersicht">
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      </Tafel>
    );
  }

  if (werte === null || uebertragung === null) {
    return (
      <Tafel titel="Übersicht">
        <div role="status" aria-label="Übersicht wird geladen">
          <Platzhalter breite="100%" hoehe="6rem" />
          <Platzhalter breite="100%" hoehe="12rem" />
        </div>
      </Tafel>
    );
  }

  return (
    <Tafel
      titel="Übersicht"
      beiwort={
        werte.offen === 0
          ? "nichts zu prüfen"
          : `${werte.offen} von ${werte.spiele} ${werte.spiele === 1 ? "Bericht" : "Berichten"} offen`
      }
    >
      <ul className={stil.kennzahlen} aria-label="Überblick">
        <Zahl wert={werte.offen} name="zu prüfen" onKlick={() => onWechsel("spiele")} />
        {/* "befunde" gibt es als Bereich nicht - das Register kennt ihn
            nicht, und die Modulseite leitete beide Zahlen deshalb stumm auf
            die Uebersicht zurueck, also auf die Flaeche, von der man kam.
            Die Befundliste steht unter "Ergebnisse". */}
        <Zahl
          wert={werte.befunde_kritisch}
          name="kritische Befunde"
          warnend
          onKlick={() => onWechsel("ergebnisse")}
        />
        <Zahl
          wert={werte.befunde_offen}
          name="offene Befunde"
          onKlick={() => onWechsel("ergebnisse")}
        />
        <Zahl
          wert={werte.vorgaenge_entwurf}
          name="Entwürfe"
          onKlick={() => onWechsel("vorgaenge")}
        />
      </ul>

      {auftrag !== null && (
        <Karte className={stil.stapel}>
          <div className={stil.zeile}>
            <span className={stil.paarung}>
              {auftrag.art === "pruflauf" ? "Prüflauf" : "Initialisierung"}
            </span>
            <Etikett ton={auftrag.zustand === "laeuft" ? "neutral" : "warnung"}>
              {auftrag.zustand === "laeuft" ? "Läuft" : "Wartet"}
            </Etikett>
          </div>
          <p className={stil.vorgangHinweis}>
            {auftrag.fortschritt} % · {auftrag.schritt || "Wartet auf den Prüfdienst"}
          </p>
          <div className={stil.knoepfe}>
            <Knopf
              groesse="sm"
              auspraegung="sekundaer"
              onClick={() => onWechsel("prueflauf")}
            >
              Zum Prüflauf
            </Knopf>
          </div>
        </Karte>
      )}

      {uebertragung.fehler > 0 && (
        <Hinweis ton="fehler" dringend>
          {uebertragung.fehler}{" "}
          {uebertragung.fehler === 1 ? "Übertragung ist" : "Übertragungen sind"}{" "}
          gescheitert. Sie stehen unter Prüflauf.
        </Hinweis>
      )}

      {werte.staffeln_aktiv === 0 && (
        <Leerzustand
          titel="Keine aktive Staffel"
          aktion={<Knopf onClick={() => onWechsel("staffeln")}>Staffeln verwalten</Knopf>}
        >
          Ohne Staffel kommen keine Spielberichte herein. Leg die erste an — Name und
          Spielklasse genau so, wie sie in DFBnet heißen.
        </Leerzustand>
      )}

      <Abschnitt titel="Als Nächstes">
        {naechste.length === 0 ? (
          <Leerzustand titel="Nichts fällig">
            Kein Spielbericht im Prüfzeitraum wartet auf eine Entscheidung.
          </Leerzustand>
        ) : (
          <Tabelle
            beschriftung="Als Nächstes"
            raster="1.8fr 1fr 0.8fr"
            spalten={["Paarung", "Befunde", "Angesetzt"]}
          >
            {naechste.map((z) => (
              <Reihe key={z.id} onKlick={() => onWechsel("spiele")}>
                <Zelle>
                  {z.heim} – {z.gast}
                </Zelle>
                <Zelle>
                  {z.kritische_befunde > 0 ? (
                    <Etikett ton="fehler">{z.kritische_befunde} kritisch</Etikett>
                  ) : z.offene_befunde > 0 ? (
                    <>
                      <Statuspunkt ton="akzent" />
                      {`${z.offene_befunde} offen`}
                    </>
                  ) : (
                    <span className={stil.ohneBefund}>ohne Befund</span>
                  )}
                </Zelle>
                <Zelle leise>{alsDatum(z.datum)}</Zelle>
              </Reihe>
            ))}
          </Tabelle>
        )}
      </Abschnitt>
    </Tafel>
  );
}

/**
 * Wie laut eine Zahl auftritt.
 *
 * Leer, wenn es nichts zu tun gibt; warnend nur, wenn wirklich etwas offen
 * ist. Eine Null in Rot wäre eine Warnung ohne Anlass, eine Null in voller
 * Schriftstärke ein Blickfang ohne Inhalt.
 */
// Der Rueckgabetyp ist `string | undefined` und nicht `string`: die
// Stilklassen sind so getypt, und `className` nimmt beides. Ein `!` hier
// waere eine Behauptung ueber eine Datei, die der Uebersetzer erzeugt.
function zahlStil(wert: number, warnend?: boolean): string | undefined {
  if (wert === 0) return stil.zahlLeer;
  return warnend ? stil.zahlWarnend : stil.zahl;
}

function Zahl({
  wert,
  name,
  warnend,
  onKlick,
}: {
  wert: number;
  name: string;
  warnend?: boolean;
  onKlick: () => void;
}) {
  return (
    <li className={stil.kennzahl}>
      {/* Jede Zahl ist ein Weg dorthin, wo man etwas damit tut. Eine Zahl,
          die nur dasteht, lässt den Leser die Navigation suchen. */}
      <button type="button" className={stil.kennzahlKnopf} onClick={onKlick}>
        {/* Drei Stufen, nicht zwei. Eine Null ist eine gute Nachricht und
            braucht keine Aufmerksamkeit -- sie stand hier aber genauso laut da
            wie "8 kritische Befunde" daneben. Was nichts zu tun gibt, tritt
            zurueck. */}
        <span className={zahlStil(wert, warnend)}>{wert}</span>
        <span className={stil.zahlName}>{name}</span>
      </button>
    </li>
  );
}
