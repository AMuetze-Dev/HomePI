import { useEffect, useState } from "react";

import { restSekunden } from "./abruf";
import stil from "./Quiz.module.css";

/**
 * Die verbleibende Zeit, nach der Uhr des Servers.
 *
 * Viermal je Sekunde neu gezeichnet, nicht einmal: sonst springt die Zahl
 * je nach Takt des Abrufs mal nach 0,1 und mal nach 0,9 Sekunden um.
 */
export function Countdown({ frist, versatz }: { frist: string; versatz: number }) {
  const [rest, setRest] = useState(() => restSekunden(frist, versatz));

  useEffect(() => {
    setRest(restSekunden(frist, versatz));
    const uhr = window.setInterval(() => setRest(restSekunden(frist, versatz)), 250);
    return () => window.clearInterval(uhr);
  }, [frist, versatz]);

  return (
    <span
      className={stil.countdown}
      data-knapp={rest <= 5}
      role="timer"
      aria-label={`Noch ${rest} Sekunden`}
    >
      {rest > 0 ? `${rest} s` : "Zeit um"}
    </span>
  );
}
