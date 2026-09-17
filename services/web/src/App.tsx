import { Route, Routes } from "react-router-dom";

import { AnmeldungProvider } from "./anmeldung/AnmeldungProvider";
import { Einrichtungstor } from "./einrichtung/Einrichtungstor";
import { Huelle } from "./huelle/Huelle";
import { Anmeldeseite } from "./seiten/Anmeldeseite";
import { ModulSeite } from "./seiten/ModulSeite";
import { Start } from "./seiten/Start";

export function App() {
  return (
    <AnmeldungProvider>
      {/* Vor allem anderen: hat diese Installation überhaupt schon ein Konto?
          Solange nicht, hat keine andere Ansicht Sinn - das Tor bringt für
          diesen Fall seine eigene, schlichte Hülle mit. */}
      <Einrichtungstor>
        <Huelle>
          <Routes>
            <Route path="/" element={<Start />} />
            <Route path="/anmelden" element={<Anmeldeseite />} />
            <Route path="/modul/:id" element={<ModulSeite />} />
            <Route path="*" element={<Start />} />
          </Routes>
        </Huelle>
      </Einrichtungstor>
    </AnmeldungProvider>
  );
}
