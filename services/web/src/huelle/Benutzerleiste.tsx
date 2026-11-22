import { Link, useLocation } from "react-router-dom";

import { useAnmeldung } from "../anmeldung/kontext";
import { Monogramm } from "../ui";
import stil from "./Benutzerleiste.module.css";

/**
 * Wer angemeldet ist - und der Weg hinein.
 *
 * Ein Kürzel und sonst nichts. Der volle Name stand vorher in der
 * Kopfzeile, wurde dort aber bei jedem zweiten Konto abgeschnitten und sagte
 * dem, der ohnehin weiß, wer er ist, nichts Neues. Das Kürzel führt zu den
 * Einstellungen, wo der Name ausgeschrieben steht.
 *
 * „Abmelden" liegt in der Navigation, nicht hier: Es ist die seltenste
 * Handlung dieser Oberfläche und stand als Knopf dauerhaft neben einer, die
 * man ständig braucht.
 *
 * Während der erste Abruf läuft, bleibt der Platz leer statt „Anmelden" zu
 * zeigen: sonst blitzt bei jedem Seitenaufruf kurz auf, man sei abgemeldet.
 */
export function Benutzerleiste() {
  const { zustand, benutzer } = useAnmeldung();
  const ort = useLocation();

  if (zustand === "laedt") {
    return <span className={stil.platz} aria-hidden="true" />;
  }

  if (zustand === "abgemeldet") {
    // Die Einstellungen auch ohne Konto: Farbschema und Bewegung gehören
    // dem Gerät, nicht dem Konto. Wer noch keins hat, sitzt sonst vor einem
    // hellen Anmeldeformular und kommt nicht in den Dunkelmodus.
    // Wo man schon ist, steht der Verweis nicht noch einmal: Der Pfad links
    // nennt die Seite bereits.
    return (
      <span className={stil.ohneKonto}>
        {ort.pathname !== "/einstellungen" && (
          <Link to="/einstellungen" className={stil.leise}>
            Einstellungen
          </Link>
        )}
        {ort.pathname !== "/anmelden" && (
          <Link to="/anmelden" className={stil.anmelden}>
            Anmelden
          </Link>
        )}
      </span>
    );
  }

  const name = benutzer?.anzeigename || benutzer?.name || "";

  return (
    <Link
      to="/einstellungen"
      className={stil.konto}
      aria-label={`Einstellungen für ${name}`}
      title={name}
    >
      <Monogramm name={name} betont />
    </Link>
  );
}
