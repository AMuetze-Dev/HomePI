import {
  useId,
  useState,
  type FormEvent,
  type MouseEvent,
  type TextareaHTMLAttributes,
} from "react";

import { Feld, Hinweis, Knopf } from "../../ui";
import type {
  BildOption,
  FrageDaten,
  FrageEingabe,
  Fragetyp,
  Option,
  Paar,
  Ziel,
} from "./api";
import { TYPWORT } from "./texte";
import { bereinigt, TYPEN, vorlage, zeilen } from "./vorlage";
import stil from "./Quiz.module.css";

interface Props {
  anfang: FrageEingabe;
  /** Nur bei einer gespeicherten Hotspot-Frage mit Bild: dort setzt man die Ziele. */
  bildAdresse?: string | null | undefined;
  speichern: (frage: FrageEingabe) => Promise<boolean>;
  abbrechen: () => void;
  knopf: string;
}

export function FrageFormular({
  anfang,
  bildAdresse,
  speichern,
  abbrechen,
  knopf,
}: Props) {
  const [frage, setFrage] = useState<FrageEingabe>(anfang);
  const [sendet, setSendet] = useState(false);
  const d = frage.daten;

  function setzeDaten(daten: FrageDaten) {
    setFrage({ ...frage, daten });
  }

  async function absenden(ereignis: FormEvent) {
    ereignis.preventDefault();
    setSendet(true);
    // Ein Fehler lässt das Formular stehen, samt Eingabe: Die Meldung des
    // Backends steht darüber, und niemand tippt zehn Optionen neu.
    await speichern(bereinigt(frage));
    setSendet(false);
  }

  return (
    <form className={stil.formular} onSubmit={(e) => void absenden(e)}>
      <label className={stil.auswahl}>
        <span>Fragetyp</span>
        <select
          value={d.typ}
          onChange={(e) => setzeDaten(vorlage(e.target.value as Fragetyp))}
        >
          {TYPEN.map((typ) => (
            <option key={typ} value={typ}>
              {TYPWORT[typ]}
            </option>
          ))}
        </select>
      </label>
      <Textfeld
        beschriftung="Frage"
        value={frage.text}
        maxLength={500}
        rows={2}
        required
        onChange={(e) => setFrage({ ...frage, text: e.target.value })}
      />
      <div className={stil.feldreihe}>
        <Feld
          beschriftung="Kategorie"
          value={frage.kategorie}
          maxLength={60}
          onChange={(e) => setFrage({ ...frage, kategorie: e.target.value })}
        />
        <Feld
          beschriftung="Punkte"
          type="number"
          min={1}
          max={100}
          value={frage.punkte}
          onChange={(e) => setFrage({ ...frage, punkte: Number(e.target.value) })}
        />
        <Feld
          beschriftung="Zeitlimit (s)"
          hinweis="leer: ohne Timer"
          type="number"
          min={5}
          max={600}
          value={frage.zeitlimit ?? ""}
          onChange={(e) =>
            setFrage({
              ...frage,
              zeitlimit: e.target.value === "" ? null : Number(e.target.value),
            })
          }
        />
      </div>

      <TypFelder daten={d} setzen={setzeDaten} bildAdresse={bildAdresse} />

      <div className={stil.knopfzeile}>
        <Knopf type="submit" disabled={sendet}>
          {knopf}
        </Knopf>
        <Knopf type="button" auspraegung="leise" onClick={abbrechen}>
          Abbrechen
        </Knopf>
      </div>
    </form>
  );
}

function TypFelder({
  daten: d,
  setzen,
  bildAdresse,
}: {
  daten: FrageDaten;
  setzen: (daten: FrageDaten) => void;
  bildAdresse: string | null | undefined;
}) {
  switch (d.typ) {
    case "freitext":
    case "bild":
      return (
        <Textfeld
          beschriftung={
            d.typ === "bild"
              ? "Richtige Antworten (leer: du bewertest von Hand)"
              : "Richtige Antworten"
          }
          hinweis={
            "Eine je Zeile. Groß- und Kleinschreibung zählt nicht." +
            (d.typ === "bild" ? " Das Bild lädst du nach dem Speichern hoch." : "")
          }
          rows={3}
          value={d.loesungen.join("\n")}
          onChange={(e) => setzen({ ...d, loesungen: zeilen(e.target.value) })}
        />
      );
    case "zahl":
      return (
        <div className={stil.feldreihe}>
          <Zahlfeld
            beschriftung="Lösung"
            wert={d.loesung}
            setzen={(loesung) => setzen({ ...d, loesung })}
          />
          <Zahlfeld
            beschriftung="Toleranz ±"
            wert={d.toleranz}
            setzen={(toleranz) => setzen({ ...d, toleranz })}
          />
          <Feld
            beschriftung="Einheit"
            value={d.einheit}
            maxLength={20}
            onChange={(e) => setzen({ ...d, einheit: e.target.value })}
          />
        </div>
      );
    case "schaetzung":
      return (
        <div className={stil.feldreihe}>
          <Zahlfeld
            beschriftung="Minimum"
            wert={d.minimum}
            setzen={(minimum) => setzen({ ...d, minimum })}
          />
          <Zahlfeld
            beschriftung="Maximum"
            wert={d.maximum}
            setzen={(maximum) => setzen({ ...d, maximum })}
          />
          <Zahlfeld
            beschriftung="Schritt"
            wert={d.schritt}
            setzen={(schritt) => setzen({ ...d, schritt })}
          />
          <Zahlfeld
            beschriftung="Lösung"
            wert={d.loesung}
            setzen={(loesung) => setzen({ ...d, loesung })}
          />
          <Feld
            beschriftung="Einheit"
            value={d.einheit}
            maxLength={20}
            onChange={(e) => setzen({ ...d, einheit: e.target.value })}
          />
        </div>
      );
    case "auswahl":
      return (
        <Optionen
          optionen={d.optionen}
          setzen={(optionen) => setzen({ ...d, optionen })}
        />
      );
    case "buzzer":
      return (
        <Feld
          beschriftung="Lösung (nur für dich sichtbar)"
          hinweis="Wer zuerst buzzert, antwortet laut. Du entscheidest richtig oder falsch."
          value={d.loesung}
          maxLength={200}
          onChange={(e) => setzen({ ...d, loesung: e.target.value })}
        />
      );
    case "hotspot":
      return (
        <Ziele
          ziele={d.ziele}
          setzen={(ziele) => setzen({ ...d, ziele })}
          bildAdresse={bildAdresse}
        />
      );
    case "sortieren":
      return (
        <Textfeld
          beschriftung="Elemente in der richtigen Reihenfolge"
          hinweis="Eines je Zeile, zwei bis acht. Die Spieler bekommen sie gemischt."
          rows={4}
          value={d.elemente.join("\n")}
          onChange={(e) => setzen({ ...d, elemente: zeilen(e.target.value) })}
        />
      );
    case "zuordnen":
      return <Paare paare={d.paare} setzen={(paare) => setzen({ ...d, paare })} />;
    case "bildauswahl":
      return (
        <Bildoptionen
          optionen={d.optionen}
          setzen={(optionen) => setzen({ ...d, optionen })}
        />
      );
  }
}

function Paare({ paare, setzen }: { paare: Paar[]; setzen: (p: Paar[]) => void }) {
  const aendern = (index: number, neu: Partial<Paar>) =>
    setzen(paare.map((p, i) => (i === index ? { ...p, ...neu } : p)));
  return (
    <fieldset className={stil.optionen}>
      <legend className={stil.nebensache}>
        Paare - links steht, was die Spieler sehen; rechts das Gegenstück, das sie
        gemischt zuordnen.
      </legend>
      {paare.map((paar, index) => (
        <div key={index} className={stil.paarzeile}>
          <input
            value={paar.links}
            maxLength={200}
            onChange={(e) => aendern(index, { links: e.target.value })}
            aria-label={`Paar ${index + 1} links`}
          />
          <span aria-hidden="true">→</span>
          <input
            value={paar.rechts}
            maxLength={200}
            onChange={(e) => aendern(index, { rechts: e.target.value })}
            aria-label={`Paar ${index + 1} rechts`}
          />
          <Knopf
            type="button"
            auspraegung="leise"
            groesse="sm"
            disabled={paare.length <= 2}
            onClick={() => setzen(paare.filter((_, i) => i !== index))}
            aria-label={`Paar ${index + 1} entfernen`}
          >
            ×
          </Knopf>
        </div>
      ))}
      <div>
        <Knopf
          type="button"
          auspraegung="sekundaer"
          groesse="sm"
          disabled={paare.length >= 8}
          onClick={() => setzen([...paare, { links: "", rechts: "" }])}
        >
          Paar hinzufügen
        </Knopf>
      </div>
    </fieldset>
  );
}

function Bildoptionen({
  optionen,
  setzen,
}: {
  optionen: BildOption[];
  setzen: (o: BildOption[]) => void;
}) {
  const aendern = (index: number, neu: Partial<BildOption>) =>
    setzen(optionen.map((o, i) => (i === index ? { ...o, ...neu } : o)));
  return (
    <fieldset className={stil.optionen}>
      <legend className={stil.nebensache}>
        Antworten als Bilder - kreuze die richtigen an. Die Bilder lädst du nach dem
        Speichern hoch; die Beschreibung lesen Screenreader vor.
      </legend>
      {optionen.map((option, index) => (
        <div key={index} className={stil.optionzeile}>
          <input
            type="checkbox"
            checked={option.richtig}
            onChange={(e) => aendern(index, { richtig: e.target.checked })}
            aria-label={`Bild ${index + 1} ist richtig`}
          />
          <input
            className={stil.optiontext}
            value={option.text}
            maxLength={80}
            placeholder={`Bild ${index + 1}`}
            onChange={(e) => aendern(index, { text: e.target.value })}
            aria-label={`Beschreibung Bild ${index + 1}`}
          />
          <Knopf
            type="button"
            auspraegung="leise"
            groesse="sm"
            disabled={optionen.length <= 2}
            onClick={() => setzen(optionen.filter((_, i) => i !== index))}
            aria-label={`Bild ${index + 1} entfernen`}
          >
            ×
          </Knopf>
        </div>
      ))}
      <div>
        <Knopf
          type="button"
          auspraegung="sekundaer"
          groesse="sm"
          disabled={optionen.length >= 6}
          onClick={() => setzen([...optionen, { text: "", richtig: false }])}
        >
          Bild hinzufügen
        </Knopf>
      </div>
    </fieldset>
  );
}

/** Mehrzeiliges Feld. Der Hinweis steht neben der Beschriftung, nicht in
 *  ihr - sonst läse ein Screenreader beides als Namen des Feldes. */
function Textfeld({
  beschriftung,
  hinweis,
  ...rest
}: {
  beschriftung: string;
  hinweis?: string;
} & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <div className={stil.textfeld}>
      <label htmlFor={id}>{beschriftung}</label>
      <textarea
        id={id}
        aria-describedby={hinweis ? `${id}-hinweis` : undefined}
        {...rest}
      />
      {hinweis && (
        <span id={`${id}-hinweis`} className={stil.nebensache}>
          {hinweis}
        </span>
      )}
    </div>
  );
}

function Zahlfeld({
  beschriftung,
  wert,
  setzen,
}: {
  beschriftung: string;
  wert: number;
  setzen: (wert: number) => void;
}) {
  const [text, setText] = useState(String(wert));
  return (
    <Feld
      beschriftung={beschriftung}
      inputMode="decimal"
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        const zahl = Number(e.target.value.replace(",", "."));
        if (e.target.value.trim() !== "" && Number.isFinite(zahl)) setzen(zahl);
      }}
    />
  );
}

function Optionen({
  optionen,
  setzen,
}: {
  optionen: Option[];
  setzen: (o: Option[]) => void;
}) {
  const aendern = (index: number, neu: Partial<Option>) =>
    setzen(optionen.map((o, i) => (i === index ? { ...o, ...neu } : o)));
  return (
    <fieldset className={stil.optionen}>
      <legend className={stil.nebensache}>
        Antworten - kreuze die richtigen an. Mehr als eine richtige heißt Mehrfachauswahl.
      </legend>
      {optionen.map((option, index) => (
        <div key={index} className={stil.optionzeile}>
          <input
            type="checkbox"
            checked={option.richtig}
            onChange={(e) => aendern(index, { richtig: e.target.checked })}
            aria-label={`Antwort ${index + 1} ist richtig`}
          />
          <input
            className={stil.optiontext}
            value={option.text}
            maxLength={200}
            onChange={(e) => aendern(index, { text: e.target.value })}
            aria-label={`Antwort ${index + 1}`}
          />
          <Knopf
            type="button"
            auspraegung="leise"
            groesse="sm"
            disabled={optionen.length <= 2}
            onClick={() => setzen(optionen.filter((_, i) => i !== index))}
            aria-label={`Antwort ${index + 1} entfernen`}
          >
            ×
          </Knopf>
        </div>
      ))}
      <div>
        <Knopf
          type="button"
          auspraegung="sekundaer"
          groesse="sm"
          disabled={optionen.length >= 8}
          onClick={() => setzen([...optionen, { text: "", richtig: false }])}
        >
          Antwort hinzufügen
        </Knopf>
      </div>
    </fieldset>
  );
}

function Ziele({
  ziele,
  setzen,
  bildAdresse,
}: {
  ziele: Ziel[];
  setzen: (ziele: Ziel[]) => void;
  bildAdresse: string | null | undefined;
}) {
  const radius = ziele[0]?.radius ?? 10;

  function tippen(ereignis: MouseEvent<HTMLButtonElement>) {
    const rahmen = ereignis.currentTarget.getBoundingClientRect();
    if (!rahmen.width || !rahmen.height) return;
    const x = Math.round(((ereignis.clientX - rahmen.left) / rahmen.width) * 1000) / 10;
    const y = Math.round(((ereignis.clientY - rahmen.top) / rahmen.height) * 1000) / 10;
    setzen([{ x, y, radius }]);
  }

  return (
    <div className={stil.formular}>
      {bildAdresse ? (
        <button
          type="button"
          className={stil.hotspotFlaeche}
          onClick={tippen}
          aria-label="Richtige Stelle setzen"
        >
          <img src={bildAdresse} alt="Bild der Frage" className={stil.bild} />
          {ziele.map((ziel, i) => (
            <span
              key={i}
              className={stil.zielkreis}
              style={{
                left: `${ziel.x}%`,
                top: `${ziel.y}%`,
                width: `${ziel.radius * 2}%`,
              }}
              aria-hidden="true"
            />
          ))}
        </button>
      ) : (
        <Hinweis>
          Speichere die Frage und lade ein Bild hoch. Danach tippst du hier die richtige
          Stelle an.
        </Hinweis>
      )}
      {/* Ueber das Zahlfeld und nicht direkt: ein geleertes Feld sprang
          sonst sofort auf 1, und aus einer getippten 5 wurde eine 15. */}
      <Zahlfeld
        beschriftung="Radius in % der Bildbreite"
        wert={radius}
        setzen={(wert) => setzen(ziele.map((z) => ({ ...z, radius: wert })))}
      />
    </div>
  );
}
