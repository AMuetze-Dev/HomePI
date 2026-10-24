import { useCallback, useEffect, useRef, useState } from "react";

import { Etikett, Feld, Hinweis, Knopf } from "../../ui";
import {
  type Auftrag,
  type Einrichtungsstand,
  fordereAuftragAn,
  ladeAuftrag,
  ladeEinrichtung,
  speichereEinstellungen,
  speichereZugang,
} from "./api";
import stil from "./Einrichtung.module.css";

/** Die Schritte in ihrer Reihenfolge. `willkommen` erklärt nur. */
const SCHRITTE = ["willkommen", "zugang", "staffeln", "fertig"] as const;
type Schritt = (typeof SCHRITTE)[number];

const WORT: Record<Schritt, string> = {
  willkommen: "Start",
  zugang: "Zugang",
  staffeln: "Staffeln",
  fertig: "Fertig",
};

/** Wie oft nachgesehen wird, solange ein Auftrag unterwegs ist. */
const TAKT_MS = 2000;

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

function beendet(auftrag: Auftrag | null): boolean {
  return (
    auftrag !== null && auftrag.zustand !== "angefordert" && auftrag.zustand !== "laeuft"
  );
}

/**
 * Der Weg durch die Einrichtung: Zugang, Staffeln, fertig.
 *
 * **Warum ein eigener Weg und keine zwei Formulare.** Beides gibt es schon —
 * „DFBnet-Zugang" und „Staffeln". Wer frisch anfängt, weiß nur nicht, dass es
 * beide gibt, in welcher Reihenfolge sie drankommen und dass ohne sie jede
 * Liste leer bleibt. Genau das stand vorher nirgends: die Spielprüfung sagte
 * „keine Spielberichte" und meinte „nicht eingerichtet".
 *
 * **Eine Seite je Schritt, kein Scrollen.** Ein Formular mit allem
 * untereinander ist schneller gebaut und langsamer auszufüllen: man sieht
 * nicht, wie weit man ist, und ein Fehler oben bleibt unbemerkt, während man
 * unten weitertippt.
 *
 * **Geprüft wird wirklich.** Der Zugang wird nicht nur abgelegt, sondern mit
 * einer Anmeldeprobe gegen DFBnet geprüft — dem kürzesten Auftrag, den es
 * gibt. Ein Passwort, das erst beim ersten Prüflauf auffällt, ist das
 * Gegenteil einer Einrichtung.
 *
 * **Hier läuft nichts.** Ein Auftrag ist ein Datensatz; gearbeitet wird im
 * Prüfdienst. Läuft der nicht, bleibt die Probe auf „Wartet" stehen — und das
 * steht auch so da, statt einen Fortschritt vorzutäuschen.
 */
export function Einrichtung({ onFertig }: { onFertig: () => void }) {
  const [stand, setStand] = useState<Einrichtungsstand | null>(null);
  const [schritt, setSchritt] = useState<Schritt>("willkommen");
  const [benutzer, setBenutzer] = useState("");
  const [passwort, setPasswort] = useState("");
  const [auftrag, setAuftrag] = useState<Auftrag | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState("");

  // Ohne das springt der Weg beim ersten Abruf zurueck: `stand` wird nach
  // jedem Auftrag neu geladen, und ein frisch geholter Stand wuerde den
  // Schritt sonst erneut setzen -- mitten im Tippen.
  const begonnen = useRef(false);

  const standLaden = useCallback(async (signal?: AbortSignal) => {
    try {
      const frisch = await ladeEinrichtung(signal);
      setStand(frisch);
      if (!begonnen.current) {
        begonnen.current = true;
        // Wer nur den Zugang vermisst, faengt beim Willkommen an; wer ihn
        // schon hat, mitten im Weg. Die Erklaerung zweimal zu lesen ist
        // niemandem zuzumuten.
        if (frisch.schritt === "staffeln") setSchritt("staffeln");
      }
    } catch (f) {
      if (signal?.aborted) return;
      setFehler(meldung(f));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void standLaden(controller.signal);
    return () => controller.abort();
  }, [standLaden]);

  // Nur nachsehen, solange etwas unterwegs ist. Ein Takt, der auf einer
  // fertigen Seite weiterlaeuft, haelt den Pi wach.
  useEffect(() => {
    if (auftrag === null || beendet(auftrag)) return;
    const id = auftrag.id;
    const uhr = setInterval(() => {
      void (async () => {
        try {
          setAuftrag(await ladeAuftrag(id));
        } catch (f) {
          setFehler(meldung(f));
        }
      })();
    }, TAKT_MS);
    return () => clearInterval(uhr);
  }, [auftrag]);

  // Ein fertiger Auftrag bringt den Weg weiter -- aber erst, wenn er fertig
  // ist. Vorher waere es eine Zusage, die noch niemand eingeloest hat.
  useEffect(() => {
    if (auftrag === null || auftrag.zustand !== "fertig") return;
    void standLaden();
    if (auftrag.art === "anmeldeprobe") setSchritt("staffeln");
    if (auftrag.art === "staffeln") setSchritt("fertig");
  }, [auftrag, standLaden]);

  async function handeln(tun: () => Promise<void>) {
    setFehler("");
    setLaeuft(true);
    try {
      await tun();
    } catch (f) {
      setFehler(meldung(f));
    } finally {
      setLaeuft(false);
    }
  }

  function zugangPruefen() {
    void handeln(async () => {
      await speichereZugang(benutzer.trim(), passwort);
      // Nicht nur ablegen: ein Passwort, das erst beim ersten Prueflauf
      // auffaellt, ist das Gegenteil einer Einrichtung.
      setAuftrag(await fordereAuftragAn("anmeldeprobe"));
      setPasswort("");
    });
  }

  function staffelnHolen() {
    void handeln(async () => {
      setAuftrag(await fordereAuftragAn("staffeln"));
    });
  }

  function abschliessen() {
    void handeln(async () => {
      await speichereEinstellungen({ einrichtung_erledigt: true });
      onFertig();
    });
  }

  const schrittNummer = SCHRITTE.indexOf(schritt);

  return (
    <div className={stil.buehne}>
      <ol className={stil.leiste} aria-label="Schritte der Einrichtung">
        {SCHRITTE.map((s, i) => (
          <li
            key={s}
            className={
              i < schrittNummer
                ? stil.punktFertig
                : i === schrittNummer
                  ? stil.punktJetzt
                  : stil.punkt
            }
            aria-current={i === schrittNummer ? "step" : undefined}
          >
            <span className={stil.punktZahl} aria-hidden="true">
              {i < schrittNummer ? "✓" : i + 1}
            </span>
            <span className={stil.punktWort}>{WORT[s]}</span>
          </li>
        ))}
      </ol>

      {/* Der Schluessel wechselt mit dem Schritt: dadurch baut React die
          Flaeche neu auf, und die Bewegung laeuft. Ohne ihn wechselte nur der
          Text, und der Weg fuehlte sich an wie ein Formular, das sich selbst
          ueberschreibt. */}
      <section key={schritt} className={stil.blatt} aria-live="polite">
        {fehler && (
          <Hinweis ton="fehler" dringend>
            {fehler}
          </Hinweis>
        )}

        {schritt === "willkommen" && (
          <Willkommen
            stand={stand}
            onWeiter={() => setSchritt("zugang")}
            onSpaeter={abschliessen}
            laeuft={laeuft}
          />
        )}

        {schritt === "zugang" && (
          <Zugang
            benutzer={benutzer}
            passwort={passwort}
            onBenutzer={setBenutzer}
            onPasswort={setPasswort}
            onPruefen={zugangPruefen}
            auftrag={auftrag?.art === "anmeldeprobe" ? auftrag : null}
            laeuft={laeuft}
            schluesselFehlt={stand !== null && !stand.schluessel_vorhanden}
          />
        )}

        {schritt === "staffeln" && (
          <Staffeln
            auftrag={auftrag?.art === "staffeln" ? auftrag : null}
            onHolen={staffelnHolen}
            onWeiter={() => setSchritt("fertig")}
            laeuft={laeuft}
          />
        )}

        {schritt === "fertig" && (
          <Fertig stand={stand} onLos={abschliessen} laeuft={laeuft} />
        )}
      </section>
    </div>
  );
}

function Willkommen({
  stand,
  onWeiter,
  onSpaeter,
  laeuft,
}: {
  stand: Einrichtungsstand | null;
  onWeiter: () => void;
  onSpaeter: () => void;
  laeuft: boolean;
}) {
  return (
    <>
      <p className={stil.ueber}>Einrichtung</p>
      <h1 className={stil.titel}>Zwei Schritte, dann prüft er mit.</h1>
      <p className={stil.satz}>
        StaffelPilot liest die Spielberichte deiner Staffeln aus DFBnet und prüft sie
        gegen die Spielordnung. Dafür braucht er genau zwei Dinge — und ohne sie bleibt
        jede Liste leer.
      </p>

      <ul className={stil.punkte}>
        <li>
          <span className={stil.punkteZahl} aria-hidden="true">
            1
          </span>
          <div>
            <strong>Dein DFBnet-Zugang.</strong> Wird verschlüsselt abgelegt und gleich
            ausprobiert: eine Anmeldung, sonst nichts.
          </div>
        </li>
        <li>
          <span className={stil.punkteZahl} aria-hidden="true">
            2
          </span>
          <div>
            <strong>Deine Staffeln.</strong> Holt er selbst aus „Eigene Staffeln" —
            abgetippt wird nichts, und genau daran ist die Prüfung schon einmal
            gescheitert.
          </div>
        </li>
      </ul>

      <p className={stil.leise}>
        Beides lässt sich später jederzeit ändern. Eingetragen wird in DFBnet nichts: die
        Übertragung steht auf pausiert, bis du sie freigibst.
      </p>

      <div className={stil.fuss}>
        <Knopf auspraegung="primaer" onClick={onWeiter}>
          Los geht’s
        </Knopf>
        <Knopf auspraegung="leise" onClick={onSpaeter} disabled={laeuft}>
          Später, ich richte selbst ein
        </Knopf>
      </div>

      {stand !== null && !stand.schluessel_vorhanden && (
        <Hinweis ton="warnung">
          Dieser Installation fehlt der Schlüssel für den Zugang (
          <code>STAFFELPILOT_SCHLUESSEL</code>). Ohne ihn lässt sich kein Passwort ablegen
          — das ist eine Sache für den Betreiber, nicht für dich.
        </Hinweis>
      )}
    </>
  );
}

function Zugang({
  benutzer,
  passwort,
  onBenutzer,
  onPasswort,
  onPruefen,
  auftrag,
  laeuft,
  schluesselFehlt,
}: {
  benutzer: string;
  passwort: string;
  onBenutzer: (wert: string) => void;
  onPasswort: (wert: string) => void;
  onPruefen: () => void;
  auftrag: Auftrag | null;
  laeuft: boolean;
  schluesselFehlt: boolean;
}) {
  const unterwegs = auftrag !== null && !beendet(auftrag);

  return (
    <>
      <p className={stil.ueber}>Schritt 1 von 2</p>
      <h1 className={stil.titel}>Dein DFBnet-Zugang</h1>
      <p className={stil.satz}>
        Dieselben Daten, mit denen du dich bei DFBnet anmeldest. Das Passwort wird
        verschlüsselt abgelegt und kommt nie wieder heraus — auch nicht in diese
        Oberfläche.
      </p>

      <form
        className={stil.formular}
        onSubmit={(e) => {
          e.preventDefault();
          onPruefen();
        }}
      >
        <Feld
          beschriftung="DFBnet-Benutzername"
          value={benutzer}
          autoComplete="off"
          onChange={(e) => onBenutzer(e.target.value)}
          disabled={unterwegs}
        />
        <Feld
          beschriftung="Passwort"
          type="password"
          value={passwort}
          autoComplete="off"
          onChange={(e) => onPasswort(e.target.value)}
          disabled={unterwegs}
        />

        <div className={stil.fuss}>
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={
              laeuft || unterwegs || !benutzer.trim() || !passwort || schluesselFehlt
            }
          >
            Speichern und anmelden
          </Knopf>
        </div>
      </form>

      {auftrag !== null && (
        <Lauf auftrag={auftrag} wartetext="Wartet auf den Prüfdienst" />
      )}

      {auftrag?.zustand === "gescheitert" && (
        <Hinweis ton="fehler" dringend>
          {auftrag.meldung || "Die Anmeldung hat nicht geklappt."} Trag die Daten noch
          einmal ein — DFBnet unterscheidet Groß- und Kleinschreibung im Passwort.
        </Hinweis>
      )}
    </>
  );
}

function Staffeln({
  auftrag,
  onHolen,
  onWeiter,
  laeuft,
}: {
  auftrag: Auftrag | null;
  onHolen: () => void;
  onWeiter: () => void;
  laeuft: boolean;
}) {
  const unterwegs = auftrag !== null && !beendet(auftrag);

  return (
    <>
      <p className={stil.ueber}>Schritt 2 von 2</p>
      <h1 className={stil.titel}>Deine Staffeln</h1>
      <p className={stil.satz}>
        Der Prüfdienst meldet sich an und liest „Eigene Staffeln" — also genau die, für
        die du zuständig bist. Abgetippt wird nichts: eine Spielklasse, die DFBnet anders
        schreibt als du, hat die Prüfung schon einmal ins Leere laufen lassen.
      </p>

      <div className={stil.fuss}>
        <Knopf auspraegung="primaer" onClick={onHolen} disabled={laeuft || unterwegs}>
          {auftrag?.zustand === "gescheitert"
            ? "Noch einmal versuchen"
            : "Staffeln holen"}
        </Knopf>
        <Knopf auspraegung="leise" onClick={onWeiter} disabled={unterwegs}>
          Überspringen
        </Knopf>
      </div>

      {auftrag !== null && (
        <Lauf auftrag={auftrag} wartetext="Wartet auf den Prüfdienst" />
      )}

      {auftrag?.zustand === "gescheitert" && (
        <Hinweis ton="fehler" dringend>
          {auftrag.meldung || "Die Staffeln ließen sich nicht holen."}
        </Hinweis>
      )}
    </>
  );
}

function Fertig({
  stand,
  onLos,
  laeuft,
}: {
  stand: Einrichtungsstand | null;
  onLos: () => void;
  laeuft: boolean;
}) {
  return (
    <>
      <div className={stil.haken} aria-hidden="true">
        ✓
      </div>
      <p className={stil.ueber}>Eingerichtet</p>
      <h1 className={stil.titel}>Fertig.</h1>
      <p className={stil.satz}>
        {stand && stand.staffeln > 0
          ? `${stand.staffeln} ${stand.staffeln === 1 ? "Staffel steht" : "Staffeln stehen"} bereit. Ein Prüflauf liest jetzt die Spielberichte der letzten Wochen und legt die Befunde in die Spielprüfung.`
          : "Es steht noch keine Staffel. Du kannst sie jederzeit unter „Staffeln“ anlegen oder die Einrichtung in den Einstellungen noch einmal starten."}
      </p>

      <ul className={stil.punkte}>
        <li>
          <span className={stil.punkteZahl} aria-hidden="true">
            →
          </span>
          <div>
            <strong>Als Nächstes:</strong> unter „Prüflauf" einen Lauf anfordern. Er holt
            die Berichte und prüft sie; eingetragen wird in DFBnet nichts.
          </div>
        </li>
      </ul>

      <div className={stil.fuss}>
        <Knopf auspraegung="primaer" onClick={onLos} disabled={laeuft}>
          Zur Spielprüfung
        </Knopf>
      </div>
    </>
  );
}

/**
 * Was der Prüfdienst gerade tut — oder dass er es noch nicht tut.
 *
 * „Wartet" heißt wirklich warten: ein Auftrag ist ein Datensatz, und solange
 * der Dienst nicht läuft, passiert nichts. Ein Balken, der trotzdem kriecht,
 * wäre eine Lüge, die genau dann auffällt, wenn jemand Hilfe braucht.
 */
function Lauf({ auftrag, wartetext }: { auftrag: Auftrag; wartetext: string }) {
  const wartet = auftrag.zustand === "angefordert";
  const laeuft = auftrag.zustand === "laeuft";
  const letzte = auftrag.protokoll.at(-1)?.text ?? "";

  return (
    <div className={stil.lauf}>
      <div className={stil.laufKopf}>
        <Etikett
          ton={
            auftrag.zustand === "fertig"
              ? "gut"
              : auftrag.zustand === "gescheitert"
                ? "fehler"
                : "neutral"
          }
        >
          {wartet
            ? wartetext
            : laeuft
              ? auftrag.schritt || "Läuft"
              : auftrag.meldung || "Fertig"}
        </Etikett>
        {(wartet || laeuft) && <span className={stil.pulsschlag} aria-hidden="true" />}
      </div>

      <div
        className={stil.balken}
        role="progressbar"
        aria-valuenow={auftrag.fortschritt}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={wartet ? stil.balkenWartet : stil.balkenWert}
          style={{ width: `${Math.max(auftrag.fortschritt, laeuft ? 8 : 0)}%` }}
        />
      </div>

      {letzte && <p className={stil.laufZeile}>{letzte}</p>}
    </div>
  );
}
