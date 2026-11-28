import { Anmeldeformular } from "../../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../../anmeldung/kontext";
import { Hinweis, Tafel } from "../../ui";
import type { ModulProps } from "../typen";
import { AnzeigeTafel } from "./AnzeigeTafel";
import { KatalogTafel } from "./KatalogTafel";
import { LeitungTafel } from "./LeitungTafel";
import { SpielerTafel } from "./SpielerTafel";

/**
 * Vier Bereiche, und zwei davon gehen ohne Konto.
 *
 * „Mitspielen“ und „Anzeigetafel“ sind der Grund, warum dieses Artefakt
 * öffentlich ist - wer die Kachel ohne Konto antippt, landet beim
 * Mitspielen. „Runden“ und „Kataloge“ gehören der Leitung; dort hängt
 * alles an `darf("quiz", …)` und wird im Backend noch einmal geprüft.
 */
export function QuizSeite({ unterseite = "spielen" }: ModulProps) {
  const { darf, zustand } = useAnmeldung();

  if (unterseite === "spielen") return <SpielerTafel />;
  if (unterseite === "tafel") return <AnzeigeTafel />;

  const titel = unterseite === "kataloge" ? "Fragenkataloge" : "Runden";
  if (!darf("quiz", "leser")) {
    return (
      <Tafel titel={titel}>
        <Hinweis>
          Diesen Bereich führt die Spielleitung. Mitspielen geht ohne Konto - unter
          „Mitspielen“ mit dem Code der Runde.
        </Hinweis>
        {zustand === "abgemeldet" && (
          <Anmeldeformular
            titel="Anmeldung nötig"
            beschreibung="Zum Leiten einer Runde brauchst du ein Recht auf diesem Artefakt."
          />
        )}
      </Tafel>
    );
  }

  return unterseite === "kataloge" ? (
    <KatalogTafel
      darfLeiten={darf("quiz", "nutzer")}
      darfVerwalten={darf("quiz", "verwalter")}
    />
  ) : (
    <LeitungTafel darfLeiten={darf("quiz", "nutzer")} />
  );
}
