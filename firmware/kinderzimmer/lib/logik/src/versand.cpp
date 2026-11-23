#include "versand.h"

namespace kz {

void SpeicherPuffer::anhaengen(const std::vector<std::string>& zeilen) {
    zeilen_.insert(zeilen_.end(), zeilen.begin(), zeilen.end());
}

std::vector<std::string> SpeicherPuffer::erste(size_t n) {
    if (n > zeilen_.size()) n = zeilen_.size();
    return std::vector<std::string>(zeilen_.begin(), zeilen_.begin() + static_cast<long>(n));
}

void SpeicherPuffer::entferne_erste(size_t n) {
    if (n > zeilen_.size()) n = zeilen_.size();
    zeilen_.erase(zeilen_.begin(), zeilen_.begin() + static_cast<long>(n));
}

Versand::Versand(Puffer& puffer, size_t stapel, size_t puffer_max)
    : puffer_(puffer), stapel_(stapel == 0 ? 1 : stapel), puffer_max_(puffer_max) {}

void Versand::neu(const Ereignis& e) {
    ram_.push_back(e);
}

bool Versand::offen() {
    return !ram_.empty() || puffer_.anzahl() > 0;
}

Stapel Versand::stapel() {
    Stapel s;
    // Zuerst der Flash. Kaputte Zeilen zaehlen mit, damit erfolg() sie
    // entfernt - sonst blockierten sie den Puffer fuer immer.
    for (const auto& zeile : puffer_.erste(stapel_)) {
        ++s.aus_puffer;
        Ereignis e;
        if (aus_zeile(zeile, e)) s.ereignisse.push_back(e);
    }
    while (s.ereignisse.size() < stapel_ && s.aus_ram < ram_.size()) {
        s.ereignisse.push_back(ram_[s.aus_ram]);
        ++s.aus_ram;
    }
    return s;
}

void Versand::erfolg(const Stapel& s) {
    puffer_.entferne_erste(s.aus_puffer);
    size_t n = s.aus_ram < ram_.size() ? s.aus_ram : ram_.size();
    ram_.erase(ram_.begin(), ram_.begin() + static_cast<long>(n));
    wartezeit_ms_ = 0;
}

void Versand::fehlschlag(const Stapel& s) {
    in_den_puffer(s.aus_ram);
    if (wartezeit_ms_ == 0)
        wartezeit_ms_ = ERSTE_WARTEZEIT_MS;
    else
        wartezeit_ms_ = wartezeit_ms_ * 2 > LAENGSTE_WARTEZEIT_MS ? LAENGSTE_WARTEZEIT_MS
                                                                    : wartezeit_ms_ * 2;
}

void Versand::offline() {
    in_den_puffer(ram_.size());
}

void Versand::in_den_puffer(size_t n) {
    if (n > ram_.size()) n = ram_.size();
    if (n == 0) return;
    std::vector<std::string> zeilen;
    zeilen.reserve(n);
    for (size_t i = 0; i < n; ++i) zeilen.push_back(als_zeile(ram_[i]));
    puffer_.anhaengen(zeilen);
    ram_.erase(ram_.begin(), ram_.begin() + static_cast<long>(n));
    size_t da = puffer_.anzahl();
    if (da > puffer_max_) puffer_.entferne_erste(da - puffer_max_);
}

}  // namespace kz
