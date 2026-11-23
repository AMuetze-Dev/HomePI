import { useEffect, useRef, useState } from "react";

import {
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Reihe,
  Segmentwahl,
  Tabelle,
  Zelle,
} from "../../ui";
import {
  aufnahmeAdresse,
  type Aufnahme,
  type AufnahmeArt,
  type Figur,
  type Knopf as GeraeteKnopf,
} from "./api";
import * as audio from "./audio";
import { Auswahl } from "./bausteine";
import stil from "./KinderzimmerSeite.module.css";
import { dauer, verwendungen } from "./texte";

interface Props {
  aufnahmen: readonly Aufnahme[];
  figuren: readonly Figur[];
  knoepfe: readonly GeraeteKnopf[];
  darfAendern: boolean;
  formularOffen: boolean;
  onFormular: (offen: boolean) => void;
  onHochladen: (titel: string, art: AufnahmeArt, wav: Blob) => Promise<boolean>;
  onAendern: (id: string, titel: string, art: AufnahmeArt) => Promise<boolean>;
  onEntfernen: (aufnahme: Aufnahme) => void;
}

const ARTEN: readonly [AufnahmeArt, string][] = [
  ["stimme", "Stimme"],
  ["klang", "Klang"],
];

/**
 * Eure Stimmen und Klänge.
 *
 * Aufgenommen wird direkt hier im Browser, am Handy wie am Rechner. Eine
 * fertige Datei geht genauso - etwa ein Tiergeräusch. Beides wird vor dem
 * Hochladen auf das Format des Geräts gebracht (siehe `audio.ts`).
 */
export function AufnahmenTafel({
  aufnahmen,
  figuren,
  knoepfe,
  darfAendern,
  formularOffen,
  onFormular,
  onHochladen,
  onAendern,
  onEntfernen,
}: Props) {
  const [offen, setOffen] = useState<string | null>(null);

  return (
    <>
      {formularOffen && (
        <NeueAufnahme onAbbrechen={() => onFormular(false)} onHochladen={onHochladen} />
      )}

      {aufnahmen.length === 0 ? (
        <Leerzustand titel="Noch keine Aufnahme">
          Nehmt zuerst eure Stimmen auf, etwa „Hallo, meine Kleine!“, und einen kurzen,
          freundlichen Klang für den Knopf. Am besten in einem ruhigen Raum, eine
          Handbreit vom Mikrofon entfernt.
        </Leerzustand>
      ) : (
        <Tabelle
          beschriftung="Aufnahmen"
          raster="1.6fr .8fr .6fr 1.4fr"
          spalten={["Aufnahme", "Art", "Dauer", "Benutzt von"]}
        >
          {aufnahmen.map((aufnahme) => {
            const wo = verwendungen(aufnahme, figuren, knoepfe);
            return (
              <Reihe
                key={aufnahme.id}
                onKlick={() => setOffen(offen === aufnahme.id ? null : aufnahme.id)}
                offen={offen === aufnahme.id}
                ausklappung={
                  offen === aufnahme.id && (
                    <Ausklappung
                      aufnahme={aufnahme}
                      darfAendern={darfAendern}
                      benutzt={wo.length > 0}
                      onAendern={onAendern}
                      onEntfernen={onEntfernen}
                    />
                  )
                }
              >
                <Zelle>{aufnahme.titel}</Zelle>
                <Zelle leise>{aufnahme.art === "stimme" ? "Stimme" : "Klang"}</Zelle>
                <Zelle leise>{dauer(aufnahme.dauer_ms)}</Zelle>
                <Zelle leise>{wo.length > 0 ? wo.join(", ") : "noch nichts"}</Zelle>
              </Reihe>
            );
          })}
        </Tabelle>
      )}
    </>
  );
}

function Ausklappung({
  aufnahme,
  darfAendern,
  benutzt,
  onAendern,
  onEntfernen,
}: {
  aufnahme: Aufnahme;
  darfAendern: boolean;
  benutzt: boolean;
  onAendern: (id: string, titel: string, art: AufnahmeArt) => Promise<boolean>;
  onEntfernen: (aufnahme: Aufnahme) => void;
}) {
  const [titel, setTitel] = useState(aufnahme.titel);
  const [art, setArt] = useState<AufnahmeArt>(aufnahme.art);
  const geaendert = titel.trim() !== aufnahme.titel || art !== aufnahme.art;

  return (
    <div className={stil.ausklappung}>
      <audio
        controls
        preload="none"
        src={aufnahmeAdresse(aufnahme.id)}
        aria-label={`${aufnahme.titel} anhören`}
      />
      {darfAendern && (
        <form
          className={`${stil.zweispaltig} ${stil.umbenennen}`}
          onSubmit={(e) => {
            e.preventDefault();
            void onAendern(aufnahme.id, titel.trim(), art);
          }}
        >
          <Feld
            beschriftung="Titel"
            value={titel}
            onChange={(e) => setTitel(e.target.value)}
            autoComplete="off"
          />
          <Auswahl beschriftung="Art" wert={art} optionen={ARTEN} beiWahl={setArt} />
          <div className={stil.handlungen}>
            <Knopf
              type="submit"
              groesse="sm"
              disabled={!geaendert || titel.trim() === ""}
            >
              Speichern
            </Knopf>
            <Knopf
              groesse="sm"
              auspraegung="leise"
              onClick={() => onEntfernen(aufnahme)}
              title={
                benutzt
                  ? "Wird noch benutzt - erst bei Figur oder Knopf eine andere wählen"
                  : undefined
              }
            >
              „{aufnahme.titel}“ löschen
            </Knopf>
          </div>
        </form>
      )}
    </div>
  );
}

type Aufnehmer =
  | { zustand: "bereit" }
  | { zustand: "nimmt-auf"; rekorder: MediaRecorder }
  | { zustand: "rechnet" };

function NeueAufnahme({
  onAbbrechen,
  onHochladen,
}: {
  onAbbrechen: () => void;
  onHochladen: (titel: string, art: AufnahmeArt, wav: Blob) => Promise<boolean>;
}) {
  const [titel, setTitel] = useState("");
  const [art, setArt] = useState<AufnahmeArt>("stimme");
  const [aufnehmer, setAufnehmer] = useState<Aufnehmer>({ zustand: "bereit" });
  const [wav, setWav] = useState<{ blob: Blob; url: string; sekunden: number } | null>(
    null,
  );
  const [problem, setProblem] = useState("");
  const [laeuft, setLaeuft] = useState(false);
  const stuecke = useRef<Blob[]>([]);

  const kannAufnehmen =
    typeof navigator !== "undefined" &&
    // Ohne HTTPS gibt es mediaDevices gar nicht.
    navigator.mediaDevices !== undefined &&
    typeof MediaRecorder !== "undefined";

  // Die Vorschau hält einen Verweis auf den Speicher des Browsers. Ohne
  // Aufräumen bleibt jede verworfene Aufnahme bis zum Neuladen liegen.
  useEffect(
    () => () => {
      if (wav) URL.revokeObjectURL(wav.url);
    },
    [wav],
  );

  async function verarbeite(roh: Blob) {
    setAufnehmer({ zustand: "rechnet" });
    setProblem("");
    try {
      const fertig = await audio.bereiteAuf(roh);
      setWav({
        blob: fertig,
        url: URL.createObjectURL(fertig),
        sekunden: (fertig.size - 44) / 2 / audio.ABTASTRATE,
      });
    } catch (fehler) {
      setProblem(fehler instanceof Error ? fehler.message : String(fehler));
    } finally {
      setAufnehmer({ zustand: "bereit" });
    }
  }

  async function starte() {
    setProblem("");
    try {
      const strom = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rekorder = new MediaRecorder(strom);
      stuecke.current = [];
      rekorder.ondataavailable = (e) => stuecke.current.push(e.data);
      rekorder.onstop = () => {
        strom.getTracks().forEach((spur) => spur.stop());
        void verarbeite(new Blob(stuecke.current, { type: rekorder.mimeType }));
      };
      rekorder.start();
      setAufnehmer({ zustand: "nimmt-auf", rekorder });
    } catch {
      setProblem(
        "Das Mikrofon ist nicht freigegeben. Der Browser fragt danach - oder es ist in seinen Einstellungen für diese Seite gesperrt.",
      );
    }
  }

  async function speichere(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (!wav || laeuft) return;
    setLaeuft(true);
    const geklappt = await onHochladen(titel.trim(), art, wav.blob);
    setLaeuft(false);
    if (geklappt) onAbbrechen();
  }

  return (
    <Karte>
      <form onSubmit={(e) => void speichere(e)} className={stil.formular}>
        <div className={stil.zweispaltig}>
          <Feld
            beschriftung="Titel"
            value={titel}
            onChange={(e) => setTitel(e.target.value)}
            placeholder="Oma sagt Hallo"
            autoComplete="off"
          />
          <Segmentwahl
            beschriftung="Art der Aufnahme"
            optionen={ARTEN.map(([wert, wort]) => ({ wert, wort }))}
            wert={art}
            beiWahl={setArt}
          />
        </div>

        <div className={stil.aufnahme}>
          {kannAufnehmen ? (
            aufnehmer.zustand === "nimmt-auf" ? (
              <Knopf auspraegung="primaer" onClick={() => aufnehmer.rekorder.stop()}>
                Aufnahme beenden
              </Knopf>
            ) : (
              <Knopf
                onClick={() => void starte()}
                disabled={aufnehmer.zustand === "rechnet"}
              >
                {wav ? "Neu aufnehmen" : "Aufnahme starten"}
              </Knopf>
            )
          ) : (
            <p className={stil.nebensache}>
              Aufnehmen geht hier nicht – der Browser erlaubt das Mikrofon nur über HTTPS.
              Eine Datei geht trotzdem.
            </p>
          )}
          {aufnehmer.zustand === "nimmt-auf" && (
            <span role="status" className={stil.nebensache}>
              Nimmt auf …
            </span>
          )}
          {aufnehmer.zustand === "rechnet" && (
            <span role="status" className={stil.nebensache}>
              Wird aufbereitet …
            </span>
          )}
        </div>

        <label className={stil.dateiwahl}>
          Oder eine Tondatei wählen
          <input
            type="file"
            accept="audio/*"
            onChange={(e) => {
              const datei = e.target.files?.[0];
              if (datei) void verarbeite(datei);
            }}
          />
        </label>

        {problem && (
          <Hinweis ton="fehler" dringend>
            {problem}
          </Hinweis>
        )}

        {wav && (
          <div className={stil.aufnahme}>
            <audio controls src={wav.url} aria-label="Vorschau anhören" />
            <span className={stil.nebensache}>
              {dauer(wav.sekunden * 1000)}, Stille abgeschnitten, Lautstärke angeglichen
            </span>
          </div>
        )}

        <div className={stil.formularfuss}>
          <Knopf auspraegung="leise" onClick={onAbbrechen}>
            Abbrechen
          </Knopf>
          <Knopf
            type="submit"
            auspraegung="primaer"
            disabled={!wav || titel.trim() === "" || laeuft}
          >
            {laeuft ? "Wird hochgeladen …" : "Aufnahme speichern"}
          </Knopf>
        </div>
      </form>
    </Karte>
  );
}
