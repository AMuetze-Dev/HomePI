import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { meldung } from "../../api/client";
import {
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Platzhalter,
  Tafel,
} from "../../ui";
import {
  aendereFrage,
  bildAdresse,
  entferneBild,
  ladeBildHoch,
  ladeKatalog,
  ladeKataloge,
  legeFrageAn,
  legeKatalogAn,
  loescheFrage,
  loescheKatalog,
  sortiereFragen,
  type Frage,
  type FrageEingabe,
  type Katalog,
  type KatalogDetail,
} from "./api";
import { FrageFormular } from "./FrageFormular";
import { LEERE_FRAGE } from "./vorlage";
import { loesungstext, TYPWORT } from "./texte";
import stil from "./Quiz.module.css";

/** Fragenkataloge - Liste oder ein Katalog, je nach `?katalog=`. */
export function KatalogTafel({
  darfLeiten,
  darfVerwalten,
}: {
  darfLeiten: boolean;
  darfVerwalten: boolean;
}) {
  const [suche, setSuche] = useSearchParams();
  const id = suche.get("katalog");
  if (id) {
    return (
      <KatalogBearbeiten
        id={id}
        darfLeiten={darfLeiten}
        darfVerwalten={darfVerwalten}
        zurueck={() => setSuche({})}
      />
    );
  }
  return (
    <KatalogListe darfLeiten={darfLeiten} oeffnen={(neu) => setSuche({ katalog: neu })} />
  );
}

type Liste =
  | { phase: "laedt" }
  | { phase: "fertig"; kataloge: Katalog[] }
  | { phase: "fehler"; nachricht: string };

function KatalogListe({
  darfLeiten,
  oeffnen,
}: {
  darfLeiten: boolean;
  oeffnen: (id: string) => void;
}) {
  const [liste, setListe] = useState<Liste>({ phase: "laedt" });
  const [titel, setTitel] = useState("");
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    ladeKataloge(controller.signal)
      .then((kataloge) => setListe({ phase: "fertig", kataloge }))
      .catch((grund: unknown) => {
        if (!controller.signal.aborted)
          setListe({ phase: "fehler", nachricht: meldung(grund) });
      });
    return () => controller.abort();
  }, []);

  async function anlegen(ereignis: FormEvent) {
    ereignis.preventDefault();
    setFehler("");
    try {
      oeffnen((await legeKatalogAn(titel)).id);
    } catch (grund) {
      setFehler(meldung(grund));
    }
  }

  if (liste.phase === "laedt") {
    return (
      <Tafel titel="Fragenkataloge">
        <div className={stil.laden} role="status" aria-label="Kataloge werden geladen">
          <Platzhalter hoehe="3rem" />
          <Platzhalter hoehe="8rem" />
        </div>
      </Tafel>
    );
  }
  if (liste.phase === "fehler") {
    return (
      <Tafel titel="Fragenkataloge">
        <Hinweis ton="fehler" dringend>
          {liste.nachricht}
        </Hinweis>
      </Tafel>
    );
  }

  return (
    <Tafel titel="Fragenkataloge" beiwort={`${liste.kataloge.length} Kataloge`}>
      {darfLeiten && (
        <Karte>
          <form className={stil.eroeffnen} onSubmit={(e) => void anlegen(e)}>
            <Feld
              beschriftung="Neuer Katalog"
              value={titel}
              maxLength={120}
              onChange={(e) => setTitel(e.target.value)}
            />
            <Knopf type="submit" disabled={titel.trim() === ""}>
              Anlegen
            </Knopf>
          </form>
          {fehler && (
            <Hinweis ton="fehler" dringend>
              {fehler}
            </Hinweis>
          )}
        </Karte>
      )}
      {liste.kataloge.length === 0 ? (
        <Leerzustand titel="Noch kein Fragenkatalog">
          Ein Katalog sammelt die Fragen eines Abends. Leg oben einen an - danach
          schreibst du die Fragen und eröffnest unter „Runden“ ein Spiel damit.
        </Leerzustand>
      ) : (
        <ul className={stil.liste}>
          {liste.kataloge.map((k) => (
            <li key={k.id} className={stil.listenzeile}>
              <button
                type="button"
                className={stil.zeilenknopf}
                onClick={() => oeffnen(k.id)}
              >
                <span className={stil.zeilentext}>{k.titel}</span>
                <span className={stil.nebensache}>{k.anzahl_fragen} Fragen</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Tafel>
  );
}

type Detail =
  | { phase: "laedt" }
  | { phase: "fertig"; katalog: KatalogDetail }
  | { phase: "fehler"; nachricht: string };

function KatalogBearbeiten({
  id,
  darfLeiten,
  darfVerwalten,
  zurueck,
}: {
  id: string;
  darfLeiten: boolean;
  darfVerwalten: boolean;
  zurueck: () => void;
}) {
  const [detail, setDetail] = useState<Detail>({ phase: "laedt" });
  const [fehler, setFehler] = useState("");
  // "neu" oder die Kennung der Frage, die gerade offen ist.
  const [offen, setOffen] = useState<string | null>(null);
  // Haengt an jeder Bildadresse: Ein ersetztes Bild hat dieselbe Adresse,
  // und ohne neuen Zusatz zeigte der Browser das alte weiter.
  const [version, setVersion] = useState(0);

  const laden = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setDetail({ phase: "fertig", katalog: await ladeKatalog(id, signal) });
        setVersion((v) => v + 1);
      } catch (grund) {
        if (!signal?.aborted) setDetail({ phase: "fehler", nachricht: meldung(grund) });
      }
    },
    [id],
  );

  useEffect(() => {
    const controller = new AbortController();
    void laden(controller.signal);
    return () => controller.abort();
  }, [laden]);

  async function handeln(aktion: () => Promise<unknown>): Promise<boolean> {
    setFehler("");
    try {
      await aktion();
      await laden();
      return true;
    } catch (grund) {
      setFehler(meldung(grund));
      return false;
    }
  }

  if (detail.phase === "laedt") {
    return (
      <Tafel titel="Fragenkatalog">
        <div className={stil.laden} role="status" aria-label="Katalog wird geladen">
          <Platzhalter hoehe="10rem" />
        </div>
      </Tafel>
    );
  }
  if (detail.phase === "fehler") {
    return (
      <Tafel titel="Fragenkatalog">
        <Hinweis ton="fehler" dringend>
          {detail.nachricht}
        </Hinweis>
        <div>
          <Knopf auspraegung="sekundaer" onClick={zurueck}>
            Alle Kataloge
          </Knopf>
        </div>
      </Tafel>
    );
  }

  const { katalog } = detail;
  const reihen = katalog.fragen.map((f) => f.id);

  function verschieben(index: number, richtung: -1 | 1) {
    const neu = [...reihen];
    const ziel = index + richtung;
    [neu[index], neu[ziel]] = [neu[ziel]!, neu[index]!];
    void handeln(() => sortiereFragen(id, neu));
  }

  return (
    <Tafel
      titel={katalog.titel}
      beiwort={`${katalog.fragen.length} Fragen`}
      aktionen={
        <Knopf auspraegung="leise" groesse="sm" onClick={zurueck}>
          Alle Kataloge
        </Knopf>
      }
    >
      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {katalog.fragen.length === 0 && offen !== "neu" && (
        <Leerzustand titel="Noch keine Fragen">
          Acht Fragetypen stehen bereit: von Freitext über Schätzfrage und Buzzer bis zum
          Bild, auf das man tippt.
        </Leerzustand>
      )}

      <ol className={stil.liste}>
        {katalog.fragen.map((frage, index) => (
          <li key={frage.id} className={stil.fragezeile}>
            {offen === frage.id ? (
              <Karte>
                <FrageFormular
                  anfang={frage}
                  bildAdresse={
                    frage.hat_bild ? bildAdresse(frage.id, String(version)) : null
                  }
                  knopf="Speichern"
                  abbrechen={() => setOffen(null)}
                  speichern={async (eingabe: FrageEingabe) => {
                    const ok = await handeln(() => aendereFrage(frage.id, eingabe));
                    if (ok) setOffen(null);
                    return ok;
                  }}
                />
                <BildVerwaltung frage={frage} stand={String(version)} handeln={handeln} />
              </Karte>
            ) : (
              <div className={stil.listenzeile}>
                <span className={stil.sortiernummer}>{index + 1}</span>
                <span className={stil.zeilentext}>
                  {frage.text}
                  <span className={stil.nebensache}>
                    {" "}
                    · {TYPWORT[frage.daten.typ]} · {loesungstext(frage)}
                  </span>
                </span>
                {frage.hat_bild && <Etikett>Bild</Etikett>}
                {darfLeiten && (
                  <span className={stil.sortierknoepfe}>
                    <Knopf
                      auspraegung="leise"
                      groesse="sm"
                      disabled={index === 0}
                      onClick={() => verschieben(index, -1)}
                      aria-label={`Frage ${index + 1} nach oben`}
                    >
                      ↑
                    </Knopf>
                    <Knopf
                      auspraegung="leise"
                      groesse="sm"
                      disabled={index === reihen.length - 1}
                      onClick={() => verschieben(index, 1)}
                      aria-label={`Frage ${index + 1} nach unten`}
                    >
                      ↓
                    </Knopf>
                    <Knopf
                      auspraegung="leise"
                      groesse="sm"
                      onClick={() => setOffen(frage.id)}
                      aria-label={`Frage ${index + 1} bearbeiten`}
                    >
                      Bearbeiten
                    </Knopf>
                    <Knopf
                      auspraegung="leise"
                      groesse="sm"
                      onClick={() => {
                        if (window.confirm("Diese Frage löschen?"))
                          void handeln(() => loescheFrage(frage.id));
                      }}
                      aria-label={`Frage ${index + 1} löschen`}
                    >
                      ×
                    </Knopf>
                  </span>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>

      {darfLeiten &&
        (offen === "neu" ? (
          <Karte>
            <FrageFormular
              anfang={LEERE_FRAGE}
              knopf="Frage anlegen"
              abbrechen={() => setOffen(null)}
              speichern={async (eingabe) => {
                const ok = await handeln(() => legeFrageAn(id, eingabe));
                if (ok) setOffen(null);
                return ok;
              }}
            />
          </Karte>
        ) : (
          <div className={stil.knopfzeile}>
            <Knopf onClick={() => setOffen("neu")}>Frage hinzufügen</Knopf>
            {darfVerwalten && (
              <Knopf
                auspraegung="leise"
                onClick={() => {
                  if (
                    window.confirm(
                      `„${katalog.titel}“ samt Fragen und beendeter Runden löschen?`,
                    )
                  )
                    void handeln(async () => {
                      await loescheKatalog(id);
                      zurueck();
                    });
                }}
              >
                Katalog löschen
              </Knopf>
            )}
          </div>
        ))}
    </Tafel>
  );
}

function BildVerwaltung({
  frage,
  stand,
  handeln,
}: {
  frage: Frage;
  stand: string;
  handeln: (aktion: () => Promise<unknown>) => Promise<boolean>;
}) {
  return (
    <div className={stil.bildverwaltung}>
      {frage.hat_bild && (
        <img
          src={bildAdresse(frage.id, stand)}
          alt="Bild der Frage"
          className={stil.vorschau}
        />
      )}
      <label className={stil.auswahl}>
        <span>
          {frage.hat_bild ? "Bild ersetzen" : "Bild hochladen"} (PNG, JPEG, WebP, GIF,
          höchstens 3 MB)
        </span>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={(e) => {
            const datei = e.target.files?.[0];
            if (datei) void handeln(() => ladeBildHoch(frage.id, datei));
          }}
        />
      </label>
      {frage.hat_bild && (
        <div>
          <Knopf
            auspraegung="leise"
            groesse="sm"
            onClick={() => void handeln(() => entferneBild(frage.id))}
          >
            Bild entfernen
          </Knopf>
        </div>
      )}
    </div>
  );
}
