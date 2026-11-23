#pragma once
// Sanftes Ueberblenden einer LED. Es gibt keinen Sprung: Die Stufe bewegt
// sich immer von dort, wo sie gerade steht, gleichmaessig zum Ziel.

#include <cstdint>

namespace kz {

class Blende {
   public:
    // Kuerzeste erlaubte Blende. Kuerzere Wuensche werden auf sie verlaengert.
    static constexpr uint32_t KUERZESTE_MS = 100;

    // Neues Ziel, erreicht in `dauer_ms` vom aktuellen Stand aus.
    void ziel(uint8_t stufe, uint32_t dauer_ms);
    void schritt(uint32_t dt_ms);

    uint8_t stufe() const { return static_cast<uint8_t>(stufe_ >> 8); }
    uint8_t zielstufe() const { return ziel_; }
    bool fertig() const { return stufe() == ziel_; }

   private:
    uint32_t stufe_ = 0;    // 8.8 Festkomma, damit langsame Blenden nicht stehen bleiben
    uint32_t rate_ = 0;     // Festkomma-Einheiten je Millisekunde
    uint8_t ziel_ = 0;
};

}  // namespace kz
