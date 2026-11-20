import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchOeffentlicheUrl, type ModulEintrag } from "../api/client";
import { Anmeldeformular } from "../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../anmeldung/kontext";
import { useModule } from "../module/useModule";
import { Etikett, Knopf, Leerzustand, Platzhalter, Regel } from "../ui";
import { QrKarte } from "./QrKarte";
import stil from "./Start.module.css";

const QR_SCHLUESSEL = "homepi.qr-code";

function qrGemerkt(): boolean {
  try {
    return localStorage.getItem(QR_SCHLUESSEL) === "an";
  } catch {
    return false;
  }
}

/**
 * Ob der QR-Code steht, und für welche Adresse.
 *
 * Gemerkt im Browser, nicht im Konto: Er gehört zu dem Rechner, der bei
 * der Vorstellung am Beamer hängt, nicht zu dem, der dort angemeldet ist.
 * Die Adresse wird erst geholt, wenn der Code das erste Mal zu sehen ist.
 */
function useQrCode() {
  const [sichtbar, setSichtbar] = useState(qrGemerkt);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!sichtbar || url !== null) return;
    const abbruch = new AbortController();
    // Kennt das Gateway keine öffentliche Adresse - oder antwortet es gar
    // nicht -, gilt die, unter der die Seite gerade läuft. Ein Code, der
    // im Heimnetz funktioniert, ist besser als eine Fehlermeldung.
    fetchOeffentlicheUrl(abbruch.signal)
      .then((oeffentlich) => setUrl(oeffentlich ?? window.location.origin))
      .catch(() => {
        if (!abbruch.signal.aborted) setUrl(window.location.origin);
      });
    return () => abbruch.abort();
  }, [sichtbar, url]);

  function umschalten() {
    const neu = !sichtbar;
    setSichtbar(neu);
    try {
      localStorage.setItem(QR_SCHLUESSEL, neu ? "an" : "aus");
    } catch {
      // Ohne Speicher steht er eben nach dem Neuladen nicht mehr da.
    }
  }

  return { sichtbar, url, umschalten };
}

/**
 * Die Startseite: eine Liste von Namen, sonst nichts.
 *
 * Vorher standen hier Kacheln mit Titel, Beschreibung, Version und Pfad.
 * Bei vier Artefakten war das eine Wand aus Text, in der der Name - das
 * einzige, wonach jemand sucht - die kleinste Zeile war. Jetzt trägt der
 * Name die Zeile, und was daneben steht, steht nur dann da, wenn es etwas
 * zu melden gibt.
 *
 * Die Nummern sind keine Verzierung: Sie machen aus einer Aufzählung eine
 * Reihenfolge, die über Tage dieselbe bleibt - man greift irgendwann nach
 * „der dritten" statt zu lesen.
 */
export function Start() {
  // Dieselbe Liste, die auch die Navigation zeigt - einmal geholt.
  const zustand = useModule();
  const { zustand: anmeldung, benutzer } = useAnmeldung();
  const qr = useQrCode();

  // Solange das Manifest unterwegs ist, steht noch nicht fest, ob diese
  // Seite eine Übersicht wird oder ein Anmeldeformular. Deshalb hier nur
  // ein neutraler Platzhalter: eine Begrüßung, die einen Wimpernschlag
  // später vom Anmeldeformular abgelöst wird, ist schlechter als keine.
  if (anmeldung === "laedt" || zustand.phase === "laedt") {
    return (
      <div className={stil.buehne}>
        <div className={stil.laden} role="status" aria-label="Wird geladen">
          <Platzhalter breite="18rem" hoehe="2.5rem" />
          <Platzhalter breite="26rem" hoehe="1rem" />
          <div className={stil.ladeliste} aria-hidden="true">
            <Platzhalter breite="100%" hoehe="1px" />
            <Platzhalter breite="12rem" hoehe="1.875rem" />
            <Platzhalter breite="100%" hoehe="1px" />
            <Platzhalter breite="10rem" hoehe="1.875rem" />
            <Platzhalter breite="100%" hoehe="1px" />
          </div>
        </div>
      </div>
    );
  }

  const module = zustand.phase === "fertig" ? zustand.module : [];

  // Nichts zu sehen und niemand angemeldet: dann ist die Anmeldung das, was
  // hier hingehört - und nicht der Hinweis, es sei kein Artefakt vorhanden.
  //
  // Nur dann: Ein öffentliches Artefakt ist ohne Konto erreichbar, und wer
  // bloß das Turnier-Dashboard sehen will, soll nicht an einem
  // Anmeldeformular vorbei müssen.
  if (anmeldung === "abgemeldet" && module.length === 0) {
    return <Anmeldeformular />;
  }

  return (
    <div className={stil.buehne}>
      <div className={qr.sichtbar ? stil.inhaltMitQr : stil.inhalt}>
        <div className={stil.mitte}>
          <h1 className={stil.gruss}>
            {begruessung()}
            {benutzer ? `, ${vorname(benutzer.anzeigename || benutzer.name)}.` : "."}
          </h1>
          <p className={stil.unterzeile}>
            {satzZurAnzahl(module.length)} Es steht hier nur, wofür du berechtigt bist.
          </p>

          {zustand.phase === "fehler" && (
            <Leerzustand titel="Verzeichnis nicht abrufbar">
              Das Gateway hat nicht geantwortet: {zustand.nachricht}
            </Leerzustand>
          )}

          {zustand.phase === "fertig" && module.length === 0 && (
            <Leerzustand titel="Noch kein Artefakt angemeldet">
              Ein neues legst du mit <code>homepi new &lt;name&gt;</code> an. Nach dem
              Deploy erscheint es hier von selbst — am Frontend ist dafür nichts zu
              ändern.
            </Leerzustand>
          )}

          {module.length > 0 && (
            <ul className={stil.liste} aria-label="Artefakte">
              <Regel />
              {module.map((modul, i) => (
                <li key={modul.id}>
                  <Zeile modul={modul} nummer={i + 1} />
                  <Regel />
                </li>
              ))}
            </ul>
          )}
        </div>
        {qr.sichtbar && <QrKarte url={qr.url} />}
      </div>

      <div className={stil.fuss}>
        <p className={stil.tastenhinweis}>
          Alles erreichbar über <kbd className={stil.taste}>Esc</kbd>
        </p>
        <Knopf
          groesse="sm"
          auspraegung="leise"
          aria-controls={qr.sichtbar ? "qr-code" : undefined}
          onClick={qr.umschalten}
        >
          {qr.sichtbar ? "QR-Code ausblenden" : "QR-Code zeigen"}
        </Knopf>
      </div>
    </div>
  );
}

function Zeile({ modul, nummer }: { modul: ModulEintrag; nummer: number }) {
  const zahl = (
    <span className={stil.nummer} aria-hidden="true">
      {String(nummer).padStart(2, "0")}
    </span>
  );

  // Ein defektes Artefakt bleibt stehen, wird aber kein Verweis: Dahinter
  // wartet nichts, was sich öffnen ließe, und ein Klick, der auf einer
  // Fehlerseite endet, ist eine Auskunft, die man auch hier geben kann.
  if (modul.status === "fehler") {
    return (
      <div className={stil.zeileGestoert}>
        {zahl}
        <span className={stil.name}>{modul.titel}</span>
        <span className={stil.meldung}>
          <Etikett ton="fehler">Fehler</Etikett>
        </span>
        {/* Die Meldung des Gateways wörtlich. Eine eigene Formulierung
            darüber wäre die eine Zeile, die beim Suchen fehlt. */}
        <p className={stil.grund} role="alert">
          {modul.beschreibung || "Das Artefakt konnte nicht geladen werden."}
        </p>
      </div>
    );
  }

  return (
    <Link to={`/modul/${modul.id}`} className={stil.zeile}>
      {zahl}
      <span className={stil.name}>{modul.titel}</span>
    </Link>
  );
}

/** Nach Tageszeit. Ohne Namen bleibt es bei der Grußformel allein. */
function begruessung(): string {
  const stunde = new Date().getHours();
  if (stunde < 5) return "Gute Nacht";
  if (stunde < 11) return "Guten Morgen";
  if (stunde < 18) return "Guten Tag";
  return "Guten Abend";
}

/** „Andreas Mütze" → „Andreas". Wer sich selbst begrüßt, tut das nicht mit
 *  dem Nachnamen. */
function vorname(name: string): string {
  return name.trim().split(/\s+/)[0] ?? name;
}

const ZAHLWORT = [
  "Keine",
  "Eine",
  "Zwei",
  "Drei",
  "Vier",
  "Fünf",
  "Sechs",
  "Sieben",
  "Acht",
  "Neun",
  "Zehn",
  "Elf",
  "Zwölf",
];

/**
 * „Vier Anwendungen laufen in diesem Haus."
 *
 * Ausgeschrieben, weil die Zahl hier Prosa ist und keine Kennzahl. Ab
 * dreizehn stehen wieder Ziffern - ab dort liest man „13" schneller als
 * „dreizehn", und eine Installation mit so vielen Artefakten ist ohnehin
 * keine, die sich an einem Satz erfreut.
 */
function satzZurAnzahl(anzahl: number): string {
  if (anzahl === 0) return "In diesem Haus läuft noch nichts.";

  const wort = ZAHLWORT[anzahl] ?? String(anzahl);
  const verb = anzahl === 1 ? "läuft" : "laufen";
  const ding = anzahl === 1 ? "Anwendung" : "Anwendungen";
  return `${wort} ${ding} ${verb} in diesem Haus.`;
}
