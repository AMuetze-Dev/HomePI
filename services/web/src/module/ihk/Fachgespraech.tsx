import { useEffect, useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Etikett, Hinweis, Knopf } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { meldung, themenAus } from "./zeit";

/** Prozent statt Brüchen - wie bei den übrigen Kriterien. */
function prozent(stufe: number): string {
  return `${Math.round(stufe * 100)} %`;
}

/**
 * Das Fachgespräch hat keine festen Kriterien: Bewertet wird jede gestellte
 * Frage für sich, der Vorschlag ist das Mittel daraus. Fragen kommen von Hand
 * dazu oder zufällig aus der Sammlung - ohne die, die schon gestellt sind.
 */
export function FragenListe({
  fragen,
  skala,
  onAendern,
}: {
  fragen: api.FgFrage[];
  skala: number[];
  onAendern: (neu: api.FgFrageEingabe[]) => void;
}) {
  function bewerte(id: string, wert: number | null) {
    onAendern(fragen.map((f) => (f.id === id ? { ...f, wert } : f)));
  }

  return (
    <>
      {fragen.length === 0 ? (
        <p className={stil.leise}>
          Noch keine Frage gestellt. Trag eine eigene ein oder zieh eine aus der Sammlung.
        </p>
      ) : (
        <ol className={stil.fragenliste}>
          {fragen.map((f) => (
            <li key={f.id} className={stil.kriterium}>
              <div className={stil.kriteriumtext}>{f.text}</div>
              <div className={stil.fragenwerkzeug}>
                <div role="group" aria-label={f.text} className={stil.punkte}>
                  {skala.map((stufe) => {
                    const gewaehlt = f.wert === stufe;
                    return (
                      <button
                        key={stufe}
                        type="button"
                        className={stil.punkt}
                        aria-pressed={gewaehlt}
                        onClick={() => bewerte(f.id, gewaehlt ? null : stufe)}
                      >
                        {prozent(stufe)}
                      </button>
                    );
                  })}
                </div>
                <button
                  type="button"
                  className={stil.entfernen}
                  aria-label={`„${f.text}“ entfernen`}
                  title="Frage entfernen"
                  onClick={() => onAendern(fragen.filter((g) => g.id !== f.id))}
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
      <EigeneFrage onStellen={(text) => onAendern([...fragen, neu(text, null)])} />
      <Ziehen
        gestellt={fragen.flatMap((f) => (f.quelle ? [f.quelle] : []))}
        onStellen={(frage) => onAendern([...fragen, neu(frage.text, frage.id)])}
      />
    </>
  );
}

function neu(text: string, quelle: string | null): api.FgFrageEingabe {
  return { text, wert: null, quelle };
}

function EigeneFrage({ onStellen }: { onStellen: (text: string) => void }) {
  const [text, setText] = useState("");

  function absenden(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    onStellen(text.trim());
    setText("");
  }

  return (
    <form onSubmit={absenden} className={stil.fragenzeile}>
      <input
        className={stil.eingabezeile}
        aria-label="Eigene Frage"
        placeholder="Eigene Frage …"
        value={text}
        maxLength={500}
        onChange={(e) => setText(e.target.value)}
        autoComplete="off"
      />
      <Knopf type="submit" groesse="sm" disabled={!text.trim()}>
        Hinzufügen
      </Knopf>
    </form>
  );
}

function Ziehen({
  gestellt,
  onStellen,
}: {
  gestellt: string[];
  onStellen: (frage: api.Frage) => void;
}) {
  const themaId = useId();
  const [sammlung, setSammlung] = useState<api.Frage[] | null>(null);
  const [thema, setThema] = useState("");
  const [gezogen, setGezogen] = useState<api.Frage | null>(null);
  // In dieser Sitzung verworfene - „Andere ziehen“ soll nicht dieselbe bringen.
  const [verworfen, setVerworfen] = useState<string[]>([]);
  const [fehler, setFehler] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    const steuerung = new AbortController();
    api
      .ladeFragen(steuerung.signal)
      .then(setSammlung)
      .catch((e: unknown) => {
        if (!steuerung.signal.aborted) setFehler(meldung(e));
      });
    return () => steuerung.abort();
  }, []);

  async function ziehe(ohneDiese: string[]) {
    setLaeuft(true);
    setFehler("");
    try {
      setGezogen(await api.zieheFrage(thema, [...gestellt, ...ohneDiese]));
    } catch (e) {
      setGezogen(null);
      setFehler(meldung(e));
    } finally {
      setLaeuft(false);
    }
  }

  function andere() {
    const neu = gezogen ? [...verworfen, gezogen.id] : verworfen;
    setVerworfen(neu);
    void ziehe(neu);
  }

  if (sammlung === null && !fehler) return null;
  const leer = sammlung !== null && sammlung.length === 0;

  return (
    <div className={stil.ziehen}>
      {leer ? (
        <p className={stil.leise}>
          Die <Link to="?fragen">Fragensammlung</Link> ist noch leer - nimm dort Fragen
          auf, dann lassen sie sich hier ziehen.
        </p>
      ) : (
        <div className={stil.fragenzeile}>
          <label htmlFor={themaId} className={stil.unsichtbar}>
            Thema
          </label>
          <select
            id={themaId}
            className={stil.auswahl}
            value={thema}
            onChange={(e) => {
              setThema(e.target.value);
              setGezogen(null);
            }}
          >
            <option value="">Alle Themen</option>
            {themenAus(sammlung ?? []).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <Knopf groesse="sm" disabled={laeuft} onClick={() => void ziehe(verworfen)}>
            Frage ziehen
          </Knopf>
          <Link to="?fragen" className={stil.verweis}>
            Sammlung
          </Link>
        </div>
      )}
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}
      {gezogen && (
        <div className={stil.gezogen} aria-live="polite">
          <p className={stil.gezogentext}>{gezogen.text}</p>
          {gezogen.thema && <Etikett>{gezogen.thema}</Etikett>}
          <div className={stil.knopfreihe}>
            <Knopf
              groesse="sm"
              auspraegung="primaer"
              onClick={() => {
                onStellen(gezogen);
                setGezogen(null);
              }}
            >
              Stellen
            </Knopf>
            <Knopf groesse="sm" disabled={laeuft} onClick={andere}>
              Andere ziehen
            </Knopf>
          </div>
        </div>
      )}
    </div>
  );
}
