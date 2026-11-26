import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  Etikett,
  Feld,
  Hinweis,
  Karte,
  KnopfVerweis,
  Knopf,
  Schalter,
  Segmentwahl,
  Tafel,
} from "../../ui";
import * as api from "./api";
import { DokuFormular, PraesiFormular } from "./Bewertung";
import { Dokumente } from "./Dokumente";
import { GesamtFormular } from "./Gesamt";
import { Lade } from "./IhkSeite";
import stil from "./IhkSeite.module.css";
import { datum, meldung, note, punkte } from "./zeit";

type Reiter = "doku" | "praesi" | "gesamt";

const REITER = [
  // Kurz, weil alle drei bei 375 px nebeneinander passen müssen.
  { wert: "doku", wort: "Dokumentation" },
  { wert: "praesi", wort: "Präsentation" },
  { wert: "gesamt", wort: "Gesamt" },
] as const;

/**
 * Neben dem Raster ist Platz für das Dokument erst ab Tabletbreite. Auf dem
 * Telefon stünde es davor und schöbe das Raster um eine Bildschirmhöhe nach
 * unten - dort beginnt es ausgeblendet und lässt sich zuschalten.
 */
function dokumentAnfangsSichtbar(): boolean {
  return (
    typeof window.matchMedia !== "function" ||
    window.matchMedia("(width >= 48rem)").matches
  );
}

const STATUS: { schluessel: keyof api.Status; wort: string }[] = [
  { schluessel: "runtergeladen", wort: "Doku runtergeladen" },
  { schluessel: "kontrolliert", wort: "Kontrolliert" },
  { schluessel: "abgestimmt", wort: "Abgestimmt" },
  { schluessel: "hochgeladen", wort: "Hochgeladen" },
];

/** Was eine Ansicht braucht, um etwas am Prüfling zu ändern. */
export type Aendern = (aktion: () => Promise<api.Pruefling>) => Promise<boolean>;

export function PrueflingTafel({ prueflingId }: { prueflingId: string }) {
  const [katalog, setKatalog] = useState<api.Katalog | null>(null);
  const [pruefling, setPruefling] = useState<api.Pruefling | null>(null);
  const [ladefehler, setLadefehler] = useState("");
  // Getrennt vom Ladefehler: eine abgelehnte Punktzahl darf das Raster nicht
  // gegen eine Fehlerseite austauschen.
  const [fehler, setFehler] = useState("");
  const [reiter, setReiter] = useState<Reiter>("doku");
  const [mitDokument, setMitDokument] = useState(dokumentAnfangsSichtbar);

  const laden = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const [k, p] = await Promise.all([
          api.ladeKatalog(signal),
          api.ladePruefling(prueflingId, signal),
        ]);
        setKatalog(k);
        setPruefling(p);
      } catch (e) {
        if (signal?.aborted) return;
        setLadefehler(meldung(e));
      }
    },
    [prueflingId],
  );

  useEffect(() => {
    const steuerung = new AbortController();
    void laden(steuerung.signal);
    return () => steuerung.abort();
  }, [laden]);

  const aendern: Aendern = useCallback(async (aktion) => {
    setFehler("");
    try {
      setPruefling(await aktion());
      return true;
    } catch (e) {
      setFehler(meldung(e));
      return false;
    }
  }, []);

  if (ladefehler) {
    return (
      <Tafel titel="Prüfling">
        <Link to="?" className={stil.zurueck}>
          ← Alle Prüfungstage
        </Link>
        <Hinweis ton="fehler" dringend>
          {ladefehler}
        </Hinweis>
      </Tafel>
    );
  }
  if (!katalog || !pruefling) return <Lade titel="Prüfling" />;

  const p = pruefling;
  const { doku, praesentation } = p.auswertung;

  return (
    <Tafel
      titel={p.name}
      beiwort={
        <>
          Doku {punkte(doku.gesamt)} P · Note {note(doku.note)} · Präsentation{" "}
          {punkte(praesentation.gesamt)} P · Note {note(praesentation.note)}
        </>
      }
      aktionen={
        <>
          <Knopf
            groesse="sm"
            auspraegung="leise"
            onClick={() => setMitDokument((an) => !an)}
          >
            {mitDokument ? "Dokument ausblenden" : "Dokument zeigen"}
          </Knopf>
          <KnopfVerweis groesse="sm" href={api.korrekturbogenAdresse(p.id)} download>
            Korrekturbogen (PDF)
          </KnopfVerweis>
        </>
      }
    >
      <Link to={`?tag=${encodeURIComponent(p.tag.id)}`} className={stil.zurueck}>
        ← Prüfungstag {datum(p.tag.datum)}
      </Link>

      <div className={mitDokument ? stil.arbeitsflaeche : undefined}>
        {mitDokument && (
          <div className={stil.dokumentspalte}>
            <Dokumente pruefling={p} onGeaendert={() => laden()} onFehler={setFehler} />
          </div>
        )}

        <div className={stil.stapel}>
          {/* In der Spalte des Rasters, nicht darüber: Klebend über die
              ganze Breite deckte sie sonst das Dokument zu. */}
          {fehler && (
            <div className={stil.klebend}>
              <Hinweis ton="fehler" dringend>
                {fehler}
              </Hinweis>
            </div>
          )}
          <Stammdaten pruefling={p} aendern={aendern} katalog={katalog} />

          <Segmentwahl
            beschriftung="Bewertungsteil"
            optionen={REITER}
            wert={reiter}
            beiWahl={setReiter}
          />

          {reiter === "doku" && (
            <DokuFormular katalog={katalog} pruefling={p} aendern={aendern} />
          )}
          {reiter === "praesi" && (
            <PraesiFormular katalog={katalog} pruefling={p} aendern={aendern} />
          )}
          {reiter === "gesamt" && (
            <GesamtFormular katalog={katalog} pruefling={p} aendern={aendern} />
          )}
        </div>
      </div>
    </Tafel>
  );
}

function Stammdaten({
  pruefling: p,
  aendern,
  katalog,
}: {
  pruefling: api.Pruefling;
  aendern: Aendern;
  katalog: api.Katalog;
}) {
  const [name, setName] = useState(p.name);
  const [ident, setIdent] = useState(p.ident);

  useEffect(() => setName(p.name), [p.name]);
  useEffect(() => setIdent(p.ident), [p.ident]);

  return (
    <Karte>
      <div className={stil.stammdaten}>
        <Feld
          beschriftung="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => {
            if (name.trim() && name.trim() !== p.name) {
              void aendern(() => api.aenderePruefling(p.id, { name: name.trim() }));
            }
          }}
        />
        <Feld
          beschriftung="Prüflingsident"
          value={ident}
          onChange={(e) => setIdent(e.target.value)}
          onBlur={() => {
            if (ident.trim() !== p.ident) {
              void aendern(() => api.aenderePruefling(p.id, { ident: ident.trim() }));
            }
          }}
        />
        <label className={stil.auswahlgruppe}>
          <span className={stil.beschriftung}>Korrekturart</span>
          <select
            className={stil.auswahl}
            value={p.korrekturart}
            onChange={(e) =>
              void aendern(() =>
                api.aenderePruefling(p.id, {
                  korrekturart: e.target.value as api.Korrekturart,
                }),
              )
            }
          >
            {katalog.korrekturarten.map((art) => (
              <option key={art}>{art}</option>
            ))}
          </select>
        </label>
      </div>
      <ul className={stil.schalterliste}>
        {STATUS.map(({ schluessel, wort }) => (
          <li key={schluessel} className={stil.schalterzeile}>
            <span>{wort}</span>
            <Schalter
              beschriftung={wort === "Doku runtergeladen" ? "Doku runtergeladen" : wort}
              an={p.status[schluessel]}
              beiWechsel={(an) =>
                void aendern(() =>
                  api.aenderePruefling(p.id, { status: { [schluessel]: an } }),
                )
              }
            />
          </li>
        ))}
      </ul>
      {p.auswertung.doku.grenzfall && (
        <Etikett ton="warnung">Dokumentation: Grenzfall</Etikett>
      )}
    </Karte>
  );
}
