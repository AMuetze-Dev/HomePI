import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

/**
 * Seitenbezug für Bemerkungen: Tippt man im PDF auf „S. 7“, landet „S. 7: “
 * im zuletzt benutzten Bemerkungsfeld.
 *
 * Das Ziel ist das ZULETZT benutzte Feld, nicht das gerade fokussierte - der
 * Fokus wandert ja beim Antippen der Seite aus dem Feld heraus.
 */
type Einfuegen = (text: string) => void;

interface Zitat {
  hatZiel: boolean;
  /** Ein Bemerkungsfeld meldet sich als Ziel an; null meldet es ab. */
  setzeZiel: (ziel: Einfuegen | null, von?: Einfuegen) => void;
  zitiere: (seite: number) => void;
}

const Kontext = createContext<Zitat | null>(null);

export function ZitatBereich({ children }: { children: React.ReactNode }) {
  const ziel = useRef<Einfuegen | null>(null);
  const [hatZiel, setHatZiel] = useState(false);

  const setzeZiel = useCallback((neu: Einfuegen | null, von?: Einfuegen) => {
    // Abmelden nur, wenn das Feld noch das Ziel ist - sonst nähme ein
    // verschwindendes Feld einem anderen sein Ziel weg.
    if (neu === null && von !== undefined && ziel.current !== von) return;
    ziel.current = neu;
    setHatZiel(neu !== null);
  }, []);

  const zitiere = useCallback((seite: number) => {
    ziel.current?.(`S. ${seite}: `);
  }, []);

  const wert = useMemo(
    () => ({ hatZiel, setzeZiel, zitiere }),
    [hatZiel, setzeZiel, zitiere],
  );
  return <Kontext.Provider value={wert}>{children}</Kontext.Provider>;
}

/** null außerhalb eines ZitatBereichs - dann gibt es den Seitenbezug nicht. */
export function useZitat(): Zitat | null {
  return useContext(Kontext);
}
