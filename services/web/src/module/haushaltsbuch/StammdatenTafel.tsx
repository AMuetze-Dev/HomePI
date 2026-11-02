import { useState } from "react";

import { Etikett, Feld, Karte, Knopf, Leerzustand } from "../../ui";
import {
  entferneKategorie,
  entferneKonto,
  entfernePerson,
  legeGrundgeruestAn,
  legeKategorieAn,
  legeKontoAn,
  legePersonAn,
  type Kontoart,
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

function Personen({ daten, aktion }: Props) {
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() => legePersonAn({ name: name.trim() }));
    setLaeuft(false);
    if (geklappt) setName("");
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
                <Knopf
                  groesse="sm"
                  auspraegung="leise"
                  onClick={() => void aktion(() => entfernePerson(person.id))}
                  aria-label={`${person.name} entfernen`}
                >
                  Entfernen
                </Knopf>
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
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={name.trim() === "" || laeuft}
          >
            {laeuft ? "Wird angelegt …" : "Person anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}

function Konten({ daten, aktion }: Props) {
  const [name, setName] = useState("");
  const [art, setArt] = useState<Kontoart>("verteiler");
  const [inhaber, setInhaber] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  const inhaberName = new Map(daten.personen.map((p) => [p.id, p.name]));

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() =>
      legeKontoAn({
        name: name.trim(),
        art,
        inhaber_id: inhaber === "" ? null : inhaber,
      }),
    );
    setLaeuft(false);
    if (geklappt) setName("");
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
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    onClick={() => void aktion(() => entferneKonto(konto.id))}
                    aria-label={`${konto.name} entfernen`}
                  >
                    Entfernen
                  </Knopf>
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
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={name.trim() === "" || laeuft}
          >
            {laeuft ? "Wird angelegt …" : "Konto anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}

function Kategorien({ daten, aktion }: Props) {
  const [name, setName] = useState("");
  const [spart, setSpart] = useState(false);
  const [laeuft, setLaeuft] = useState(false);

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (name.trim() === "" || laeuft) return;

    setLaeuft(true);
    const geklappt = await aktion(() =>
      legeKategorieAn({ name: name.trim(), zaehlt_als_sparen: spart }),
    );
    setLaeuft(false);
    if (geklappt) setName("");
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
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    onClick={() => void aktion(() => entferneKategorie(kategorie.id))}
                    aria-label={`${kategorie.name} entfernen`}
                  >
                    Entfernen
                  </Knopf>
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
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={name.trim() === "" || laeuft}
          >
            {laeuft ? "Wird angelegt …" : "Kategorie anlegen"}
          </Knopf>
        </form>
      </Karte>
    </section>
  );
}
