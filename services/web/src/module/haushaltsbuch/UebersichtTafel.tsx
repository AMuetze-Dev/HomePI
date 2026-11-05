import { Etikett, Hinweis, Karte, Knopf, Leerzustand } from "../../ui";
import type { PersonBilanz, PostenZeile, Uebersicht } from "./api";
import { alsEuro, alsProzent, alsZahl, monatswort, rhythmus } from "./geld";
import type { Daten, Zeitraum } from "./daten";
import stil from "./HaushaltsbuchSeite.module.css";

interface Props {
  daten: Daten;
  zeitraum: Zeitraum;
  onZeitraum: (schritte: number) => void;
  onHeute: () => void;
}

export function UebersichtTafel({ daten, zeitraum, onZeitraum, onHeute }: Props) {
  const { uebersicht } = daten;

  if (daten.posten.length === 0) {
    return (
      <Leerzustand titel="Noch kein Posten erfasst">
        Lege zuerst unter <strong>Stammdaten</strong> die Personen und Konten an — und
        dort mit einem Griff die üblichen Kategorien. Danach trägst du unter{" "}
        <strong>Posten</strong> ein, was jeden Monat kommt und geht. Diese Seite rechnet
        aus, wer wie viel einzahlt.
      </Leerzustand>
    );
  }

  return (
    <>
      <Monatswaehler zeitraum={zeitraum} onZeitraum={onZeitraum} onHeute={onHeute} />

      {uebersicht.gemeinschaft.ohne_aufteilung.length > 0 && (
        <Hinweis ton="warnung">
          Diese gemeinsamen Posten hat niemand übernommen und sie fehlen deshalb in jeder
          Einzahlung: {uebersicht.gemeinschaft.ohne_aufteilung.join(", ")}. Trage unter
          Posten eine Aufteilung ein.
        </Hinweis>
      )}

      <div className={stil.bilanzen}>
        {uebersicht.personen.map((person) => (
          <Bilanzkarte key={person.person_id} person={person} />
        ))}
        <Gemeinschaftskarte uebersicht={uebersicht} />
      </div>

      <Zeilenblock
        titel={`Im ${monatswort(uebersicht.monat)} bucht die Bank ab`}
        leer="In diesem Monat bucht nichts ab."
        zeilen={uebersicht.faellig}
        spalte="Betrag"
        wert={(z) => z.betrag}
      />

      <Zeilenblock
        titel="Rücklagen"
        leer="Alles kommt monatlich — es muss nichts zurückgelegt werden."
        zeilen={uebersicht.ruecklagen}
        spalte="zurückgelegt"
        wert={(z) => z.ruecklagenstand}
        fuss={`zusammen ${alsEuro(uebersicht.ruecklagen_summe)}`}
      />
    </>
  );
}

function Monatswaehler({ zeitraum, onZeitraum, onHeute }: Omit<Props, "daten">) {
  return (
    <div className={stil.monatswaehler}>
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={() => onZeitraum(-1)}
        aria-label="Einen Monat zurück"
      >
        ←
      </Knopf>
      <h2 className={stil.monat}>
        {monatswort(zeitraum.monat)} {zeitraum.jahr}
      </h2>
      <Knopf
        groesse="sm"
        auspraegung="leise"
        onClick={() => onZeitraum(1)}
        aria-label="Einen Monat vor"
      >
        →
      </Knopf>
      <Knopf groesse="sm" auspraegung="leise" onClick={onHeute}>
        Heute
      </Knopf>
    </div>
  );
}

function Bilanzkarte({ person }: { person: PersonBilanz }) {
  const einkommen = alsZahl(person.einnahmen) + alsZahl(person.gutschrift_gemeinschaft);
  const knapp = alsZahl(person.rest) < 0;

  return (
    <Karte className={stil.bilanz}>
      <div className={stil.bilanzkopf}>
        <h3 className={stil.bilanzname}>{person.name}</h3>
        <Etikett ton={knapp ? "fehler" : "neutral"}>
          {knapp ? "Unterdeckung" : `${alsProzent(person.sparquote)} gespart`}
        </Etikett>
      </div>

      <Balken person={person} einkommen={einkommen} />

      <dl className={stil.zahlen}>
        <Zahl name="Einkommen" wert={alsEuro(String(einkommen))} />
        <Zahl name="Feste Kosten" wert={alsEuro(person.feste_kosten)} />
        <Zahl
          name="davon in die Gemeinschaft"
          wert={alsEuro(person.einzahlung_gemeinschaft)}
          leise
        />
        <Zahl name="Sparen und Anlage" wert={alsEuro(person.sparen)} />
        <Zahl name="Frei verfügbar" wert={alsEuro(person.variabel)} />
        <Zahl
          name="Bleibt übrig"
          wert={alsEuro(person.rest)}
          ton={knapp ? "fehler" : "gut"}
        />
        <Zahl
          name="Sparen wäre möglich bis"
          wert={`${alsEuro(person.moeglich)} (${alsProzent(person.moegliche_sparquote)})`}
          leise
        />
      </dl>

      {person.nach_kategorie.length > 0 && (
        <ul
          className={stil.kategorien}
          aria-label={`Ausgaben von ${person.name} nach Kategorie`}
        >
          {person.nach_kategorie.map((eintrag) => (
            <li key={eintrag.kategorie} className={stil.kategorie}>
              <span>{eintrag.kategorie}</span>
              <span className={stil.kategoriebetrag}>{alsEuro(eintrag.betrag)}</span>
            </li>
          ))}
        </ul>
      )}
    </Karte>
  );
}

/**
 * Ein Band statt dreier Zahlen.
 *
 * Wer monatlich auf seine Fixkosten schaut, will nicht rechnen, sondern
 * sehen, wie viel vom Balken noch ihm gehört.
 */
function Balken({ person, einkommen }: { person: PersonBilanz; einkommen: number }) {
  const teile = [
    { name: "Feste Kosten", wert: alsZahl(person.feste_kosten), klasse: stil.teilFest },
    { name: "Sparen", wert: alsZahl(person.sparen), klasse: stil.teilSparen },
    { name: "Frei verfügbar", wert: alsZahl(person.variabel), klasse: stil.teilVariabel },
    { name: "Übrig", wert: Math.max(0, alsZahl(person.rest)), klasse: stil.teilRest },
  ].filter((teil) => teil.wert > 0);

  const gesamt = teile.reduce((summe, teil) => summe + teil.wert, 0) || 1;
  const beschreibung = teile
    .map((teil) => `${teil.name} ${alsEuro(String(teil.wert))}`)
    .join(", ");

  if (einkommen <= 0) return null;

  return (
    <div
      className={stil.balken}
      role="img"
      aria-label={`${person.name}: ${beschreibung}`}
    >
      {teile.map((teil) => (
        <span
          key={teil.name}
          className={`${stil.teil} ${teil.klasse}`}
          style={{ flexGrow: teil.wert / gesamt }}
        />
      ))}
    </div>
  );
}

function Zahl({
  name,
  wert,
  leise = false,
  ton,
}: {
  name: string;
  wert: string;
  leise?: boolean;
  ton?: "gut" | "fehler";
}) {
  return (
    <div className={`${stil.zahl} ${leise ? stil.zahlLeise : ""}`}>
      <dt>{name}</dt>
      <dd className={ton ? stil[ton] : ""}>{wert}</dd>
    </div>
  );
}

function Gemeinschaftskarte({ uebersicht }: { uebersicht: Uebersicht }) {
  const { gemeinschaft } = uebersicht;

  return (
    <Karte className={stil.bilanz}>
      <div className={stil.bilanzkopf}>
        <h3 className={stil.bilanzname}>Gemeinsam</h3>
        <Etikett ton="neutral">{alsEuro(gemeinschaft.bedarf)} im Monat</Etikett>
      </div>

      <dl className={stil.zahlen}>
        <Zahl name="Gemeinsame Ausgaben" wert={alsEuro(gemeinschaft.ausgaben)} />
        <Zahl name="Gemeinsame Einnahmen" wert={alsEuro(gemeinschaft.einnahmen)} />
        <Zahl name="Muss eingezahlt werden" wert={alsEuro(gemeinschaft.bedarf)} />
      </dl>

      <ul className={stil.kategorien} aria-label="Einzahlungen in die Gemeinschaft">
        {uebersicht.personen.map((person) => (
          <li key={person.person_id} className={stil.kategorie}>
            <span>{person.name} zahlt ein</span>
            <span className={stil.kategoriebetrag}>
              {alsEuro(person.einzahlung_gemeinschaft)}
            </span>
          </li>
        ))}
      </ul>
    </Karte>
  );
}

function Zeilenblock({
  titel,
  leer,
  zeilen,
  spalte,
  wert,
  fuss,
}: {
  titel: string;
  leer: string;
  zeilen: PostenZeile[];
  spalte: string;
  wert: (zeile: PostenZeile) => string;
  fuss?: string;
}) {
  return (
    <section aria-labelledby={`block-${spalte}`} className={stil.block}>
      <h2 id={`block-${spalte}`} className={stil.abschnittstitel}>
        {titel}
      </h2>

      {zeilen.length === 0 ? (
        <Karte>
          <p className={stil.leer}>{leer}</p>
        </Karte>
      ) : (
        <Karte blank>
          <div className={stil.rollbereich}>
            <table className={stil.tabelle}>
              <caption className="nur-vorlesen">{titel}</caption>
              <thead>
                <tr>
                  <th scope="col">Posten</th>
                  <th scope="col">Konto</th>
                  <th scope="col">Rhythmus</th>
                  <th scope="col" className={stil.rechts}>
                    monatlich
                  </th>
                  <th scope="col" className={stil.rechts}>
                    {spalte}
                  </th>
                </tr>
              </thead>
              <tbody>
                {zeilen.map((zeile) => (
                  <tr key={zeile.id}>
                    <td>
                      {zeile.name}
                      <span className={stil.unterzeile}>{zeile.kategorie}</span>
                    </td>
                    <td>{zeile.konto}</td>
                    <td>{rhythmus(zeile.intervall_monate, zeile.faellige_monate)}</td>
                    <td className={stil.rechts}>{alsEuro(zeile.monatsrate)}</td>
                    <td className={`${stil.rechts} ${stil.betont}`}>
                      {alsEuro(wert(zeile))}
                    </td>
                  </tr>
                ))}
              </tbody>
              {fuss && (
                <tfoot>
                  <tr>
                    <td colSpan={4}></td>
                    <td className={`${stil.rechts} ${stil.betont}`}>{fuss}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </Karte>
      )}
    </section>
  );
}
