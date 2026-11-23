#include "farbe.h"

namespace kz {

namespace {

int ziffer(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

uint8_t kanal(uint8_t wert, uint32_t prozent, uint32_t stufe) {
    // wert * (stufe/255)^2 * prozent/100, ganzzahlig und abgerundet.
    uint32_t zaehler = static_cast<uint32_t>(wert) * stufe * stufe * prozent;
    return static_cast<uint8_t>(zaehler / (255u * 255u * 100u));
}

}  // namespace

bool farbe_lesen(const char* hex, Farbe& aus) {
    if (hex == nullptr || hex[0] != '#') return false;
    int z[6];
    for (int i = 0; i < 6; ++i) {
        if (hex[i + 1] == '\0') return false;
        z[i] = ziffer(hex[i + 1]);
        if (z[i] < 0) return false;
    }
    if (hex[7] != '\0') return false;
    aus.r = static_cast<uint8_t>(z[0] * 16 + z[1]);
    aus.g = static_cast<uint8_t>(z[2] * 16 + z[3]);
    aus.b = static_cast<uint8_t>(z[4] * 16 + z[5]);
    return true;
}

Farbe gedimmt(Farbe farbe, uint16_t prozent, uint8_t stufe) {
    uint32_t p = prozent > 100 ? 100 : prozent;
    return {kanal(farbe.r, p, stufe), kanal(farbe.g, p, stufe), kanal(farbe.b, p, stufe)};
}

}  // namespace kz
