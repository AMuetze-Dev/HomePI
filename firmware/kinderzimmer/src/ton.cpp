#include "ton.h"

#include <Arduino.h>
#include <LittleFS.h>
#include <driver/i2s.h>

#include <cstring>

#include "pegel.h"
#include "pins.h"
#include "wav.h"

namespace ton {

namespace {

constexpr i2s_port_t PORT = I2S_NUM_0;
constexpr size_t PFADE_MAX = 2;
constexpr size_t PFAD_LAENGE = 96;
constexpr size_t BLOCK = 256;  // Samples je Lesevorgang

struct Auftrag {
    bool stopp = false;
    uint32_t nr = 0;
    uint8_t lautstaerke = 0;
    uint8_t anzahl = 0;
    char pfad[PFADE_MAX][PFAD_LAENGE] = {};
};

QueueHandle_t auftraege = nullptr;
QueueHandle_t enden = nullptr;

void verstaerker(bool an) {
    digitalWrite(PIN_VERSTAERKER_AN, an ? HIGH : LOW);
}

void stille() {
    i2s_zero_dma_buffer(PORT);
}

// Spielt eine Datei. false = abgebrochen, weil ein neuer Auftrag wartet.
bool datei_spielen(const char* pfad, uint16_t faktor) {
    File f = LittleFS.open(pfad, "r");
    if (!f) {
        Serial.printf("[ton] fehlt: %s\n", pfad);
        return true;
    }
    uint8_t kopf[512];
    size_t n = f.read(kopf, sizeof(kopf));
    kz::WavInfo info;
    kz::WavFehler fehler = kz::wav_lesen(kopf, n, info);
    if (fehler != kz::WavFehler::keiner) {
        Serial.printf("[ton] kein WAV im Format 1: %s\n", pfad);
        return true;
    }
    f.seek(info.daten_ab);
    uint32_t rest = info.daten_bytes;
    int16_t mono[BLOCK];
    int16_t stereo[BLOCK * 2];
    while (rest > 0) {
        Auftrag wartend;
        if (xQueuePeek(auftraege, &wartend, 0) == pdTRUE) return false;
        size_t wunsch = rest < sizeof(mono) ? rest : sizeof(mono);
        size_t gelesen = f.read(reinterpret_cast<uint8_t*>(mono), wunsch);
        if (gelesen < 2) break;
        size_t samples = gelesen / 2;
        kz::skaliere_puffer(mono, samples, faktor);
        // Beide Kanaele gleich: Der MAX98357A spielt so immer dasselbe,
        // egal wie sein SD-Pin die Kanalwahl trifft.
        for (size_t i = 0; i < samples; ++i) stereo[2 * i] = stereo[2 * i + 1] = mono[i];
        size_t geschrieben = 0;
        i2s_write(PORT, stereo, samples * 4, &geschrieben, portMAX_DELAY);
        rest -= gelesen;
    }
    return true;
}

void aufgabe(void*) {
    Auftrag a;
    for (;;) {
        if (xQueueReceive(auftraege, &a, portMAX_DELAY) != pdTRUE) continue;
        if (a.stopp) {
            stille();
            verstaerker(false);
            continue;
        }
        uint16_t faktor = kz::faktor_q15(a.lautstaerke);
        verstaerker(true);
        bool durch = true;
        for (uint8_t i = 0; i < a.anzahl && durch; ++i) durch = datei_spielen(a.pfad[i], faktor);
        if (!durch) continue;  // der neue Auftrag wird gleich abgeholt
        // Die DMA-Puffer laufen noch leer, dann Ruhe.
        vTaskDelay(pdMS_TO_TICKS(60));
        stille();
        if (uxQueueMessagesWaiting(auftraege) == 0) verstaerker(false);
        xQueueSend(enden, &a.nr, 0);
    }
}

}  // namespace

void beginnen() {
    pinMode(PIN_VERSTAERKER_AN, OUTPUT);
    verstaerker(false);

    i2s_config_t cfg;
    std::memset(&cfg, 0, sizeof(cfg));
    cfg.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX);
    cfg.sample_rate = kz::ABTASTRATE;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags = 0;
    cfg.dma_buf_count = 8;  // 8 x 256 Frames = 93 ms: genug, wenn der Flash kurz schreibt
    cfg.dma_buf_len = 256;
    cfg.use_apll = false;
    cfg.tx_desc_auto_clear = true;
    i2s_driver_install(PORT, &cfg, 0, nullptr);

    i2s_pin_config_t pins;
    std::memset(&pins, 0, sizeof(pins));
    pins.mck_io_num = I2S_PIN_NO_CHANGE;
    pins.bck_io_num = PIN_I2S_BCLK;
    pins.ws_io_num = PIN_I2S_LRC;
    pins.data_out_num = PIN_I2S_DIN;
    pins.data_in_num = I2S_PIN_NO_CHANGE;
    i2s_set_pin(PORT, &pins);
    stille();

    auftraege = xQueueCreate(4, sizeof(Auftrag));
    enden = xQueueCreate(8, sizeof(uint32_t));
    xTaskCreatePinnedToCore(aufgabe, "ton", 8192, nullptr, 5, nullptr, 1);
}

void spielen(uint32_t nr, const std::vector<std::string>& pfade, uint8_t lautstaerke) {
    Auftrag a;
    a.nr = nr;
    a.lautstaerke = lautstaerke;
    for (const auto& p : pfade) {
        if (a.anzahl >= PFADE_MAX) break;
        std::strncpy(a.pfad[a.anzahl], p.c_str(), PFAD_LAENGE - 1);
        ++a.anzahl;
    }
    xQueueSend(auftraege, &a, pdMS_TO_TICKS(20));
}

void stoppen() {
    Auftrag a;
    a.stopp = true;
    xQueueSend(auftraege, &a, pdMS_TO_TICKS(20));
}

bool fertig(uint32_t& nr) {
    return xQueueReceive(enden, &nr, 0) == pdTRUE;
}

}  // namespace ton
