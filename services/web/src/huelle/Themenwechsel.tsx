import stil from "./Themenwechsel.module.css";
import { useThema } from "./useThema";

export function Themenwechsel() {
  const { istDunkel, wechsle } = useThema();

  return (
    <button
      type="button"
      className={stil.knopf}
      onClick={wechsle}
      aria-label={
        istDunkel
          ? "Zu hellem Erscheinungsbild wechseln"
          : "Zu dunklem Erscheinungsbild wechseln"
      }
      title={istDunkel ? "Heller Modus" : "Dunkler Modus"}
    >
      {istDunkel ? <Sonne /> : <Mond />}
    </button>
  );
}

/* Symbole inline statt als Paket: zwei Pfade rechtfertigen keine Abhängigkeit,
   und so erben sie die Farbe ohne Umweg. */

function Sonne() {
  return (
    <svg
      className={stil.symbol}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1v1.5M8 13.5V15M15 8h-1.5M2.5 8H1M12.95 3.05l-1.06 1.06M4.11 11.89l-1.06 1.06M12.95 12.95l-1.06-1.06M4.11 4.11L3.05 3.05" />
    </svg>
  );
}

function Mond() {
  return (
    <svg
      className={stil.symbol}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1Z" />
    </svg>
  );
}
