import { useCallback, useEffect, useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand, Platzhalter } from "../../ui";
import {
  type Mailentwurf,
  type Vorgang,
  type VorgangZeile,
  type VorgangZustand,
  aendereVorgang,
  ladeMailentwurf,
  ladeVorgaenge,
  ladeVorgang,
  mahnungAdresse,
  setzeVorgangZustand,
  verwerfeVorgang,
} from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

const ZUSTAND_WORT: Record<VorgangZustand, string> = {
  entwurf: "Entwurf",
  versandt: "Versandt",
  erledigt: "Erledigt",
};

const ZUSTAND_TON: Record<VorgangZustand, "warnung" | "neutral" | "gut"> = {
  entwurf: "warnung",
  versandt: "neutral",
  erledigt: "gut",
};

const ART_WORT = { mahnung: "Mahnung", sportgericht: "Sportgericht" } as const;

/** Was von hier aus möglich ist. Dieselbe Tabelle wie im Backend — dort wird
 *  geprüft, hier wird nur nichts angeboten, was ohnehin abgelehnt würde. */
const NAECHSTE: Record<VorgangZustand, VorgangZustand[]> = {
  entwurf: ["versandt"],
  versandt: ["erledigt", "entwurf"],
  erledigt: ["versandt"],
};

/**
 * Mahnungen und Anträge ans Sportgericht.
 *
 * **Hier geht nichts hinaus.** Der Text steht zum Kopieren da; abgeschickt
 * wird er im Mailprogramm, von einem Menschen. „Versandt" hält fest, was
 * draußen passiert ist — es löst nichts aus.
 */
export function VorgaengeTafel() {
  const [zeilen, setZeilen] = useState<VorgangZeile[] | null>(null);
  const [filter, setFilter] = useState<VorgangZustand | "">("");
  const [offen, setOffen] = useState<Vorgang | null>(null);
  const [fehler, setFehler] = useState("");
  const [ladefehler, setLadefehler] = useState("");

  const laden = useCallback(
    async (zustand: VorgangZustand | "", signal?: AbortSignal) => {
      try {
        setZeilen(await ladeVorgaenge(zustand || undefined, signal));
      } catch (f) {
        if (signal?.aborted) return;
        setLadefehler(meldung(f));
      }
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    void laden(filter, controller.signal);
    return () => controller.abort();
  }, [laden, filter]);

  async function oeffnen(zeile: VorgangZeile) {
    if (offen?.id === zeile.id) {
      setOffen(null);
      return;
    }
    setFehler("");
    try {
      setOffen(await ladeVorgang(zeile.id));
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  async function handeln(aktion: () => Promise<Vorgang | void>) {
    setFehler("");
    try {
      const danach = await aktion();
      setOffen(danach ?? null);
      await laden(filter);
      return true;
    } catch (f) {
      setFehler(meldung(f));
      return false;
    }
  }

  if (ladefehler && zeilen === null) {
    return (
      <Hinweis ton="fehler" dringend>
        {ladefehler}
      </Hinweis>
    );
  }

  if (zeilen === null) {
    return (
      <div role="status" aria-label="Vorgänge werden geladen">
        <Platzhalter breite="100%" hoehe="12rem" />
      </div>
    );
  }

  return (
    <>
      <div className={stil.filterZeile} role="group" aria-label="Nach Zustand filtern">
        {(["", "entwurf", "versandt", "erledigt"] as const).map((z) => (
          <Knopf
            key={z || "alle"}
            groesse="sm"
            auspraegung={filter === z ? "primaer" : "leise"}
            aria-pressed={filter === z}
            onClick={() => {
              setOffen(null);
              setFilter(z);
            }}
          >
            {z === "" ? "Alle" : ZUSTAND_WORT[z]}
          </Knopf>
        ))}
      </div>

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {zeilen.length === 0 ? (
        <Leerzustand titel="Keine Vorgänge">
          Ein Vorgang entsteht aus einem Befund: bei den Spielberichten auf „Mahnung
          entwerfen" oder „Antrag entwerfen". Nur Befunde, für die der Prüflauf einen Weg
          gemeldet hat, bekommen einen.
        </Leerzustand>
      ) : (
        <ul className={stil.liste} aria-label="Vorgänge">
          {zeilen.map((zeile) => (
            <li key={zeile.id}>
              <VorgangKarte
                zeile={zeile}
                offen={offen?.id === zeile.id ? offen : null}
                onOeffnen={() => void oeffnen(zeile)}
                onSpeichern={(daten) => handeln(() => aendereVorgang(zeile.id, daten))}
                onZustand={(z) => handeln(() => setzeVorgangZustand(zeile.id, z))}
                onVerwerfen={() => handeln(() => verwerfeVorgang(zeile.id))}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function VorgangKarte({
  zeile,
  offen,
  onOeffnen,
  onSpeichern,
  onZustand,
  onVerwerfen,
}: {
  zeile: VorgangZeile;
  offen: Vorgang | null;
  onOeffnen: () => void;
  onSpeichern: (daten: { empfaenger: string; text: string }) => Promise<boolean>;
  onZustand: (zustand: VorgangZustand) => Promise<boolean>;
  onVerwerfen: () => Promise<boolean>;
}) {
  return (
    <Karte>
      <button
        type="button"
        className={stil.kopf}
        onClick={onOeffnen}
        aria-expanded={offen !== null}
      >
        <span className={stil.paarung}>{zeile.betreff}</span>
        <span className={stil.zeile}>
          <Etikett mono>{zeile.aktenzeichen}</Etikett>
          <Etikett>{ART_WORT[zeile.art]}</Etikett>
          <Etikett ton={ZUSTAND_TON[zeile.zustand]}>
            {ZUSTAND_WORT[zeile.zustand]}
          </Etikett>
        </span>
      </button>

      {offen !== null && (
        <VorgangInhalt {...{ offen, onSpeichern, onZustand, onVerwerfen }} />
      )}
    </Karte>
  );
}

function VorgangInhalt({
  offen,
  onSpeichern,
  onZustand,
  onVerwerfen,
}: {
  offen: Vorgang;
  onSpeichern: (daten: { empfaenger: string; text: string }) => Promise<boolean>;
  onZustand: (zustand: VorgangZustand) => Promise<boolean>;
  onVerwerfen: () => Promise<boolean>;
}) {
  // Eigener Zustand, aus dem geladenen Vorgang vorbelegt. Beim Zuklappen
  // verschwindet die Komponente, und damit auch ein halb getippter Text -
  // das ist gewollt: gespeichert wird über den Knopf, nicht nebenbei.
  const [empfaenger, setEmpfaenger] = useState(offen.empfaenger);
  const [text, setText] = useState(offen.text);
  const [kopiert, setKopiert] = useState(false);
  const [entwurf, setEntwurf] = useState<Mailentwurf | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    ladeMailentwurf(offen.id, controller.signal)
      .then(setEntwurf)
      .catch(() => {
        // Der Entwurf ist eine Zugabe: Betreff und Lücken des Formulars. Ohne
        // ihn bleiben Text und Empfänger, und die sind die Hauptsache.
      });
    return () => controller.abort();
  }, [offen.id]);

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(text);
      setKopiert(true);
    } catch {
      /* Ohne Zwischenablage bleibt der Text markierbar - mehr geht nicht. */
    }
  }

  /**
   * Das Mailprogramm mit Betreff und Text öffnen.
   *
   * `mailto:` und kein eigener Versand: dieses Programm verschickt nichts,
   * und es hat auch keinen Weg dorthin. Der Empfänger steht drin, wenn einer
   * eingetragen ist — sonst wählt ihn der Staffelleiter im Mailfenster.
   *
   * Lange Texte kürzt mancher Mailclient. Deshalb steht „Text kopieren"
   * daneben und nicht darunter.
   */
  function mailOeffnen() {
    const betreff = entwurf?.betreff ?? offen.betreff;
    const ziel =
      `mailto:${encodeURIComponent(empfaenger)}` +
      `?subject=${encodeURIComponent(betreff)}` +
      `&body=${encodeURIComponent(text)}`;
    window.location.href = ziel;
  }

  return (
    <div className={stil.befunde}>
      <p className={stil.vorgangHinweis}>
        Dieses Programm verschickt nichts. Formular herunterladen, E-Mail öffnen,
        Empfänger wählen, anhängen, senden — und danach hier auf „Versandt" stellen.
      </p>

      <Feld
        beschriftung="Empfänger"
        value={empfaenger}
        onChange={(e) => {
          setEmpfaenger(e.target.value);
          setKopiert(false);
        }}
      />

      <label className={stil.textfeldEtikett}>
        <span>Text</span>
        <textarea
          className={stil.textfeld}
          rows={16}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setKopiert(false);
          }}
        />
      </label>

      {entwurf !== null && entwurf.fehlende_felder.length > 0 && (
        <Hinweis ton="warnung">
          Im Formular fehlen: {entwurf.fehlende_felder.join(", ")}. Bitte vor dem Absenden
          von Hand eintragen — erfunden wird hier nichts.
        </Hinweis>
      )}

      <div className={stil.knoepfe}>
        <Knopf groesse="sm" onClick={() => void onSpeichern({ empfaenger, text })}>
          Speichern
        </Knopf>
        <Knopf groesse="sm" auspraegung="sekundaer" onClick={() => void kopieren()}>
          {kopiert ? "Kopiert" : "Text kopieren"}
        </Knopf>
        <Knopf groesse="sm" auspraegung="sekundaer" onClick={mailOeffnen}>
          E-Mail öffnen
        </Knopf>
        {offen.art === "mahnung" && (
          <a
            className={stil.dateiknopf}
            href={mahnungAdresse(offen.id)}
            target="_blank"
            rel="noreferrer"
          >
            Mahnung (PDF)
          </a>
        )}
        {NAECHSTE[offen.zustand].map((z) => (
          <Knopf
            key={z}
            groesse="sm"
            auspraegung="sekundaer"
            onClick={() => void onZustand(z)}
          >
            {z === "entwurf"
              ? "Zurück in den Entwurf"
              : `Auf „${ZUSTAND_WORT[z]}" setzen`}
          </Knopf>
        ))}
        <Knopf groesse="sm" auspraegung="leise" onClick={() => void onVerwerfen()}>
          Verwerfen
        </Knopf>
      </div>

      {offen.versandt_am !== null && (
        <p className={stil.vorgangHinweis}>
          Versandt am {new Date(offen.versandt_am).toLocaleDateString("de-DE")}.
        </p>
      )}
    </div>
  );
}
