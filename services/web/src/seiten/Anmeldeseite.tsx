import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { Anmeldeformular } from "../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../anmeldung/kontext";

/** Eigene Adresse für die Anmeldung, damit ein Lesezeichen und der Zurück-Knopf
 *  funktionieren. Wer schon angemeldet ist, hat hier nichts zu suchen. */
export function Anmeldeseite() {
  const { zustand } = useAnmeldung();
  const navigate = useNavigate();

  useEffect(() => {
    if (zustand === "angemeldet") void navigate("/", { replace: true });
  }, [zustand, navigate]);

  if (zustand === "angemeldet") return null;

  return <Anmeldeformular />;
}
