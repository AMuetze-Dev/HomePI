import type { ComponentType } from "react";

import type { ModulEintrag } from "../api/client";

/**
 * Der Vertrag zwischen einem Artefakt und der Startseite.
 *
 * Eine eigene Oberfläche ist optional. Ohne sie bekommt das Modul die
 * generische Ansicht, die seine Endpunkte aus dem OpenAPI-Schema liest -
 * ein neues Artefakt ist damit sofort benutzbar, auch bevor jemand ein
 * Frontend dafür geschrieben hat.
 */
export interface ModulOberflaeche {
  /** Muss der Kennung aus dem Backend-Manifest entsprechen. */
  id: string;
  Komponente: ComponentType<{ modul?: ModulEintrag }>;
}
