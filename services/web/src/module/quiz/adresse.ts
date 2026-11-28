import { useEffect, useState } from "react";

import { fetchOeffentlicheUrl } from "../../api/client";

/** Die Adresse, unter der Mitspieler direkt in diese Runde kommen. */
export function beitrittsAdresse(basis: string, code: string): string {
  return `${basis.replace(/\/$/, "")}/modul/quiz/spielen?code=${code}`;
}

/** Die Adresse, unter der ein anderes Gerät die Leitung übernimmt. */
export function leitungsAdresse(basis: string, moderatorcode: string): string {
  return `${basis.replace(/\/$/, "")}/modul/quiz/leiten?zugang=${encodeURIComponent(moderatorcode)}`;
}

/** Die öffentliche Adresse, sonst die, unter der die Seite gerade läuft. */
export function useBasisAdresse(): string | null {
  const [basis, setBasis] = useState<string | null>(null);
  useEffect(() => {
    const abbruch = new AbortController();
    fetchOeffentlicheUrl(abbruch.signal)
      .then((url) => setBasis(url ?? window.location.origin))
      .catch(() => {
        if (!abbruch.signal.aborted) setBasis(window.location.origin);
      });
    return () => abbruch.abort();
  }, []);
  return basis;
}
