#include "blende.h"

namespace kz {

void Blende::ziel(uint8_t stufe, uint32_t dauer_ms) {
    if (stufe == ziel_ && rate_ != 0) return;
    if (dauer_ms < KUERZESTE_MS) dauer_ms = KUERZESTE_MS;
    ziel_ = stufe;
    uint32_t ziel_fest = static_cast<uint32_t>(stufe) << 8;
    uint32_t abstand = ziel_fest > stufe_ ? ziel_fest - stufe_ : stufe_ - ziel_fest;
    // Mindestens die Rate, die von ganz dunkel nach ganz hell in `dauer_ms`
    // fuehrt; so dauert ein kurzer Weg nicht laenger als ein langer.
    // Aufgerundet, sonst fehlt am Ende eine Stufe.
    uint32_t rate_voll = ((255u << 8) + dauer_ms - 1) / dauer_ms;
    uint32_t rate_weg = (abstand + dauer_ms - 1) / dauer_ms;
    rate_ = rate_weg > rate_voll ? rate_weg : rate_voll;
    if (rate_ == 0) rate_ = 1;
}

void Blende::schritt(uint32_t dt_ms) {
    uint32_t ziel_fest = static_cast<uint32_t>(ziel_) << 8;
    uint32_t weg = rate_ * dt_ms;
    if (stufe_ < ziel_fest) {
        stufe_ = (ziel_fest - stufe_ <= weg) ? ziel_fest : stufe_ + weg;
    } else if (stufe_ > ziel_fest) {
        stufe_ = (stufe_ - ziel_fest <= weg) ? ziel_fest : stufe_ - weg;
    }
}

}  // namespace kz
