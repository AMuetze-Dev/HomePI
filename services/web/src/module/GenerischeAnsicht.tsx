import { useEffect, useState } from "react";

import { fetchEndpunkte, type Endpunkt, type ModulEintrag } from "../api/client";

/**
 * Was ein Artefakt bekommt, solange es keine eigene Oberfläche hat.
 *
 * Die Endpunkte kommen aus dem OpenAPI-Schema, das FastAPI ohnehin erzeugt.
 * Damit ist ein frisch deploytes Artefakt sofort benutzbar und die Anzeige
 * kann nicht veralten - anders als eine von Hand gepflegte Liste.
 */
export function GenerischeAnsicht({ modul }: { modul: ModulEintrag }) {
  const [endpunkte, setEndpunkte] = useState<Endpunkt[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchEndpunkte(modul.pfad, controller.signal)
      .then(setEndpunkte)
      .catch(() => {
        if (!controller.signal.aborted) setEndpunkte([]);
      });

    return () => controller.abort();
  }, [modul.pfad]);

  if (endpunkte === null) return <p role="status">Schnittstelle wird gelesen …</p>;

  if (endpunkte.length === 0) {
    return (
      <p>
        Dieses Artefakt hat noch keine eigene Oberfläche und meldet auch keine Endpunkte.
        Eine eigene Ansicht trägst du in <code>src/module/register.ts</code> ein.
      </p>
    );
  }

  return (
    <section aria-labelledby="endpunkte">
      <h2 id="endpunkte">Schnittstelle</h2>
      <p>Noch ohne eigene Oberfläche — hier steht, was das Artefakt anbietet.</p>
      <table>
        <thead>
          <tr>
            <th scope="col">Methode</th>
            <th scope="col">Pfad</th>
            <th scope="col">Zweck</th>
          </tr>
        </thead>
        <tbody>
          {endpunkte.map((e) => (
            <tr key={`${e.methode} ${e.pfad}`}>
              <td>{e.methode}</td>
              <td>
                <code>{e.pfad}</code>
              </td>
              <td>{e.beschreibung}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
