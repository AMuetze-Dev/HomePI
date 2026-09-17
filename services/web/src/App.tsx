import { Route, Routes } from "react-router-dom";

import { AnmeldungProvider } from "./anmeldung/AnmeldungProvider";
import { Huelle } from "./huelle/Huelle";
import { Anmeldeseite } from "./seiten/Anmeldeseite";
import { ModulSeite } from "./seiten/ModulSeite";
import { Start } from "./seiten/Start";

export function App() {
  return (
    <AnmeldungProvider>
      <Huelle>
        <Routes>
          <Route path="/" element={<Start />} />
          <Route path="/anmelden" element={<Anmeldeseite />} />
          <Route path="/modul/:id" element={<ModulSeite />} />
          <Route path="*" element={<Start />} />
        </Routes>
      </Huelle>
    </AnmeldungProvider>
  );
}
