#include "wav.h"

#include <cstring>

namespace kz {

namespace {

uint32_t le32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

uint16_t le16(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (p[1] << 8));
}

}  // namespace

WavFehler wav_lesen(const uint8_t* kopf, size_t n, WavInfo& info) {
    if (kopf == nullptr || n < 12) return WavFehler::kaputt;
    if (std::memcmp(kopf, "RIFF", 4) != 0 || std::memcmp(kopf + 8, "WAVE", 4) != 0)
        return WavFehler::kaputt;

    bool fmt_gesehen = false;
    size_t pos = 12;
    while (pos + 8 <= n) {
        const uint8_t* block = kopf + pos;
        uint32_t laenge = le32(block + 4);
        if (std::memcmp(block, "fmt ", 4) == 0) {
            if (laenge < 16 || pos + 8 + 16 > n) return WavFehler::kaputt;
            const uint8_t* f = block + 8;
            uint16_t format = le16(f);
            uint16_t kanaele = le16(f + 2);
            uint32_t rate = le32(f + 4);
            uint16_t bits = le16(f + 14);
            if (format != 1 || kanaele != 1 || rate != ABTASTRATE || bits != 16)
                return WavFehler::falsches_format;
            fmt_gesehen = true;
        } else if (std::memcmp(block, "data", 4) == 0) {
            if (!fmt_gesehen) return WavFehler::kaputt;
            info.daten_ab = static_cast<uint32_t>(pos + 8);
            info.daten_bytes = laenge;
            return WavFehler::keiner;
        }
        // Bloecke sind auf gerade Laengen aufgefuellt.
        pos += 8 + laenge + (laenge & 1);
    }
    return WavFehler::kaputt;
}

}  // namespace kz
