import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { meldung } from "../../api/client";
import { useAnmeldung } from "../../anmeldung/kontext";
import { QrKarte } from "../../seiten/QrKarte";
import { Feld, Hinweis, Knopf, Leerzustand, Platzhalter, Tafel } from "../../ui";
import { leitungsAdresse, useBasisAdresse } from "./adresse";
import {
  ladeFreieKataloge,
  ladeKataloge,
  ladeRunden,
  starteEigenes,
  starteRunde,
  uebernimmLeitung,
  type FreierKatalog,
  type Runde,
  type RundeGestartet,
} from "./api";
import { Dashboard } from "./Dashboard";
import { Symbol } from "./Symbol";
import stil from "./Quiz.module.css";

/**
 * Leiten - für jeden, mit oder ohne Konto.
 *
 * Drei Wege hinein: eine Runde aus einem freigegebenen Katalog starten, mit
 * einem eigenen Quiz starten, oder mit dem Moderatorcode eine laufende Runde
 * übernehmen (auch über den QR-Code: `?zugang=…`). Danach ist die Adresse
 * `?runde=…`, und dort steht das Dashboard.
 */
export function Leiten() {
  const [suche, setSuche] = useSearchParams();
  const rundeId = suche.get("runde");
  const zugang = suche.get("zugang");
  const [gestartet, setGestartet] = useState<RundeGestartet | null>(null);

  if (zugang) {
    return (
      <Zugang code={zugang} weiter={(id) => setSuche({ runde: id }, { replace: true })} />
    );
  }
  if (rundeId) {
    return (
      <>
        <Dashboard id={rundeId} zurueck={() => setSuche({})} />
        {gestartet && (
          <CodeEinmal gestartet={gestartet} fertig={() => setGestartet(null)} />
        )}
      </>
    );
  }
  return (
    <Start
      oeffnen={(id) => setSuche({ runde: id })}
      gestartet={(ergebnis) => {
        setGestartet(ergebnis);
        setSuche({ runde: ergebnis.runde.id });
      }}
    />
  );
}

/** Der Moderatorcode direkt nach dem Start - genau einmal zu sehen. */
function CodeEinmal({
  gestartet,
  fertig,
}: {
  gestartet: RundeGestartet;
  fertig: () => void;
}) {
  const basis = useBasisAdresse();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (element && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
  }, []);
  return (
    <dialog
      ref={ref}
      className={stil.dialog}
      aria-label="Dein Moderatorcode"
      onCancel={fertig}
    >
      <div className={stil.dialogInhalt}>
        <h2 className={stil.dialogTitel}>Dein Moderatorcode</h2>
        <div className={stil.dialogMitte}>
          <QrKarte
            url={basis === null ? null : leitungsAdresse(basis, gestartet.moderatorcode)}
          />
          <p className={stil.grosserCode}>{gestartet.moderatorcode}</p>
          <p className={stil.nebensache}>
            Mit diesem Code - oder dem QR-Code - übernimmst du die Runde auf jedem Gerät.
            Er steht hier nur jetzt. Dieses Gerät merkt ihn sich.
          </p>
          {gestartet.hinweise.length > 0 && (
            <Hinweis ton="warnung">
              Übernommen - bis auf:
              <ul className={stil.hinweisliste}>
                {gestartet.hinweise.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            </Hinweis>
          )}
          <Knopf onClick={fertig}>Verstanden - zur Runde</Knopf>
        </div>
      </div>
    </dialog>
  );
}

function Zugang({ code, weiter }: { code: string; weiter: (id: string) => void }) {
  const [fehler, setFehler] = useState("");
  useEffect(() => {
    uebernimmLeitung(code)
      .then((runde) => weiter(runde.id))
      .catch((grund: unknown) => setFehler(meldung(grund)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);
  return (
    <Tafel titel="Leiten">
      {fehler ? (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      ) : (
        <div role="status" aria-label="Runde wird übernommen">
          <Platzhalter hoehe="6rem" />
        </div>
      )}
    </Tafel>
  );
}

type Liste =
  | { phase: "laedt" }
  | { phase: "fertig"; kataloge: FreierKatalog[]; runden: Runde[] }
  | { phase: "fehler"; nachricht: string };

function Start({
  oeffnen,
  gestartet,
}: {
  oeffnen: (id: string) => void;
  gestartet: (ergebnis: RundeGestartet) => void;
}) {
  const { darf } = useAnmeldung();
  const mitRecht = darf("quiz", "nutzer");
  const [liste, setListe] = useState<Liste>({ phase: "laedt" });
  const [gewaehlt, setGewaehlt] = useState("");
  const [fehler, setFehler] = useState("");
  const [sendet, setSendet] = useState(false);
  const [code, setCode] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    // Mit Recht: alle Kataloge und die laufenden Runden; ohne nur die freien.
    const kataloge = mitRecht
      ? ladeKataloge(controller.signal).then((alle) =>
          alle.filter((k) => k.anzahl_fragen > 0),
        )
      : ladeFreieKataloge(controller.signal);
    const runden = mitRecht ? ladeRunden(controller.signal) : Promise.resolve([]);
    Promise.all([kataloge, runden])
      .then(([k, r]) => {
        setListe({
          phase: "fertig",
          kataloge: k,
          runden: r.filter((x) => x.status !== "beendet"),
        });
        setGewaehlt((vorher) => vorher || k[0]?.id || "");
      })
      .catch((grund: unknown) => {
        if (!controller.signal.aborted)
          setListe({ phase: "fehler", nachricht: meldung(grund) });
      });
    return () => controller.abort();
  }, [mitRecht]);

  async function los(aktion: () => Promise<RundeGestartet>) {
    setFehler("");
    setSendet(true);
    try {
      gestartet(await aktion());
    } catch (grund) {
      setFehler(meldung(grund));
    } finally {
      setSendet(false);
    }
  }

  async function uebernehmen(e: FormEvent) {
    e.preventDefault();
    setFehler("");
    try {
      oeffnen((await uebernimmLeitung(code)).id);
    } catch (grund) {
      setFehler(meldung(grund));
    }
  }

  return (
    <Tafel titel="Leiten">
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}
      <div className={stil.startgitter}>
        <section className={stil.startkarte} aria-labelledby="neu">
          <h2 id="neu" className={stil.startTitel}>
            <Symbol name="start" /> Neue Runde
          </h2>
          {liste.phase === "laedt" && (
            <div role="status" aria-label="Kataloge werden geladen">
              <Platzhalter hoehe="8rem" />
            </div>
          )}
          {liste.phase === "fehler" && (
            <Hinweis ton="fehler" dringend>
              {liste.nachricht}
            </Hinweis>
          )}
          {liste.phase === "fertig" &&
            (liste.kataloge.length === 0 ? (
              <Leerzustand titel="Noch kein Quiz freigegeben">
                Lade dein eigenes Quiz hoch - ein gespeichertes Battle.Net-Quiz oder ein
                hier gesichertes ZIP.
              </Leerzustand>
            ) : (
              <fieldset className={stil.katalogwahl}>
                <legend className={stil.nebensache}>Quiz wählen</legend>
                {liste.kataloge.map((k) => (
                  <label
                    key={k.id}
                    className={stil.katalogkachel}
                    data-gewaehlt={gewaehlt === k.id}
                  >
                    <input
                      type="radio"
                      name="katalog"
                      checked={gewaehlt === k.id}
                      onChange={() => setGewaehlt(k.id)}
                    />
                    <span className={stil.katalogtitel}>{k.titel}</span>
                    <span className={stil.nebensache}>
                      {k.anzahl_fragen} Fragen
                      {k.beschreibung ? ` · ${k.beschreibung}` : ""}
                    </span>
                  </label>
                ))}
              </fieldset>
            ))}
          <div className={stil.steuerzeile}>
            {liste.phase === "fertig" && liste.kataloge.length > 0 && (
              <button
                type="button"
                className={stil.hauptknopf}
                disabled={!gewaehlt || sendet}
                onClick={() => void los(() => starteRunde(gewaehlt))}
              >
                <Symbol name="start" gefuellt /> Runde starten
              </button>
            )}
            <label className={stil.hochladeknopf}>
              <Symbol name="hochladen" />
              <span>Eigenes Quiz</span>
              <input
                type="file"
                accept=".zip,.json,application/zip,application/json"
                aria-label="Eigenes Quiz hochladen und starten"
                disabled={sendet}
                onChange={(e) => {
                  const datei = e.target.files?.[0];
                  if (datei) void los(() => starteEigenes(datei));
                }}
              />
            </label>
          </div>
          <p className={stil.nebensache}>
            Ohne Konto: Eine Runde und ein eigenes Quiz verschwinden zwei Tage nach der
            letzten Aktivität.
          </p>
        </section>

        <section className={stil.startkarte} aria-labelledby="zurueck">
          <h2 id="zurueck" className={stil.startTitel}>
            <Symbol name="schluessel" /> Zurück in deine Runde
          </h2>
          <form className={stil.formular} onSubmit={(e) => void uebernehmen(e)}>
            <Feld
              beschriftung="Moderatorcode"
              hinweis="Steht nach dem Start im Dialog - oder scanne seinen QR-Code."
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              className={stil.codefeld}
            />
            <Knopf
              type="submit"
              auspraegung="sekundaer"
              disabled={code.trim().length < 16}
            >
              Übernehmen
            </Knopf>
          </form>
          {liste.phase === "fertig" && liste.runden.length > 0 && (
            <>
              <h3 className={stil.nebensache}>Laufende Runden (mit deinem Konto)</h3>
              <ul className={stil.liste}>
                {liste.runden.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={stil.zeilenknopf}
                      onClick={() => oeffnen(r.id)}
                    >
                      <span className={stil.code}>{r.code}</span>
                      <span className={stil.zeilentext}>{r.katalog_titel}</span>
                      <span className={stil.nebensache}>{r.anzahl_spieler} Spieler</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </Tafel>
  );
}
