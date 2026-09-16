#!/usr/bin/env bash
# Prueft, ob der Pi wirklich von der NVMe bootet und mit welcher Geschwindigkeit.
set -uo pipefail

echo "=== Root-Dateisystem ==="
findmnt -no SOURCE,FSTYPE,SIZE /
if findmnt -no SOURCE / | grep -q nvme; then
    echo "OK: Boot laeuft von der NVMe."
else
    echo "ACHTUNG: / liegt NICHT auf der NVMe. Bootorder pruefen (raspi-config)."
fi

echo
echo "=== Blockgeraete ==="
lsblk -o NAME,SIZE,MODEL,MOUNTPOINT

echo
echo "=== PCIe-Verbindung ==="
# LnkSta zeigt die tatsaechlich ausgehandelte Geschwindigkeit.
# 8GT/s = Gen3, 5GT/s = Gen2. Erwartet: 8GT/s bei dtparam=pciex1_gen=3
sudo lspci -vv 2>/dev/null | grep -A2 -i 'non-volatile' | grep -i 'lnksta' \
    || sudo lspci | grep -i 'non-volatile' \
    || echo "kein NVMe-Controller auf dem PCIe-Bus gefunden"

echo
echo "=== SMART / Gesundheit ==="
sudo nvme smart-log /dev/nvme0 2>/dev/null \
    | grep -Ei 'temperature|percentage_used|data_units_written|media_errors|critical' \
    || echo "nvme-cli liefert nichts - Geraet vorhanden?"

echo
echo "=== Durchsatz (fio, 1 GB sequenziell lesen) ==="
echo "Erwartung: Gen3 ~800-900 MB/s, Gen2 ~440 MB/s"
TESTFILE="$(findmnt -no TARGET / )/.fio-test"
sudo fio --name=seqread --filename="$TESTFILE" --size=1G --bs=1M \
    --rw=read --ioengine=libaio --direct=1 --iodepth=16 --numjobs=1 \
    --runtime=20 --time_based --group_reporting 2>/dev/null \
    | grep -E 'READ:|IOPS' || echo "fio nicht verfuegbar"
sudo rm -f "$TESTFILE"

echo
echo "=== Throttling / Temperatur ==="
vcgencmd measure_temp 2>/dev/null || true
# 0x0 = alles gut. Bits: 0 under-voltage, 1 freq capped, 2 throttled, 3 temp limit
printf "throttled: %s  (0x0 = alles in Ordnung)\n" "$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)"
