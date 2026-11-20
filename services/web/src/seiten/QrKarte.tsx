import { useMemo } from "react";

import { Platzhalter } from "../ui";
import { qrMuster, qrPfad } from "./qrcode";
import stil from "./Start.module.css";

/** Vier Felder Rand ringsum: So viel heller Abstand braucht eine Kamera. */
const RUHEZONE = 4;

/**
 * Die Adresse der Seite als QR-Code - zum Abfotografieren bei der
 * Vorstellung.
 *
 * Immer dunkel auf hell, auch im Dunkelmodus: Ein umgekehrter Code liest
 * nicht jede Kamera, und ein Code, den das halbe Publikum nicht scannen
 * kann, ist an der Wand schlimmer als keiner.
 *
 * Unter dem Code steht die Adresse noch einmal als Text, ohne `https://` -
 * für jedes Handy, dessen Kamera keine QR-Codes liest.
 */
export function QrKarte({ url }: { url: string | null }) {
  const pfad = useMemo(() => {
    if (url === null) return null;
    const muster = qrMuster(url);
    return { d: qrPfad(muster, RUHEZONE), seite: muster.length + 2 * RUHEZONE };
  }, [url]);

  return (
    <figure className={stil.qr} id="qr-code">
      {url === null || pfad === null ? (
        // Gleich groß wie der Code: Er erscheint an derselben Stelle und
        // schiebt nichts weg.
        <div className={stil.qrfeld} role="status" aria-label="Adresse wird geholt">
          <Platzhalter breite="100%" hoehe="100%" />
        </div>
      ) : (
        <svg
          className={stil.qrfeld}
          viewBox={`0 0 ${pfad.seite} ${pfad.seite}`}
          role="img"
          aria-label={`QR-Code für ${url}`}
          // Sonst glättet der Browser die Kanten der Felder, und zwischen
          // zwei dunklen Quadraten bleibt ein heller Haarstrich stehen.
          shapeRendering="crispEdges"
        >
          <rect className={stil.qrgrund} width={pfad.seite} height={pfad.seite} />
          <path className={stil.qrmuster} d={pfad.d} />
        </svg>
      )}
      <figcaption className={stil.qrtext}>
        <span className={stil.qrhinweis}>Mit dem Handy öffnen</span>
        {url !== null && (
          <span className={stil.qradresse}>{url.replace(/^https?:\/\//, "")}</span>
        )}
      </figcaption>
    </figure>
  );
}
