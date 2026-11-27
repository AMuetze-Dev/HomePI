import { useState } from "react";

import {
  Abschnitt,
  Feld,
  Karte,
  Knopf,
  Leerzustand,
  Reihe,
  Tabelle,
  Zelle,
} from "../../ui";
import type { Ereignis, Tagebucheintrag } from "./api";
import { Textfeld } from "./bausteine";
import stil from "./KinderzimmerSeite.module.css";
import { datum, heute, zeit } from "./texte";

interface Props {
  eintraege: readonly Tagebucheintrag[];
  protokoll: readonly Ereignis[];
  darfAendern: boolean;
  formularOffen: boolean;
  onFormular: (offen: boolean) => void;
  onSchreiben: (werte: { datum: string; text: string }) => Promise<boolean>;
  onEntfernen: (eintrag: Tagebucheintrag) => void;
}

/**
 * Beobachten statt messen.
 *
 * Oben schreibt ihr selbst auf, was euch auffällt. Darunter steht, was am
 * Gerät passiert ist - als Sätze, nicht als Zahlen. Es gibt bewusst keine
 * Trefferquote und keine Kurve: Entwicklung verläuft in Sprüngen und bei
 * jedem Kind anders, und eine Zahl macht daraus einen Wettbewerb.
 */
export function TagebuchTafel({
  eintraege,
  protokoll,
  darfAendern,
  formularOffen,
  onFormular,
  onSchreiben,
  onEntfernen,
}: Props) {
  const [offen, setOffen] = useState<string | null>(null);

  return (
    <>
      {formularOffen && (
        <Eintragsformular
          onAbbrechen={() => onFormular(false)}
          onSchreiben={onSchreiben}
        />
      )}

      <Abschnitt titel="Eure Notizen" regel>
        {eintraege.length === 0 ? (
          <Leerzustand titel="Noch nichts notiert">
            Das erste Mal selbst auf den Knopf gedrückt, gelacht, als Omas Stimme kam?
            Haltet es hier fest. In ein paar Jahren seid ihr froh darum.
          </Leerzustand>
        ) : (
          <ul className={stil.eintraege} aria-label="Notizen">
            {eintraege.map((eintrag) => (
              <li key={eintrag.id} className={stil.eintrag}>
                <span className={stil.eintragsdatum}>{datum(eintrag.datum)}</span>
                <p className={stil.eintragstext}>{eintrag.text}</p>
                {darfAendern && offen === eintrag.id ? (
                  <div className={stil.handlungen}>
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => onEntfernen(eintrag)}
                    >
                      Notiz löschen
                    </Knopf>
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => setOffen(null)}
                    >
                      Doch behalten
                    </Knopf>
                  </div>
                ) : (
                  darfAendern && (
                    <div>
                      <Knopf
                        groesse="sm"
                        auspraegung="leise"
                        aria-label={`Notiz vom ${datum(eintrag.datum)} löschen …`}
                        onClick={() => setOffen(eintrag.id)}
                      >
                        Löschen …
                      </Knopf>
                    </div>
                  )
                )}
              </li>
            ))}
          </ul>
        )}
      </Abschnitt>

      <Abschnitt titel="Am Gerät" beiwort="die letzten 100 Ereignisse" regel>
        {protokoll.length === 0 ? (
          <Leerzustand titel="Noch nichts gemeldet">
            Sobald das Gerät eingeschaltet ist und gespielt wird, steht hier, was passiert
            ist.
          </Leerzustand>
        ) : (
          <Tabelle
            beschriftung="Protokoll"
            raster=".8fr 2fr .8fr"
            spalten={["Wann", "Was", "Gerät"]}
          >
            {protokoll.map((e) => (
              <Reihe key={e.id}>
                <Zelle leise>{zeit(e.zeitpunkt)}</Zelle>
                <Zelle>{e.text}</Zelle>
                <Zelle leise>{e.geraet}</Zelle>
              </Reihe>
            ))}
          </Tabelle>
        )}
      </Abschnitt>
    </>
  );
}

function Eintragsformular({
  onAbbrechen,
  onSchreiben,
}: {
  onAbbrechen: () => void;
  onSchreiben: (werte: { datum: string; text: string }) => Promise<boolean>;
}) {
  const [tag, setTag] = useState(heute());
  const [text, setText] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (laeuft || text.trim() === "") return;
    setLaeuft(true);
    const geklappt = await onSchreiben({ datum: tag, text: text.trim() });
    setLaeuft(false);
    if (geklappt) onAbbrechen();
  }

  return (
    <Karte>
      <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
        <Feld
          beschriftung="Tag"
          type="date"
          value={tag}
          onChange={(e) => setTag(e.target.value)}
        />
        <Textfeld
          beschriftung="Was ist passiert?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={2000}
        />
        <div className={stil.formularfuss}>
          <Knopf auspraegung="leise" onClick={onAbbrechen}>
            Abbrechen
          </Knopf>
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={laeuft || text.trim() === ""}
            grund={text.trim() === "" ? "Erst etwas schreiben" : undefined}
          >
            {laeuft ? "Wird gespeichert …" : "Notiz speichern"}
          </Knopf>
        </div>
      </form>
    </Karte>
  );
}
