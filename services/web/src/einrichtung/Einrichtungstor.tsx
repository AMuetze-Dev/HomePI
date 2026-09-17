import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { holeStand } from "../api/einrichtung";
import { Huelle } from "../huelle/Huelle";
import { Platzhalter } from "../ui";
import { Einrichtungsmaske } from "./Einrichtungsmaske";

/**
 * Entscheidet beim Start, ob diese Installation erst eingerichtet werden muss.
 *
 * Solange es keinen Verwalter gibt, hat jede andere Ansicht keinen Sinn: das
 * Manifest wäre leer, die Anmeldung hätte kein Konto anzubieten. Deshalb ein
 * Tor und keine Route - wer irgendeine Adresse aufruft, landet hier.
 *
 * Kein Schutz, sondern Führung. Ob wirklich eingerichtet werden darf,
 * entscheidet das Backend bei jedem Aufruf neu.
 */
export function Einrichtungstor({ children }: { children: ReactNode }) {
  const [noetig, setNoetig] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    holeStand(controller.signal)
      .then((stand) => setNoetig(stand.noetig))
      .catch(() => {
        if (controller.signal.aborted) return;
        // Antwortet das Gateway nicht, ist "nicht nötig" die richtige
        // Annahme: dann zeigt die Anwendung ihre gewohnten Fehlermeldungen,
        // statt einem Besucher eine Einrichtungsmaske vorzusetzen, die er
        // ohnehin nicht ausfüllen kann.
        setNoetig(false);
      });

    return () => controller.abort();
  }, []);

  const fertig = useCallback(() => setNoetig(false), []);

  // Waehrend der Einrichtung bringt das Tor seinen eigenen Rahmen mit: die
  // schlichte Huelle ohne Benutzerleiste. Ein "Anmelden" neben einer Maske,
  // die gerade erst das erste Konto anlegt, waere eine Einladung ins Leere.
  if (noetig === null) {
    return (
      <Huelle schlicht>
        <div role="status" aria-label="Wird geladen">
          <Platzhalter breite="100%" hoehe="12rem" />
        </div>
      </Huelle>
    );
  }

  if (noetig) {
    return (
      <Huelle schlicht>
        <Einrichtungsmaske onFertig={fertig} />
      </Huelle>
    );
  }

  return <>{children}</>;
}
