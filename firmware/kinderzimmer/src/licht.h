#pragma once
// WS2812B unter den Knoepfen. Farbe, Blende und Helligkeitsgrenze rechnet
// das Spielgeraet; hier wird nur hinausgeschrieben.

#include "spielgeraet.h"

namespace licht {

void beginnen();
void zeigen(const kz::Spielgeraet& geraet);

}  // namespace licht
