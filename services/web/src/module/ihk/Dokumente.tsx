import { useState } from "react";

import { Karte, Knopf, Leerzustand } from "../../ui";
import * as api from "./api";
import stil from "./IhkSeite.module.css";
import { meldung } from "./zeit";
import { PdfAnsicht } from "./PdfAnsicht";

const ART_WORT: Record<api.DokumentArt, string> = {
  projekt: "Projektdokumentation",
  kunde: "Kundendokumentation",
};

/**
 * Die Dokumentation des Prüflings neben dem Raster.
 *
 * Im ExamManager lagen die PDFs nur auf dem Tablet. Hier liegen sie beim
 * Artefakt und sind damit von jedem Gerät aus da, an dem man angemeldet ist.
 */
export function Dokumente({
  pruefling: p,
  onGeaendert,
  onFehler,
}: {
  pruefling: api.Pruefling;
  onGeaendert: () => Promise<void>;
  onFehler: (nachricht: string) => void;
}) {
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const aktiv = p.dokumente.find((d) => d.id === gewaehlt) ?? p.dokumente[0] ?? null;

  async function hochladen(dateien: FileList | null, art: api.DokumentArt) {
    if (!dateien?.length) return;
    setLaeuft(true);
    onFehler("");
    try {
      let letztes: api.Dokument | null = null;
      for (const datei of Array.from(dateien)) {
        letztes = await api.ladeDokumentHoch(p.id, art, datei);
      }
      await onGeaendert();
      if (letztes) setGewaehlt(letztes.id);
    } catch (e) {
      onFehler(meldung(e));
    } finally {
      setLaeuft(false);
    }
  }

  async function entfernen(dokument: api.Dokument) {
    if (!window.confirm(`${dokument.dateiname} entfernen?`)) return;
    onFehler("");
    try {
      await api.entferneDokument(p.id, dokument.id);
      setGewaehlt(null);
      await onGeaendert();
    } catch (e) {
      onFehler(meldung(e));
    }
  }

  const hochladeKnoepfe = (
    <div className={stil.knopfreihe}>
      {(Object.keys(ART_WORT) as api.DokumentArt[]).map((art) => (
        <label key={art} className={stil.dateiknopf}>
          {`${ART_WORT[art]} hochladen`}
          <input
            type="file"
            accept="application/pdf"
            multiple
            className="nur-vorlesen"
            disabled={laeuft}
            onChange={(e) => {
              void hochladen(e.target.files, art);
              e.target.value = "";
            }}
          />
        </label>
      ))}
    </div>
  );

  if (!aktiv) {
    return (
      <Leerzustand titel="Noch keine Dokumentation" aktion={hochladeKnoepfe}>
        Lade die Projektdokumentation als PDF hoch - sie steht dann neben dem
        Bewertungsraster.
      </Leerzustand>
    );
  }

  return (
    <Karte>
      <div className={stil.dokumentkopf}>
        <label className={stil.auswahlgruppe}>
          <span className={stil.beschriftung}>Dokument</span>
          <select
            className={stil.auswahl}
            value={aktiv.id}
            onChange={(e) => setGewaehlt(e.target.value)}
          >
            {p.dokumente.map((d) => (
              <option key={d.id} value={d.id}>
                {ART_WORT[d.art]}: {d.dateiname}
              </option>
            ))}
          </select>
        </label>
        <Knopf groesse="sm" auspraegung="leise" onClick={() => void entfernen(aktiv)}>
          Entfernen
        </Knopf>
      </div>
      <PdfAnsicht key={aktiv.id} pruefling={p} dokument={aktiv} />
      {hochladeKnoepfe}
    </Karte>
  );
}
