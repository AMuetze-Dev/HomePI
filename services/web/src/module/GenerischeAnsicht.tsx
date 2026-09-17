import { useEffect, useState } from "react";

import { fetchEndpunkte, type Endpunkt, type ModulEintrag } from "../api/client";
import { Karte, Leerzustand, Platzhalter } from "../ui";
import stil from "./GenerischeAnsicht.module.css";

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

  if (endpunkte === null) {
    return (
      <div role="status" aria-label="Schnittstelle wird gelesen">
        <Platzhalter breite="100%" hoehe="10rem" />
      </div>
    );
  }

  if (endpunkte.length === 0) {
    return (
      <Leerzustand titel="Noch keine Oberfläche">
        Dieses Artefakt bringt keine eigene Ansicht mit, und über seine Schnittstelle ist
        hier nichts zu erfahren — es meldet keine Endpunkte, oder das Schema ist
        abgeschaltet, wie in Produktion üblich. Eine eigene Oberfläche trägst du in{" "}
        <code>src/module/register.ts</code> ein.
      </Leerzustand>
    );
  }

  return (
    <section className={stil.bereich} aria-labelledby="endpunkte">
      <h2 id="endpunkte" className="nur-vorlesen">
        Schnittstelle
      </h2>
      <p className={stil.einleitung}>
        Dieses Artefakt hat noch keine eigene Oberfläche. Solange das so ist, steht hier,
        was es anbietet — direkt aus seinem Schema gelesen.
      </p>

      <Karte blank>
        <div className={stil.rollbereich}>
          <table className={stil.tabelle}>
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
                  <td className={stil.methode}>{e.methode}</td>
                  <td>
                    <code className={stil.pfad}>{e.pfad}</code>
                  </td>
                  <td className={stil.zweck}>{e.beschreibung || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Karte>
    </section>
  );
}
