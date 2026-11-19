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

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("beruhigt, wenn alles läuft", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);

    render(<SystemStatus />);

    expect(await screen.findByText(/Alle Systeme betriebsbereit/)).toBeInTheDocument();
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
  });

  it("nennt im Normalfall keine einzelne Abhängigkeit", async () => {
    // Die Zeile soll beruhigen, nicht aufzählen. Erst wenn etwas nicht
    // stimmt, wird sie konkret.
    vi.spyOn(client, "fetchHealth").mockResolvedValue(gesund);

    render(<SystemStatus />);
    await screen.findByText(/Alle Systeme betriebsbereit/);

    expect(screen.queryByText(/database/)).not.toBeInTheDocument();
  });

  it("benennt die gestörte Abhängigkeit statt nur 'Fehler'", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue({
      status: "down",
      version: "0.1.0",
      checks: { database: false, cache: true },
    });

    render(<SystemStatus />);

    expect(await screen.findByText(/Störung/)).toBeInTheDocument();
    expect(screen.getByText(/gestört: database/)).toBeInTheDocument();
  });

  it("unterscheidet eingeschränkt von Störung", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue({
      status: "degraded",
      version: "0.1.0",
      checks: { database: true, cache: false },
    });

    render(<SystemStatus />);

    expect(await screen.findByText(/Eingeschränkt betriebsbereit/)).toBeInTheDocument();
    expect(screen.getByText(/gestört: cache/)).toBeInTheDocument();
  });

  it("meldet, wenn das Backend gar nicht antwortet", async () => {
    vi.spyOn(client, "fetchHealth").mockRejectedValue(new Error("Network down"));

    render(<SystemStatus />);

    const meldung = await screen.findByRole("alert");
    expect(meldung).toHaveTextContent(/nicht erreichbar/);
    expect(meldung).toHaveTextContent(/Network down/);
  });
});
