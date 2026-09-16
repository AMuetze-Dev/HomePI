import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/main.tsx",
        "src/setupTests.ts",
        "src/**/*.test.{ts,tsx}",
        "src/**/*.d.ts",
      ],
      // Die Schwelle ist das eigentliche Sicherheitsnetz. Sie darf steigen,
      // aber niemals sinken - wer sie senkt, muss das im PR begruenden.
      thresholds: {
        lines: 85,
        functions: 85,
        branches: 80,
        statements: 85,
      },
    },
  },
});
