# 08 — Designsystem

Ruhig, strukturiert, wertig. Das Ziel ist nicht, aufzufallen, sondern
vertrauenswürdig zu wirken: eine Oberfläche, der man einen Blick lang ansieht,
dass jemand über sie nachgedacht hat — und die einem danach nicht mehr im Weg
steht.

## Fünf Regeln

1. **Wertigkeit entsteht aus Abstufung, nicht aus Kontrast.** Die neutrale
   Skala ist eng gestuft. Wo ein Sprung nötig wäre, fehlt meist Struktur.
2. **Farbe trägt Bedeutung, nicht Dekoration.** Es gibt genau drei
   Signalfarben, alle entsättigt. Die Primäraktion ist schlicht die
   kontrastreichste Fläche — ein bunter Knopf wäre das Erste, was billig wirkt.
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
src/ui/                 Bausteine (Knopf, Karte, Feld, Etikett, …)
src/huelle/             Rahmen: Kopfzeile, Inhaltsspalte, Themenwechsel
src/seiten/             Ansichten
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

| Token | Verwendung |
|---|---|
| `--farbe-grund` | Seitenhintergrund |
| `--farbe-flaeche` | Karten, Eingabefelder |
| `--farbe-flaeche-gedaempft` | Zeilen beim Zeigen, deaktivierte Felder |
| `--farbe-rand` / `--farbe-rand-stark` | Trennlinien, Ränder beim Zeigen |
| `--farbe-text` / `-gedaempft` / `-leise` | drei Stufen, mehr braucht es nicht |
| `--farbe-aktion` | Primärknopf, Markenzeichen |
| `--farbe-fokus` | Fokusring — die einzige gesättigte Farbe im Grundzustand |
| `--signal-gut` / `-warnung` / `-fehler` | Zustände, je mit `-flaeche` |

Hell und Dunkel stehen über `light-dark()` in **einer** Deklaration:

```css
--farbe-grund: light-dark(var(--neutral-25), var(--neutral-950));
```

Das ist kein Schönheitsgewinn, sondern der Grund, warum die beiden Schemata
nicht auseinanderlaufen können: es gibt keinen zweiten Satz Farben, den man
vergessen könnte mitzupflegen. Der Umschalter setzt nur `color-scheme`.

Der Dunkelmodus ist **kein invertierter Hellmodus**. Im Dunkeln braucht es
weniger Kontrast, nicht denselben; Flächen werden angehoben statt Schatten
verstärkt.

### Typografie

Kein Webfont. Der Systemstapel rendert auf jeder Plattform nativ optimiert,
lädt in null Millisekunden und braucht keine Verbindung nach außen — auf einem
Pi ohne Internetzwang die richtige Wahl.

| Token | Größe | Verwendung |
|---|---|---|
| `--text-xs` | 12 px | Etiketten, Pfade, Versionen |
| `--text-sm` | 13 px | Sekundärtext, Tabellen |
| `--text-md` | 14 px | **Basisgröße der Oberfläche** |
| `--text-lg` | 16 px | Abschnittsüberschriften |
| `--text-2xl` | 24 px | Seitentitel |

Negative Laufweite (`--laufweite-eng`, `--laufweite-enger`) erst ab
Überschriftengröße — im Fließtext macht sie die Zeile schlechter lesbar, nicht
besser. Zahlen laufen durchgehend mit `tabular-nums`, damit Spalten nicht
tanzen.

**Inter statt Systemstapel**, falls gewünscht: die woff2-Datei unter
`public/schriften/` ablegen, eine `@font-face`-Regel in `basis.css` ergänzen und
in `tokens.css` `--schrift` voranstellen. Bewusst nicht von Google Fonts — das
wäre eine Abhängigkeit vom Internet für eine Anwendung, die gerade deshalb im
eigenen Netz läuft.

### Maß und Bewegung

Vierer-Raster: `--raum-1` (4 px) bis `--raum-20` (80 px). Jeder Abstand im
Produkt ist ein Vielfaches davon.

Rundungen: `--rundung-sm` 6 px (Etiketten), `--rundung-md` 8 px (Knöpfe,
Felder), `--rundung-lg` 12 px (Karten).

| Dauer | Wofür |
|---|---|
| `--dauer-sofort` 80 ms | Druckpunkt beim Klick |
| `--dauer-schnell` 140 ms | Zeigen, Fokus, Farbwechsel |
| `--dauer-normal` 220 ms | Eintritt von Inhalten |

Zwei Verläufe: `--verlauf` für Zustandswechsel, `--verlauf-eintritt` für
erscheinende Elemente. Beide ohne Überschwingen.

## Bausteine

| Komponente | Zweck |
|---|---|
| `Knopf` | drei Ausprägungen: `primaer`, `sekundaer`, `leise` |
| `Karte` | abgegrenzte Fläche; `blank` für Inhalte mit eigenem Innenabstand |
| `Feld` | Eingabe mit verbundener Beschriftung |
| `Etikett` | kompakter Zustand oder Kennung; `mono` für Technisches |
| `Statuspunkt` | reine Dekoration, Bedeutung steht im Text daneben |
| `Hinweis` | Meldung mit `role="alert"` oder `role="status"` |
| `Leerzustand` | Erstzustand mit Erklärung, was als Nächstes zu tun ist |
| `Platzhalter` | Skelett während des Ladens |
| `Seitenkopf` | Titel, Beschreibung, Zurück-Verweis |

**Es gibt genau drei Knopf-Ausprägungen, und das ist Absicht.** Sobald eine
vierte dazukommt, hat die Seite eine Hierarchie zu viel und keine ist mehr klar.

Deaktiviert heißt gedämpft, nicht durchscheinend: bloße Transparenz macht aus
einem dunklen Primärknopf einen schweren grauen Block, der mehr Aufmerksamkeit
zieht als der aktive daneben.

## Verhalten auf schmalen Geräten

Zwei Umbruchpunkte, mehr braucht es nicht:

| Breite | Was passiert |
|---|---|
| < 40 rem | Tabellenzeilen werden zu Karten, Seitenränder schrumpfen |
| < 34 rem | Formularzeile wird zum Stapel |

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
- **`prefers-reduced-motion`** schaltet alle Übergänge ab. Für Menschen mit
  vestibulären Beschwerden sind Animationen ein echtes Problem, keine
  Geschmacksfrage.
- **Sprung zum Inhalt** als erstes fokussierbares Element.
- Kontraste der Textrollen erfüllen WCAG AA in beiden Schemata.

## Anpassen

**Andere Akzentfarbe:** nur `--farbe-aktion`, `--farbe-aktion-schrift` und
`--farbe-aktion-hover` in `tokens.css`. Sonst nichts — keine Komponente kennt
eine Farbe.

**Dichter oder luftiger:** die `--raum-*`-Skala skalieren. Alle Abstände folgen.

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
