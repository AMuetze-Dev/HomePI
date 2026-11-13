# 08 — Designsystem

Ruhig, strukturiert, wertig. Das Ziel ist nicht, aufzufallen, sondern
vertrauenswürdig zu wirken: eine Oberfläche, der man einen Blick lang ansieht,
dass jemand über sie nachgedacht hat — und die einem danach nicht mehr im Weg
steht.

## Fünf Regeln

1. **Wertigkeit entsteht aus Abstufung, nicht aus Kontrast.** Die neutrale
   Skala ist eng gestuft. Wo ein Sprung nötig wäre, fehlt meist Struktur.
2. **Farbe trägt Bedeutung, nicht Dekoration.** Es gibt genau drei
   Signalfarben, alle entsättigt, und **einen** Akzent. Der Akzent tritt als
   Linie, Rand und Punkt auf, nie als gefüllte Fläche: Bei dieser Dichte ist
   ein geschlossener Farbblock das Erste, was auf einer Seite laut wird.
3. **Typografie macht die Hierarchie, nicht Linien und Kästen.** Größe, Gewicht
   und Abstand reichen. Rahmen trennen Ebenen, sie betonen nichts.
4. **Bewegung bestätigt, sie inszeniert nicht.** Nichts über 250 ms, nichts mit
   Überschwingen.
5. **Weniger Elemente, mehr Luft.** Jedes zusätzliche Element muss sich gegen
   den Weißraum rechtfertigen, den es kostet.

## Aufbau

```
src/styles/tokens.css   alle Werte - Farben, Typo, Maße, Bewegung
src/styles/basis.css    Reset und Elementgrundlagen
src/ui/                 Bausteine (Knopf, Karte, Feld, Regel, Marke, …)
src/huelle/             Rahmen: Kopfleiste, Navigationsfläche, Darstellung
src/module/register.ts  was jedes Artefakt an Platz und Bereichen anmeldet
src/seiten/             Ansichten, einschließlich der Einstellungen
```

Jede Komponente bringt ihr eigenes `*.module.css` mit. CSS Modules statt einer
Utility-Bibliothek: die Klassennamen bleiben lesbar, das Markup bleibt frei von
Stilrauschen, und es kommt keine Abhängigkeit dazu. Der Vite-Build kann das von
Haus aus.

**Eine Komponente greift nie zu einem festen Wert.** Jede Farbe, jeder Abstand,
jede Dauer kommt aus einem Token. Sobald irgendwo `#f5f5f5` oder `13px` steht,
beginnt das Erscheinungsbild auseinanderzulaufen.

## Tokens

### Farbe

Die Namen beschreiben die **Rolle**, nicht den Wert: `--farbe-text-leise` statt
`--grau-500`. Dadurch ist der Dunkelmodus eine Frage der Werte, nicht der
Komponenten.

| Token                                    | Verwendung                                              |
| ---------------------------------------- | ------------------------------------------------------- |
| `--farbe-grund`                          | Seitenhintergrund                                       |
| `--farbe-flaeche`                        | Karten, Eingabefelder                                   |
| `--farbe-flaeche-gedaempft`              | Zeilen beim Zeigen, Felder zum Nachsehen                |
| `--farbe-rand` / `--farbe-rand-stark`    | Ränder von Kästen und Feldern                           |
| `--farbe-linie`                          | die ausblendende Trennlinie (`<Regel>`)                 |
| `--farbe-text` / `-gedaempft` / `-leise` | drei Stufen, mehr braucht es nicht                      |
| `--farbe-akzent`                         | Linie, Rand, Punkt — der Akzent als **Kante**           |
| `--farbe-akzent-schrift`                 | derselbe Akzent als **Schrift**, eine Stufe tiefer      |
| `--farbe-akzent-fuellung` / `-spur`      | 10 % bzw. 7 % Akzent — die einzigen Akzentflächen       |
| `--farbe-aktion`                         | Marken, aktive Kanten; zeigt auf den Akzent             |
| `--farbe-fokus`                          | Fokusring — ebenfalls der Akzent, kein zweites Blau     |
| `--signal-gut` / `-warnung` / `-fehler`  | Zustände, je mit `-flaeche`                             |

**Kante und Schrift sind zwei Tokens, und das ist kein Luxus.** Das Paar
Akzent/Grund ist auf 3:1 gestimmt — genug für Symbole, große Schrift und
Bedienränder, nicht für einen Absatz. Wo der Akzent als Text in Lesegröße
steht, gilt `--farbe-akzent-schrift`; wo er eine Linie ist, `--farbe-akzent`.
Auf hellem Grund liegen zwei Rampenstufen dazwischen.

Hell und Dunkel stehen über `light-dark()` in **einer** Deklaration:

```css
--farbe-grund: light-dark(var(--ton-100), var(--ton-950));
```

Das ist kein Schönheitsgewinn, sondern der Grund, warum die beiden Schemata
nicht auseinanderlaufen können: es gibt keinen zweiten Satz Farben, den man
vergessen könnte mitzupflegen. Der Umschalter setzt nur `color-scheme`.

Der Dunkelmodus ist **kein invertierter Hellmodus**. Im Dunkeln braucht es
weniger Kontrast, nicht denselben; Flächen werden angehoben statt Schatten
verstärkt. Gezeichnet wurde der Entwurf für Dunkel; die hellen Werte sind in
derselben Farbfamilie daraus abgeleitet. Wer die Palette ändert, ändert beide
Seiten in einem Zug.

### Typografie

`--schrift` nennt **Inter zuerst** und fällt auf den Systemstapel zurück.
Geladen wird Inter **nicht**: Ein Webfont von einem fremden Server
widerspricht dem Zweck dieser Installation, und lokal eingebunden kostet er
den ersten Seitenaufbau. Wer Inter installiert hat, sieht Inter; alle anderen
den Systemstapel, der auf jeder Plattform nativ optimiert rendert.

| Token        | Größe | Verwendung                    |
| ------------ | ----- | ----------------------------- |
| `--text-xs`  | 12 px | Etiketten, Pfade, Versionen   |
| `--text-sm`  | 13 px | Sekundärtext, Tabellen        |
| `--text-md`  | 14 px | **Basisgröße der Oberfläche** |
| `--text-lg`  | 16 px | Abschnittsüberschriften       |
| `--text-xl`  | 19 px | „Übersicht" in der Navigation |
| `--text-2xl` | 24 px | Seitentitel, Artefaktnamen    |
| `--text-3xl` | 32 px | Artefakte auf der Startseite  |
| `--text-4xl` | 40 px | die Begrüßung, und sonst nichts |

Überschriften tragen Gewicht **500**, nicht 600: Die Hierarchie entsteht hier
aus Größe und Abstand. Eine fette Überschrift über dünnem Fließtext wirkt bei
dieser Dichte gedrängt statt geordnet. 600 bleibt für Etiketten,
Tabellenköpfe und Zahlen, die hervorstehen sollen.

Negative Laufweite (`--laufweite-eng`, `--laufweite-enger`) erst ab
Überschriftengröße — im Fließtext macht sie die Zeile schlechter lesbar, nicht
besser. Positiv wird sie nur in den gesperrten Kapitälchen über einem
Abschnitt (`--laufweite-weit`) und in der Wortmarke (`--laufweite-marke`).
Zahlen laufen durchgehend mit `tabular-nums`, damit Spalten nicht tanzen.

**Inter wirklich mitliefern**, falls gewünscht: die woff2-Datei unter
`public/schriften/` ablegen und eine `@font-face`-Regel in `basis.css`
ergänzen — `--schrift` nennt sie bereits an erster Stelle. Bewusst nicht von
Google Fonts: Das wäre eine Abhängigkeit vom Internet für eine Anwendung, die
gerade deshalb im eigenen Netz läuft.

### Maß und Bewegung

Vierer-Raster: `--raum-1` (4 px) bis `--raum-20` (80 px). Jeder Abstand im
Produkt ist ein Vielfaches davon.

Rundungen: `--rundung-sm` 4 px (Etiketten, Tasten), `--rundung-md` 8 px
(Knöpfe, Felder, Monogramme), `--rundung-lg` 14 px (Karten).

| Dauer                    | Wofür                      |
| ------------------------ | -------------------------- |
| `--dauer-sofort` 80 ms   | Druckpunkt beim Klick      |
| `--dauer-schnell` 140 ms | Zeigen, Fokus, Farbwechsel |
| `--dauer-normal` 220 ms  | Eintritt von Inhalten      |

Zwei Verläufe: `--verlauf` für Zustandswechsel, `--verlauf-eintritt` für
erscheinende Elemente. Beide ohne Überschwingen.

## Bausteine

| Komponente      | Zweck                                                            |
| --------------- | ---------------------------------------------------------------- |
| `Knopf`         | drei Ausprägungen: `primaer`, `sekundaer`, `leise`               |
| `Karte`         | abgegrenzte Fläche; `blank` für Inhalte mit eigenem Innenabstand |
| `Feld`          | Eingabe mit verbundener Beschriftung                             |
| `Tafel`         | der Kopf einer Fläche: Titel, Zahl daneben, Handlungen rechts    |
| `Tabelle` + `Reihe` + `Zelle` | dichte Liste in Spalten, Reihen klappen auf       |
| `Regel`         | die ausblendende Trennlinie; `kurz` für schmale Spalten          |
| `Marke`         | vier Felder, eines im Akzent — Zeichen und Navigationsknopf      |
| `Monogramm`     | Kürzel für ein Konto (zwei Buchstaben) oder ein Artefakt (einer) |
| `Segmentwahl`   | zwei bis vier Möglichkeiten, auf echten Optionsfeldern           |
| `Schalter`      | ein Zustand, der sofort gilt, auf einem echten Kästchen          |
| `Etikett`       | kompakter Zustand oder Kennung; `mono` für Technisches           |
| `Statuspunkt`   | reine Dekoration, Bedeutung steht im Text daneben                |
| `Hinweis`       | Meldung mit `role="alert"` oder `role="status"`                  |
| `Leerzustand`   | Erstzustand mit Erklärung, was als Nächstes zu tun ist           |
| `Platzhalter`   | Skelett während des Ladens                                       |
| `Seitenkopf`    | Titel, Beschreibung, Zurück-Verweis                              |
| `Inhaltsbreite` | begrenzt eine Ansicht auf die angemeldete Stufe                  |

**Es gibt genau drei Knopf-Ausprägungen, und das ist Absicht.** Sobald eine
vierte dazukommt, hat die Seite eine Hierarchie zu viel und keine ist mehr klar.
Die Primäraktion ist dabei ein **Akzentrand auf fast nichts**, keine gefüllte
Fläche: In einer Tabellenzeile mit drei Knöpfen stünden sonst drei Farbblöcke.

Deaktiviert heißt gedämpft, nicht durchscheinend: bloße Transparenz macht aus
einem Primärknopf einen schweren grauen Block, der mehr Aufmerksamkeit zieht
als der aktive daneben.

**Segmentwahl und Schalter sitzen auf nativen Elementen** — Optionsfeld und
Kästchen. Pfeiltasten, Gruppenansage und die Frage „welches ist gewählt"
bringt der Browser mit; ein nachgebautes Element müsste das erst wieder
lernen, und es lernt es erfahrungsgemäß halb. Das Feld selbst ist unsichtbar,
aber nicht `display: none` — damit verschwände es auch aus der Tastaturfolge.

**Jede Auswahl aus zwei bis vier Möglichkeiten ist eine `Segmentwahl.`** Im
StaffelPilot standen dafür dreimal Knöpfe mit `aria-pressed` nebeneinander —
dieselbe Bedeutung, dreimal von Hand gebaut, jedes Mal ohne Pfeiltasten.

### Mengen stehen in einer `Tabelle`, nicht in Karten

Spaltenköpfe in gesperrten Kapitälchen, darunter Reihen, die eine
ausblendende Linie trennt. **Kein Rahmen je Zeile:** Zwanzig Zeilen in
zwanzig Kästen sind zwanzigmal dieselbe Kante, und die liest man mit.

Eine Reihe kann **aufklappen**, statt wegzuführen. Das ist der Grund, warum
es trotz Spalten eine Liste ist und kein `<table>`: Ein Tabellenfeld, in dem
ein ganzer Bericht aufgeht, ist für einen Screenreader eine Zelle, die
plötzlich eine Seite enthält; als Liste mit `aria-expanded` am Reihenkopf ist
dieselbe Bedienung erklärbar. Der Preis ist, dass die Spaltennamen nicht zu
jedem Wert mitgesagt werden — **deshalb muss jede Zelle für sich sprechen**
(„2 offen", nicht „2").

Zwei Zustände trägt die Reihe selbst: `betont` für das, was dran ist (ein
Hauch Akzent von links), und `leise` für Erledigtes. Erledigtes verschwindet
nicht — wer nachsehen will, was letzte Woche war, findet es noch.

Unter 48 rem löst sich das Raster auf: Die erste Zelle wird zur Überschrift
der Reihe, die übrigen zu einer Zeile dahinter, mit Mittelpunkten getrennt.
Eine Tabelle, die auf einem Telefon waagerecht scrollt, versteckt
ausgerechnet die rechte Spalte — also meist den Zustand, wegen dessen man
hinsieht.

### Wer die Überschrift setzt

Für einen Bereich setzt die Modulseite den Bereichsnamen als `h1`. Das
genügt, solange über dem Inhalt nur ein Wort stehen muss.

Sobald daneben etwas gehört, das **nur der Bereich kennt** — „3 Berichte
warten · 2 fällig", ein Filter, die eine Handlung dieser Fläche —, geht das
nicht mehr: Die Modulseite kennt diese Zahlen nicht. Dann trägt der Bereich
`eigenerTitel: true` im Register, baut seinen Kopf selbst mit `<Tafel>`, und
die Modulseite hält sich heraus. Ohne diese Unterscheidung stünde dasselbe
Wort zweimal untereinander.

## Aufbau der Oberfläche

**Eine Zeile oben, sonst nichts.** Die Kopfleiste ist 48 px hoch und
beantwortet genau eine Frage — wo bin ich gerade: Zeichen, Weg, Konto. Die
vollständige Navigation ist eine **Fläche über der Seite**, die man ruft und
wieder wegschickt.

Bis zu dieser Fassung stand links eine Navigationsleiste über die volle Höhe.
Sie kostete 15 rem Breite auf **jeder** Seite, dauerhaft, und zeigte dabei
meistens dasselbe: vier Artefakte, von denen eines offen ist. Bei einer
Spielprüftabelle mit fünf Spalten ist das der Unterschied zwischen lesbar und
gequetscht. Die Fläche ist seltener sichtbar, dafür ist sie dann ganz da:
beide Ebenen **nebeneinander** statt eingerückt untereinander, in Wortgrößen,
die man aus zwei Metern liest.

Der Preis ist ein Griff mehr zum nächsten Artefakt. Deshalb liegt dieser Griff
auf **Escape** und nicht in einem Menü — eine Taste, die jede Tastatur hat und
auf der ohnehin „weg hier" liegt. Escape öffnet die Fläche und schließt sie
wieder; wer gerade in einem Feld tippt, behält Escape für das Feld. Ohne
Tastatur führt dasselbe Zeichen oben links hinein, und die Startseite nennt
die Taste in ihrer Fußzeile — außer auf Geräten, die keine haben.

Die Seite darunter bleibt schemenhaft sichtbar. Nicht als Effekt: Sie ist die
Antwort auf „wohin komme ich zurück, wenn ich das hier wegklicke".

Ein Artefakt ohne Bereiche hat schlicht keine zweite Ebene. Kein leerer
Platzhalter, keine Spalte, die aussieht, als fehle etwas — **derselbe Stil,
unterschiedlicher Umfang.**

### Die Bereiche stehen über dem Inhalt — auf jeder Breite

Solange die Dauerleiste die Bereiche trug, erschien die Leiste über dem Inhalt
nur auf Telefonen: zweimal dieselbe Navigation wäre eine zu viel gewesen.

Diese Leiste gibt es nicht mehr. Der Bereichswechsel ist aber die häufigste
Bewegung innerhalb eines Artefakts — bei StaffelPilot zwischen zehn Flächen.
Jedes Mal erst ein Overlay zu öffnen wären zwei Handgriffe statt einem, und
zwar genau dort, wo man am häufigsten greift. Die Leiste zeigt dabei nur die
**sichtbaren** Unterseiten: Eine versteckte ist eine echte Adresse, aber kein
Reiter.

### Die Breite meldet das Artefakt an, nicht die Hülle

Vorher gab es genau ein `--breite-inhalt` von 68 rem für alles. Das ging so
lange gut, wie es ein Artefakt gab. Bei dreien ist es falsch: Eine Geräteliste
mit drei Einträgen braucht keine 1088 px, eine Spielprüftabelle hätte gern
mehr, und auf einem 2560-px-Monitor war über die Hälfte Rand.

Jetzt meldet jedes Artefakt seinen Bedarf in `src/module/register.ts` an:

| Stufe    | Maß         | Wofür                                       |
| -------- | ----------- | ------------------------------------------- |
| `text`   | 40 rem      | Formulare, Fließtext, Einstellungen         |
| `normal` | 68 rem      | **Voreinstellung.** Karten, mittlere Listen |
| `weit`   | 100 rem     | dichte Listen, mehrspaltige Raster          |
| `voll`   | ohne Grenze | Tabellen, Pläne, Übersichten                |

Vier Stufen, mehr nicht. Eine fünfte wäre schon eine, bei der niemand mehr
sagen könnte, wann man sie nimmt.

**Auch ein einzelner Bereich darf abweichen.** Das ist kein Feinschliff,
sondern ein Fehler, den man sofort sieht: Bei StaffelPilot braucht die
Spielprüfung jeden Millimeter, während das Formular „Staffel anlegen" bei
voller Breite Eingabefelder von 1400 px bekäme — quer über den Monitor, mit
dem Namensfeld links und der Beschriftung außer Sichtweite.

```ts
{
  id: "staffelpilot",
  breite: "voll",                                  // Grundmaß des Artefakts
  unterseiten: [
    { id: "spiele", wort: "Spielprüfung" },        // erbt "voll"
    { id: "zugang", wort: "DFBnet-Zugang",
      breite: "text" },                            // weicht ab
  ],
}
```

Die Suche geht von genau nach grob: Bereich, dann Artefakt, dann
Voreinstellung. Ein Bereich muss also nur etwas sagen, wenn er abweicht.

### Bereiche sind Adressen, keine Zustände

`/modul/staffelpilot/spiele` ist eine echte Adresse. Das ist keine
Förmlichkeit:

- Ein Bereich lässt sich verlinken und als Lesezeichen ablegen.
- Der Zurück-Knopf führt zum vorigen Bereich statt aus dem Artefakt heraus.
- Ein Neuladen landet dort, wo man war — und nicht wieder auf der ersten von
  neun Flächen.

Der frühere Einwand dagegen lautete, ein Seitenwechsel bedeute einen neuen
Ladevorgang samt verlorener Stelle in der Liste. Das verwechselt Unterseite
mit Neuladen: **Die Modulkomponente bleibt über allen Bereichen montiert**,
ihre Daten bleiben stehen, der Wechsel kostet keinen Abruf. In `ModulSeite`
steht deshalb ausdrücklich _kein_ `key` am Inhalt — ein wechselnder `key`
montierte neu und brächte genau den Nachteil zurück.

## Verhalten auf schmalen Geräten

Vier Umbruchpunkte, mehr braucht es nicht:

| Breite    | Was passiert                                                 |
| --------- | ------------------------------------------------------------ |
| ≥ 60 rem  | die Navigationsfläche legt ihre beiden Ebenen nebeneinander  |
| < 48 rem  | Seitenränder schrumpfen, die Linien blenden kürzer aus       |
| < 40 rem  | Tabellenzeilen werden zu Karten, Einstellungszeilen stapeln  |
| < 34 rem  | Formularzeile wird zum Stapel                                |

Unterhalb von 60 rem stehen Artefakte und Bereiche untereinander statt
nebeneinander — zwei Spalten à 180 px wären zwei zu schmale Spalten. Die
Bereichsleiste über dem Inhalt scrollt waagerecht statt umzubrechen: Zehn
Wörter brechen auf einem Telefon in drei Zeilen um, und der Inhalt darunter
rutscht bei jedem Wechsel hoch und runter.

Was an einer **Tastatur** hängt, verschwindet ohne sie. Bei `pointer: coarse`
entfällt der Esc-Hinweis auf der Startseite, und der Knopf in der
Navigationsfläche heißt dort „Schließen" statt „Esc schließt" — ein Hinweis
auf eine Taste, die das Gerät nicht hat, ist nicht nutzlos, sondern falsch.
Der zugängliche Name bleibt in beiden Fällen „Navigation schließen".

Die Tabelle **scrollt nicht horizontal**. Das würde ausgerechnet die
Schaltflächen am rechten Rand verstecken — also genau das, wofür man die
Seite geöffnet hat. Stattdessen wird jede Zeile zu einer Karte: Name und
Zustand oben, Raum darunter, Aktionen in voller Breite.

Damit `display: block` den Tabellenelementen nicht ihre Bedeutung nimmt, tragen
sie ausdrückliche `role`-Attribute. Ohne die liest ein Screenreader danach nur
noch lose Textblöcke.

CSS ist **mobil zuerst** geschrieben: Stapel als Grundregel, Zeile ab genug
Breite. Andersherum müsste die Ausnahme das `flex: 1 1 12rem` der Kinder wieder
aufheben — und dafür bräuchte sie dieselbe Spezifität. Diese Richtung spart den
Kampf.

## Zugänglichkeit

Kein Zusatz, sondern Teil der Qualität:

- **Fokus** über `:focus-visible` — sichtbar bei Tastaturbedienung, kein
  Aufblitzen bei jedem Mausklick. Bei Eingabefeldern liegt der Ring als
  Schatten an, damit er der Rundung folgt.
- **Kein Zustand nur über Farbe.** Der Statuspunkt ist `aria-hidden`, die
  Bedeutung steht immer im Text daneben.
- **Kennzahlen** tragen ein `aria-label`, das Zahl und Bezeichnung
  zusammenfasst — sonst kommt „1" und „Geräte" als zwei zusammenhanglose
  Fetzen an.
- **Kachelraster, Kennzahlen und Kartenlisten sind `<ul>`**, damit ein
  Screenreader „Liste, 5 Einträge" ansagt. Punkte und Einzug tragen dazu
  nichts bei und brechen das Raster: `basis.css` nimmt sie allen Listen ab.
  Eine echte Aufzählung im Fließtext holt sie sich mit `list-style: disc`
  zurück.
- **`prefers-reduced-motion`** schaltet alle Übergänge ab. Für Menschen mit
  vestibulären Beschwerden sind Animationen ein echtes Problem, keine
  Geschmacksfrage. Daneben gibt es in den Einstellungen einen eigenen
  Schalter, der `data-bewegung="reduziert"` setzt: Auf einem Pi im Wohnzimmer
  bedient oft jemand das Gerät, dessen Systemeinstellung jemand anderem
  gehört. Der Schalter gilt **zusätzlich**, nie stattdessen.
- **Die Navigationsfläche ist ein `dialog` mit `aria-modal`.** Der Fokus
  springt beim Öffnen hinein, Tabulator bleibt darin, und beim Schließen kehrt
  er dorthin zurück, wo er war. Ohne das bedient die Tastatur eine Seite,
  die gerade niemand sieht.
- **Thema und Bewegung werden vor dem ersten Rendern gesetzt**
  (`huelle/darstellung.ts`, aufgerufen in `main.tsx`). In einem Effekt gesetzt,
  zeigte die Seite einen Wimpernschlag lang das Thema des Systems, bevor sie
  auf die Wahl des Benutzers umspringt — ein Aufblitzen, das man einmal sieht
  und nicht mehr vergisst.
- **Sprung zum Inhalt** als erstes fokussierbares Element.
- Kontraste der Textrollen erfüllen WCAG AA in beiden Schemata.

## Anpassen

**Andere Akzentfarbe:** die Rampe `--akzent-100` … `--akzent-900` in
`tokens.css` und die vier Rollen darüber (`--farbe-akzent`, `-hell`,
`-schrift`, `-fuellung`). Sonst nichts — keine Komponente kennt eine Farbe.
Wichtig ist nur, dass `-schrift` auf hellem Grund **tiefer** liegt als
`--farbe-akzent`: Sonst verliert jeder Akzenttext seinen Kontrast.

**Dichter oder luftiger:** die `--raum-*`-Skala skalieren. Alle Abstände folgen.

**Ein Artefakt bekommt mehr oder weniger Platz:** eine Zeile in
`src/module/register.ts`. Keine Ansicht kennt ihre eigene Breite — sonst
stünde die Entscheidung an so vielen Stellen, wie es Ansichten gibt.

**Ein Bereich kommt dazu:** ebenfalls dort, in `unterseiten`. Navigation,
Adresse und Markierung entstehen daraus von selbst; das Artefakt bekommt nur
noch mitgeteilt, welcher Bereich gerade dran ist.

**Andere Rundung:** `--rundung-*`. Kanten statt Rundungen bekommt man mit `0`.

**Ein neuer Baustein** gehört nach `src/ui/`, bekommt ein eigenes
`*.module.css` und wird in `src/ui/index.ts` exportiert. Ansichten importieren
ausschließlich von dort.

## Export dieser Dokumentation

Die Datei ist bewusst reines Markdown ohne projektspezifische Erweiterungen —
sie lässt sich unverändert weiterreichen.

```bash
# als PDF (Pandoc)
pandoc docs/08-design.md -o designsystem.pdf \
  -V geometry:margin=2.5cm -V mainfont="Segoe UI"

# als eigenständiges HTML
pandoc docs/08-design.md -o designsystem.html --standalone --toc
```

Die Tokens selbst sind maschinenlesbar: `src/styles/tokens.css` ist eine
gewöhnliche CSS-Datei und lässt sich für Figma oder ein anderes Werkzeug direkt
auslesen.
