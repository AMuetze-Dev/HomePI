#pragma once
// Protokoll: Ereignisse fuer POST /kinderzimmer/geraet/ereignisse (Format 1).
//
// (geraet, start, nr) ist beim Pi eindeutig. Doppelt senden ist deshalb
// harmlos, verlieren nicht: Im Zweifel lieber noch einmal.

#include <cstdint>
#include <string>
#include <vector>

namespace kz {

enum class Art : uint8_t { start, knopf, figur_auf, figur_ab, spiel, ruhe, abgleich };

const char* art_name(Art art);
bool art_aus_name(const char* name, Art& art);

struct Ereignis {
    uint32_t start = 0;  // Startzaehler, in dem es geschah
    uint32_t nr = 0;     // laufend je Start, ab 1
    uint32_t ms = 0;     // seit dem Start
    std::string zeit;    // ISO 8601, leer = Uhr noch nicht gestellt
    Art art = Art::start;
    uint8_t knopf = 0;   // bei knopf
    std::string uid;     // bei figur_auf / figur_ab
    std::string spiel;   // bei spiel
};

class Protokoll {
   public:
    explicit Protokoll(uint32_t start) : start_(start) {}
    Ereignis neu(Art art, uint32_t ms, const std::string& zeit);
    uint32_t start() const { return start_; }

   private:
    uint32_t start_;
    uint32_t nr_ = 0;
};

// Rumpf einer Sendung. Ein Ereignis traegt "start" nur, wenn es aus einem
// frueheren Start nachgereicht wird. Leerer `stand` wird zu null.
std::string sendung(uint32_t start, uint32_t jetzt_ms, const std::string& firmware,
                    const std::string& stand, const std::vector<Ereignis>& ereignisse);

// Antwort {"neu": .., "doppelt": .., "stand": ".."} -> stand.
bool antwort_lesen(const std::string& json, std::string& stand);

// Eine Zeile im Flash-Puffer: JSON ohne Zeilenumbruch, mit "start".
std::string als_zeile(const Ereignis& e);
bool aus_zeile(const std::string& zeile, Ereignis& e);

// Sekunden seit 1970 (UTC) -> "2026-11-20T07:15:02+00:00". Vor 2024 heisst
// das: NTP lief noch nicht. Dann leer.
std::string iso_utc(int64_t sekunden);

}  // namespace kz
