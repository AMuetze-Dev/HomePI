import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchModule, type ModulEintrag } from "../api/client";
import { SystemStatus } from "../components/SystemStatus";

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
    <main>
      <header>
        <h1>HomePI</h1>
        <SystemStatus />
      </header>

      <section aria-labelledby="artefakte">
        <h2 id="artefakte">Artefakte</h2>
        {zustand.phase === "laedt" && <p role="status">Artefakte werden geladen …</p>}
        {zustand.phase === "fehler" && (
          <p role="alert">Manifest nicht abrufbar: {zustand.nachricht}</p>
        )}
        {zustand.phase === "fertig" && <Kacheln module={zustand.module} />}
      </section>
    </main>
  );
}

function Kacheln({ module }: { module: ModulEintrag[] }) {
  if (module.length === 0) {
    // Der Erstzustand. Eine leere Fläche ohne Erklärung lässt einen ratlos
    // zurück - hier steht, was als Nächstes zu tun ist.
    return (
      <p>
        Noch kein Artefakt angemeldet. Ein neues legst du mit{" "}
        <code>homepi new &lt;name&gt;</code> an; nach dem Deploy erscheint es hier von
        selbst.
      </p>
    );
  }

  return (
    <ul aria-label="Artefakte">
      {module.map((modul) => (
        <li key={modul.id}>
          <Kachel modul={modul} />
        </li>
      ))}
    </ul>
  );
}

function Kachel({ modul }: { modul: ModulEintrag }) {
  if (modul.status === "fehler") {
    return (
      <article aria-labelledby={`t-${modul.id}`} data-status="fehler">
        <h3 id={`t-${modul.id}`}>{modul.titel}</h3>
        <p role="alert">Konnte nicht geladen werden: {modul.beschreibung}</p>
      </article>
    );
  }

  return (
    <article aria-labelledby={`t-${modul.id}`} data-status="bereit">
      <h3 id={`t-${modul.id}`}>
        <Link to={`/modul/${modul.id}`}>{modul.titel}</Link>
      </h3>
      {modul.beschreibung && <p>{modul.beschreibung}</p>}
      <p>Version {modul.version}</p>
    </article>
  );
}
