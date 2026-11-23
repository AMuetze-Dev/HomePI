#pragma once
// NFC-UIDs so, wie der Pi sie speichert: Grossbuchstaben in Hex, ohne
// Trenner, 4, 7 oder 10 Byte.

#include <cstdint>
#include <string>

namespace kz {

// Leer bei einer Laenge, die der Vertrag nicht kennt.
std::string uid_hex(const uint8_t* bytes, uint8_t laenge);

}  // namespace kz
