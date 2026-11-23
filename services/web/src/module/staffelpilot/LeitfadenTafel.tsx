import { Abschnitt, Knopf, Regel, Tafel } from "../../ui";
import stil from "./LeitfadenTafel.module.css";

/**
 * Der Weg durch StaffelPilot, in der Reihenfolge, in der man ihn geht.
 *
 * `ziel` ist ein Bereich aus `src/module/register.ts`. Ein Test hält fest,
 * dass es ihn gibt: ein Verweis auf einen unbekannten Bereich landet stumm auf
 * der Übersicht.
 */
export const SCHRITTE = [
  {
    titel: "Einrichten",
    text: "StaffelPilot braucht deinen DFBnet-Zugang und deine Staffeln. Das Passwort wird verschlüsselt abgelegt, die Staffeln holt er selbst aus DFBnet. Das machst du einmal je Saison.",
    ziel: "einrichten",
    wort: "Zur Einrichtung",
  },
  {
    titel: "Regeln einstellen",
    text: "Alle Regeln der Spielordnung sind vorbelegt, du musst nichts tun. Was du nicht brauchst, schaltest du aus. Bei Fristen kannst du die Werte ändern. Beides gilt nur für dich und die Staffeln, die du leitest.",
    ziel: "regeln",
    wort: "Zu den Regeln",
  },
  {
    titel: "Prüflauf starten",
    text: "Ein Klick, und StaffelPilot liest die Spielberichte aus DFBnet und prüft sie. Das dauert ein paar Minuten; du kannst die Seite so lange verlassen. Berichte, die du in DFBnet schon freigegeben hast, lässt er aus.",
    ziel: "prueflauf",
    wort: "Zum Prüflauf",
  },
  {
    titel: "Befunde entscheiden",
    text: "Was auffällt, steht als Befund am Spiel. Zu jedem entscheidest du: zur Kenntnis nehmen, mit Begründung verwerfen oder ein Schreiben daraus machen. Jede Entscheidung lässt sich zurücknehmen, solange kein Schreiben dazu versandt ist.",
    ziel: "spiele",
    wort: "Zur Spielprüfung",
  },
  {
    titel: "Schreiben vorbereiten",
    text: "Aus einem Befund wird eine Mahnung oder ein Antrag ans Sportgericht, mit festen Sätzen und dem passenden Paragrafen. Verschickt wird nichts: Du liest den Entwurf, änderst ihn, wenn du willst, und sendest ihn aus deinem Mailprogramm.",
    ziel: "vorgaenge",
    wort: "Zu den Vorgängen",
  },
  {
    titel: "Abhaken",
    text: "Sind alle Befunde eines Spiels entschieden, hakst du es ab. Damit wird die Prüferfreigabe in DFBnet vorgemerkt. Eingetragen wird sie erst, wenn du unter „Prüflauf“ die Übertragung freigibst; am Anfang ist sie angehalten.",
    ziel: "spiele",
    wort: "Zur Spielprüfung",
  },
] as const;

const FRAGEN = [
  {
    frage: "Mir reicht es, wenn am selben Tag bestätigt wird. Wo stelle ich das ein?",
    antwort:
      "Unter „Regeln“ die Regel „Bestätigung zu spät“ aufklappen und bei Kulanz 6 Stunden eintragen. Aus 18:00 Uhr wird damit Mitternacht. Für die Freigabe durch den Schiedsrichter gibt es dieselbe Einstellung an „Freigabe des Schiedsrichters zu spät“.",
  },
  {
    frage: "Eine Regel meldet ständig etwas, das mich nicht interessiert.",
    antwort:
      "Schalte sie unter „Regeln“ aus. Ab dem nächsten Prüflauf meldet sie in deinen Staffeln nichts mehr. Wie viele Regeln aus waren, steht im Protokoll des Prüflaufs.",
  },
  {
    frage: "Ich habe etwas verstellt. Wie komme ich zurück?",
    antwort:
      "Der Filter „Angepasst“ zeigt alles, was bei dir von der Vorgabe abweicht. „Auf Vorgabe zurücksetzen“ in der Ausklappung stellt die Werte einer Regel wieder her.",
  },
  {
    frage: "Wir sind mehrere Staffelleiter. Wer stellt was ein?",
    antwort:
      "Jeder hat sein eigenes Konto und seinen eigenen Regelsatz. Welcher an einem Spiel gilt, hängt an der Staffel: an dem, der sie leitet. Das steht unter „Staffeln“, dort kannst du eine Staffel übernehmen oder abgeben. Sehen können zurzeit alle Konten alle Staffeln, und der DFBnet-Zugang ist gemeinsam.",
  },
  {
    frage: "Was passiert mit den Befunden, wenn ich noch einmal prüfe?",
    antwort:
      "Sie werden neu geschrieben. Deine Entscheidungen bleiben dabei stehen, solange Regel und Person dieselben sind.",
  },
] as const;

/**
 * Wie StaffelPilot funktioniert — zum Lesen, nicht zum Durchklicken.
 *
 * Eine Seite und keine Einblendungen über der Oberfläche: Eine Führung, die
 * sich beim ersten Besuch über alles legt, klickt man weg, bevor man weiß,
 * wonach man fragen würde. Diese Seite bleibt da, wenn die Frage kommt.
 */
export function LeitfadenTafel({ onWechsel }: { onWechsel: (ziel: string) => void }) {
  return (
    <Tafel titel="Leitfaden">
      <p className={stil.einleitung}>
        StaffelPilot liest die Spielberichte deiner Staffeln aus DFBnet, vergleicht sie
        mit der Spielordnung und legt dir vor, was auffällt. Was daraus wird, entscheidest
        immer du.
      </p>

      <Abschnitt titel="So geht es" regel>
        <ol className={stil.schritte} aria-label="Die sechs Schritte">
          {SCHRITTE.map((schritt, i) => (
            <li key={schritt.titel} className={stil.schritt}>
              <span className={stil.zahl} aria-hidden="true">
                {i + 1}
              </span>
              <div className={stil.inhalt}>
                <h3 className={stil.titel}>{schritt.titel}</h3>
                <p className={stil.text}>{schritt.text}</p>
                <div>
                  <Knopf groesse="sm" onClick={() => onWechsel(schritt.ziel)}>
                    {schritt.wort}
                  </Knopf>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </Abschnitt>

      <Abschnitt titel="Häufige Fragen" regel>
        <div className={stil.fragen}>
          {FRAGEN.map((f) => (
            <div key={f.frage}>
              <h3 className={stil.titel}>{f.frage}</h3>
              <p className={stil.text}>{f.antwort}</p>
              <Regel kurz className={stil.linie} />
            </div>
          ))}
        </div>
      </Abschnitt>
    </Tafel>
  );
}
