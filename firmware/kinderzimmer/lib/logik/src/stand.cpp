#include "stand.h"

#include <ArduinoJson.h>

#include <algorithm>
#include <cctype>

namespace kz {

namespace {

std::string text(JsonVariantConst v) {
    const char* s = v.as<const char*>();
    return s == nullptr ? std::string() : std::string(s);
}

std::string gross(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
    return s;
}

std::string klein(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

// Fehlt der Wert, gilt `vorgabe`; liegt er ausserhalb, wird er in den
// Bereich gezogen, den auch der Pi erlaubt.
long begrenzt(JsonVariantConst v, long vorgabe, long unten, long oben) {
    if (!v.is<long>()) return vorgabe;
    long x = v.as<long>();
    return x < unten ? unten : (x > oben ? oben : x);
}

}  // namespace

bool Stand::spiel_aktiv(const std::string& id) const {
    return std::find(spiele_aktiv.begin(), spiele_aktiv.end(), id) != spiele_aktiv.end();
}

const Knopf* Stand::knopf(uint8_t nummer) const {
    for (const auto& k : knoepfe)
        if (k.nummer == nummer) return &k;
    return nullptr;
}

const Figur* Stand::figur(const std::string& uid) const {
    std::string g = gross(uid);
    for (const auto& f : figuren)
        if (f.uid == g) return &f;
    return nullptr;
}

const Datei* Stand::datei(const std::string& id) const {
    for (const auto& d : dateien)
        if (d.id == id) return &d;
    return nullptr;
}

LeseErgebnis stand_lesen(const std::string& json, Stand& aus) {
    JsonDocument doc;
    if (deserializeJson(doc, json)) return LeseErgebnis::kaputt;
    if (!doc["format"].is<int>()) return LeseErgebnis::kaputt;
    if (doc["format"].as<int>() > FORMAT) return LeseErgebnis::format_zu_neu;
    if (doc["format"].as<int>() < 1) return LeseErgebnis::kaputt;
    std::string stand = text(doc["stand"]);
    if (stand.empty()) return LeseErgebnis::kaputt;

    Stand s;
    s.stand = stand;
    JsonObjectConst e = doc["einstellungen"];
    s.lautstaerke_max = static_cast<uint8_t>(begrenzt(e["lautstaerke_max"], 40, 5, 100));
    s.helligkeit_max = static_cast<uint8_t>(begrenzt(e["helligkeit_max"], 40, 5, 100));
    s.ruhe_nach_min = static_cast<uint16_t>(begrenzt(e["ruhe_nach_min"], 10, 1, 60));
    if (e["startspiel"].is<const char*>()) s.startspiel = text(e["startspiel"]);
    if (e["spiele_aktiv"].is<JsonArrayConst>()) {
        for (JsonVariantConst id : e["spiele_aktiv"].as<JsonArrayConst>())
            if (id.is<const char*>()) s.spiele_aktiv.push_back(text(id));
    } else {
        s.spiele_aktiv = {"licht-und-klang", "stimmen"};
    }
    for (JsonObjectConst k : e["knoepfe"].as<JsonArrayConst>()) {
        Knopf knopf;
        knopf.nummer = static_cast<uint8_t>(begrenzt(k["nummer"], 0, 0, 8));
        if (knopf.nummer == 0) continue;
        if (!farbe_lesen(k["farbe"].as<const char*>(), knopf.farbe)) continue;
        knopf.klang = text(k["klang"]);
        s.knoepfe.push_back(knopf);
    }
    for (JsonObjectConst f : doc["figuren"].as<JsonArrayConst>()) {
        Figur figur;
        figur.uid = gross(text(f["uid"]));
        if (figur.uid.empty()) continue;
        figur.name = text(f["name"]);
        figur.stimme = text(f["stimme"]);
        figur.klang = text(f["klang"]);
        s.figuren.push_back(figur);
    }
    for (JsonObjectConst d : doc["dateien"].as<JsonArrayConst>()) {
        Datei datei;
        datei.id = text(d["id"]);
        datei.sha256 = klein(text(d["sha256"]));
        if (datei.id.empty() || datei.sha256.empty()) continue;
        datei.bytes = d["bytes"].as<uint32_t>();
        datei.dauer_ms = d["dauer_ms"].as<uint32_t>();
        s.dateien.push_back(datei);
    }
    aus = std::move(s);
    return LeseErgebnis::ok;
}

Stand stand_vorgabe() {
    Stand s;
    s.spiele_aktiv = {"licht-und-klang", "stimmen"};
    Knopf eins;
    eins.nummer = 1;
    farbe_lesen("#FFB000", eins.farbe);
    s.knoepfe.push_back(eins);
    return s;
}

}  // namespace kz
