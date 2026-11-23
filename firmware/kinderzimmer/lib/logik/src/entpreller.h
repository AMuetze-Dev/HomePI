#pragma once
// Mikroschalter prellen. Ein Druck zaehlt, wenn der Kontakt STABIL_MS lang
// ruhig anliegt; gemeldet wird nur die Flanke "jetzt gedrueckt".

#include <cstdint>

namespace kz {

class Entpreller {
   public:
    static constexpr uint32_t STABIL_MS = 20;

    // `roh`: true = Kontakt geschlossen. Liefert true genau einmal je Druck.
    bool schritt(bool roh, uint32_t jetzt) {
        if (roh != letzter_roh_) {
            letzter_roh_ = roh;
            seit_ = jetzt;
            return false;
        }
        if (roh != stabil_ && jetzt - seit_ >= STABIL_MS) {
            stabil_ = roh;
            return roh;
        }
        return false;
    }

    bool gedrueckt() const { return stabil_; }

   private:
    bool letzter_roh_ = false;
    bool stabil_ = false;
    uint32_t seit_ = 0;
};

}  // namespace kz
