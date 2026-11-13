import { Route, Routes } from "react-router-dom";

import { AnmeldungProvider } from "./anmeldung/AnmeldungProvider";
import { Passwortwechseltor } from "./anmeldung/Passwortwechseltor";
import { Einrichtungstor } from "./einrichtung/Einrichtungstor";
import { Huelle } from "./huelle/Huelle";
import { Anmeldeseite } from "./seiten/Anmeldeseite";
import { Einstellungen } from "./seiten/Einstellungen";
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
          {/* Wer noch das vergebene Startpasswort hat, kommt an kein
              Artefakt - also auch nicht an eine Ansicht davon. */}
          <Passwortwechseltor>
            <Routes>
              <Route path="/" element={<Start />} />
              <Route path="/anmelden" element={<Anmeldeseite />} />
              {/* Die Einstellungen gehören dem Konto, nicht einem Artefakt -
                  deshalb eine eigene Adresse neben den Modulen und nicht
                  eine Unterseite der Nutzerverwaltung. */}
              <Route path="/einstellungen" element={<Einstellungen />} />
              <Route path="/modul/:id" element={<ModulSeite />} />
              {/* Bereiche sind echte Adressen: verlinkbar, mit dem
                  Zurück-Knopf erreichbar, und ein Neuladen landet dort,
                  wo man war. Die Modulkomponente bleibt dabei montiert,
                  der Wechsel kostet keinen Abruf. */}
              <Route path="/modul/:id/:unterseite" element={<ModulSeite />} />
              <Route path="*" element={<Start />} />
            </Routes>
          </Passwortwechseltor>
        </Huelle>
      </Einrichtungstor>
    </AnmeldungProvider>
  );
}
