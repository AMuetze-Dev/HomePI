import { NavLink, useMatch } from "react-router-dom";

import { sichtbareUnterseiten } from "../module/register";
import stil from "./Bereichsleiste.module.css";

/**
 * Die Bereiche des geöffneten Artefakts — direkt unter der Kopfleiste.
 *
 * Sie stand bis hierher **im Inhalt**, und damit in dessen Spalte: Ein
 * Bereich mit `breite: "text"` ist 40 rem breit, einer mit `"voll"` nimmt
 * den ganzen Monitor. Die Leiste wanderte also bei jedem Wechsel mit — sie
 * sprang in der Breite und, weil die Spalte zentriert war, auch seitwärts.
 * Auf einem breiten Monitor saß sie mitten im Bild statt an einer Kante.
 *
 * Navigation gehört zur Hülle, nicht zum Inhalt. Hier steht sie über die
 * volle Breite, an derselben Kante wie die Brotkrume darüber, und bleibt
 * stehen, egal wie breit der Bereich darunter sein will.
 *
 * Sie rendert nichts, wo es nichts zu wechseln gibt: kein Artefakt offen,
 * oder eines ohne zweite Ebene.
 */
export function Bereichsleiste() {
  // useMatch und nicht useParams: Die Leiste steht in der Hülle und damit
  // AUSSERHALB von <Routes>. Dort liefert useParams immer ein leeres Objekt.
  const treffer = useMatch("/modul/:id/*");
  const id = treffer?.params.id ?? "";
  const bereiche = sichtbareUnterseiten(id);

  if (bereiche.length === 0) return null;

  return (
    <nav className={stil.leiste} aria-label="Bereiche">
      {bereiche.map((bereich) => (
        <NavLink
          key={bereich.id}
          to={`/modul/${id}/${bereich.id}`}
          className={({ isActive }) => (isActive ? stil.bereichAktiv : stil.bereich)}
        >
          {bereich.wort}
        </NavLink>
      ))}
    </nav>
  );
}
