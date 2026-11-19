import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./styles/index.css";

import { App } from "./App";
import { wendeDarstellungAn } from "./huelle/darstellung";

// Vor dem ersten Rendern, nicht in einem Effekt: Sonst zeigt die Seite
// einen Wimpernschlag lang das Thema des Systems, bevor sie auf die Wahl
// des Benutzers umspringt.
wendeDarstellungAn();

const root = document.getElementById("root");
if (!root) throw new Error("#root fehlt in index.html");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
