#pragma once
// Das Spielgeraet: Eingaben rein, Licht, Ton und Protokoll raus.
//
// Phase 1 kennt zwei Spiele, die sich nicht in die Quere kommen, weil sie an
// verschiedenen Eingaben haengen:
//   licht-und-klang  Knopf -> sofort Licht in der Knopffarbe und sein Klang
//   stimmen          Figur auflegen -> Stimme, dann Klang der Figur
// Beide antworten, solange sie in `spiele_aktiv` stehen. Welches zuletzt
// benutzt wurde, steht als Ereignis "spiel" im Tagebuch.
//
// Paedagogische Leitlinien, die hier Code geworden sind: sofort und immer
// gleich (6), nie von sich aus (7), kein Blinken, Licht und Ton hart
// gedeckelt (8). Siehe modules/kinderzimmer/AGENTS.md.

#include <cstdint>
#include <string>
#include <vector>

#include "blende.h"
#include "farbe.h"
#include "protokoll.h"
#include "stand.h"

namespace kz {

struct Meldung {
    Art art = Art::start;
    uint8_t knopf = 0;
    std::string uid;
    std::string spiel;
};

struct Ausgabe {
    std::vector<Meldung> meldungen;
    bool ton_stoppen = false;  // laufenden Ton abbrechen (vor einem neuen)
    bool ton_starten = false;
    std::vector<std::string> ton;  // Aufnahme-IDs, nacheinander
    uint32_t ton_nr = 0;           // Kennung fuer wiedergabe_ende()
};

class Spielgeraet {
   public:
    static constexpr uint8_t LEDS = 8;
    static constexpr uint32_t AN_MS = 150;              // Aufblenden: sofort, aber weich
    static constexpr uint32_t NACHLEUCHTEN_MS = 2000;   // nach dem Klang
    static constexpr uint32_t AUS_MS = 1200;            // Abblenden
    static constexpr uint32_t RUHE_AUS_MS = 3000;       // Abblenden in die Ruhe
    static constexpr uint32_t ABGLEICH_PAUSE_MS = 15000;
    static constexpr uint32_t LAENGSTER_TAKT_MS = 50;   // laengere Luecken werden kein Sprung

    explicit Spielgeraet(Stand stand);

    Ausgabe start(uint32_t jetzt);
    Ausgabe knopf(uint8_t nummer, uint32_t jetzt);
    Ausgabe figur_auf(const std::string& uid, uint32_t jetzt);
    Ausgabe figur_ab(uint32_t jetzt);
    void wiedergabe_ende(uint32_t ton_nr, uint32_t jetzt);
    Ausgabe tick(uint32_t jetzt);

    // Gilt ab der naechsten Handlung. Nur aufrufen, wenn darf_abgleichen().
    void neuer_stand(Stand stand);
    const Stand& stand() const { return stand_; }

    // Kein Ton, keine Figur, eine Weile nichts gedrueckt: Jetzt stoert ein
    // Abgleich niemanden.
    bool darf_abgleichen(uint32_t jetzt) const;
    bool ruht() const { return ruht_; }
    bool spielt() const { return spielt_; }

    Farbe led(uint8_t index) const;
    uint8_t lautstaerke() const { return stand_.lautstaerke_max; }

   private:
    void handlung(uint32_t jetzt);
    void spielwechsel(const char* spiel, Ausgabe& a);
    void ton_stoppen(Ausgabe& a);
    void ton_starten(std::vector<std::string> ids, int led, Ausgabe& a);

    Stand stand_;
    Blende blende_[LEDS];
    Farbe farbe_[LEDS];
    bool haelt_[LEDS] = {};
    uint32_t halten_bis_[LEDS] = {};

    bool spielt_ = false;
    uint32_t ton_nr_ = 0;
    int led_zum_ton_ = -1;

    std::string figur_;
    std::string aktuelles_spiel_;
    bool hatte_handlung_ = false;
    uint32_t letzte_handlung_ = 0;
    bool ruht_ = false;
    uint32_t letzter_takt_ = 0;
};

}  // namespace kz
