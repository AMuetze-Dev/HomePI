import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Im Container muss der Server nach aussen lauschen, sonst ist er von
    // Windows aus nicht erreichbar.
    host: "0.0.0.0",
    watch: {
      // Bind-Mounts von Windows reichen keine inotify-Ereignisse durch;
      // ohne Polling bemerkt Vite Dateiaenderungen schlicht nicht.
      usePolling: true,
      interval: 300,
    },
    proxy: {
      // Damit spricht der Browser nur mit dem Vite-Server: kein CORS, keine
      // zweite Adresse in der Konfiguration. In Produktion uebernimmt Traefik
      // diese Rolle, und VITE_API_URL zeigt direkt auf api.<domain>.
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:18000",
        changeOrigin: true,
        rewrite: (pfad) => pfad.replace(/^\/api/, ""),
        configure: (proxy) => {
          // Waehrend das Gateway neu startet, ist es fuer ein paar Sekunden
          // weg. Ohne diesen Handler schreibt Vite einen Stacktrace ins Log
          // und der Browser bekommt eine leere Antwort. Mit ihm bekommt er
          // dasselbe problem+json wie in Produktion - die Oberflaeche zeigt
          // also auch lokal die Meldung, die sie spaeter zeigen wuerde.
          proxy.on("error", (fehler, _anfrage, antwort) => {
            if (!("writeHead" in antwort)) return;
            antwort.writeHead(503, { "Content-Type": "application/problem+json" });
            antwort.end(
              JSON.stringify({
                type: "about:blank",
                title: "Gateway nicht erreichbar",
                status: 503,
                detail: `Der Entwicklungs-Proxy erreicht das Gateway nicht: ${fehler.message}`,
              }),
            );
          });
        },
      },
    },
  },
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
