import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";

/**
 * Der Weg zur API - fuer den Entwicklungsserver UND fuer die Vorschau.
 *
 * Damit spricht der Browser nur mit dem Vite-Server: kein CORS, keine zweite
 * Adresse in der Konfiguration. In Produktion uebernimmt Traefik diese Rolle,
 * und VITE_API_URL zeigt direkt auf api.<domain>.
 *
 * Beide brauchen ihn, und zwar denselben: die Oberflaechentests laufen gegen
 * die Vorschau (`vite preview`), also gegen das fertige Bundle. Zwei Fassungen
 * dieses Proxys waeren zwei Stellen, an denen der Weg zur API auseinanderlaufen
 * kann - und der Unterschied fiele erst im Test auf, nicht hier.
 */
const API_PROXY: Record<string, ProxyOptions> = {
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
};

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
    proxy: API_PROXY,
  },

  /**
   * Die Vorschau liefert das gebaute Bundle aus - fertig uebersetzt.
   *
   * Hier laufen die Oberflaechentests. Der Entwicklungsserver uebersetzt die
   * Anwendung erst, wenn ein Browser sie zum ersten Mal anfordert, und das
   * waechst mit jedem Artefakt: zwanzigtausend Zeilen Modul-Oberflaeche wollen
   * beim ersten Aufruf durch esbuild. Auf einem ausgelasteten CI-Runner hat
   * das die Tests gekippt, bevor einer von ihnen etwas geprueft hatte.
   *
   * Der Port kommt von der Kommandozeile (`--port`), damit die Testumgebung
   * ihren eigenen benutzen kann und niemals den der Entwicklungsumgebung.
   */
  preview: {
    host: "127.0.0.1",
    proxy: API_PROXY,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    css: false,
    // Die Oberflaechentests gehoeren Playwright: sie brauchen einen echten
    // Browser und eine laufende Instanz. Vitest wuerde sie sonst einsammeln
    // und an "test is not defined" scheitern.
    include: ["src/**/*.{test,spec}.{ts,tsx}", "pruefungen/**/*.test.ts"],
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
