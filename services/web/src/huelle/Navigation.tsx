import { NavLink, useMatch } from "react-router-dom";

import type { ModulEintrag } from "../api/client";
import { unterseitenFuer } from "../module/register";
import { useModule } from "../module/useModule";
import { Platzhalter } from "../ui";
import stil from "./Navigation.module.css";

interface Props {
  /** Nach einem Klick auf schmalen Geräten: Schublade zu. */
  beiAuswahl?: () => void;
}

/**
 * Die Navigation: Artefakte, und darunter die Bereiche des geöffneten.
 *
 * Beide Ebenen in EINER Spalte. Die naheliegende Alternative wäre eine
 * zweite Leiste für die Bereiche gewesen - wie in manchen Editoren. Sie
 * kostet dauerhaft rund 200 px, und zwar ausgerechnet bei den Modulen, die
 * Breite brauchen: Ein Modul mit neun Bereichen ist meist auch eins mit
 * breiten Tabellen.
 *
 * Die Bereiche erscheinen deshalb eingerückt unter ihrem Artefakt und nur
 * dann, wenn es geöffnet ist. Ein Artefakt ohne Bereiche hat schlicht keine
 * zweite Ebene - kein leerer Platzhalter, keine Leiste, die aussieht, als
 * fehle etwas.
 */
export function Navigation({ beiAuswahl }: Props) {
  const zustand = useModule();
  // useMatch und nicht useParams: Die Leiste steht in der Hülle und damit
  // AUSSERHALB von <Routes>. Dort liefert useParams immer ein leeres
  // Objekt, und die Bereiche klappten nie auf. useMatch liest die Adresse
  // selbst und funktioniert überall innerhalb des Routers.
  const treffer = useMatch("/modul/:id/*");
  const offenesModul = treffer?.params.id ?? "";

  return (
    <nav className={stil.navigation} aria-label="Artefakte">
      <NavLink
        to="/"
        end
        className={({ isActive }) => (isActive ? stil.eintragAktiv : stil.eintrag)}
        onClick={beiAuswahl}
      >
        <span className={stil.zeichen} aria-hidden="true">
          ◆
        </span>
        Übersicht
      </NavLink>

      {zustand.phase === "laedt" && (
        <div className={stil.laden} aria-hidden="true">
          <Platzhalter breite="100%" hoehe="1.75rem" />
          <Platzhalter breite="100%" hoehe="1.75rem" />
          <Platzhalter breite="100%" hoehe="1.75rem" />
        </div>
      )}

      {zustand.phase === "fertig" && zustand.module.length > 0 && (
        <>
          <p className={stil.gruppe} id="nav-artefakte">
            Artefakte
          </p>
          <ul className={stil.liste} aria-labelledby="nav-artefakte">
            {zustand.module.map((modul) => (
              <li key={modul.id}>
                <Eintrag
                  modul={modul}
                  offen={modul.id === offenesModul}
                  beiAuswahl={beiAuswahl}
                />
              </li>
            ))}
          </ul>
        </>
      )}
    </nav>
  );
}

function Eintrag({
  modul,
  offen,
  beiAuswahl,
}: {
  modul: ModulEintrag;
  offen: boolean;
  beiAuswahl?: (() => void) | undefined;
}) {
  const bereiche = unterseitenFuer(modul.id);

  return (
    <>
      <NavLink
        to={`/modul/${modul.id}`}
        className={({ isActive }) => (isActive ? stil.eintragAktiv : stil.eintrag)}
        onClick={beiAuswahl}
      >
        <span className={stil.zeichen} aria-hidden="true">
          {modul.icon || modul.titel.slice(0, 1)}
        </span>
        <span className={stil.wort}>{modul.titel}</span>
        {/* Der Punkt ist Dekoration, das Wort trägt die Bedeutung. Nur
            farbig markiert käme die Störung weder bei einem Screenreader
            noch bei Farbenblindheit an. */}
        {modul.status === "fehler" && (
          <>
            <span className={stil.stoerung} aria-hidden="true" />
            <span className="nur-vorlesen">Nicht erreichbar</span>
          </>
        )}
      </NavLink>

      {/* Nur beim geoeffneten Artefakt. Alle Bereiche aller Artefakte
          untereinander waeren eine Liste, in der man sucht statt findet. */}
      {offen && bereiche.length > 0 && (
        <ul className={stil.bereiche} aria-label={`Bereiche von ${modul.titel}`}>
          {bereiche.map((bereich) => (
            <li key={bereich.id}>
              <NavLink
                to={`/modul/${modul.id}/${bereich.id}`}
                className={({ isActive }) =>
                  isActive ? stil.bereichAktiv : stil.bereich
                }
                onClick={beiAuswahl}
              >
                {bereich.wort}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
