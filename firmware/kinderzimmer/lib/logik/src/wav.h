#pragma once
// WAV-Kopf pruefen. Der Vertrag (Format 1) erlaubt genau ein Format:
// PCM, 16 Bit, mono, 22 050 Hz. Damit braucht das Geraet keinen Decoder.

#include <cstddef>
#include <cstdint>

namespace kz {

constexpr uint32_t ABTASTRATE = 22050;

enum class WavFehler { keiner, kaputt, falsches_format };

struct WavInfo {
    uint32_t daten_ab = 0;     // Byte-Versatz der Samples in der Datei
    uint32_t daten_bytes = 0;  // Laenge des data-Blocks
};

// `kopf` sind die ersten `n` Bytes der Datei; 512 reichen fuer jede
// Aufnahme, die der Pi ausliefert.
WavFehler wav_lesen(const uint8_t* kopf, size_t n, WavInfo& info);

}  // namespace kz
