import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as client from "./api/client";
import { App } from "./App";

describe("App", () => {
  it("rendert Titel und Systemstatus", async () => {
    vi.spyOn(client, "fetchHealth").mockResolvedValue({
      status: "ok",
      version: "0.1.0",
      checks: { database: true },
    });

    render(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("HomePI");
    expect(await screen.findByRole("heading", { level: 2 })).toBeInTheDocument();
  });
});
