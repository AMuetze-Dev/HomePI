import { useState } from "react";

import { Etikett, Feld, Karte, Knopf, Leerzustand } from "../../ui";
import {
  aendereKategorie,
  aendereKonto,
  aenderePerson,
  entferneKategorie,
  entferneKonto,
  entfernePerson,
  legeGrundgeruestAn,
  legeKategorieAn,
  legeKontoAn,
  legePersonAn,
  type Kategorie,
  type Konto,
  type Kontoart,
  type Person,
} from "./api";
import type { Daten } from "./daten";
import stil from "./HaushaltsbuchSeite.module.css";
import { Auswahl } from "./PostenTafel";

interface Props {
  daten: Daten;
  aktion: (was: () => Promise<unknown>) => Promise<boolean>;
}

const KONTOARTEN: readonly [Kontoart, string][] = [
  ["verteiler", "Verteiler — hier kommt das Geld an"],
  ["verbrauch", "Verbrauch — hieraus wird der Alltag bezahlt"],
  ["sparen", "Sparen — was liegen bleibt"],
  ["ruecklage", "Rücklage — für die seltenen Abbuchungen"],
];

const KONTOART_WORT: Record<Kontoart, string> = {
  verteiler: "Verteiler",
  verbrauch: "Verbrauch",
  sparen: "Sparen",
  ruecklage: "Rücklage",
};

export function StammdatenTafel({ daten, aktion }: Props) {
  return (
    <>
      <Personen daten={daten} aktion={aktion} />
      <Konten daten={daten} aktion={aktion} />
      <Kategorien daten={daten} aktion={aktion} />
    </>
  );
}

/**
 * Ein Knopfpaar, das an jeder dieser drei Listen gleich aussieht.
 *
 * Ändern steht vor Entfernen, und zwar überall: wer einen Tippfehler sucht,
 * soll ihn nicht neben der Schaltfläche finden, die den Eintrag wegwirft.
 */
function Zeilenknoepfe({
  was,
  onBearbeiten,
  onEntfernen,
}: {
  was: string;
  onBearbeiten: () => void;
  onEntfernen: () => void;
}) {
  return (
    <>
      <Knopf
        groesse="sm"
        auspraegung="primaer"
        onClick={onBearbeiten}
        aria-label={`${was} ändern`}
      >
        Ändern
      </Knopf>
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={onEntfernen}
        aria-label={`${was} entfernen`}
      >
        Entfernen
      </Knopf>
    </>
  );
}

function Personen({ daten, aktion }: Props) {
  const [bearbeitet, setBearbeitet] = useState<Person | null>(null);
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  function beginne(person: Person) {
    setBearbeitet(person);
    setName(person.name);
  }

  function abbrechen() {
    setBearbeitet(null);
    setName("");
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() =>
      bearbeitet
        ? aenderePerson(bearbeitet.id, { name: name.trim() })
        : legePersonAn({ name: name.trim() }),
    );
    setLaeuft(false);
    if (geklappt) abbrechen();
  }

  return (
    <section aria-labelledby="personen" className={stil.block}>
      <h2 id="personen" className={stil.abschnittstitel}>
        Personen
      </h2>

      {daten.personen.length === 0 ? (
        <Leerzustand titel="Noch niemand eingetragen">
          Wer teilt sich diesen Haushalt? Die Namen hier sind keine Anmeldungen am HomePI
          — sie sagen nur, zwischen wem eine gemeinsame Rechnung aufgeteilt wird.
        </Leerzustand>
      ) : (
        <Karte blank>
          <ul className={stil.zeilenliste} aria-label="Personen">
            {daten.personen.map((person) => (
              <li key={person.id} className={stil.zeile}>
                <span>{person.name}</span>
                <div className={stil.aktionen}>
                  <Zeilenknoepfe
                    was={person.name}
                    onBearbeiten={() => beginne(person)}
                    onEntfernen={() => void aktion(() => entfernePerson(person.id))}
                  />
                </div>
              </li>
            ))}
          </ul>
        </Karte>
      )}

      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Aaron"
            autoComplete="off"
          />
          <div className={stil.formularfuss}>
            {bearbeitet && (
              <Knopf type="button" auspraegung="leise" onClick={abbrechen}>
                Abbrechen
              </Knopf>
            )}
            <Knopf
              type="submit"
              auspraegung="primaer"
              disabled={name.trim() === "" || laeuft}
            >
              {laeuft
                ? "Wird gespeichert …"
                : bearbeitet
                  ? `„${bearbeitet.name}" umbenennen`
                  : "Person anlegen"}
            </Knopf>
          </div>
        </form>
      </Karte>
    </section>
  );
}

function Konten({ daten, aktion }: Props) {
  const [bearbeitet, setBearbeitet] = useState<Konto | null>(null);
  const [name, setName] = useState("");
  const [art, setArt] = useState<Kontoart>("verteiler");
  const [inhaber, setInhaber] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const inhaberName = new Map(daten.personen.map((p) => [p.id, p.name]));

  function beginne(konto: Konto) {
    setBearbeitet(konto);
    setName(konto.name);
    setArt(konto.art);
    setInhaber(konto.inhaber_id ?? "");
  }

  function abbrechen() {
    setBearbeitet(null);
    setName("");
    setArt("verteiler");
    setInhaber("");
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() =>
      bearbeitet
        ? aendereKonto(bearbeitet.id, {
            name: name.trim(),
            art,
            // Ein leeres inhaber_id hiesse beim Ändern "nicht angefasst" -
            // deshalb sagt das eigene Feld, dass es gemeinsam werden soll.
            ...(inhaber === ""
              ? { gemeinschaftlich: true }
              : { inhaber_id: inhaber, gemeinschaftlich: false }),
          })
        : legeKontoAn({
            name: name.trim(),
            art,
            inhaber_id: inhaber === "" ? null : inhaber,
          }),
    );
    setLaeuft(false);
    if (geklappt) abbrechen();
  }

  return (
    <section aria-labelledby="konten" className={stil.block}>
      <h2 id="konten" className={stil.abschnittstitel}>
        Konten
      </h2>

      {daten.konten.length === 0 ? (
        <Leerzustand titel="Noch kein Konto">
          Ein Konto ohne Inhaber ist ein gemeinsames — darauf liegen die Posten, die
          aufgeteilt werden.
        </Leerzustand>
      ) : (
        <Karte blank>
          <ul className={stil.zeilenliste} aria-label="Konten">
            {daten.konten.map((konto) => (
              <li key={konto.id} className={stil.zeile}>
                <span>
                  {konto.name}
                  <span className={stil.unterzeile}>
                    {KONTOART_WORT[konto.art]} ·{" "}
                    {konto.inhaber_id === null
                      ? "gemeinsam"
                      : (inhaberName.get(konto.inhaber_id) ?? "unbekannt")}
                  </span>
                </span>
                <div className={stil.aktionen}>
                  {konto.inhaber_id === null && (
                    <Etikett ton="neutral">gemeinsam</Etikett>
                  )}
                  <Zeilenknoepfe
                    was={konto.name}
                    onBearbeiten={() => beginne(konto)}
                    onEntfernen={() => void aktion(() => entferneKonto(konto.id))}
                  />
                </div>
              </li>
            ))}
          </ul>
        </Karte>
      )}

      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Gemeinschaftskonto"
            autoComplete="off"
          />
          <Auswahl
            beschriftung="Art"
            value={art}
            onChange={(wert) => setArt(wert as Kontoart)}
            optionen={KONTOARTEN}
          />
          <Auswahl
            beschriftung="Inhaber"
            value={inhaber}
            onChange={setInhaber}
            optionen={[
              ["", "gemeinsam"],
              ...daten.personen.map((p): [string, string] => [p.id, p.name]),
            ]}
          />
          <div className={stil.formularfuss}>
            {bearbeitet && (
              <Knopf type="button" auspraegung="leise" onClick={abbrechen}>
                Abbrechen
              </Knopf>
            )}
            <Knopf
              type="submit"
              auspraegung="primaer"
              disabled={name.trim() === "" || laeuft}
            >
              {laeuft
                ? "Wird gespeichert …"
                : bearbeitet
                  ? `„${bearbeitet.name}" ändern`
                  : "Konto anlegen"}
            </Knopf>
          </div>
        </form>
      </Karte>
    </section>
  );
}

function Kategorien({ daten, aktion }: Props) {
  const [bearbeitet, setBearbeitet] = useState<Kategorie | null>(null);
  const [name, setName] = useState("");
  const [spart, setSpart] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  function beginne(kategorie: Kategorie) {
    setBearbeitet(kategorie);
    setName(kategorie.name);
    setSpart(kategorie.zaehlt_als_sparen);
  }

  function abbrechen() {
    setBearbeitet(null);
    setName("");
    setSpart(false);
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() =>
      bearbeitet
        ? aendereKategorie(bearbeitet.id, { name: name.trim(), zaehlt_als_sparen: spart })
        : legeKategorieAn({ name: name.trim(), zaehlt_als_sparen: spart }),
    );
    setLaeuft(false);
    if (geklappt) abbrechen();
  }

  return (
    <section aria-labelledby="kategorien" className={stil.block}>
      <h2 id="kategorien" className={stil.abschnittstitel}>
        Kategorien
      </h2>

      {daten.kategorien.length === 0 ? (
        <Leerzustand
          titel="Noch keine Kategorie"
          aktion={
            <Knopf
              auspraegung="primaer"
              onClick={() => void aktion(() => legeGrundgeruestAn())}
            >
              Die üblichen anlegen
            </Knopf>
          }
        >
          Kategorien fassen Posten zusammen — und sagen, was Verbrauch ist und was Sparen.
          Davon hängt die Sparquote ab.
        </Leerzustand>
      ) : (
        <Karte blank>
          <ul className={stil.zeilenliste} aria-label="Kategorien">
            {daten.kategorien.map((kategorie) => (
              <li key={kategorie.id} className={stil.zeile}>
                <span>{kategorie.name}</span>
                <div className={stil.aktionen}>
                  {kategorie.zaehlt_als_sparen && (
                    <Etikett ton="gut">zählt als Sparen</Etikett>
                  )}
                  <Zeilenknoepfe
                    was={kategorie.name}
                    onBearbeiten={() => beginne(kategorie)}
                    onEntfernen={() => void aktion(() => entferneKategorie(kategorie.id))}
                  />
                </div>
              </li>
            ))}
          </ul>
        </Karte>
      )}

      <Karte>
        <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
          <Feld
            beschriftung="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Mobilität"
            autoComplete="off"
          />
          <label className={stil.schalter}>
            <input
              type="checkbox"
              checked={spart}
              onChange={(e) => setSpart(e.target.checked)}
            />
            <span>
              Zählt als Sparen
              <span className={stil.unterzeile}>
                Was hierhin geht, ist kein Verbrauch — es erhöht die Sparquote statt die
                festen Kosten.
              </span>
            </span>
          </label>
          <div className={stil.formularfuss}>
            {bearbeitet && (
              <Knopf type="button" auspraegung="leise" onClick={abbrechen}>
                Abbrechen
              </Knopf>
            )}
            <Knopf
              type="submit"
              auspraegung="primaer"
              disabled={name.trim() === "" || laeuft}
            >
              {laeuft
                ? "Wird gespeichert …"
                : bearbeitet
                  ? `„${bearbeitet.name}" ändern`
                  : "Kategorie anlegen"}
            </Knopf>
          </div>
        </form>
      </Karte>
    </section>
  );
}
