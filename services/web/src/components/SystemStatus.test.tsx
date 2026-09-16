import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as client from "../api/client";
import { SystemStatus } from "./SystemStatus";

afterEach(() => {
  vi.restoreAllMocks();
});

const gesund: client.Health = {
  status: "ok",
  version: "0.1.0",
  checks: { database: true },
};

describe("SystemStatus", () => {
  it("zeigt zuerst einen Ladehinweis", () => {
    vi.spyOn(client, "fetchHealth").mockReturnValue(new Promise(() => {}));

    render(<SystemStatus />);

    expect(screen.getByRole("status")).toHaveTextContent(/geladen/i);
  });

  it("zeigt den Zustand, sobald er da ist", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);

    render(<SystemStatus />);

    expect(await screen.findByRole("heading")).toHaveTextContent("Alle Systeme laufen");
    expect(screen.getByText(/Version 0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/database: in Ordnung/)).toBeInTheDocument();
  });

  it("benennt die gestörte Abhängigkeit statt nur 'Fehler'", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue({
      status: "down",
      version: "0.1.0",
      checks: { database: false },
    });

    render(<SystemStatus />);

    expect(await screen.findByRole("heading")).toHaveTextContent("Ausfall");
    expect(screen.getByText(/database: gestört/)).toBeInTheDocument();
  });

  it("meldet, wenn das Backend gar nicht antwortet", async () => {
    vi.spyOn(client, "fetchHealth").mockRejectedValue(new Error("Network down"));

    render(<SystemStatus />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Network down/);
  });
});
