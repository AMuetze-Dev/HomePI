# 01 — Hardware & NVMe-Boot

## Was du zusätzlich brauchst

| Teil | Empfehlung | Warum |
|---|---|---|
| Netzteil | **offizielles 27 W USB-C PD** | Ohne PD-Handshake drosselt der Pi 5 den USB-Strom auf 600 mA. Mit NVMe-HAT ist das grenzwertig. |
| Kühlung | **Aktivkühler** (offizieller Active Cooler oder Gehäuse mit Lüfter) | Der Pi 5 throttelt sonst unter Dauerlast; Postgres + HA laufen 24/7. |
| M.2-HAT | offizieller *M.2 HAT+*, Pimoroni *NVMe Base*, Geekworm *X1001/X1011* | Alle nutzen den PCIe-FFC-Port. Achte auf **2280**-Support, wenn deine SSD lang ist. |
| SSD | WD SN570 / SN770, Crucial P3, Kingston NV2 (2242–2280) | Siehe Kompatibilitätshinweis unten. |
| microSD | irgendeine 16 GB | Nur zum Erstinstallieren/Klonen und als Notfall-Boot. |

**Kompatibilität:** Nicht jede NVMe läuft sauber am Pi 5. Bekannte Stolperfalle sind
Laufwerke mit aggressivem APST (u. a. einige Samsung 9xx). Symptom: Boot hängt oder
`nvme: I/O timeout` im `dmesg`. Gegenmittel steht in `04-runbook.md`.
Kaufe keine SSD, die im Pi-Umfeld nicht mehrfach positiv erwähnt wird.

## Ablauf

### 1. Von SD booten, Firmware aktualisieren
```bash
sudo rpi-eeprom-update -a
sudo reboot
```

### 2. PCIe Gen 3 aktivieren
`/boot/firmware/config.txt`, unter `[all]`:
```ini
dtparam=pciex1_gen=3
```
Gen 3 ist offiziell **nicht** zertifiziert, läuft aber auf den meisten HAT/SSD-Kombis und
verdoppelt den Durchsatz (~450 MB/s → ~900 MB/s). Wenn es instabil ist: Zeile entfernen
oder auf `=2` setzen. Stabilität schlägt Benchmark.

Falls du ein 5 V/5 A-Netzteil hast, das der Pi nicht als solches erkennt:
```ini
usb_max_current_enable=1
```

### 3. System auf die NVMe kopieren
Mit laufendem SD-System und montiertem HAT:
```bash
lsblk                       # SSD muss als /dev/nvme0n1 auftauchen
sudo apt install -y rpi-clone     # oder: Raspberry Pi OS "SD Card Copier" (GUI)
sudo rpi-clone nvme0n1
```
Alternativ sauberer: `rpi-imager` **direkt auf die NVMe** schreiben (über USB-Adapter am
Desktop) und die SD danach nur noch als Notfall behalten.

### 4. Bootreihenfolge auf NVMe umstellen
```bash
sudo raspi-config     # Advanced Options → Boot Order → NVMe/USB Boot
```
oder direkt per EEPROM-Config:
```
BOOT_ORDER=0xf416
```
Gelesen wird von rechts nach links: `6` NVMe → `1` SD → `4` USB → `f` Neustart der Schleife.
Damit bleibt die SD als Fallback drin.

### 5. Verifizieren
```bash
./scripts/check-nvme.sh
```
Prüft Bootdevice, ausgehandelte PCIe-Geschwindigkeit, SMART-Status und macht einen
kurzen fio-Lauf. Erwartung bei Gen 3: 700–900 MB/s sequenziell.

### 6. Statische IP
Vergib die IP **im Router per DHCP-Reservation**, nicht auf dem Pi. Grund: Pi-hole wird
gleich dein DNS; wenn du dich bei einer statischen Konfiguration auf dem Pi vertust,
sperrst du dich aus dem eigenen Netz aus. Router-Reservation ist von außen korrigierbar.
