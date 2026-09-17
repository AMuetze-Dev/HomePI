import { useState } from "react";

import { Hinweis, Karte, Knopf } from "../../ui";
import stil from "./Startpasswort.module.css";

interface Props {
  /** Benutzername, zu dem das Passwort gehört. */
  name: string;
  wert: string;
  onWeg: () => void;
}

/**
 * Ein Startpasswort, genau einmal.
 *
 * Es steht weder in der Datenbank noch in einer weiteren Antwort - wer es hier
 * wegklickt, ohne es weiterzugeben, muss ein neues erzeugen. Deshalb steht es
 * groß, in Monospace und mit einem Knopf zum Kopieren; und deshalb verschwindet
 * es erst auf ausdrückliches Wegklicken.
 */
export function Startpasswort({ name, wert, onWeg }: Props) {
  const [kopiert, setKopiert] = useState(false);

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(wert);
      setKopiert(true);
    } catch {
      // Ohne Berechtigung oder über http ohne localhost gibt es keine
      // Zwischenablage. Das Passwort steht ja lesbar da.
      setKopiert(false);
    }
  }

  return (
    <Karte className={stil.karte}>
      <div className={stil.kopf}>
        <h2 className={stil.titel}>Startpasswort für {name}</h2>
        <Knopf
          groesse="sm"
          auspraegung="leise"
          onClick={onWeg}
          aria-label="Startpasswort ausblenden"
        >
          Verstanden
        </Knopf>
      </div>

      <div className={stil.zeile}>
        <code className={stil.wert}>{wert}</code>
        <Knopf groesse="sm" onClick={() => void kopieren()}>
          {kopiert ? "Kopiert" : "Kopieren"}
        </Knopf>
      </div>

      <Hinweis ton="warnung">
        Notiere es jetzt — es ist danach nicht mehr abrufbar. {name} muss es beim ersten
        Anmelden durch ein eigenes ersetzen und kommt bis dahin an kein Artefakt.
      </Hinweis>
    </Karte>
  );
}
