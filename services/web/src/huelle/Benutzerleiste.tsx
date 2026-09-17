import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAnmeldung } from "../anmeldung/kontext";
import { Knopf } from "../ui";
import stil from "./Benutzerleiste.module.css";

/**
 * Wer angemeldet ist - und der Weg hinein und hinaus.
 *
 * Während der erste Abruf läuft, bleibt der Platz leer statt "Anmelden" zu
 * zeigen: sonst blitzt bei jedem Seitenaufruf kurz auf, man sei abgemeldet.
 */
export function Benutzerleiste() {
  const { zustand, benutzer, abmelden } = useAnmeldung();
  const navigate = useNavigate();
  const ort = useLocation();

  if (zustand === "laedt") {
    return <span className={stil.platz} aria-hidden="true" />;
  }

  if (zustand === "abgemeldet") {
    if (ort.pathname === "/anmelden")
      return <span className={stil.platz} aria-hidden="true" />;
    return (
      <Link to="/anmelden" className={stil.anmelden}>
        Anmelden
      </Link>
    );
  }

  return (
    <div className={stil.leiste}>
      <span className={stil.name} title={benutzer?.name}>
        {benutzer?.anzeigename || benutzer?.name}
      </span>
      <Knopf
        auspraegung="leise"
        groesse="sm"
        onClick={() => {
          void abmelden().then(() => navigate("/"));
        }}
      >
        Abmelden
      </Knopf>
    </div>
  );
}
