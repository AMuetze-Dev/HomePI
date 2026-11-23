#pragma once
// Ton ueber I2S an den MAX98357A. Eine eigene Aufgabe liest die WAV-Dateien
// aus dem Flash, deckelt die Lautstaerke und schiebt die Samples hinaus;
// die Hauptschleife bleibt dabei frei fuer Knoepfe und Licht.

#include <cstdint>
#include <string>
#include <vector>

namespace ton {

void beginnen();

// Bricht Laufendes ab und spielt `pfade` nacheinander. Fehlt eine Datei,
// geht es mit der naechsten weiter. `lautstaerke` in Prozent, Obergrenze.
void spielen(uint32_t nr, const std::vector<std::string>& pfade, uint8_t lautstaerke);
void stoppen();

// Ende einer Wiedergabe, die nicht abgebrochen wurde. true, solange es welche gibt.
bool fertig(uint32_t& nr);

}  // namespace ton
