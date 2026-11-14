import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { useAnmeldung } from "../anmeldung/kontext";
import stil from "./Huelle.module.css";
import { Kopfleiste } from "./Kopfleiste";
import { Navigation } from "./Navigation";

interface Props {
  children: ReactNode;
  /** Ohne Kopfleiste und Navigation. Fuer die Ersteinrichtung: dort gibt es
   *  noch kein Konto und kein Artefakt, und beides daneben waere eine
   *  Einladung ins Leere. */
  schlicht?: boolean;
}

/**
 * Rahmen für alle Ansichten: eine Zeile Kopfleiste, darunter der Inhalt.
 *
 * Die Hülle kennt keine Fachlichkeit - und auch nicht die Breite des
 * Inhalts. Die meldet das Modul selbst an (src/module/typen.ts); die Hülle
 * stellt nur den Platz bereit.
 *
 * ── Warum keine Leiste mehr am Rand ───────────────────────────────────
 * Bis hierher stand links eine Navigationsleiste über die volle Höhe. Sie
 * kostete 15 rem Breite auf JEDER Seite, dauerhaft, und zeigte dabei
 * meistens dasselbe: vier Artefakte, von denen man eines offen hat. Bei
 * einer Spielprüftabelle mit fünf Spalten ist das der Unterschied zwischen
 * lesbar und gequetscht.
 *
 * Stattdessen eine Zeile oben, die sagt, wo man ist - und die vollständige
 * Navigation als Fläche, die man ruft und wieder wegschickt. Sie ist
 * seltener sichtbar, dafür ist sie dann ganz da: beide Ebenen nebeneinander
 * statt eingerückt untereinander.
 *
 * Der Preis ist, dass der Weg zum nächsten Artefakt einen Griff mehr
 * kostet. Deshalb liegt dieser Griff auf Escape und nicht in einem Menü:
 * eine Taste, die jede Tastatur hat und auf der ohnehin „weg hier" liegt.
 */
export function Huelle({ children, schlicht = false }: Props) {
  const [navOffen, setNavOffen] = useState(false);
  const { pathname } = useLocation();
  const { zustand: anmeldung } = useAnmeldung();

  // Abgemeldet gibt es nichts zu navigieren: Das Manifest ist leer, und ein
  // Zeichen, das eine leere Fläche aufzieht, ist ein Versprechen, das die
  // Anwendung nicht halten kann.
  const navigierbar = !schlicht && anmeldung === "angemeldet";

  const schliessen = useCallback(() => setNavOffen(false), []);

  // Nach jedem Wechsel zu. Ohne das bleibt die Fläche über dem Ziel stehen,
  // das man gerade angetippt hat.
  useEffect(() => setNavOffen(false), [pathname]);

  // Und zu, sobald es nichts mehr zu navigieren gibt. Der Fall ist nicht
  // theoretisch: „Abmelden" steht IN der Fläche. Wer es auf der Startseite
  // anklickt, wechselt die Adresse nicht - die Fläche bliebe also über
  // einer Anwendung stehen, in der sie nichts mehr anzuzeigen hat.
  useEffect(() => {
    if (!navigierbar) setNavOffen(false);
  }, [navigierbar]);

  useEffect(() => {
    if (!navigierbar) return undefined;

    const beiTaste = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // Wer gerade in einem Feld tippt, meint mit Escape dieses Feld -
      // nicht die Navigation. Dasselbe gilt für ein offenes <dialog>, das
      // Escape selbst behandelt.
      if (navOffen) {
        setNavOffen(false);
        return;
      }
      if (tipptGerade()) return;
      if (document.querySelector("dialog[open]")) return;
      setNavOffen(true);
    };

    document.addEventListener("keydown", beiTaste);
    return () => document.removeEventListener("keydown", beiTaste);
  }, [navigierbar, navOffen]);

  // Solange die Fläche offen ist, scrollt die Seite darunter nicht mit.
  // Ohne das wandert der Inhalt weg, während man die Navigation liest, und
  // beim Schließen ist man woanders.
  useEffect(() => {
    if (!navOffen) return undefined;
    const vorher = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = vorher;
    };
  }, [navOffen]);

  return (
    <div className={stil.huelle}>
      <a className={stil.sprung} href="#inhalt">
        Zum Inhalt springen
      </a>

      {!schlicht && (
        <Kopfleiste
          navigierbar={navigierbar}
          navOffen={navOffen}
          beiNavigation={() => setNavOffen((offen) => !offen)}
        />
      )}

      <main id="inhalt" className={schlicht ? stil.inhaltSchlicht : stil.inhalt}>
        {children}
      </main>

      {navOffen && <Navigation beiSchliessen={schliessen} />}
    </div>
  );
}

/** Steht der Schreibpunkt gerade in einem Feld? */
function tipptGerade(): boolean {
  const aktiv = document.activeElement;
  if (!(aktiv instanceof HTMLElement)) return false;
  if (aktiv.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(aktiv.tagName);
}
