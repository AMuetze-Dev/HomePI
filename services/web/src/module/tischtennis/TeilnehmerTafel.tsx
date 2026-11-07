import { useState } from "react";

import { Etikett, Feld, Karte, Knopf, Leerzustand } from "../../ui";
import type { NeuerTeilnehmer, Teilnehmer, Turnier } from "./api";
import stil from "./TischtennisSeite.module.css";

interface Props {
  turnier: Turnier;
  teilnehmer: Teilnehmer[];
  onAnlegen: (daten: NeuerTeilnehmer) => Promise<boolean>;
  onAendern: (id: string, daten: NeuerTeilnehmer) => Promise<boolean>;
  onEntfernen: (id: string) => void;
}

/**
 * Die Liste, mit der alles anfängt.
 *
 * Das Formular steht oben und nicht unten: hier werden zwanzig Namen
 * hintereinander eingetippt, und nach jedem rutschte es sonst eine Zeile
 * weiter nach unten. Der Fokus bleibt nach dem Anlegen im Namensfeld - sonst
 * ist nach jedem Namen ein Mausweg fällig.
 */
export function TeilnehmerTafel({
  turnier,
  teilnehmer,
  onAnlegen,
  onAendern,
  onEntfernen,
}: Props) {
  const [name, setName] = useState("");
  const [notiz, setNotiz] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const [bearbeitet, setBearbeitet] = useState<string | null>(null);

  const offen = turnier.zustand === "planung";

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await onAnlegen({ name: name.trim(), notiz: notiz.trim() });
    setLaeuft(false);

    // Nur leeren, wenn es geklappt hat - sonst tippt man alles neu.
    if (geklappt) {
      setName("");
      setNotiz("");
    }
  }

  return (
    <>
      {offen ? (
        <section aria-labelledby="eintragen">
          <h2 id="eintragen" className={stil.abschnittstitel}>
            Teilnehmer eintragen
          </h2>
          <Karte>
            <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
              <Feld
                beschriftung="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="off"
                autoFocus
                required
              />
              <Feld
                beschriftung="Notiz"
                hinweis="Abteilung, Standort – was beim Zuordnen hilft"
                value={notiz}
                onChange={(e) => setNotiz(e.target.value)}
                autoComplete="off"
              />
              <Knopf
                type="submit"
                auspraegung="primaer"
                disabled={name.trim() === "" || laeuft}
                className={stil.absenden}
              >
                {laeuft ? "Wird eingetragen …" : "Eintragen"}
              </Knopf>
            </form>
          </Karte>
        </section>
      ) : (
        <Karte>
          <p className={stil.nebensache}>
            Der Spielplan steht. Wer jetzt dazukäme, hätte keine Spiele – setze das
            Turnier unter „Auswürfeln“ zurück, wenn sich die Liste doch noch ändert.
          </p>
        </Karte>
      )}

      <section aria-labelledby="liste">
        <h2 id="liste" className={stil.abschnittstitel}>
          {teilnehmer.length === 1 ? "Ein Teilnehmer" : `${teilnehmer.length} Teilnehmer`}
        </h2>

        {teilnehmer.length === 0 ? (
          <Leerzustand titel="Noch niemand dabei">
            Trage oben den ersten Namen ein. Ab zwei Teilnehmern lässt sich auswürfeln.
          </Leerzustand>
        ) : (
          <Karte blank>
            <ul className={stil.liste}>
              {teilnehmer.map((wer) =>
                bearbeitet === wer.id ? (
                  <li key={wer.id} className={stil.zeile}>
                    <Umbenennen
                      wer={wer}
                      onSpeichern={async (daten) => {
                        const geklappt = await onAendern(wer.id, daten);
                        if (geklappt) setBearbeitet(null);
                        return geklappt;
                      }}
                      onAbbrechen={() => setBearbeitet(null)}
                    />
                  </li>
                ) : (
                  <li key={wer.id} className={stil.zeile}>
                    <span className={stil.name}>
                      {wer.name}
                      {wer.notiz && (
                        <span className={stil.nebensache}> · {wer.notiz}</span>
                      )}
                    </span>
                    <span className={stil.zeilenaktionen}>
                      {wer.gruppe && <Etikett ton="neutral">{wer.gruppe}</Etikett>}
                      {wer.freilose > 0 && <Etikett ton="warnung">Freilos</Etikett>}
                      {offen && (
                        <>
                          <Knopf
                            groesse="sm"
                            auspraegung="leise"
                            onClick={() => setBearbeitet(wer.id)}
                            aria-label={`${wer.name} umbenennen`}
                          >
                            Umbenennen
                          </Knopf>
                          <Knopf
                            groesse="sm"
                            auspraegung="leise"
                            onClick={() => onEntfernen(wer.id)}
                            aria-label={`${wer.name} entfernen`}
                          >
                            Entfernen
                          </Knopf>
                        </>
                      )}
                    </span>
                  </li>
                ),
              )}
            </ul>
          </Karte>
        )}
      </section>
    </>
  );
}

function Umbenennen({
  wer,
  onSpeichern,
  onAbbrechen,
}: {
  wer: Teilnehmer;
  onSpeichern: (daten: NeuerTeilnehmer) => Promise<boolean>;
  onAbbrechen: () => void;
}) {
  const [name, setName] = useState(wer.name);
  const [notiz, setNotiz] = useState(wer.notiz);

  return (
    <form
      className={stil.formular}
      onSubmit={(ereignis) => {
        ereignis.preventDefault();
        void onSpeichern({ name: name.trim(), notiz: notiz.trim() });
      }}
    >
      <Feld
        beschriftung="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoComplete="off"
        autoFocus
        required
      />
      <Feld
        beschriftung="Notiz"
        value={notiz}
        onChange={(e) => setNotiz(e.target.value)}
        autoComplete="off"
      />
      <span className={stil.zeilenaktionen}>
        <Knopf
          type="submit"
          groesse="sm"
          auspraegung="primaer"
          disabled={name.trim() === ""}
        >
          Speichern
        </Knopf>
        <Knopf groesse="sm" auspraegung="leise" onClick={onAbbrechen}>
          Abbrechen
        </Knopf>
      </span>
    </form>
  );
}
