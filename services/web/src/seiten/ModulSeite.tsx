import { Navigate, useParams } from "react-router-dom";

import { Anmeldeformular } from "../anmeldung/Anmeldeformular";
import { useAnmeldung } from "../anmeldung/kontext";
import { GenerischeAnsicht } from "../module/GenerischeAnsicht";
import { breiteFuer, ersteUnterseite, oberflaecheFuer } from "../module/register";
import { useModule } from "../module/useModule";
import {
  Etikett,
  Hinweis,
  Inhaltsbreite,
  Leerzustand,
  Platzhalter,
  Seitenkopf,
} from "../ui";
import stil from "./ModulSeite.module.css";

export function ModulSeite() {
  const { id = "", unterseite } = useParams();
  const zustand = useModule();
  const { zustand: anmeldung } = useAnmeldung();

  if (zustand.phase === "laedt") {
    return (
      <Inhaltsbreite breite={breiteFuer(id, unterseite)}>
        <div className={stil.laden} role="status" aria-label="Wird geladen">
          <Platzhalter breite="14rem" hoehe="1.75rem" />
          <Platzhalter breite="100%" hoehe="12rem" />
        </div>
      </Inhaltsbreite>
    );
  }

  if (zustand.phase === "fehler") {
    return (
      <Inhaltsbreite breite="normal">
        <Seitenkopf titel="Nicht erreichbar" />
        <Hinweis ton="fehler" dringend>
          {zustand.nachricht}
        </Hinweis>
      </Inhaltsbreite>
    );
  }

  const modul = zustand.module.find((m) => m.id === id);

  if (!modul) {
    // Ein Artefakt, fuer das ein Recht fehlt, steht gar nicht erst im
    // Manifest - von hier aus ist es von einem nicht vorhandenen nicht zu
    // unterscheiden. Wer nicht angemeldet ist, bekommt deshalb nicht die
    // Auskunft "gibt es nicht", sondern die Anmeldung.
    if (anmeldung === "abgemeldet") {
      return (
        <Inhaltsbreite breite="text">
          <Anmeldeformular
            titel="Anmeldung nötig"
            beschreibung="Dieser Bereich ist nicht öffentlich. Melde dich an, um zu sehen, ob er für dich freigeschaltet ist."
          />
        </Inhaltsbreite>
      );
    }

    return (
      <Inhaltsbreite breite="normal">
        <Seitenkopf titel="Unbekanntes Artefakt" />
        <Leerzustand titel={`Kein Modul mit der Kennung „${id}“`}>
          Das Gateway kennt dieses Artefakt nicht. Vermutlich wurde es umbenannt oder ist
          noch nicht ausgerollt.
        </Leerzustand>
      </Inhaltsbreite>
    );
  }

  const eigene = oberflaecheFuer(modul.id);
  const bereiche = eigene?.unterseiten ?? [];
  const erste = ersteUnterseite(modul.id);

  // Ein Modul mit Bereichen ohne Bereich in der Adresse ist kein gueltiger
  // Zustand: Sonst zeigte /modul/staffelpilot etwas anderes als
  // /modul/staffelpilot/uebersicht, und die Leiste markierte nichts.
  if (bereiche.length > 0 && !unterseite && erste) {
    return <Navigate to={`/modul/${modul.id}/${erste}`} replace />;
  }

  // Eine erfundene Adresse fuehrt nicht ins Leere, sondern an den Anfang.
  if (unterseite && bereiche.length > 0 && !bereiche.some((b) => b.id === unterseite)) {
    return <Navigate to={`/modul/${modul.id}/${erste}`} replace />;
  }

  // Die Überschrift ist der BEREICH, nicht das Artefakt: Das Artefakt steht
  // schon in der Kopfleiste darüber („StaffelPilot / Spielprüfung"), und
  // zweimal dasselbe Wort untereinander sagt beim zweiten Mal nichts mehr.
  // Dasselbe gilt für die Beschreibung des Artefakts - sie gehört an den
  // Anfang, nicht über jeden seiner neun Bereiche.
  const offenerBereich = bereiche.find((b) => b.id === unterseite);

  return (
    <Inhaltsbreite breite={breiteFuer(modul.id, unterseite)}>
      {/* Ein Bereich mit `eigenerTitel` baut seinen Kopf selbst - samt dem,
          was nur er kennt: eine Zahl, ein Filter, die eine Handlung dieser
          Fläche. Hier noch eine Überschrift daraufzusetzen hieße, dasselbe
          Wort zweimal untereinander zu schreiben. */}
      {!offenerBereich?.eigenerTitel && (
        <Seitenkopf
          titel={offenerBereich?.wort ?? modul.titel}
          beschreibung={offenerBereich ? undefined : modul.beschreibung || undefined}
          neben={offenerBereich ? undefined : <Etikett mono>v{modul.version}</Etikett>}
        />
      )}

      {/* Bewusst OHNE key auf den Bereich: Ein wechselnder key montierte die
          Modulkomponente bei jedem Bereichswechsel neu - und damit wären die
          geladenen Daten weg, also genau der Nachteil, wegen dessen es hier
          früher gar keine Unterseiten gab. */}
      <div className={stil.inhalt}>
        {eigene ? (
          <eigene.Komponente modul={modul} unterseite={unterseite} />
        ) : (
          <GenerischeAnsicht modul={modul} />
        )}
      </div>
    </Inhaltsbreite>
  );
}
