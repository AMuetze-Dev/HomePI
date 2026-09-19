import { useState } from "react";

import { Etikett, Feld, Hinweis, Karte, Knopf, Leerzustand } from "../../ui";
import { type Altersklasse, type NeueStaffel, type Staffel } from "./api";
import { MannschaftenListe } from "./MannschaftenTafel";
import stil from "./StaffelpilotSeite.module.css";

const ALTERSKLASSEN = [
  ["maenner", "Männer"],
  ["frauen", "Frauen"],
  ["ue32", "Ü32"],
  ["ue35", "Ü35"],
  ["ue40", "Ü40"],
  ["ue50", "Ü50"],
] as const;

function klassenWort(wert: string): string {
  return ALTERSKLASSEN.find(([id]) => id === wert)?.[1] ?? wert;
}

/**
 * Staffeln anlegen, ändern, stilllegen — und ihre Mannschaften.
 *
 * Beides auf einer Fläche, weil es dieselbe Arbeit ist: eine Staffel wird
 * einmal im Jahr eingerichtet, und dazu gehört, wer darin spielt.
 */
export function StaffelnTafel({
  staffeln,
  onAnlegen,
  onAendern,
  onLoeschen,
}: {
  staffeln: Staffel[];
  onAnlegen: (daten: NeueStaffel) => Promise<boolean>;
  onAendern: (id: string, daten: Partial<Omit<Staffel, "id">>) => Promise<boolean>;
  onLoeschen: (id: string) => Promise<boolean>;
}) {
  return (
    <>
      {staffeln.length === 0 ? (
        <Leerzustand titel="Noch keine Staffel angelegt">
          Eine Staffel ist der Ort, an dem Spielberichte ankommen. Leg die erste an — Name
          und Spielklasse genau so, wie sie in DFBnet heißen, sonst findet der Prüfdienst
          sie dort nicht wieder.
        </Leerzustand>
      ) : (
        <ul className={stil.liste} aria-label="Staffeln">
          {staffeln.map((s) => (
            <li key={s.id}>
              <StaffelKarte
                staffel={s}
                onAendern={(daten) => onAendern(s.id, daten)}
                onLoeschen={() => onLoeschen(s.id)}
              />
            </li>
          ))}
        </ul>
      )}

      <StaffelAnlegen onAnlegen={onAnlegen} />
    </>
  );
}

function StaffelKarte({
  staffel,
  onAendern,
  onLoeschen,
}: {
  staffel: Staffel;
  onAendern: (daten: Partial<Omit<Staffel, "id">>) => Promise<boolean>;
  onLoeschen: () => Promise<boolean>;
}) {
  const [offen, setOffen] = useState(false);
  const [name, setName] = useState(staffel.name);
  const [spielklasse, setSpielklasse] = useState(staffel.spielklasse);
  const [saison, setSaison] = useState(staffel.saison);
  const [fragtNach, setFragtNach] = useState(false);

  return (
    <Karte>
      <button
        type="button"
        className={stil.kopf}
        onClick={() => setOffen(!offen)}
        aria-expanded={offen}
      >
        <span className={stil.paarung}>{staffel.name}</span>
        <span className={stil.zeile}>
          <span className={stil.datum}>{staffel.spielklasse}</span>
          <Etikett>{klassenWort(staffel.altersklasse)}</Etikett>
          {staffel.saison && <Etikett mono>{staffel.saison}</Etikett>}
          <Etikett ton={staffel.aktiv ? "gut" : "neutral"}>
            {staffel.aktiv ? "aktiv" : "stillgelegt"}
          </Etikett>
        </span>
      </button>

      {offen && (
        <div className={stil.detail}>
          <form
            className={stil.formular}
            onSubmit={(e) => {
              e.preventDefault();
              void onAendern({ name, spielklasse, saison });
            }}
          >
            <Feld
              beschriftung="Name"
              hinweis="Genau wie in DFBnet — darüber findet der Prüfdienst sie wieder."
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <Feld
              beschriftung="Spielklasse"
              value={spielklasse}
              onChange={(e) => setSpielklasse(e.target.value)}
            />
            <Feld
              beschriftung="Saison"
              value={saison}
              onChange={(e) => setSaison(e.target.value)}
            />
            <div className={stil.knoepfe}>
              <Knopf type="submit" groesse="sm">
                Speichern
              </Knopf>
              <Knopf
                groesse="sm"
                auspraegung="sekundaer"
                onClick={() => void onAendern({ aktiv: !staffel.aktiv })}
              >
                {staffel.aktiv ? "Stilllegen" : "Wieder aktiv setzen"}
              </Knopf>
            </div>
          </form>

          {/* Löschen fragt nach. Es nimmt jeden Spielbericht dieser Staffel
              mit, und das ist die Arbeit einer Saison. */}
          {fragtNach ? (
            <Hinweis ton="fehler" dringend>
              <span className={stil.entschieden}>
                <span>
                  Löscht auch alle Spielberichte und Befunde dieser Staffel. Das lässt
                  sich nicht rückgängig machen.
                </span>
                <span className={stil.knoepfe}>
                  <Knopf groesse="sm" onClick={() => void onLoeschen()}>
                    Endgültig löschen
                  </Knopf>
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    onClick={() => setFragtNach(false)}
                  >
                    Abbrechen
                  </Knopf>
                </span>
              </span>
            </Hinweis>
          ) : (
            <div className={stil.knoepfe}>
              <Knopf groesse="sm" auspraegung="leise" onClick={() => setFragtNach(true)}>
                Staffel löschen
              </Knopf>
            </div>
          )}

          <h3 className={stil.formularTitel}>Mannschaften</h3>
          <MannschaftenListe staffelId={staffel.id} />
        </div>
      )}
    </Karte>
  );
}

function StaffelAnlegen({
  onAnlegen,
}: {
  onAnlegen: (daten: NeueStaffel) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [spielklasse, setSpielklasse] = useState("");
  const [saison, setSaison] = useState("");
  const [altersklasse, setAltersklasse] = useState<Altersklasse>("maenner");

  return (
    <Karte>
      <form
        className={stil.formular}
        onSubmit={(e) => {
          e.preventDefault();
          void onAnlegen({ name, spielklasse, saison, altersklasse }).then((geklappt) => {
            // Ein fehlgeschlagenes Formular behält seine Eingabe.
            if (!geklappt) return;
            setName("");
            setSpielklasse("");
            setSaison("");
          });
        }}
      >
        <h2 className={stil.formularTitel}>Staffel anlegen</h2>

        <Feld
          beschriftung="Name"
          hinweis="Genau wie in DFBnet."
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Feld
          beschriftung="Spielklasse"
          required
          value={spielklasse}
          onChange={(e) => setSpielklasse(e.target.value)}
        />
        <Feld
          beschriftung="Saison"
          hinweis="Zum Beispiel 26/27. Sie steht auf jedem Aktenzeichen."
          value={saison}
          onChange={(e) => setSaison(e.target.value)}
        />
        <label className={stil.wahl}>
          <span className={stil.wahlName}>Altersklasse</span>
          <select
            className={stil.auswahl}
            value={altersklasse}
            onChange={(e) => setAltersklasse(e.target.value as Altersklasse)}
          >
            {ALTERSKLASSEN.map(([id, wort]) => (
              <option key={id} value={id}>
                {wort}
              </option>
            ))}
          </select>
        </label>

        <Knopf type="submit">Anlegen</Knopf>
      </form>
    </Karte>
  );
}
