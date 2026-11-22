#pragma once
// Lautstaerke. `lautstaerke_max` ist eine harte Obergrenze: Die Samples
// werden linear mit hoechstens `prozent / 100` multipliziert. Die Leistung
// am Lautsprecher steigt mit dem Quadrat der Amplitude, liegt also immer
// unter der Grenze, nie darueber.

#include <cstddef>
#include <cstdint>

namespace kz {

// Faktor in Q15 (32767 = 1,0). Ueber 100 Prozent wird auf 100 gekappt.
uint16_t faktor_q15(uint16_t prozent);

int16_t skaliere(int16_t sample, uint16_t faktor);
void skaliere_puffer(int16_t* samples, size_t anzahl, uint16_t faktor);

}  // namespace kz
