import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchModule, type ModulEintrag } from "../api/client";
import { SystemStatus } from "../components/SystemStatus";
import { Etikett, Karte, Leerzustand, Platzhalter, Seitenkopf, Statuspunkt } from "../ui";
import stil from "./Start.module.css";

type Zustand =
  | { phase: "laedt" }
  | { phase: "fertig"; module: ModulEintrag[] }
  | { phase: "fehler"; nachricht: string };

export function Start() {
  const [zustand, setZustand] = useState<Zustand>({ phase: "laedt" });

  useEffect(() => {
    const controller = new AbortController();

    fetchModule(controller.signal)
      .then((module) => setZustand({ phase: "fertig", module }))
      .catch((fehler: unknown) => {
        if (controller.signal.aborted) return;
        const nachricht = fehler instanceof Error ? fehler.message : "Unbekannter Fehler";
        setZustand({ phase: "fehler", nachricht });
      });

    return () => controller.abort();
  }, []);

  return (
    <>
      <Seitenkopf
        titel="Übersicht"
        beschreibung="Alle Dienste dieser Installation an einem Ort. Neue Artefakte erscheinen hier, sobald das Gateway sie geladen hat."
      />

      <Karte className={stil.statuskarte}>
        <SystemStatus />
      </Karte>

      <section className={stil.bereich} aria-labelledby="artefakte">
        <div className={stil.bereichskopf}>
          <h2 id="artefakte" className={stil.bereichstitel}>
            Artefakte
          </h2>
          {zustand.phase === "fertig" && zustand.module.length > 0 && (
            <span className={stil.anzahl}>{zustand.module.length}</span>
          )}
        </div>

        {zustand.phase === "laedt" && <Ladegitter />}

        {zustand.phase === "fehler" && (
          <Leerzustand titel="Manifest nicht abrufbar">
            Das Gateway hat nicht geantwortet: {zustand.nachricht}
          </Leerzustand>
        )}

        {zustand.phase === "fertig" && <Kacheln module={zustand.module} />}
      </section>
    </>
  );
}

function Ladegitter() {
  return (
    <div className={stil.gitter} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <Karte key={i}>
          <Platzhalter breite="7rem" hoehe="1rem" />
          <div className={stil.ladezeile}>
            <Platzhalter breite="100%" hoehe="0.75rem" />
          </div>
          <Platzhalter breite="4rem" hoehe="0.75rem" />
        </Karte>
      ))}
    </div>
  );
}

function Kacheln({ module }: { module: ModulEintrag[] }) {
  if (module.length === 0) {
    return (
      <Leerzustand titel="Noch kein Artefakt angemeldet">
        Ein neues legst du mit <code>homepi new &lt;name&gt;</code> an. Nach dem Deploy
        erscheint es hier von selbst — am Frontend ist dafür nichts zu ändern.
      </Leerzustand>
    );
  }

  return (
    <ul className={stil.gitter} aria-label="Artefakte">
      {module.map((modul, index) => (
        <li
          key={modul.id}
          className={stil.eintrag}
          /* Gestaffeltes Erscheinen, gedeckelt: bei zwanzig Kacheln wuerde
             sonst die letzte erst nach zwei Sekunden auftauchen. */
          style={{ animationDelay: `${Math.min(index, 6) * 40}ms` }}
        >
          <Kachel modul={modul} />
        </li>
      ))}
    </ul>
  );
}

function Kachel({ modul }: { modul: ModulEintrag }) {
  if (modul.status === "fehler") {
    return (
      <Karte className={stil.kachel}>
        <div className={stil.kachelkopf}>
          <h3 className={stil.kacheltitel}>{modul.titel}</h3>
          <Etikett ton="fehler">Fehler</Etikett>
        </div>
        <p className={stil.kacheltext} role="alert">
          {modul.beschreibung || "Das Modul konnte nicht geladen werden."}
        </p>
      </Karte>
    );
  }

  return (
    <Link to={`/modul/${modul.id}`} className={stil.verweis}>
      <Karte className={`${stil.kachel} ${stil.klickbar}`}>
        <div className={stil.kachelkopf}>
          <h3 className={stil.kacheltitel}>{modul.titel}</h3>
          <Statuspunkt ton="gut" />
        </div>

        {modul.beschreibung && <p className={stil.kacheltext}>{modul.beschreibung}</p>}

        <div className={stil.kachelfuss}>
          <Etikett mono>v{modul.version}</Etikett>
          <span className={stil.pfad}>{modul.pfad}</span>
        </div>
      </Karte>
    </Link>
  );
}
