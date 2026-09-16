import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Ohne cleanup stapeln sich die gerenderten Baeume und getByRole findet
// ploetzlich mehrere Treffer - eine der haeufigsten Ursachen fuer Tests,
// die einzeln gruen und im Verbund rot sind.
afterEach(() => {
  cleanup();
});
