import type { ReactNode } from "react";

import { useAnmeldung } from "./kontext";
import { Passwortwechsel } from "./Passwortwechsel";

/**
 * Führt zum Passwortwechsel, solange einer aussteht.
 *
 * Kein Schutz, sondern Führung: das Backend weist ein Konto mit vergebenem
 * Startpasswort an jedem Artefakt ab, unabhängig davon, was hier gerendert
 * wird. Ohne dieses Tor sähe der Benutzer nur eine leere Übersicht und wüsste
 * nicht, warum.
 */
export function Passwortwechseltor({ children }: { children: ReactNode }) {
  const { mussPasswortWechseln } = useAnmeldung();

  if (mussPasswortWechseln) return <Passwortwechsel />;

  return <>{children}</>;
}
