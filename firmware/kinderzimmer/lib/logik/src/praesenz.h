#pragma once
// Liegt eine Figur auf dem Leser? Der PN532 liest nicht bei jedem Versuch;
// ein einzelner Aussetzer ist kein Abheben. Erst nach HALTE_MS ohne Lesen
// gilt die Figur als weg.

#include <cstdint>
#include <string>

namespace kz {

struct Wechsel {
    bool ab = false;   // die bisherige Figur ist weg (uid: welche, falls nicht auch auf)
    bool auf = false;  // eine Figur kam dazu (uid: welche)
    std::string uid;
};

class Praesenz {
   public:
    static constexpr uint32_t HALTE_MS = 700;

    // `gelesen`: UID aus diesem Leseversuch, leer = nichts gelesen.
    Wechsel melde(const std::string& gelesen, uint32_t jetzt) {
        Wechsel w;
        if (!gelesen.empty()) {
            if (gelesen != liegt_) {
                w.ab = !liegt_.empty();
                w.auf = true;
                w.uid = gelesen;
                liegt_ = gelesen;
            }
            zuletzt_ = jetzt;
        } else if (!liegt_.empty() && jetzt - zuletzt_ >= HALTE_MS) {
            w.ab = true;
            w.uid = liegt_;
            liegt_.clear();
        }
        return w;
    }

    const std::string& liegt() const { return liegt_; }

   private:
    std::string liegt_;
    uint32_t zuletzt_ = 0;
};

}  // namespace kz
