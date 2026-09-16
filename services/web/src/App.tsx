import { Route, Routes } from "react-router-dom";

import { Huelle } from "./huelle/Huelle";
import { ModulSeite } from "./seiten/ModulSeite";
import { Start } from "./seiten/Start";

export function App() {
  return (
    <Huelle>
      <Routes>
        <Route path="/" element={<Start />} />
        <Route path="/modul/:id" element={<ModulSeite />} />
        <Route path="*" element={<Start />} />
      </Routes>
    </Huelle>
  );
}
