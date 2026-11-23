import { useState } from "react";

import {
  Etikett,
  Feld,
  Hinweis,
  Karte,
  Knopf,
  Leerzustand,
  Reihe,
  Tabelle,
  Zelle,
} from "../../ui";
import { geraeteAdresse, type Geraet, type GeraetMitToken } from "./api";
import stil from "./KinderzimmerSeite.module.css";
import { zeit } from "./texte";

interface Props {
  geraete: readonly Geraet[];
  darfVerwalten: boolean;
  formularOffen: boolean;
  /** Steht nur direkt nach dem Anlegen oder Neuausstellen da. */
  neuesToken: GeraetMitToken | null;
  onFormular: (offen: boolean) => void;
  onAnlegen: (name: string) => Promise<boolean>;
  onNeuesToken: (geraet: Geraet) => void;
  onEntfernen: (geraet: Geraet) => void;
  onTokenGelesen: () => void;
}

function Stand({ geraet }: { geraet: Geraet }) {
  if (geraet.stand_aktuell === null) return <Etikett>noch nie abgeglichen</Etikett>;
  if (geraet.stand_aktuell) return <Etikett ton="gut">aktuell</Etikett>;
  return <Etikett ton="warnung">übernimmt beim nächsten Abgleich</Etikett>;
}

/**
 * Die Geräte, die sich hier melden dürfen.
 *
 * Ein Gerät meldet sich mit einem Token an, nicht mit einem Konto. Das Token
 * steht genau einmal da - in der Datenbank liegt nur seine Prüfsumme. Wer
 * es verliert, stellt ein neues aus.
 */
export function GeraeteTafel({
  geraete,
  darfVerwalten,
  formularOffen,
  neuesToken,
  onFormular,
  onAnlegen,
  onNeuesToken,
  onEntfernen,
  onTokenGelesen,
}: Props) {
  const [offen, setOffen] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  async function anlegen(ereignis: React.FormEvent) {
    ereignis.preventDefault();
    if (laeuft || name.trim() === "") return;
    setLaeuft(true);
    const geklappt = await onAnlegen(name.trim());
    setLaeuft(false);
    if (geklappt) setName("");
  }

  return (
    <>
      {neuesToken && (
        <Karte>
          <div className={stil.token}>
            <Hinweis ton="warnung">
              Das Token für „{neuesToken.name}“ steht nur jetzt hier. Tragt es in die
              Firmware ein, bevor ihr die Seite verlasst.
            </Hinweis>
            <Feld
              beschriftung="Token"
              value={neuesToken.token}
              readOnly
              className={stil.mono}
            />
            <Feld
              beschriftung="Adresse für das Gerät"
              value={geraeteAdresse()}
              readOnly
            />
            <p className={stil.nebensache}>
              Das Gerät schickt bei jeder Anfrage „Authorization: Bearer &lt;Token&gt;“
              mit. Im Heimnetz nimmt es besser die Adresse im LAN als die aus dem
              Internet.
            </p>
            <div className={stil.formularfuss}>
              <Knopf onClick={onTokenGelesen}>Eingetragen</Knopf>
            </div>
          </div>
        </Karte>
      )}

      {formularOffen && (
        <Karte>
          <form onSubmit={(e) => void anlegen(e)} className={stil.formular}>
            <Feld
              beschriftung="Name des Geräts"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Spielkiste"
              autoComplete="off"
            />
            <div className={stil.formularfuss}>
              <Knopf auspraegung="leise" onClick={() => onFormular(false)}>
                Abbrechen
              </Knopf>
              <Knopf
                type="submit"
                auspraegung="primaer"
                disabled={laeuft || name.trim() === ""}
              >
                {laeuft ? "Wird angelegt …" : "Gerät anlegen"}
              </Knopf>
            </div>
          </form>
        </Karte>
      )}

      {geraete.length === 0 ? (
        <Leerzustand titel="Noch kein Gerät">
          {darfVerwalten
            ? "Legt das Gerät hier an. Ihr bekommt ein Token, das in die Firmware gehört - damit darf es Figuren und Aufnahmen holen und sein Protokoll schicken."
            : "Ein Gerät legt an, wer dieses Artefakt verwaltet."}
        </Leerzustand>
      ) : (
        <Tabelle
          beschriftung="Geräte"
          raster="1.2fr 1fr 1.4fr .8fr"
          spalten={["Gerät", "Zuletzt gemeldet", "Stand", "Firmware"]}
        >
          {geraete.map((geraet) => (
            <Reihe
              key={geraet.id}
              onKlick={() => setOffen(offen === geraet.id ? null : geraet.id)}
              offen={offen === geraet.id}
              ausklappung={
                darfVerwalten ? (
                  <div className={stil.handlungen}>
                    <Knopf groesse="sm" onClick={() => onNeuesToken(geraet)}>
                      Neues Token für „{geraet.name}“
                    </Knopf>
                    <Knopf
                      groesse="sm"
                      auspraegung="leise"
                      onClick={() => onEntfernen(geraet)}
                    >
                      „{geraet.name}“ entfernen
                    </Knopf>
                  </div>
                ) : (
                  <p className={stil.nebensache}>
                    Geräte verwaltet, wer hier „verwalter“ ist.
                  </p>
                )
              }
            >
              <Zelle>{geraet.name}</Zelle>
              <Zelle leise>
                {geraet.zuletzt_gesehen ? zeit(geraet.zuletzt_gesehen) : "noch nie"}
              </Zelle>
              <Zelle>
                <Stand geraet={geraet} />
              </Zelle>
              <Zelle leise>{geraet.firmware ?? "–"}</Zelle>
            </Reihe>
          ))}
        </Tabelle>
      )}
    </>
  );
}
