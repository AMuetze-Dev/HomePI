import { useState, type MouseEvent } from "react";

import { Feld, Knopf } from "../../ui";
import type { Element, OeffentlicheFrage } from "./api";
import type { Entwurf } from "./entwurf";
import stil from "./Quiz.module.css";

interface Props {
  frage: OeffentlicheFrage;
  entwurf: Entwurf;
  aendern: (entwurf: Entwurf) => void;
  bildAdresse: string | null;
  gesperrt: boolean;
}

export function Eingabe({ frage, entwurf, aendern, bildAdresse, gesperrt }: Props) {
  switch (frage.typ) {
    case "zahl":
      return (
        <Feld
          beschriftung={frage.einheit ? `Deine Zahl (${frage.einheit})` : "Deine Zahl"}
          inputMode="decimal"
          value={entwurf.zahl}
          disabled={gesperrt}
          onChange={(e) => aendern({ ...entwurf, zahl: e.target.value })}
        />
      );
    case "schaetzung":
      return (
        <Schaetzung
          frage={frage}
          entwurf={entwurf}
          aendern={aendern}
          gesperrt={gesperrt}
        />
      );
    case "auswahl":
      return (
        <Auswahl frage={frage} entwurf={entwurf} aendern={aendern} gesperrt={gesperrt} />
      );
    case "hotspot":
      return (
        <Hotspot
          bildAdresse={bildAdresse}
          entwurf={entwurf}
          aendern={aendern}
          gesperrt={gesperrt}
        />
      );
    case "sortieren":
      return (
        <Sortieren
          frage={frage}
          entwurf={entwurf}
          aendern={aendern}
          gesperrt={gesperrt}
        />
      );
    default:
      return (
        <Feld
          beschriftung="Deine Antwort"
          value={entwurf.text}
          maxLength={200}
          autoComplete="off"
          disabled={gesperrt}
          onChange={(e) => aendern({ ...entwurf, text: e.target.value })}
        />
      );
  }
}

type TeilProps = Omit<Props, "bildAdresse">;

function Schaetzung({ frage, entwurf, aendern, gesperrt }: TeilProps) {
  const einheit = frage.einheit ? ` ${frage.einheit}` : "";
  return (
    <div className={stil.schaetzung}>
      <label className={stil.regler}>
        <span>
          Deine Schätzung: <strong>{entwurf.zahl.replace(".", ",") + einheit}</strong>
        </span>
        <input
          type="range"
          min={frage.minimum ?? 0}
          max={frage.maximum ?? 100}
          step={frage.schritt ?? 1}
          value={entwurf.zahl}
          disabled={gesperrt}
          onChange={(e) => aendern({ ...entwurf, zahl: e.target.value })}
        />
      </label>
      <div className={stil.reglerGrenzen} aria-hidden="true">
        <span>{String(frage.minimum).replace(".", ",") + einheit}</span>
        <span>{String(frage.maximum).replace(".", ",") + einheit}</span>
      </div>
    </div>
  );
}

function Auswahl({ frage, entwurf, aendern, gesperrt }: TeilProps) {
  function waehle(index: number) {
    if (!frage.mehrfach) {
      aendern({ ...entwurf, auswahl: [index] });
      return;
    }
    const drin = entwurf.auswahl.includes(index);
    aendern({
      ...entwurf,
      auswahl: drin
        ? entwurf.auswahl.filter((i) => i !== index)
        : [...entwurf.auswahl, index].sort((a, b) => a - b),
    });
  }

  return (
    <fieldset className={stil.optionen} disabled={gesperrt}>
      <legend className={stil.nebensache}>
        {frage.mehrfach ? "Mehrere Antworten sind richtig" : "Eine Antwort ist richtig"}
      </legend>
      {frage.optionen.map((option, index) => (
        <label
          key={index}
          className={stil.option}
          data-gewaehlt={entwurf.auswahl.includes(index)}
        >
          <input
            type={frage.mehrfach ? "checkbox" : "radio"}
            name="auswahl"
            checked={entwurf.auswahl.includes(index)}
            onChange={() => waehle(index)}
          />
          <span>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function Hotspot({ bildAdresse, entwurf, aendern, gesperrt }: Omit<Props, "frage">) {
  function tippen(ereignis: MouseEvent<HTMLButtonElement>) {
    const rahmen = ereignis.currentTarget.getBoundingClientRect();
    // Ein Bild, das noch nicht geladen ist, hat keine Fläche - ein Tipp
    // darauf ergäbe keine Stelle, sondern NaN.
    if (!rahmen.width || !rahmen.height) return;
    const x = ((ereignis.clientX - rahmen.left) / rahmen.width) * 100;
    const y = ((ereignis.clientY - rahmen.top) / rahmen.height) * 100;
    aendern({
      ...entwurf,
      x: Math.round(Math.min(100, Math.max(0, x)) * 10) / 10,
      y: Math.round(Math.min(100, Math.max(0, y)) * 10) / 10,
    });
  }

  if (bildAdresse === null) {
    return (
      <p className={stil.nebensache}>Das Bild erscheint, sobald die Leitung es zeigt.</p>
    );
  }
  return (
    <div className={stil.hotspot}>
      <button
        type="button"
        className={stil.hotspotFlaeche}
        onClick={tippen}
        disabled={gesperrt}
        aria-label="Auf die Stelle im Bild tippen"
      >
        <img src={bildAdresse} alt="Bild zur Frage" className={stil.bild} />
        {entwurf.x !== null && entwurf.y !== null && (
          <span
            className={stil.markierung}
            style={{ left: `${entwurf.x}%`, top: `${entwurf.y}%` }}
            aria-hidden="true"
          />
        )}
      </button>
      <p className={stil.nebensache} role="status">
        {entwurf.x === null
          ? "Tippe auf die Stelle im Bild."
          : "Gesetzt - tippe erneut zum Ändern."}
      </p>
    </div>
  );
}

function Sortieren({ frage, entwurf, aendern, gesperrt }: TeilProps) {
  const texte = new Map<string, Element>(frage.elemente.map((e) => [e.kennung, e]));
  const [bewegt, setBewegt] = useState<string | null>(null);

  function schiebe(index: number, richtung: -1 | 1) {
    const ziel = index + richtung;
    if (ziel < 0 || ziel >= entwurf.reihenfolge.length) return;
    const neu = [...entwurf.reihenfolge];
    [neu[index], neu[ziel]] = [neu[ziel]!, neu[index]!];
    setBewegt(neu[ziel] ?? null);
    aendern({ ...entwurf, reihenfolge: neu });
  }

  return (
    <ol className={stil.sortierliste}>
      {entwurf.reihenfolge.map((kennung, index) => (
        <li key={kennung} className={stil.sortierzeile} data-bewegt={bewegt === kennung}>
          <span className={stil.sortiernummer}>{index + 1}</span>
          <span className={stil.sortiertext}>{texte.get(kennung)?.text ?? "?"}</span>
          <span className={stil.sortierknoepfe}>
            <Knopf
              auspraegung="leise"
              groesse="sm"
              disabled={gesperrt || index === 0}
              onClick={() => schiebe(index, -1)}
              aria-label={`${texte.get(kennung)?.text ?? ""} nach oben`}
            >
              ↑
            </Knopf>
            <Knopf
              auspraegung="leise"
              groesse="sm"
              disabled={gesperrt || index === entwurf.reihenfolge.length - 1}
              onClick={() => schiebe(index, 1)}
              aria-label={`${texte.get(kennung)?.text ?? ""} nach unten`}
            >
              ↓
            </Knopf>
          </span>
        </li>
      ))}
    </ol>
  );
}
