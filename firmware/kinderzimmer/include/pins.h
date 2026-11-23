#pragma once
// Pinbelegung, ESP32-S3 DevKitC-1 N16R8. Verdrahtung: README.md.
//
// Frei gelassen: 0 3 45 46 (Strapping), 19 20 (USB), 26-37 (Flash und
// Octal-PSRAM), 43 44 (USB-Seriell an der Buchse "UART"), 48/38 (RGB-LED
// auf dem Board, je nach Revision).

#include <cstdint>

// MAX98357A, I2S
constexpr int PIN_I2S_BCLK = 4;
constexpr int PIN_I2S_LRC = 5;
constexpr int PIN_I2S_DIN = 6;
constexpr int PIN_VERSTAERKER_AN = 7;  // SD: HIGH = an, LOW = aus (kein Rauschen in der Stille)

// PN532, I2C
constexpr int PIN_NFC_SDA = 8;
constexpr int PIN_NFC_SCL = 9;
constexpr int PIN_NFC_IRQ = 10;
constexpr int PIN_NFC_RST = 11;

// WS2812B, eine LED je Knopf, in Reihe. LED 1 sitzt unter Knopf 1.
constexpr int PIN_LEDS = 47;

// Mikroschalter gegen GND, interner Pull-up. Knopf 1 bis 8.
constexpr uint8_t KNOPF_ANZAHL = 8;
constexpr int PIN_KNOPF[KNOPF_ANZAHL] = {12, 13, 14, 15, 16, 21, 39, 40};

// Frei fuer das Elternpult (Elegoo-Display mit eigenem ESP32), spaeter.
constexpr int PIN_PULT_TX = 17;
constexpr int PIN_PULT_RX = 18;
