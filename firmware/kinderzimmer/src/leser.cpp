#include "leser.h"

#include <Adafruit_PN532.h>
#include <Arduino.h>
#include <Wire.h>

#include <cstring>

#include "pins.h"
#include "uid.h"

namespace leser {

namespace {

struct Nachricht {
    bool ab = false;
    bool auf = false;
    char uid[24] = {};
};

QueueHandle_t nachrichten = nullptr;
Adafruit_PN532 nfc(PIN_NFC_IRQ, PIN_NFC_RST, &Wire);

bool einrichten() {
    if (!nfc.begin()) return false;
    uint32_t version = nfc.getFirmwareVersion();
    if (version == 0) return false;
    Serial.printf("[leser] PN5%02X, Firmware %u.%u\n", static_cast<unsigned>((version >> 24) & 0xFF),
                  static_cast<unsigned>((version >> 16) & 0xFF),
                  static_cast<unsigned>((version >> 8) & 0xFF));
    nfc.SAMConfig();
    return true;
}

void aufgabe(void*) {
    while (!einrichten()) {
        Serial.println("[leser] kein PN532 gefunden, neuer Versuch in 5 s");
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
    kz::Praesenz praesenz;
    for (;;) {
        uint8_t uid[10];
        uint8_t laenge = 0;
        std::string gelesen;
        if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &laenge, 80))
            gelesen = kz::uid_hex(uid, laenge);
        kz::Wechsel w = praesenz.melde(gelesen, millis());
        if (w.ab || w.auf) {
            Nachricht n;
            n.ab = w.ab;
            n.auf = w.auf;
            std::strncpy(n.uid, w.uid.c_str(), sizeof(n.uid) - 1);
            xQueueSend(nachrichten, &n, 0);
        }
        vTaskDelay(pdMS_TO_TICKS(40));
    }
}

}  // namespace

void beginnen() {
    Wire.begin(PIN_NFC_SDA, PIN_NFC_SCL);
    nachrichten = xQueueCreate(8, sizeof(Nachricht));
    xTaskCreatePinnedToCore(aufgabe, "leser", 4096, nullptr, 3, nullptr, 0);
}

bool wechsel(kz::Wechsel& w) {
    Nachricht n;
    if (xQueueReceive(nachrichten, &n, 0) != pdTRUE) return false;
    w.ab = n.ab;
    w.auf = n.auf;
    w.uid = n.uid;
    return true;
}

}  // namespace leser
