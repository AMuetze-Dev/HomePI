#pragma once
// Versand: Ereignisse live senden, ohne Verbindung im Flash puffern und beim
// naechsten Erfolg nachreichen. Gepuffertes geht vor Neuem.
//
// Die Klasse entscheidet nur. Senden tut das Netz, speichern der Puffer.

#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

#include "protokoll.h"

namespace kz {

// Zeilen im Flash, aelteste zuerst.
class Puffer {
   public:
    virtual ~Puffer() = default;
    virtual void anhaengen(const std::vector<std::string>& zeilen) = 0;
    virtual std::vector<std::string> erste(size_t n) = 0;
    virtual void entferne_erste(size_t n) = 0;
    virtual size_t anzahl() = 0;
};

// Puffer im Arbeitsspeicher, fuer die Tests.
class SpeicherPuffer : public Puffer {
   public:
    void anhaengen(const std::vector<std::string>& zeilen) override;
    std::vector<std::string> erste(size_t n) override;
    void entferne_erste(size_t n) override;
    size_t anzahl() override { return zeilen_.size(); }

   private:
    std::deque<std::string> zeilen_;
};

struct Stapel {
    std::vector<Ereignis> ereignisse;
    size_t aus_puffer = 0;  // Zeilen im Flash, die dieser Stapel abdeckt
    size_t aus_ram = 0;
};

class Versand {
   public:
    static constexpr uint32_t ERSTE_WARTEZEIT_MS = 2000;
    static constexpr uint32_t LAENGSTE_WARTEZEIT_MS = 300000;

    // `stapel`: hoechstens so viele Ereignisse je Sendung (der Pi nimmt 500).
    // `puffer_max`: so viele Zeilen hoechstens im Flash; darueber faellt das
    // Aelteste weg. Ein Tagebuch mit Luecke ist besser als ein voller Flash.
    Versand(Puffer& puffer, size_t stapel = 50, size_t puffer_max = 20000);

    void neu(const Ereignis& e);
    bool offen();

    Stapel stapel();
    void erfolg(const Stapel& s);
    void fehlschlag(const Stapel& s);
    // Keine Verbindung: alles aus dem Arbeitsspeicher sofort in den Flash,
    // damit ein Ausschalten nichts kostet.
    void offline();

    // Wie lange vor dem naechsten Versuch gewartet wird; 0 = sofort.
    uint32_t wartezeit_ms() const { return wartezeit_ms_; }

   private:
    void in_den_puffer(size_t n);

    Puffer& puffer_;
    size_t stapel_;
    size_t puffer_max_;
    std::deque<Ereignis> ram_;
    uint32_t wartezeit_ms_ = 0;
};

}  // namespace kz
