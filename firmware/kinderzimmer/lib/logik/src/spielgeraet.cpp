#include "spielgeraet.h"

#include <utility>

namespace kz {

namespace {
const char* const LICHT_UND_KLANG = "licht-und-klang";
const char* const STIMMEN = "stimmen";
}  // namespace

Spielgeraet::Spielgeraet(Stand stand) : stand_(std::move(stand)) {}

Ausgabe Spielgeraet::start(uint32_t jetzt) {
    Ausgabe a;
    letzter_takt_ = jetzt;
    a.meldungen.push_back({Art::start, 0, "", ""});
    aktuelles_spiel_ = stand_.startspiel;
    a.meldungen.push_back({Art::spiel, 0, "", aktuelles_spiel_});
    return a;
}

void Spielgeraet::handlung(uint32_t jetzt) {
    hatte_handlung_ = true;
    letzte_handlung_ = jetzt;
    ruht_ = false;
}

void Spielgeraet::spielwechsel(const char* spiel, Ausgabe& a) {
    if (aktuelles_spiel_ == spiel) return;
    aktuelles_spiel_ = spiel;
    a.meldungen.push_back({Art::spiel, 0, "", aktuelles_spiel_});
}

void Spielgeraet::ton_stoppen(Ausgabe& a) {
    if (!spielt_) return;
    spielt_ = false;
    ++ton_nr_;  // ein verspaetetes Ende des alten Tons gilt nicht mehr
    a.ton_stoppen = true;
    a.ton_nr = ton_nr_;
}

void Spielgeraet::ton_starten(std::vector<std::string> ids, int led, Ausgabe& a) {
    ton_stoppen(a);
    led_zum_ton_ = -1;
    if (ids.empty()) return;
    ++ton_nr_;
    spielt_ = true;
    led_zum_ton_ = led;
    a.ton_starten = true;
    a.ton = std::move(ids);
    a.ton_nr = ton_nr_;
}

Ausgabe Spielgeraet::knopf(uint8_t nummer, uint32_t jetzt) {
    Ausgabe a;
    handlung(jetzt);
    const Knopf* k = stand_.knopf(nummer);
    bool aktiv = stand_.spiel_aktiv(LICHT_UND_KLANG) && k != nullptr;
    if (aktiv) spielwechsel(LICHT_UND_KLANG, a);
    a.meldungen.push_back({Art::knopf, nummer, "", ""});
    if (!aktiv) return a;

    int idx = nummer >= 1 && nummer <= LEDS ? nummer - 1 : -1;
    for (int i = 0; i < LEDS; ++i) {
        if (i == idx) continue;
        blende_[i].ziel(0, AUS_MS);
        haelt_[i] = false;
    }
    if (idx >= 0) {
        farbe_[idx] = k->farbe;
        blende_[idx].ziel(255, AN_MS);
        haelt_[idx] = true;
        halten_bis_[idx] = jetzt + NACHLEUCHTEN_MS;
    }

    std::vector<std::string> ids;
    if (!k->klang.empty()) ids.push_back(k->klang);
    ton_starten(std::move(ids), idx, a);
    return a;
}

Ausgabe Spielgeraet::figur_auf(const std::string& uid, uint32_t jetzt) {
    Ausgabe a;
    handlung(jetzt);
    figur_ = uid;
    const Figur* f = stand_.figur(uid);
    bool aktiv = stand_.spiel_aktiv(STIMMEN) && f != nullptr;
    if (aktiv) spielwechsel(STIMMEN, a);
    a.meldungen.push_back({Art::figur_auf, 0, uid, ""});
    if (!aktiv) return a;

    std::vector<std::string> ids;
    if (!f->stimme.empty()) ids.push_back(f->stimme);
    if (!f->klang.empty()) ids.push_back(f->klang);
    ton_starten(std::move(ids), -1, a);
    return a;
}

Ausgabe Spielgeraet::figur_ab(uint32_t jetzt) {
    Ausgabe a;
    handlung(jetzt);
    if (figur_.empty()) return a;
    a.meldungen.push_back({Art::figur_ab, 0, figur_, ""});
    figur_.clear();
    return a;
}

void Spielgeraet::wiedergabe_ende(uint32_t ton_nr, uint32_t jetzt) {
    if (!spielt_ || ton_nr != ton_nr_) return;
    spielt_ = false;
    if (led_zum_ton_ >= 0) halten_bis_[led_zum_ton_] = jetzt + NACHLEUCHTEN_MS;
}

Ausgabe Spielgeraet::tick(uint32_t jetzt) {
    Ausgabe a;
    uint32_t dt = jetzt - letzter_takt_;
    if (dt > LAENGSTER_TAKT_MS) dt = LAENGSTER_TAKT_MS;
    letzter_takt_ = jetzt;

    uint32_t ruhe_ms = static_cast<uint32_t>(stand_.ruhe_nach_min) * 60000u;
    if (hatte_handlung_ && !ruht_ && jetzt - letzte_handlung_ >= ruhe_ms) {
        ruht_ = true;
        a.meldungen.push_back({Art::ruhe, 0, "", ""});
        ton_stoppen(a);
        a.ton_stoppen = true;
        for (int i = 0; i < LEDS; ++i) {
            blende_[i].ziel(0, RUHE_AUS_MS);
            haelt_[i] = false;
        }
    }

    for (int i = 0; i < LEDS; ++i) {
        if (!haelt_[i]) continue;
        bool klingt = spielt_ && led_zum_ton_ == i;
        if (!klingt && static_cast<int32_t>(jetzt - halten_bis_[i]) >= 0) {
            blende_[i].ziel(0, AUS_MS);
            haelt_[i] = false;
        }
    }
    for (auto& b : blende_) b.schritt(dt);
    return a;
}

void Spielgeraet::neuer_stand(Stand stand) {
    stand_ = std::move(stand);
}

bool Spielgeraet::darf_abgleichen(uint32_t jetzt) const {
    if (spielt_ || !figur_.empty()) return false;
    if (!hatte_handlung_ || ruht_) return true;
    return jetzt - letzte_handlung_ >= ABGLEICH_PAUSE_MS;
}

Farbe Spielgeraet::led(uint8_t index) const {
    if (index >= LEDS) return {};
    return gedimmt(farbe_[index], stand_.helligkeit_max, blende_[index].stufe());
}

}  // namespace kz
