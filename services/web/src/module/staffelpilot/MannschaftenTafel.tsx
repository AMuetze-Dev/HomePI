import { useCallback, useEffect, useState } from "react";

import { Etikett, Hinweis, Karte, Leerzustand, Platzhalter } from "../../ui";
import {
  type Mannschaft,
  type Staffel,
  ladeMannschaften,
  speichereMannschaften,
} from "./api";
import stil from "./StaffelpilotSeite.module.css";

function meldung(fehler: unknown): string {
  return fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
}

/**
 * Welche Mannschaft eines Vereins über welcher steht.
 *
 * DFBnet liefert das nicht mit — es wird aus dem Namenszusatz geraten. Ein
 * falscher Schluss fällt nicht laut auf: er ändert still, wessen Einsätze als
 * Stammspieler zählen, und damit prüft eine Regel leise das Falsche. Deshalb
 * steht hier ausdrücklich „geraten" oder „bestätigt", und deshalb lässt sich
 * jede Zuordnung von Hand setzen.
 */
export function MannschaftenTafel({ staffeln }: { staffeln: Staffel[] }) {
  const [staffelId, setStaffelId] = useState(staffeln[0]?.id ?? "");
  const [mannschaften, setMannschaften] = useState<Mannschaft[] | null>(null);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async (id: string, signal?: AbortSignal) => {
    if (!id) {
      setMannschaften([]);
      return;
    }
    try {
      setMannschaften(await ladeMannschaften(id, signal));
    } catch (f) {
      if (signal?.aborted) return;
      setFehler(meldung(f));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void laden(staffelId, controller.signal);
    return () => controller.abort();
  }, [laden, staffelId]);

  async function setzen(geaendert: Mannschaft[]) {
    setFehler("");
    try {
      setMannschaften(
        await speichereMannschaften(
          staffelId,
          geaendert.map((m) => ({ name: m.name, ist_sg: m.ist_sg, hoehere: m.hoehere })),
        ),
      );
    } catch (f) {
      setFehler(meldung(f));
    }
  }

  if (staffeln.length === 0) {
    return (
      <Leerzustand titel="Noch keine Staffel angelegt">
        Mannschaften gehören zu einer Staffel. Leg zuerst eine an.
      </Leerzustand>
    );
  }

  return (
    <>
      {staffeln.length > 1 && (
        <Karte>
          <label className={stil.wahl}>
            <span className={stil.wahlName}>Staffel</span>
            <select
              className={stil.auswahl}
              value={staffelId}
              onChange={(e) => setStaffelId(e.target.value)}
            >
              {staffeln.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </Karte>
      )}

      {fehler && (
        <Hinweis ton="fehler" dringend>
          {fehler}
        </Hinweis>
      )}

      {mannschaften === null ? (
        <div role="status" aria-label="Mannschaften werden geladen">
          <Platzhalter breite="100%" hoehe="10rem" />
        </div>
      ) : mannschaften.length === 0 ? (
        <Leerzustand titel="Keine Mannschaften gemeldet">
          Die Meldung kommt über{" "}
          <code>PUT /staffelpilot/staffeln/&lt;id&gt;/mannschaften</code> herein — aus
          DFBnet über den Prüfdienst.
        </Leerzustand>
      ) : (
        <ul className={stil.liste} aria-label="Mannschaften">
          {mannschaften.map((m) => (
            <li key={m.id}>
              <MannschaftKarte
                mannschaft={m}
                alle={mannschaften}
                onSetzen={(hoehere) =>
                  void setzen(
                    mannschaften.map((x) => (x.id === m.id ? { ...x, hoehere } : x)),
                  )
                }
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function MannschaftKarte({
  mannschaft,
  alle,
  onSetzen,
}: {
  mannschaft: Mannschaft;
  alle: Mannschaft[];
  onSetzen: (hoehere: string[]) => void;
}) {
  const [offen, setOffen] = useState(false);
  const andere = alle.filter((x) => x.name !== mannschaft.name);

  function umschalten(name: string) {
    const drin = mannschaft.hoehere.includes(name);
    onSetzen(
      drin
        ? mannschaft.hoehere.filter((x) => x !== name)
        : [...mannschaft.hoehere, name].sort(),
    );
  }

  return (
    <Karte>
      <button
        type="button"
        className={stil.kopf}
        onClick={() => setOffen(!offen)}
        aria-expanded={offen}
      >
        <span className={stil.paarung}>{mannschaft.name}</span>
        <span className={stil.zeile}>
          {mannschaft.ist_sg && <Etikett>SG</Etikett>}
          <Etikett ton={mannschaft.bestaetigt ? "gut" : "warnung"}>
            {mannschaft.bestaetigt ? "bestätigt" : "geraten"}
          </Etikett>
          {mannschaft.unsicher && <Etikett ton="fehler">prüfen</Etikett>}
        </span>
      </button>

      <p className={stil.vorgangHinweis}>
        {mannschaft.hoehere.length === 0
          ? "Keine höherklassige Mannschaft dieses Vereins."
          : `Darüber: ${mannschaft.hoehere.join(", ")}`}
      </p>

      {offen && (
        <div className={stil.befunde}>
          <p className={stil.vorgangHinweis}>
            Welche Mannschaften desselben Vereins spielen höherklassig? Die Antwort
            entscheidet, wessen Einsätze als Stammspieler zählen — bei einer
            Spielgemeinschaft rät der Name falsch.
          </p>
          <ul
            className={stil.auswahlListe}
            aria-label={`Höherklassig als ${mannschaft.name}`}
          >
            {andere.map((x) => (
              <li key={x.id}>
                <label className={stil.ankreuz}>
                  <input
                    type="checkbox"
                    checked={mannschaft.hoehere.includes(x.name)}
                    onChange={() => umschalten(x.name)}
                  />
                  <span>{x.name}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Karte>
  );
}
