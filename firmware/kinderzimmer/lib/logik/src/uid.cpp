#include "uid.h"

namespace kz {

std::string uid_hex(const uint8_t* bytes, uint8_t laenge) {
    if (bytes == nullptr || (laenge != 4 && laenge != 7 && laenge != 10)) return {};
    static const char ZIFFERN[] = "0123456789ABCDEF";
    std::string aus;
    aus.reserve(laenge * 2);
    for (uint8_t i = 0; i < laenge; ++i) {
        aus.push_back(ZIFFERN[bytes[i] >> 4]);
        aus.push_back(ZIFFERN[bytes[i] & 0x0F]);
    }
    return aus;
}

}  // namespace kz
