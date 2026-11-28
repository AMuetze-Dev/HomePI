import { useEffect, useRef, type ReactNode } from "react";

import { SymbolKnopf } from "./Symbol";
import stil from "./Quiz.module.css";

/**
 * Ein Dialog über dem Dashboard - für alles, was gebraucht wird, aber nicht
 * dauernd zu sehen sein muss: QR-Code, Teams, Auswertung, Moderatorcode.
 *
 * Auf dem nativen `<dialog>`: Fokusfalle, Escape und der Hintergrund, der
 * nicht mehr anklickbar ist, kommen vom Browser. Die Hülle weiß davon und
 * öffnet bei Escape nicht ihre Navigation (`dialog[open]`).
 */
export function Dialog({
  titel,
  offen,
  schliessen,
  breit = false,
  children,
}: {
  titel: string;
  offen: boolean;
  schliessen: () => void;
  breit?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (offen && !element.open) {
      // jsdom kennt showModal nicht; dort genügt das Attribut.
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
    if (!offen && element.open) {
      if (typeof element.close === "function") element.close();
      else element.removeAttribute("open");
    }
  }, [offen]);

  if (!offen) return null;
  return (
    <dialog
      ref={ref}
      className={stil.dialog}
      data-breit={breit || undefined}
      aria-label={titel}
      onCancel={(e) => {
        e.preventDefault();
        schliessen();
      }}
      onClick={(e) => {
        // Ein Klick auf den abgedunkelten Rand schliesst - wie überall.
        if (e.target === e.currentTarget) schliessen();
      }}
    >
      <div className={stil.dialogInhalt}>
        <header className={stil.dialogKopf}>
          <h2 className={stil.dialogTitel}>{titel}</h2>
          <SymbolKnopf symbol="kreuz" name="Schließen" onClick={schliessen} />
        </header>
        {children}
      </div>
    </dialog>
  );
}
