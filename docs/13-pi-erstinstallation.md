# 13 — Pi OS auf die NVMe bringen, ohne Tastatur und ohne Kabel

Wie das Betriebssystem auf die SSD kommt, wenn man nur WLAN hat, keinen
Bildschirm, keine Tastatur und keinen USB-Adapter für die SSD.

Der zweite Teil ist wichtiger als der erste: **was dabei alles schiefgegangen
ist und warum.** Vier Startversuche waren nötig. Jeder Fehlschlag steht hier
mit Ursache und Lehre — damit der nächste Aufbau beim ersten Mal sitzt.

---

## Ausgangslage

| | |
|---|---|
| Rechner | Raspberry Pi 5, 16 GB, M.2-HAT |
| SSD | Intenso 500 GB (MAXIO MAP1202, DRAM-less) |
| System | Raspberry Pi OS **Trixie arm64 Lite** |
| Vorhanden | SD-Karte mit laufendem Pi OS **Desktop**, externe USB-Festplatte |
| Nicht vorhanden | Tastatur, Bildschirm, Netzwerkkabel, USB-Adapter für die SSD |
| Netz | WLAN, 2,4 GHz, schwach |

**Begriffe, die gleich vorkommen:**

- **NVMe** — die SSD, die über PCIe am M.2-HAT hängt. Heißt im System
  `/dev/nvme0n1`.
- **Image** — eine Datei, die eine ganze Festplatte abbildet, Bit für Bit.
  `.img.xz` ist ein komprimiertes Image.
- **`dd`** — schreibt eine Datei roh auf ein Laufwerk, ohne Dateisystem.
  Überschreibt alles, was dort war.
- **PARTUUID** — Kennung einer Partition. Das System sucht seine
  Wurzelpartition darüber, nicht über `/dev/nvme0n1p2`.
- **rfkill** — der Softwareschalter für Funk. „Soft blocked" heißt: das
  Gerät ist da, darf aber nicht senden.
- **headless** — ohne Bildschirm und Tastatur betrieben.

---

## Der Weg in zehn Zeilen

1. Externe Platte als **Transportweg** benutzen — Image am PC herunterladen,
   auf die Platte kopieren, Platte an den Pi.
2. Vom **SD-System** aus arbeiten. Das läuft, hat Netz, und die SSD ist dort
   nur ein Datenträger unter vielen.
3. Image mit `dd` auf die SSD schreiben.
4. **Bevor** zum ersten Mal davon gebootet wird: SSH, Benutzer, WLAN und den
   SSH-Key in das neue System hineinlegen.
5. Bootreihenfolge prüfen — SD zuerst, NVMe danach.
6. Herunterfahren, **SD ziehen**, einschalten.
7. Geht etwas schief: SD wieder rein, altes System bootet, Fehler vom
   eingehängten SSD-Dateisystem aus beheben.
8. Wiederholen, bis es läuft.

Schritt 7 ist der eigentliche Trick. Mit dieser Bootreihenfolge ist die
SD-Karte ein Notausgang, der immer funktioniert.

---

## Schritt für Schritt

### 1. Image besorgen und auf die Platte

Am **Windows-Rechner** herunterladen (nicht am Pi — siehe Fehlschlag 3):

```
https://downloads.raspberrypi.com/raspios_lite_arm64_latest
```

Auf die externe Platte kopieren. **exFAT oder NTFS**, beides liest der Pi.

> **Falls die Platte vorher ein Image aufgespielt bekommen hat**, trägt sie ein
> Linux-Partitionsschema. Windows zeigt dann nur eine kleine Partition. Dann in
> der **Datenträgerverwaltung** (`diskmgmt.msc`) alle Partitionen löschen und
> neu als exFAT anlegen. Der Explorer allein räumt die Linux-Partitionen nicht
> weg.

### 2. Platte am Pi einhängen

```bash
lsblk -o NAME,SIZE,MODEL,TRAN,FSTYPE,LABEL
```

`TRAN` sagt, was was ist: `usb` = die Platte, `nvme` = die SSD.

```bash
sudo mkdir -p /mnt/platte
sudo mount -o ro /dev/sda1 /mnt/platte
```

`-o ro` bedeutet **read only**. Wir lesen nur — so kann nichts passieren.

### 3. Archiv prüfen, dann schreiben

```bash
xz -t /mnt/platte/*.img.xz && echo "Archiv unversehrt"
```

**Diesen Schritt nicht überspringen.** Ein abgebrochener Download, der klaglos
auf die SSD geschrieben wird, sieht bis zum ersten Boot nach Erfolg aus.

> ⚠️ Der nächste Befehl überschreibt ein ganzes Laufwerk. Steht bei `of=` das
> falsche Gerät, sind die Daten dort weg. Vorher kontrollieren:
> ```bash
> lsblk -o NAME,SIZE,MODEL,TRAN /dev/nvme0n1
> findmnt -no SOURCE /            # darf NICHT nvme sein
> ```

```bash
sudo umount /mnt/ssd/boot/firmware /mnt/ssd 2>/dev/null || true
xz -dc /mnt/platte/*.img.xz | sudo dd of=/dev/nvme0n1 bs=4M conv=fsync status=progress
sudo partprobe /dev/nvme0n1
lsblk /dev/nvme0n1
```

Gemessen: 2,9 GB in **16 Sekunden**, rund 192 MB/s.

Die Wurzelpartition ist danach nur ~2,3 GB groß. Das ist richtig so — sie
wächst beim ersten Start von selbst auf die volle SSD (`rpi-resize`).

### 4. Das neue System vorbereiten — der entscheidende Teil

Ohne Tastatur gilt: **was hier nicht hineinkommt, ist nach dem Neustart nicht
mehr erreichbar.**

```bash
sudo mkdir -p /mnt/neu
sudo mount /dev/nvme0n1p2 /mnt/neu
sudo mount /dev/nvme0n1p1 /mnt/neu/boot/firmware
```

**SSH einschalten** — eine leere Datei genügt, `sshswitch.service` wertet sie
beim Start aus:

```bash
sudo touch /mnt/neu/boot/firmware/ssh
```

**Benutzer anlegen.** Das Image bringt einen Benutzer `pi` mit der Nummer 1000
mit. `userconf.txt` benennt ihn beim ersten Start um:

```bash
HASH="$(sudo awk -F: '$1=="aaron"{print $2}' /etc/shadow)"
printf 'aaron:%s\n' "$HASH" | sudo tee /mnt/neu/boot/firmware/userconf.txt
```

Der Trick: der **Passwort-Hash wird aus dem laufenden System übernommen**.
Dasselbe Passwort gilt weiter, und der Klartext muss nirgends eingegeben
werden. Alternativ `openssl passwd -6` — das fragt interaktiv.

Was `userconf` beim ersten Start tut, ist angenehm gründlich:

```
usermod -l aaron pi                  # umbenennen
usermod -m -d /home/aaron aaron      # Home verschieben, Inhalt mitnehmen
groupmod -n aaron pi                 # Gruppe mit
sed -i "s/^pi /aaron /" /etc/sudoers.d/010_pi-nopasswd
```

Deshalb legt man Dateien in **`/home/pi/`** ab — sie wandern automatisch mit.
Und eine `sudo`-Regel, die `010_pi-nopasswd` heißt, wird automatisch auf den
neuen Namen umgeschrieben.

**WLAN übernehmen.** Auf Trixie verwaltet **netplan** das Netz und gibt es an
NetworkManager weiter. Die Zugangsdaten liegen also in `/etc/netplan/`, nicht
bei NetworkManager:

```bash
sudo cp -a /etc/netplan/*.yaml /mnt/neu/etc/netplan/
sudo chown root:root /mnt/neu/etc/netplan/*.yaml
sudo chmod 600      /mnt/neu/etc/netplan/*.yaml
```

Auch hier: das WLAN-Passwort muss nirgends neu eingegeben werden.

Vorher prüfen lassen, ob netplan die Dateien überhaupt akzeptiert:

```bash
sudo netplan generate --root-dir /mnt/neu
sudo find /mnt/neu/run/NetworkManager/system-connections -type f
```

Kommt dort eine `.nmconnection` heraus, ist die Konfiguration brauchbar.

**SSH-Key hinterlegen:**

```bash
sudo mkdir -p /mnt/neu/home/pi/.ssh
echo 'ssh-ed25519 AAAA... dein-key' | sudo tee /mnt/neu/home/pi/.ssh/authorized_keys
sudo chown -R 1000:1000 /mnt/neu/home/pi
sudo chmod 700 /mnt/neu/home/pi/.ssh
sudo chmod 600 /mnt/neu/home/pi/.ssh/authorized_keys
```

**Hostname:**

```bash
echo HomeLab | sudo tee /mnt/neu/etc/hostname
sudo sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tHomeLab/' /mnt/neu/etc/hosts
```

### 5. Die drei WLAN-Weichen — alle gleichzeitig

**Das ist der Abschnitt, der vier Startversuche gekostet hat.** Damit WLAN
headless funktioniert, müssen **drei** Dinge stimmen. Eines davon zu übersehen
reicht, und der Pi ist stumm:

```bash
# 1. Funk-Land. Ohne das sperrt der Treiber das WLAN.
#    raspi-config schreibt es als Kernel-Parameter, nicht in eine Konfigdatei.
sudo sed -i -e "s/\s*cfg80211.ieee80211_regdom=\S*//" \
            -e "s/\(.*\)/\1 cfg80211.ieee80211_regdom=DE/" \
            /mnt/neu/boot/firmware/cmdline.txt

# 2. Gespeicherter rfkill-Zustand. systemd-rfkill stellt ihn bei JEDEM
#    Start wieder her - auch eine alte Sperre.
echo 0 | sudo tee "/mnt/neu/var/lib/systemd/rfkill/platform-1001100000.mmc:wlan"

# 3. NetworkManagers EIGENE Zustandsdatei. Steht hier "false", schaltet NM
#    den Funk beim Start selbst wieder ab.
sudo sed -i "s/^WirelessEnabled=.*/WirelessEnabled=true/" \
           /mnt/neu/var/lib/NetworkManager/NetworkManager.state
```

> `cmdline.txt` muss **eine einzige Zeile** bleiben. Prüfen mit
> `wc -l < /mnt/neu/boot/firmware/cmdline.txt` — 0 oder 1 ist richtig.

### 6. Journal dauerhaft machen — vor dem ersten Start

Voreingestellt schreibt `journald` nur in den Arbeitsspeicher. Nach einem
Fehlstart ist das Log damit **weg**, und man rät statt zu lesen:

```bash
sudo mkdir -p /mnt/neu/etc/systemd/journald.conf.d
printf "[Journal]\nStorage=persistent\nSystemMaxUse=200M\n" \
  | sudo tee /mnt/neu/etc/systemd/journald.conf.d/00-dauerhaft.conf
```

**Das gehört an den Anfang, nicht ans Ende.** Siehe Fehlschlag 7.

### 7. Bootreihenfolge und Umschalten

```bash
sudo rpi-eeprom-config | grep BOOT_ORDER
```

`BOOT_ORDER=0xf461` wird **von rechts nach links** gelesen:
`1` SD → `6` NVMe → `4` USB → `f` Schleife.

Also: **SD zuerst.** Das ist genau richtig, solange man noch experimentiert —
die SD bleibt der Notausgang. Erst wenn alles läuft, lohnt `0xf416`
(NVMe zuerst).

```bash
sudo umount /mnt/neu/boot/firmware /mnt/neu
sudo shutdown -h now
```

Dann: **SD ziehen**, Strom trennen, wieder anstecken.

### 8. Gegenprobe vom anderen Rechner

Nach einer Neuinstallation hat der Pi **neue SSH-Host-Keys**. Der alte
Eintrag muss weg, sonst verweigert SSH die Verbindung:

```bash
ssh-keygen -R homelab
ssh homelab 'findmnt -no SOURCE,SIZE /; hostname; ip -4 -o addr show wlan0'
```

Erwartung: `/dev/nvme0n1p2` und die volle Größe.

---

## Was alles schiefgegangen ist

Chronologisch. Jeder Eintrag: **Symptom → Ursache → Lehre.**

### 1. `apt install rpi-clone` findet nichts

Das Paket gibt es in Raspberry Pi OS nicht. Klingt nach einem Tippfehler, ist
aber schlicht nicht vorhanden.

**Lehre:** `apt-cache policy <paket>` fragen, bevor man eine Anleitung
befolgt, die ein Paket voraussetzt.

### 2. `rpi-clone` von GitHub kann kein NVMe

Der Klon brach ab:

```
mount: /mnt/clone: fsconfig() failed: /dev/nvme0n12: Can't lookup blockdev.
```

`/dev/nvme0n12` gibt es nicht. NVMe-Partitionen heißen `nvme0n1p1`,
`nvme0n1p2` — mit **`p`**. Das Skript hängt die Nummer direkt an den
Laufwerksnamen, was für `sda` → `sda1` stimmt, für NVMe aber nicht. Das
Repository (`billw2/rpi-clone`) ist seit Jahren unverändert und älter als
NVMe am Pi.

**Lehre:** Ein Werkzeug, das seit Jahren keinen Commit hat, kennt keine
Hardware, die es damals nicht gab. Wenn es abbricht: nicht überreden,
sondern den Weg wechseln.

### 3. Download am Pi: 7 Stunden geschätzt, Abbruch nach 5 Minuten

Am PC dauerte derselbe Download fünf Minuten. Die Messung am Pi:

```
freq: 2437        → Kanal 6, also 2,4 GHz
signal: -70 dBm   → schwach
rx bitrate: 7.2 MBit/s → MCS0, die langsamste Stufe von 802.11n
```

Zu wenig Signal auf einem überfüllten 2,4-GHz-Kanal. Der **Downlink** war das
Problem — `tx` lief mit 43 Mbit/s, `rx` mit 7,2. Ein Download ist `rx`.

**Lehre:** Bei „langsam" nicht schätzen, sondern `iw dev wlan0 link` lesen.
Und: **große Dateien nicht über eine schlechte Funkstrecke ziehen**, wenn ein
USB-Stick oder eine Platte danebenliegt. Turnschuh-Netzwerk schlägt jedes
Kabelersatzverfahren.

Was **nicht** hilft: die Datei am PC herunterladen und dann per `scp`
übertragen. Der Engpass ist die Funkstrecke des Pi — der Weg dorthin ist
derselbe.

### 4. Erster Boot von der NVMe: kein Netz

Alles andere funktionierte: Partition auf 458 GB gewachsen, Benutzer `aaron`
angelegt, `userconf.txt` verarbeitet, SSH aktiviert. Nur `wlan0` blieb tot.

**Ursache:** Raspberry Pi OS sperrt das WLAN per `rfkill`, solange **kein
Funk-Land** gesetzt ist. Auf dem SD-System stand `cfg80211.ieee80211_regdom=DE`
in `cmdline.txt`; im frischen Image steht es nicht.

Das Tückische: das Land steht **nicht** in einer Konfigurationsdatei, sondern
als Kernel-Parameter. Wer in `/etc` danach sucht, findet nichts.

**Lehre:** Beim Vorbereiten eines headless-Systems das laufende System als
Vorlage nehmen — und zwar **`cmdline.txt` mit vergleichen**, nicht nur `/etc`.

### 5. Zweiter Boot: immer noch kein Netz

Funk-Land war jetzt gesetzt. Trotzdem gesperrt.

**Ursache:** `systemd-rfkill` **speichert** den Zustand jedes Funkschalters
unter `/var/lib/systemd/rfkill/` und stellt ihn bei jedem Start wieder her.
Die Sperre aus dem ersten Fehlstart war dort als `1` konserviert.

**Lehre:** Nach einem Fehlstart reicht es nicht, die Ursache zu beheben — man
muss auch wegräumen, was der Fehlstart hinterlassen hat.

### 6. Dritter Boot: immer noch kein Netz

Funk-Land gesetzt, rfkill auf `0` gesetzt. Trotzdem gesperrt, und die Datei
stand danach wieder auf `1`. Also hatte etwas sie **aktiv neu geschrieben**.

Die Antwort stand im Journal des **funktionierenden** SD-Systems:

```
NetworkManager: rfkill: Wi-Fi enabled by radio killswitch; enabled by state file
```

**Ursache:** NetworkManager führt eine eigene Zustandsdatei,
`/var/lib/NetworkManager/NetworkManager.state`. Dort stand:

```ini
WirelessEnabled=false
```

Geschrieben beim ersten Fehlstart, als der Funk mangels Land gesperrt war.
Seitdem schaltete NM das WLAN bei **jedem** Start selbst wieder ab, und
`systemd-rfkill` schrieb die Sperre brav hinterher.

**Lehre — die wichtigste hier:** Bei so etwas hört man auf, den nächsten
Verdacht zu reparieren, und **vergleicht Zeile für Zeile mit einem System,
das funktioniert.** Dieselbe Hardware, dasselbe WLAN, ein funktionierendes
System daneben — der Vergleich hätte die Ursache beim ersten Mal geliefert
statt beim vierten.

### 7. Nach dem Fehlstart: kein Log zum Nachlesen

Genau dann, wenn man wissen will, warum etwas nicht startet, ist nichts da.

**Ursache:** `journald` steht auf `Storage=auto`. Das heißt: dauerhaft nur,
wenn `/var/log/journal` **beim Systemstart schon existiert**. Im frischen
Image existiert es nicht. Das Verzeichnis nachträglich anzulegen reicht nicht
— die Einstellung muss `persistent` lauten.

**Lehre:** Das Journal dauerhaft machen, **bevor** man das erste Mal bootet.
Kostet nichts und spart eine ganze Runde Raten.

### 8. `sudo` verlangte ein Passwort

Fernwartung per Skript war damit blockiert.

**Ursache:** Der Raspberry Pi Imager legte früher `/etc/sudoers.d/010_pi-nopasswd`
an. Auf Trixie tut er das nicht mehr.

```bash
echo "aaron ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/010_aaron-nopasswd
sudo chmod 440 /etc/sudoers.d/010_aaron-nopasswd
```

**Abwägung:** Wer damit per SSH hereinkommt, ist root. Vertretbar, solange
SSH nur Key-Anmeldung erlaubt und der Pi im LAN hinter einer Firewall steht.
Für die Einrichtung praktisch — danach kann die Datei wieder weg.

### 9. Zwei Datenträger mit derselben Disk-ID

Die externe Platte und die NVMe hatten beide die MBR-Kennung `4d8fd085`,
weil das Image vorher einmal auf die Platte geschrieben worden war und
Windows die Kennung beim Formatieren behielt. Damit war
`PARTUUID=4d8fd085-01` **zweideutig** — und genau darüber wird
`/boot/firmware` eingehängt.

Entschärft hat es sich von selbst: der initramfs-Hook `set_partuuid` würfelt
beim ersten Start die Disk-ID der Wurzelplatte neu und schreibt `fstab` und
`cmdline.txt` um. Das steht in
`/usr/share/initramfs-tools/scripts/local-bottom/set_partuuid` — nachlesbar,
nicht vermutet.

**Lehre:** Vor dem ersten Start `lsblk -o NAME,PARTUUID` über **alle**
angeschlossenen Datenträger laufen lassen. Doppelte Kennungen sind der
Klassiker beim Klonen.

### 10. SSH verweigerte nach der Neuinstallation

```
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
```

**Ursache:** Neue Installation, neue Host-Keys. Kein Angriff, sondern
Normalzustand.

```bash
ssh-keygen -R homelab
```

---

## Prüfliste vor dem ersten Start

Alles auf dem **eingehängten** neuen System, bevor die SD gezogen wird:

- [ ] `boot/firmware/ssh` existiert
- [ ] `boot/firmware/userconf.txt` mit `benutzer:hash`
- [ ] `cmdline.txt` enthält `cfg80211.ieee80211_regdom=XX` — **eine Zeile**
- [ ] `var/lib/systemd/rfkill/*wlan*` steht auf `0`
- [ ] `var/lib/NetworkManager/NetworkManager.state` → `WirelessEnabled=true`
- [ ] `etc/netplan/*.yaml` kopiert, Rechte `600`, mit `netplan generate --root-dir` geprüft
- [ ] `home/pi/.ssh/authorized_keys` mit Key, Eigentümer `1000:1000`
- [ ] `etc/systemd/journald.conf.d/` mit `Storage=persistent`
- [ ] `etc/hostname` und `etc/hosts` gesetzt
- [ ] `lsblk -o NAME,PARTUUID` — keine doppelten Kennungen
- [ ] `BOOT_ORDER` lässt die SD zuerst booten

## Notausgang

Geht nach dem Umschalten nichts mehr:

1. Strom trennen, **SD wieder hinein**, Strom an
2. Das alte System bootet — Zugang ist wieder da
3. SSD einhängen und nachlesen, was passiert ist:

```bash
sudo mount /dev/nvme0n1p2 /mnt/neu
sudo journalctl -D /mnt/neu/var/log/journal -b -1 --no-pager | tail -50
```

Das funktioniert allerdings nur, wenn Punkt 6 vorher erledigt war.

---

## Ergebnis

```
/dev/nvme0n1p2 ext4  458G        Wurzel auf der SSD
Debian GNU/Linux 13 (trixie)     Kernel 6.18.50
temp=49.4'C  throttled=0x0       keine Drosselung
wlan0: Soft blocked: no          -58 dBm
```

Weiter mit [01-hardware.md](01-hardware.md) (PCIe Gen 3, `check-nvme.sh`) und
[02-os-bootstrap.md](02-os-bootstrap.md) (Härtung, Docker, Netze).
