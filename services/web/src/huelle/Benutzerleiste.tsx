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
    if (ort.pathname === "/anmelden") {
      return <span className={stil.platz} aria-hidden="true" />;
    }
    return (
      <Link to="/anmelden" className={stil.anmelden}>
        Anmelden
      </Link>
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
