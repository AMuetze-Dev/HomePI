#include "pegel.h"

namespace kz {

uint16_t faktor_q15(uint16_t prozent) {
    uint32_t p = prozent > 100 ? 100 : prozent;
    return static_cast<uint16_t>(p * 32767u / 100u);
}

int16_t skaliere(int16_t sample, uint16_t faktor) {
    // Ganzzahlige Division rundet zur Null hin: Der Betrag wird nie groesser.
    int32_t aus = static_cast<int32_t>(sample) * faktor / 32768;
    return static_cast<int16_t>(aus);
}

void skaliere_puffer(int16_t* samples, size_t anzahl, uint16_t faktor) {
    for (size_t i = 0; i < anzahl; ++i) samples[i] = skaliere(samples[i], faktor);
}

}  // namespace kz
