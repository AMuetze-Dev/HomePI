import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { manifestVerwerfen } from "./module/useModule";

// Ohne cleanup stapeln sich die gerenderten Baeume und getByRole findet
// ploetzlich mehrere Treffer - eine der haeufigsten Ursachen fuer Tests,
// die einzeln gruen und im Verbund rot sind.
//
// Das Manifest liegt aus demselben Grund hier: Es wird bewusst zwischen
// Ansichten geteilt, damit Leiste und Seite es nicht doppelt holen. Ein
// Zwischenspeicher, der den Test ueberlebt, zeigt dem naechsten aber die
// Daten des vorigen - und der sucht dann lange nach seinem Fehler.
afterEach(() => {
  cleanup();
  manifestVerwerfen();
});
