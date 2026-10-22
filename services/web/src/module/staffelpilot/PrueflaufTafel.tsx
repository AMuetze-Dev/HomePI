import { useCallback, useEffect, useRef, useState } from "react";

import { Etikett, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  type Auftrag,
  type AuftragZeile,
  type AuftragZustand,
  type Staffel,
  type UebertragungStand,
  brichAuftragAb,
  fordereAuftragAn,
  ladeAuftraege,
  ansichtAdresse,
  ladeAnsichten,
  ladeOffenenAuftrag,
  ladeUebertragung,
  setzeUebertragungPause,
  wiederholeUebertragung,
} from "./api";
import { ergebnisSatz } from "./ergebnis";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

const ZUSTAND_WORT: Record<AuftragZustand, string> = {
  angefordert: "Wartet",
  laeuft: "Läuft",
  fertig: "Fertig",
  abgebrochen: "Abgebrochen",
  gescheitert: "Gescheitert",
};

const ZUSTAND_TON: Record<AuftragZustand, "gut" | "warnung" | "fehler" | "neutral"> = {
  angefordert: "warnung",
  laeuft: "neutral",
  fertig: "gut",
  abgebrochen: "neutral",
  gescheitert: "fehler",
};

const ART_WORT = {
  pruflauf: "Prüflauf",
  initialisierung: "Initialisierung",
  staffeln: "Staffeln holen",
} as const;

/** Wie oft nachgesehen wird, solange etwas unterwegs ist. */
const TAKT_MS = 3000;

function alsZeit(wert: string): string {
  return new Date(wert).toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Prüfläufe anfordern und zusehen — und der Streifen für das, was nach
 * DFBnet hinaus soll.
 *
 * **Hier läuft nichts.** Ein Auftrag ist ein Datensatz; gearbeitet wird im
 * DFBnet-Dienst. Solange der nicht läuft, bleibt ein Auftrag auf „Wartet“
 * stehen — und das steht auch so da, statt einen Fortschritt vorzutäuschen.
 */
export function PrueflaufTafel({
  staffeln,
  onFertig,
}: {
  staffeln: Staffel[];
  /** Ein Lauf ist zu Ende — was er eingespielt hat, steht woanders. */
  onFertig?: (() => void) | undefined;
}) {
  const [offen, setOffen] = useState<Auftrag | null>(null);
  const [verlauf, setVerlauf] = useState<AuftragZeile[] | null>(null);
  const [uebertragung, setUebertragung] = useState<UebertragungStand | null>(null);
  const [staffelId, setStaffelId] = useState("");
  const [fehler, setFehler] = useState("");

  // In einer Referenz, damit `laden` nicht bei jedem Rendern neu entsteht -
  // sonst startet der Takt unten immer wieder von vorn.
  const onFertigRef = useRef(onFertig);
  onFertigRef.current = onFertig;

  const laden = useCallback(async (signal?: AbortSignal) => {
    try {
      const [aktuell, alle, stand] = await Promise.all([
        ladeOffenenAuftrag(signal),
        ladeAuftraege(signal),
        ladeUebertragung(signal),
      ]);
      // Von "da" auf "weg": der Lauf ist zu Ende. Ohne diesen Ruf steht die
      // Spielprüfung noch auf dem Stand von vorhin, und der Staffelleiter
      // sieht seine frisch eingespielten Berichte erst nach einem Neuladen.
      setOffen((vorher) => {
        if (vorher !== null && aktuell === null) onFertigRef.current?.();
        return aktuell;
      });
      setVerlauf(alle);
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

  // Nur nachsehen, solange etwas unterwegs ist. Ein Takt, der auch auf einer
  // leeren Seite weiterläuft, hält den Pi wach und die Datenbank beschäftigt.
  useEffect(() => {
    if (offen === null) return;
    const uhr = setInterval(() => void laden(), TAKT_MS);
    return () => clearInterval(uhr);
  }, [offen, laden]);

  async function handeln(aktion: () => Promise<unknown>) {
    setFehler("");
    try {
      await aktion();
      await laden();
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  if (verlauf === null || uebertragung === null) {
    return (
      <div role="status" aria-label="Prüfläufe werden geladen">
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  return (
    <>
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      <Karte>
        <h2 className={stil.formularTitel}>Prüflauf</h2>
        {offen === null ? (
          <>
            <p className={stil.vorgangHinweis}>
              Ein Prüflauf liest die Spielberichte in DFBnet und spielt seine Befunde hier
              ein. Gearbeitet wird im Prüfdienst — solange der nicht läuft, bleibt der
              Auftrag auf „Wartet“ stehen.
            </p>
            {staffeln.length > 1 && (
              <label className={stil.wahl}>
                <span className={stil.wahlName}>Staffel</span>
                <select
                  className={stil.auswahl}
                  value={staffelId}
                  onChange={(e) => setStaffelId(e.target.value)}
                >
                  <option value="">Alle aktiven Staffeln</option>
                  {staffeln.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {/* Eine Rangfolge. Vorher sahen alle drei gleich aus, obwohl
                der erste die taegliche Handlung ist und die beiden anderen
                zweimal im Jahr gebraucht werden. */}
            <div className={stil.knoepfe}>
              <Knopf
                auspraegung="primaer"
                onClick={() =>
                  void handeln(() => fordereAuftragAn("pruflauf", staffelId || undefined))
                }
              >
                Prüflauf anfordern
              </Knopf>
              <Knopf
                auspraegung="leise"
                onClick={() =>
                  void handeln(() =>
                    fordereAuftragAn("initialisierung", staffelId || undefined),
                  )
                }
              >
                Saisondaten holen
              </Knopf>
              {/* Ohne Staffelauswahl: die Liste gilt fuer das ganze Konto.
                  Sie ersetzt das Abschreiben von Hand -- und genau daran war
                  die Pruefung gescheitert, an einer Spielklasse, die DFBnet
                  nicht kennt. */}
              <Knopf
                auspraegung="leise"
                onClick={() => void handeln(() => fordereAuftragAn("staffeln"))}
              >
                Meine Staffeln aus DFBnet holen
              </Knopf>
            </div>
          </>
        ) : (
          <Laufend
            auftrag={offen}
            onAbbrechen={() => void handeln(() => brichAuftragAb(offen.id))}
          />
        )}
      </Karte>

      <Uebertragungsstreifen
        stand={uebertragung}
        onPause={(p) => void handeln(() => setzeUebertragungPause(p))}
        onWiederholen={() => void handeln(() => wiederholeUebertragung())}
      />

      <h2 className={stil.formularTitel}>Bisherige Läufe</h2>
      {verlauf.length === 0 ? (
        <Leerzustand titel="Noch kein Lauf">
          Was hier steht, sind die vergangenen Prüfläufe mit ihrem Ergebnis.
        </Leerzustand>
      ) : (
        <ul className={stil.liste} aria-label="Bisherige Läufe">
          {verlauf.map((z) => (
            <li key={z.id}>
              <Karte>
                <div className={stil.zeile}>
                  <span className={stil.paarung}>{ART_WORT[z.art]}</span>
                  <Etikett ton={ZUSTAND_TON[z.zustand]}>
                    {ZUSTAND_WORT[z.zustand]}
                  </Etikett>
                  <span className={stil.datum}>{alsZeit(z.angelegt)}</span>
                </div>
                <p className={stil.vorgangHinweis}>{ergebnisSatz(z)}</p>
              </Karte>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Laufend({
  auftrag,
  onAbbrechen,
}: {
  auftrag: Auftrag;
  onAbbrechen: () => void;
}) {
  return (
    <>
      <div className={stil.zeile}>
        <span className={stil.paarung}>{ART_WORT[auftrag.art]}</span>
        <Etikett ton={ZUSTAND_TON[auftrag.zustand]}>
          {ZUSTAND_WORT[auftrag.zustand]}
        </Etikett>
      </div>

      {/* Zahl und Balken: ein Balken allein ist auf einem Telefon bei
          schlechtem Licht nicht abzulesen. */}
      <div
        className={stil.balken}
        role="progressbar"
        aria-valuenow={auftrag.fortschritt}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Fortschritt"
      >
        <div
          className={stil.balkenFuellung}
          style={{ width: `${auftrag.fortschritt}%` }}
        />
      </div>
      <p className={stil.vorgangHinweis}>
        {auftrag.fortschritt} % ·{" "}
        {auftrag.schritt ||
          (auftrag.zustand === "angefordert" ? "Wartet auf den Prüfdienst" : "Arbeitet")}
      </p>

      {auftrag.protokoll.length > 0 && (
        <ul className={stil.protokoll} aria-label="Protokoll">
          {auftrag.protokoll.slice(-12).map((zeile, i) => (
            <li key={`${zeile.zeit}-${i}`}>
              <span className={stil.datum}>{zeile.zeit.slice(11, 19)}</span> {zeile.text}
            </li>
          ))}
        </ul>
      )}

      <Vorschau auftrag={auftrag} />

      <div className={stil.knoepfe}>
        <Knopf auspraegung="leise" onClick={onAbbrechen}>
          Abbrechen
        </Knopf>
      </div>
    </>
  );
}

/** Wie oft ein neues Abbild geholt wird, solange ein Lauf arbeitet. */
const VORSCHAU_TAKT_MS = 2000;

/**
 * Was der Prüfdienst gerade vor sich hat.
 *
 * Er fährt einen Browser in einem Container **ohne Bildschirm**: ein
 * sichtbares Chromium kann es dort nie geben (`Missing X server`), und auf
 * Windows soll der Dienst nicht laufen müssen, damit jemand zusehen kann.
 * Also fotografiert er die Seite.
 *
 * Kein gespiegeltes HTML: DFBnets CSS und Bilder liegen hinter derselben
 * Sitzung, relative Verweise zeigen ins Leere, und fremdes HTML in die eigene
 * Seite zu hängen ist ein XSS-Loch. Vor allem sind die Comboboxen
 * JS-getrieben — genau das, was man sehen will, stünde im DOM nicht drin. Im
 * Abbild schon, samt aufgeklappter Liste.
 *
 * Es erscheint **nur, wenn es etwas zu zeigen gibt**: der Schalter dafür
 * steht in den Einstellungen unter „Beim Prüfen zusehen".
 */
function Vorschau({ auftrag }: { auftrag: Auftrag }) {
  const [arten, setArten] = useState<string[]>([]);
  const [stand, setStand] = useState(() => Date.now());
  const [gross, setGross] = useState(false);

  const laeuft = auftrag.zustand === "laeuft" || auftrag.zustand === "angefordert";

  useEffect(() => {
    const controller = new AbortController();
    let aktiv = true;

    const nachsehen = () => {
      ladeAnsichten(auftrag.id, controller.signal)
        .then((a) => {
          if (!aktiv) return;
          setArten(a.arten);
          setStand(Date.now());
        })
        .catch(() => {
          // Eine Zugabe. Ohne sie bleibt der Fortschritt, und der ist die
          // Hauptsache.
        });
    };

    nachsehen();
    // Nur solange gearbeitet wird. Ein fertiger Lauf ändert sein Bild nicht
    // mehr, und ein Takt, der ewig weiterläuft, ist eine Anfrage alle zwei
    // Sekunden für nichts.
    const uhr = laeuft ? window.setInterval(nachsehen, VORSCHAU_TAKT_MS) : undefined;
    return () => {
      aktiv = false;
      controller.abort();
      if (uhr !== undefined) window.clearInterval(uhr);
    };
  }, [auftrag.id, laeuft]);

  // Das Fehlerbild gewinnt: es ist der Beweis, woran es lag, und veraltet
  // nicht.
  const art = arten.includes("fehler") ? "fehler" : arten.includes("aktuell") ? "aktuell" : "";
  if (!art) return null;

  const adresse = ansichtAdresse(auftrag.id, art, stand);
  const beschriftung =
    art === "fehler" ? "Die Seite im Augenblick des Scheiterns" : "Was der Prüfdienst gerade sieht";

  return (
    <figure className={gross ? stil.vorschauGross : stil.vorschau}>
      <figcaption className={stil.vorschauKopf}>
        <span>{beschriftung}</span>
        <Knopf groesse="sm" auspraegung="leise" onClick={() => setGross(!gross)}>
          {gross ? "Verkleinern" : "Vergrößern"}
        </Knopf>
      </figcaption>
      {/* Ohne `key` tauscht der Browser die Quelle, behält aber das alte Bild
          stehen, bis das neue da ist - bei einem Fehlerbild wäre das die
          Ansicht von davor. */}
      <img key={adresse} className={stil.vorschauBild} src={adresse} alt={beschriftung} />
    </figure>
  );
}

function Uebertragungsstreifen({
  stand,
  onPause,
  onWiederholen,
}: {
  stand: UebertragungStand;
  onPause: (pausiert: boolean) => void;
  onWiederholen: () => void;
}) {
  return (
    <Karte>
      <h2 className={stil.formularTitel}>Übertragung nach DFBnet</h2>

      {stand.pausiert ? (
        <Hinweis ton="warnung">
          Die Übertragung ist angehalten. Es wird nichts in DFBnet eingetragen — auch
          nicht das, was hier schon vorgemerkt ist.
        </Hinweis>
      ) : (
        <p className={stil.vorgangHinweis}>
          Der Prüfdienst darf eintragen. Was vorgemerkt ist, geht hinaus.
        </p>
      )}

      <ul className={stil.kennzahlen} aria-label="Übertragung">
        {/* Drei Nullen nebeneinander waren drei Blickfaenge ohne Inhalt.
            Was nichts zu tun gibt, tritt zurueck. */}
        <li className={stil.kennzahl}>
          <span className={stand.offen ? stil.zahl : stil.zahlLeer}>{stand.offen}</span>
          <span className={stil.zahlName}>vorgemerkt</span>
        </li>
        <li className={stil.kennzahl}>
          <span className={stand.fertig ? stil.zahl : stil.zahlLeer}>{stand.fertig}</span>
          <span className={stil.zahlName}>eingetragen</span>
        </li>
        <li className={stil.kennzahl}>
          <span className={stand.fehler ? stil.zahlWarnend : stil.zahlLeer}>
            {stand.fehler}
          </span>
          <span className={stil.zahlName}>gescheitert</span>
        </li>
      </ul>

      {stand.fehlerhafte.length > 0 && (
        <ul className={stil.protokoll} aria-label="Gescheiterte Übertragungen">
          {stand.fehlerhafte.map((u) => (
            <li key={u.id}>
              {u.referenz} — {u.letzter_fehler} ({u.versuche} Versuche)
            </li>
          ))}
        </ul>
      )}

      <div className={stil.knoepfe}>
        <Knopf
          groesse="sm"
          auspraegung={stand.pausiert ? "primaer" : "leise"}
          onClick={() => onPause(!stand.pausiert)}
        >
          {stand.pausiert ? "Übertragung freigeben" : "Anhalten"}
        </Knopf>
        {stand.fehler > 0 && (
          <Knopf groesse="sm" auspraegung="sekundaer" onClick={onWiederholen}>
            Gescheiterte wiederholen
          </Knopf>
        )}
      </div>
    </Karte>
  );
}
