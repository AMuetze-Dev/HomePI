import { useEffect, useRef, useState } from "react";

import { Abschnitt, Etikett, Feld, Karte, Knopf, Leerzustand } from "../../ui";
import {
  aenderePosten,
  entfernePosten,
  legePostenAn,
  type Anteil,
  type Konto,
  type Person,
  type Posten,
  type Postenart,
} from "./api";
import type { Daten } from "./daten";
import { abbuchungstext, alsEuro, MONATE, rhythmus } from "./geld";
import stil from "./HaushaltsbuchSeite.module.css";

interface Props {
  daten: Daten;
  aktion: (was: () => Promise<unknown>) => Promise<boolean>;
}

const INTERVALLE: readonly [number, string][] = [
  [1, "monatlich"],
  [3, "vierteljährlich"],
  [6, "halbjährlich"],
  [12, "jährlich"],
];

/**
 * Ein Komma ist das, was auf einer deutschen Tastatur unter dem Finger liegt.
 *
 * Das Backend will einen Punkt. Diese eine Zeile ist der Unterschied
 * zwischen "1133,47" und einer 422 mit dem Wort "decimal_parsing".
 */
function alsZahlenfeld(eingabe: string): string {
  return eingabe.trim().replace(/\s/g, "").replace(",", ".");
}

export function PostenTafel({ daten, aktion }: Props) {
  // Welcher Posten gerade im Formular liegt. null heißt: ein neuer.
  const [bearbeitet, setBearbeitet] = useState<Posten | null>(null);
  const berechnet = new Map(daten.uebersicht.alle.map((z) => [z.id, z]));

  // Nach dem Neuladen zeigt `daten` neue Objekte. Ohne das hier hinge im
  // Formular der Stand von vor dem Speichern.
  const frisch = bearbeitet
    ? (daten.posten.find((p) => p.id === bearbeitet.id) ?? null)
    : null;

  if (daten.konten.length === 0) {
    return (
      <Leerzustand titel="Erst ein Konto, dann die Posten">
        Ein Posten liegt immer auf einem Konto. Lege unter <strong>Stammdaten</strong>
        mindestens eines an.
      </Leerzustand>
    );
  }

  return (
    <>
      <Liste
        daten={daten}
        berechnet={berechnet}
        aktion={aktion}
        bearbeitetId={frisch?.id}
        onBearbeiten={setBearbeitet}
      />
      <PostenFormular
        // Der Schlüssel wechselt mit dem Posten, damit React das Formular neu
        // aufbaut: die Felder stehen sonst noch auf dem vorigen Eintrag.
        key={frisch?.id ?? "neu"}
        daten={daten}
        aktion={aktion}
        bearbeitet={frisch}
        onAbbrechen={() => setBearbeitet(null)}
      />
    </>
  );
}

function Liste({
  daten,
  berechnet,
  aktion,
  bearbeitetId,
  onBearbeiten,
}: Props & {
  berechnet: Map<string, { monatsrate: string; faellige_monate: number[] }>;
  bearbeitetId: string | undefined;
  onBearbeiten: (posten: Posten) => void;
}) {
  if (daten.posten.length === 0) {
    return (
      <Leerzustand titel="Noch kein Posten">
        Trage unten ein, was jeden Monat kommt und geht — Gehalt, Miete, Versicherung. Was
        seltener abgebucht wird, bekommt ein Intervall; die monatliche Rücklage rechnet
        das Haushaltsbuch selbst.
      </Leerzustand>
    );
  }

  const name = new Map(daten.personen.map((p) => [p.id, p.name]));
  const konto = new Map(daten.konten.map((k) => [k.id, k.name]));
  const kategorie = new Map(daten.kategorien.map((k) => [k.id, k.name]));

  return (
    <div className={stil.rollbereich}>
      <table className={stil.tabelle}>
        <caption className="nur-vorlesen">Alle Posten</caption>
        <thead>
          <tr>
            <th scope="col">Posten</th>
            <th scope="col">Konto</th>
            <th scope="col">Rhythmus</th>
            <th scope="col" className={stil.rechts}>
              Abbuchung
            </th>
            <th scope="col" className={stil.rechts}>
              monatlich
            </th>
            <th scope="col">Aufteilung</th>
            <th scope="col">
              <span className="nur-vorlesen">Aktion</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {daten.posten.map((posten) => (
            <tr
              key={posten.id}
              className={posten.aktiv ? "" : stil.pausiert}
              aria-current={posten.id === bearbeitetId ? "true" : undefined}
            >
              <td>
                {posten.name}
                <span className={stil.unterzeile}>
                  {posten.kategorie_id
                    ? (kategorie.get(posten.kategorie_id) ?? "—")
                    : "Ohne Kategorie"}
                  {posten.variabel ? " · frei verfügbar" : ""}
                </span>
              </td>
              <td>{konto.get(posten.konto_id) ?? "—"}</td>
              <td>
                {posten.anlage_gewicht ? (
                  <>
                    {posten.anlage_gewicht} vom Überschuss
                    <span className={stil.unterzeile}>
                      monatlich, so viel wie übrig bleibt
                    </span>
                  </>
                ) : (
                  <>
                    {rhythmus(
                      posten.intervall_monate,
                      berechnet.get(posten.id)?.faellige_monate ?? [],
                    )}
                    <span className={stil.unterzeile}>
                      {abbuchungstext(posten.abbuchungstag)}
                    </span>
                  </>
                )}
              </td>
              <td className={stil.rechts} data-spalte="Abbuchung">
                {posten.anlage_gewicht ? (
                  <span className={stil.leise}>—</span>
                ) : (
                  alsEuro(posten.betrag)
                )}
              </td>
              <td className={`${stil.rechts} ${stil.betont}`} data-spalte="im Monat">
                {alsEuro(berechnet.get(posten.id)?.monatsrate ?? posten.betrag)}
              </td>
              <td>
                {posten.anteile.length === 0 ? (
                  <span className={stil.leise}>—</span>
                ) : (
                  <span className={stil.leise}>
                    {posten.anteile
                      .map((a) => `${name.get(a.person_id) ?? "?"} ${a.gewicht}`)
                      .join(" : ")}
                  </span>
                )}
              </td>
              <td className={stil.aktionszelle}>
                <div className={stil.aktionen}>
                  <Knopf
                    groesse="sm"
                    onClick={() => onBearbeiten(posten)}
                    aria-label={`${posten.name} ändern`}
                  >
                    Ändern
                  </Knopf>
                  <Knopf
                    groesse="sm"
                    onClick={() =>
                      void aktion(() =>
                        aenderePosten(posten.id, { aktiv: !posten.aktiv }),
                      )
                    }
                    aria-label={`${posten.name} ${posten.aktiv ? "pausieren" : "wieder aufnehmen"}`}
                  >
                    {posten.aktiv ? "Pausieren" : "Aufnehmen"}
                  </Knopf>
                  <Knopf
                    groesse="sm"
                    auspraegung="leise"
                    onClick={() => void aktion(() => entfernePosten(posten.id))}
                    aria-label={`${posten.name} entfernen`}
                  >
                    Entfernen
                  </Knopf>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Ein Formular für beides: anlegen und ändern.
 *
 * Nicht zwei Masken mit denselben zwölf Feldern — die laufen auseinander,
 * sobald ein Feld dazukommt, und dann kann man beim Ändern weniger als beim
 * Anlegen. Was sich unterscheidet, sind drei Dinge: die Überschrift, der
 * Knopf, und wohin die Eingabe geht.
 */
function PostenFormular({
  daten,
  aktion,
  bearbeitet,
  onAbbrechen,
}: Props & { bearbeitet: Posten | null; onAbbrechen: () => void }) {
  const [name, setName] = useState(bearbeitet?.name ?? "");
  const [art, setArt] = useState<Postenart>(bearbeitet?.art ?? "ausgabe");
  // Der Betrag kommt als "31.90" und wird hier deutsch angezeigt - sonst
  // steht beim Ändern ein Punkt da, wo der Benutzer ein Komma getippt hat.
  const [betrag, setBetrag] = useState(bearbeitet?.betrag.replace(".", ",") ?? "");
  const [kontoId, setKontoId] = useState(
    bearbeitet?.konto_id ?? daten.konten[0]?.id ?? "",
  );
  const [kategorieId, setKategorieId] = useState(bearbeitet?.kategorie_id ?? "");
  const [intervall, setIntervall] = useState(bearbeitet?.intervall_monate ?? 1);
  const [monat, setMonat] = useState(bearbeitet?.faelligkeitsmonat ?? 1);
  const [tag, setTag] = useState(
    bearbeitet?.abbuchungstag === null || bearbeitet?.abbuchungstag === undefined
      ? ""
      : String(bearbeitet.abbuchungstag),
  );
  const [variabel, setVariabel] = useState(bearbeitet?.variabel ?? false);
  // Ein Anlageposten legt sich nicht auf einen Betrag fest, sondern auf
  // einen Anteil an dem, was uebrig bleibt.
  const [anlage, setAnlage] = useState(bearbeitet?.anlage_gewicht != null);
  const [gewicht, setGewicht] = useState(
    bearbeitet?.anlage_gewicht != null ? String(bearbeitet.anlage_gewicht) : "",
  );
  const [gewichte, setGewichte] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (bearbeitet?.anteile ?? []).map((a) => [a.person_id, String(a.gewicht)]),
    ),
  );
  const [laeuft, setLaeuft] = useState(false);
  const anfang = useRef<HTMLDivElement>(null);

  // Die Liste kann lang sein, das Formular steht darunter. Ohne diesen
  // Sprung klickt man "Ändern" und sieht nichts passieren.
  useEffect(() => {
    if (bearbeitet) anfang.current?.scrollIntoView?.({ block: "center" });
  }, [bearbeitet]);

  const konto: Konto | undefined = daten.konten.find((k) => k.id === kontoId);
  const gemeinschaftlich = konto?.inhaber_id === null;
  const vollstaendig =
    name.trim() !== "" &&
    kontoId !== "" &&
    (anlage ? Number(gewicht) > 0 : alsZahlenfeld(betrag) !== "");
  // Der Ueberschuss ist der einer Person - auf einem gemeinsamen Konto gibt
  // es keinen, aus dem sich der Posten bedienen koennte.
  const anlageMoeglich = konto !== undefined && konto.inhaber_id !== null;
  // Ein Gewicht allein sagt nichts - es zaehlt im Verhaeltnis zu den
  // anderen Anlageposten desselben Kontos. Deshalb stehen sie im Hinweis.
  const geschwister = daten.posten
    .filter((p) => p.id !== bearbeitet?.id && p.konto_id === kontoId && p.anlage_gewicht)
    .map((p) => `${p.name} ${p.anlage_gewicht}`);

  function anteileBauen(): Anteil[] {
    if (!gemeinschaftlich) return [];
    return daten.personen
      .map((person) => ({
        person_id: person.id,
        gewicht: Number(gewichte[person.id] ?? "0"),
      }))
      .filter((anteil) => Number.isFinite(anteil.gewicht) && anteil.gewicht > 0);
  }

  async function absenden(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (!vollstaendig || laeuft) return;

    const angelegt = anlage && anlageMoeglich;
    const felder = {
      name: name.trim(),
      art,
      // Ein Anlageposten hat keinen eigenen Betrag und keinen Rhythmus: Die
      // Zahl entsteht jeden Monat neu aus dem, was uebrig bleibt.
      betrag: angelegt ? "0" : alsZahlenfeld(betrag),
      intervall_monate: angelegt ? 1 : intervall,
      faelligkeitsmonat: angelegt || intervall === 1 ? 1 : monat,
      abbuchungstag: tag.trim() === "" ? null : Number(tag),
      konto_id: kontoId,
      kategorie_id: kategorieId === "" ? null : kategorieId,
      variabel,
      anteile: anteileBauen(),
      anlage_gewicht: angelegt ? Number(gewicht) : null,
    };

    setLaeuft(true);
    const geklappt = await aktion(() =>
      bearbeitet
        ? aenderePosten(bearbeitet.id, {
            ...felder,
            // Beim Ändern heißt ein leeres Feld sonst "nicht angefasst".
            // Diese beiden sagen: wirklich weg.
            tag_loeschen: felder.abbuchungstag === null,
            kategorie_loeschen: felder.kategorie_id === null,
            anlage_loeschen: !angelegt,
          })
        : legePostenAn(felder),
    );
    setLaeuft(false);

    if (!geklappt) return;
    // Nur bei Erfolg - sonst tippt man nach einem abgelehnten Betrag das
    // ganze Formular neu.
    if (bearbeitet) {
      onAbbrechen();
    } else {
      setName("");
      setBetrag("");
      setTag("");
      setGewicht("");
    }
  }

  return (
    /* Der Kasten traegt nur die Marke, zu der gesprungen wird: Der Abschnitt
       nimmt keine Referenz, und die Ueberschrift selbst muss dafuer auch
       nicht gefunden werden - gemeint ist der Anfang des Formulars. */
    <div ref={anfang}>
      <Abschnitt
        titel={bearbeitet ? `„${bearbeitet.name}" ändern` : "Posten anlegen"}
        id="posten-formular"
        regel
      >
        <Karte>
          <form onSubmit={(e) => void absenden(e)} className={stil.formular}>
            <Feld
              beschriftung="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Kfz-Versicherung"
              autoComplete="off"
              required
            />

            <Auswahl
              beschriftung="Art"
              value={art}
              onChange={(wert) => setArt(wert as Postenart)}
              optionen={[
                ["ausgabe", "Ausgabe"],
                ["einnahme", "Einnahme"],
              ]}
            />

            {anlageMoeglich && (
              <label className={stil.schalter}>
                <input
                  type="checkbox"
                  checked={anlage}
                  onChange={(e) => setAnlage(e.target.checked)}
                />
                <span>
                  Aus dem Überschuss anlegen
                  <span className={stil.unterzeile}>
                    Kein fester Betrag: Was nach allen Kosten übrig bleibt, geht nach
                    Gewichten in die Depots.
                  </span>
                </span>
              </label>
            )}

            {anlage && anlageMoeglich ? (
              <Feld
                beschriftung="Gewichtung"
                hinweis={
                  geschwister.length > 0
                    ? `Anteil am Überschuss. Neben ${geschwister.join(", ")} — die Summe muss nicht 100 ergeben.`
                    : "Anteil am Überschuss. Bei mehreren Posten zählt das Verhältnis, nicht die Summe."
                }
                value={gewicht}
                onChange={(e) => setGewicht(e.target.value)}
                inputMode="numeric"
                placeholder="50"
                required
              />
            ) : (
              <Feld
                beschriftung="Betrag je Abbuchung"
                hinweis="Was die Bank abbucht — nicht die monatliche Rücklage."
                value={betrag}
                onChange={(e) => setBetrag(e.target.value)}
                inputMode="decimal"
                placeholder="549,09"
                required
              />
            )}

            <Auswahl
              beschriftung="Konto"
              value={kontoId}
              onChange={setKontoId}
              optionen={daten.konten.map((k) => [
                k.id,
                k.inhaber_id === null ? `${k.name} (gemeinsam)` : k.name,
              ])}
            />

            <Auswahl
              beschriftung="Kategorie"
              value={kategorieId}
              onChange={setKategorieId}
              optionen={[
                ["", "Ohne Kategorie"],
                ...daten.kategorien.map((k): [string, string] => [k.id, k.name]),
              ]}
            />

            {!(anlage && anlageMoeglich) && (
              <Auswahl
                beschriftung="Rhythmus"
                value={String(intervall)}
                onChange={(wert) => setIntervall(Number(wert))}
                optionen={INTERVALLE.map(([wert, wort]): [string, string] => [
                  String(wert),
                  wort,
                ])}
              />
            )}

            {intervall > 1 && !(anlage && anlageMoeglich) && (
              <Auswahl
                beschriftung="Erstmals fällig im"
                value={String(monat)}
                onChange={(wert) => setMonat(Number(wert))}
                optionen={MONATE.map((wort, i): [string, string] => [
                  String(i + 1),
                  wort,
                ])}
              />
            )}

            <Feld
              beschriftung="Abbuchungstag"
              hinweis="Leer lassen, wenn es nicht darauf ankommt."
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              inputMode="numeric"
              placeholder="1"
            />

            <label className={stil.schalter}>
              <input
                type="checkbox"
                checked={variabel}
                onChange={(e) => setVariabel(e.target.checked)}
              />
              <span>
                Frei verfügbar
                <span className={stil.unterzeile}>
                  Zählt nicht zu den festen Kosten — der Puffer, der übrig bleiben darf.
                </span>
              </span>
            </label>

            {gemeinschaftlich && (
              <fieldset className={stil.anteile}>
                <legend className={stil.anteileTitel}>
                  Aufteilung
                  <span className={stil.unterzeile}>
                    Gewichte, kein Prozent: 1 und 2 heißt ein Drittel zu zwei Dritteln.
                    Null heißt nicht beteiligt.
                  </span>
                </legend>

                {daten.personen.length === 0 ? (
                  <p className={stil.leer}>
                    Es gibt noch keine Person. Ohne sie trägt diesen Posten niemand.
                  </p>
                ) : (
                  <div className={stil.anteilsfelder}>
                    {daten.personen.map((person: Person) => (
                      <Feld
                        key={person.id}
                        beschriftung={person.name}
                        value={gewichte[person.id] ?? ""}
                        onChange={(e) =>
                          setGewichte((alt) => ({ ...alt, [person.id]: e.target.value }))
                        }
                        inputMode="numeric"
                        placeholder="0"
                      />
                    ))}
                  </div>
                )}
              </fieldset>
            )}

            <div className={stil.formularfuss}>
              {gemeinschaftlich && anteileBauen().length === 0 && (
                <Etikett ton="warnung">
                  Ohne Aufteilung zahlt diesen Posten niemand
                </Etikett>
              )}
              {bearbeitet && (
                <Knopf type="button" auspraegung="leise" onClick={onAbbrechen}>
                  Abbrechen
                </Knopf>
              )}
              <Knopf
                type="submit"
                auspraegung="primaer"
                disabled={!vollstaendig || laeuft}
              >
                {laeuft
                  ? "Wird gespeichert …"
                  : bearbeitet
                    ? "Änderungen speichern"
                    : "Anlegen"}
              </Knopf>
            </div>
          </form>
        </Karte>
      </Abschnitt>
    </div>
  );
}

/**
 * Ein Auswahlfeld mit verbundener Beschriftung.
 *
 * Liegt hier und nicht in src/ui: solange genau ein Artefakt es braucht,
 * wäre ein gemeinsamer Baustein eine Behauptung über alle anderen.
 */
export function Auswahl({
  beschriftung,
  value,
  onChange,
  optionen,
}: {
  beschriftung: string;
  value: string;
  onChange: (wert: string) => void;
  optionen: readonly (readonly [string, string])[];
}) {
  return (
    <label className={stil.wahl}>
      <span className={stil.wahlName}>{beschriftung}</span>
      <select
        className={stil.auswahl}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {optionen.map(([wert, wort]) => (
          <option key={wert} value={wert}>
            {wort}
          </option>
        ))}
      </select>
    </label>
  );
}
