#pragma once
// Farben aus dem Manifest und die harte Helligkeitsgrenze.

#include <cstdint>

namespace kz {

struct Farbe {
    uint8_t r = 0;
    uint8_t g = 0;
    uint8_t b = 0;
};

// "#RRGGBB", gross oder klein. Alles andere: false, `aus` bleibt unberuehrt.
bool farbe_lesen(const char* hex, Farbe& aus);

// Farbe auf einer Blendstufe (0..255) mit Helligkeitsgrenze in Prozent.
// Die Stufe laeuft ueber eine quadratische Kurve, damit das Auge das
// Ueberblenden als gleichmaessig empfindet. `prozent` ist eine Obergrenze:
// kein Kanal liegt je ueber `kanal * prozent / 100`.
Farbe gedimmt(Farbe farbe, uint16_t prozent, uint8_t stufe);

}  // namespace kz
