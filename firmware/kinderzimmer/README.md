# Firmware „kinderzimmer“ — Spielgerät, Phase 1

Die Firmware für das Spielgerät des Artefakts `kinderzimmer`. Das Gerät spielt
allein. Der Pi liefert nur den Stand und die Aufnahmen und empfängt das
Protokoll. Ist der Pi nicht erreichbar, spielt das Gerät mit dem letzten Stand
aus dem Flash weiter.

Der Vertrag mit dem Pi (Format `1`) steht im Abschnitt „Geräteschnittstelle“
in [`modules/kinderzimmer/AGENTS.md`](../../modules/kinderzimmer/AGENTS.md).
Die pädagogischen Leitlinien stehen in derselben Datei. Mehrere Zahlen weiter
unten folgen aus ihnen.

## Was es kann

| Spiel | Eingabe | Reaktion |
|---|---|---|
| `licht-und-klang` | Knopf drücken | Die LED unter dem Knopf blendet in 150 ms auf die Knopffarbe, dazu spielt der Klang des Knopfes |
| `stimmen` | Figur auflegen | Die Stimme der Figur, danach ihr Klang |

- Beide Spiele antworten, solange sie in `spiele_aktiv` stehen. Sie hängen an
  verschiedenen Eingaben und stören sich deshalb nicht. Welches zuletzt benutzt
  wurde, steht als Ereignis `spiel` im Tagebuch.
- Ein neuer Druck bricht den laufenden Klang ab. Derselbe Knopf noch einmal
  lässt das Licht an, es flackert nicht.
- Das Licht bleibt an, solange der Klang läuft, leuchtet 2 s nach und blendet
  dann in 1,2 s aus. Es wird nur überblendet, nie geschaltet. Lange Lücken in
  der Hauptschleife werden ebenfalls nicht zu Sprüngen.
- Eine unbekannte Figur und ein Knopf ohne Eintrag erscheinen nur im
  Protokoll, es gibt keinen Ton. So kann die Website unbekannte Figuren zum
  Anlegen anbieten.
- Nach `ruhe_nach_min` ohne Handlung blendet alles aus und das Gerät meldet
  `ruhe`. Von sich aus spielt es nie etwas, auch kein Licht.

### Harte Grenzen

- **Lautstärke:** Jedes Sample wird mit höchstens `lautstaerke_max / 100`
  multipliziert. Die Leistung steigt mit dem Quadrat der Amplitude und bleibt
  damit immer unter der Grenze. Knöpfe zum Lautermachen gibt es nicht.
- **Helligkeit:** Kein Farbkanal liegt je über `kanal × helligkeit_max / 100`.
- Werte außerhalb von 5–100 werden in diesen Bereich gezogen, so wie der Pi sie
  auch prüft. Fehlen sie, gelten 40 %.

### Abgleich mit dem Pi

1. **Beim Start:** WLAN, NTP, dann `GET /kinderzimmer/geraet/stand`.
2. Fehlende Aufnahmen werden einzeln geladen und gegen `sha256` und `bytes`
   geprüft, zuerst nach `/neu/`. Erst wenn alle da sind, wandern sie nach
   `/dateien/<sha256>.wav`, und das Manifest wird zu `/stand.json`.
3. **Umgeschaltet wird nur in einer Spielpause:** kein Ton, keine Figur auf dem
   Leser und 15 s lang nichts gedrückt. Bis dahin spielt der alte Stand weiter.
   Die Dateien heißen nach ihrer Prüfsumme, deshalb verdrängen die neuen
   Dateien die alten nicht. Danach meldet das Gerät `abgleich` und löscht, was
   nicht mehr gebraucht wird.
4. **Ereignisse** gehen live an `POST /kinderzimmer/geraet/ereignisse`. Ohne
   Verbindung landen sie sofort in `/puffer.jsonl` und werden beim nächsten
   Erfolg nachgereicht, das Gepufferte zuerst. Der Puffer fasst 20 000
   Ereignisse, darüber fallen die ältesten weg. Bei Fehlern wartet das Gerät
   erst 2 s, dann doppelt so lange, höchstens 5 Minuten.
5. Nennt eine Antwort einen anderen `stand`, gleicht das Gerät ab, sobald
   gerade kein Spiel läuft. Ein regelmäßiges Abfragen gibt es nicht.

Sonderfälle:

- Ein Manifest mit `format` > 1 übernimmt das Gerät nicht. Es behält den alten
  Stand und schreibt das ins serielle Log. Der Pi erkennt es daran, dass das
  Gerät im Kopf seiner Sendungen weiter den alten Stand nennt.
- Reicht der Flash nicht, bleibt ebenfalls der alte Stand.
- Lehnt der Pi eine Sendung mit 400 oder 422 ab, wird sie verworfen. Ein
  zweiter Versuch würde daran nichts ändern und alle folgenden aufhalten.
- Beim allerersten Start ohne Pi gilt die Voreinstellung des Pi: Knopf 1 in
  Bernstein (`#FFB000`), ohne Klang. Das Licht geht damit schon, der Ton kommt
  mit dem ersten Abgleich.
- `zeit` steht erst in den Ereignissen, wenn NTP lief, und zwar in UTC. Davor
  ist es `null`, und der Pi rechnet aus `jetzt_ms - ms` zurück.

## Verdrahtung

ESP32-S3 DevKitC-1 **N16R8** (16 MB Flash, 8 MB PSRAM). Die Pins stehen
gesammelt in [`include/pins.h`](include/pins.h).

| Teil | Anschluss | ESP32-S3 |
|---|---|---|
| **MAX98357A** | VIN | 5V |
| | GND | GND |
| | BCLK | GPIO 4 |
| | LRC | GPIO 5 |
| | DIN | GPIO 6 |
| | SD | GPIO 7 (HIGH = an; in der Stille aus, damit nichts rauscht) |
| | GAIN | an VIN (6 dB) empfohlen; offen wären es 9 dB |
| | + / − | Lautsprecher 4–8 Ω |
| **PN532** | Schalter | I2C: SW1 = ON, SW2 = OFF |
| | VCC | 3V3 |
| | GND | GND |
| | SDA | GPIO 8 |
| | SCL | GPIO 9 |
| | IRQ | GPIO 10 |
| | RSTO / RST | GPIO 11 |
| **WS2812B** | 5V | 5V, dazu 470–1000 µF zwischen 5V und GND |
| | GND | GND |
| | DIN | GPIO 47 über 330 Ω |
| **Knöpfe 1–8** | Mikroschalter | GPIO 12, 13, 14, 15, 16, 21, 39, 40, jeweils gegen GND |
| frei (Elternpult) | TX / RX | GPIO 17 / 18 |

- **Die LEDs laufen in Reihe.** LED 1 sitzt unter Knopf 1, LED 2 unter Knopf 2
  und so weiter. Die Firmware steuert 8 an; fehlen welche, schadet das nicht.
- Knöpfe brauchen keinen Widerstand, der interne Pull-up reicht. Ein nicht
  verdrahteter Knopfpin bleibt still.
- Die erste WS2812B nimmt 3,3 V als Datenpegel meist an. Flackert sie, hilft
  ein 74AHCT125 als Pegelwandler.
- **Strom:** Bei 40 % Helligkeit brauchen 8 LEDs rund 200 mA, der Verstärker
  bei Spitzen bis 600 mA. Für ein fertiges Gerät besser ein Netzteil mit 5 V
  und 2 A an den 5V-Pin; für den Aufbau reicht USB.
- Ausgelassen sind GPIO 0, 3, 45 und 46 (Strapping), 19 und 20 (USB), 26–37
  (Flash und Octal-PSRAM), 43 und 44 (USB-Seriell) sowie 48/38 (die RGB-LED auf
  dem Board).

## Einrichten und flashen

1. PlatformIO installieren:

   ```bash
   uv tool install platformio
   ```

   Für die Tests auf dem PC braucht PlatformIO einen C++-Compiler. Unter
   Windows ist das z. B. `winget install BrechtSanders.WinLibs.POSIX.UCRT`.

2. Auf der Website unter *Kinderzimmer → Geräte* ein Gerät anlegen. Das
   Token wird genau einmal angezeigt.

3. Zugangsdaten eintragen. `include/secrets.h` ist in `.gitignore` und kommt
   nie ins Repo:

   ```bash
   cd firmware/kinderzimmer
   cp include/secrets.beispiel.h include/secrets.h
   ```

   `PI_ADRESSE` ist das Gateway ohne Schrägstrich am Ende. Im LAN ist das
   `https://api.<domain>`; das Zertifikat von Let's Encrypt prüft die Firmware
   gegen die mitgelieferten Wurzeln ISRG Root X1 und X2. In der Entwicklung
   ist es `http://<PC-Adresse>:18000`. Das WLAN muss 2,4 GHz sein.

4. Das Board an der Buchse **UART** anschließen und flashen:

   ```bash
   pio run -t upload
   pio device monitor
   ```

   Beim ersten Start formatiert die Firmware den LittleFS-Bereich, das dauert
   einige Sekunden. `pio run -t erase` setzt alles zurück, auch den
   Startzähler.

Im seriellen Log steht, was passiert: `[netz] Abgleich auf …`,
`[kinderzimmer] Spiele ab jetzt mit Stand …`, `[leser] kein PN532 gefunden`.

## Prüfen

```bash
pio test -e native   # Spiellogik auf dem PC, ohne Board
pio run              # für das Board bauen
```

Die Tests prüfen das Verhalten aus der Tabelle oben: die Grenzen für Licht und
Ton, dass das Licht nie springt, Ruhe, das Fenster für den Abgleich, das
Manifest, die Sendungen im Vertragsformat und den Puffer.

## Aufbau

```
lib/logik/       Entscheidungen. Kein Arduino, auf dem PC getestet.
  spielgeraet    Eingaben → Licht, Ton, Protokoll; Ruhe; Abgleich-Fenster
  stand          Manifest lesen, Grenzen, Vorgaben ohne Pi
  abgleich       welche Dateien fehlen, welche dürfen weg
  protokoll      Ereignisse und Sendungen im Vertragsformat
  versand        live senden, puffern, nachreichen, Wartezeiten
  blende, farbe  Überblenden, Helligkeitsgrenze
  pegel, wav     Lautstärkegrenze, WAV-Kopf (Format 1)
  entpreller, praesenz, uid
src/             dünne Schicht zur Hardware
  main           verbindet alles; erst reagieren, dann protokollieren
  ton            I2S-Aufgabe, liest WAV aus dem Flash
  licht          WS2812B
  leser          PN532-Aufgabe
  netz           WLAN, NTP, HTTP, Abgleich, Versand (eigene Aufgabe)
  ablage         LittleFS
test/            Unity, läuft mit `pio test -e native`
```

Flash-Aufteilung ([`partitions.csv`](partitions.csv)): 3 MB für die App,
12,8 MB für LittleFS. Abzüglich Reserve für Puffer und Stand sind das knapp
fünf Minuten Aufnahmen im Format 1 (44 KB je Sekunde).

## Noch nicht drin

- Das Elternpult auf dem Elegoo-Display. GPIO 17/18 sind dafür frei.
- Updates über WLAN. Es gibt nur einen App-Bereich.
- Spiele der Phase 2 und folgende.
