#include "licht.h"

#include <Adafruit_NeoPixel.h>

#include "pins.h"

namespace licht {

namespace {
Adafruit_NeoPixel leds(kz::Spielgeraet::LEDS, PIN_LEDS, NEO_GRB + NEO_KHZ800);
uint32_t zuletzt[kz::Spielgeraet::LEDS] = {};
}  // namespace

void beginnen() {
    leds.begin();
    leds.clear();
    leds.show();
}

void zeigen(const kz::Spielgeraet& geraet) {
    bool geaendert = false;
    for (uint8_t i = 0; i < kz::Spielgeraet::LEDS; ++i) {
        kz::Farbe f = geraet.led(i);
        uint32_t c = Adafruit_NeoPixel::Color(f.r, f.g, f.b);
        if (c != zuletzt[i]) {
            leds.setPixelColor(i, c);
            zuletzt[i] = c;
            geaendert = true;
        }
    }
    if (geaendert) leds.show();
}

}  // namespace licht
