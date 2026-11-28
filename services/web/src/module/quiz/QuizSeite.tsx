import { Anmeldeformular } from "../../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../../anmeldung/kontext";
import { Hinweis, Tafel } from "../../ui";
import type { ModulProps } from "../typen";
import { AnzeigeTafel } from "./AnzeigeTafel";
import { KatalogTafel } from "./KatalogTafel";
import { Leiten } from "./Leiten";
import { SpielerTafel } from "./SpielerTafel";

/**
 * Drei Wege, und zwei davon gehen ohne Konto.
 *
 * **Mitspielen** und **Leiten** stehen jedem offen: Wer eine Runde startet,
 * leitet sie mit einem Moderatorcode, nicht mit einem Konto. Die
 * **Anzeigetafel** ist kein eigener Bereich mehr - sie öffnet die Leitung
 * für den Beamer. **Kataloge** pflegt nur, wer ein Recht hat; geprüft wird
 * im Backend noch einmal.
 */
export function QuizSeite({ unterseite = "spielen" }: ModulProps) {
  const { darf, zustand } = useAnmeldung();

  if (unterseite === "spielen") return <SpielerTafel />;
  if (unterseite === "tafel") return <AnzeigeTafel />;
  if (unterseite === "leiten") return <Leiten />;

  if (!darf("quiz", "leser")) {
    return (
      <Tafel titel="Fragenkataloge">
        <Hinweis>
          Kataloge pflegt, wer ein Konto mit Recht auf das Quiz hat. Eine Runde leiten
          kann jeder - unter „Leiten“, mit einem freigegebenen oder dem eigenen Quiz.
        </Hinweis>
        {zustand === "abgemeldet" && (
          <Anmeldeformular
            titel="Anmeldung nötig"
            beschreibung="Zum Pflegen von Katalogen brauchst du ein Recht auf diesem Artefakt."
          />
        )}
      </Tafel>
    );
  }

  return (
    <KatalogTafel
      darfLeiten={darf("quiz", "nutzer")}
      darfVerwalten={darf("quiz", "verwalter")}
    />
  );
}
