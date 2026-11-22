#include "protokoll.h"

#include <ArduinoJson.h>

#include <cstdio>
#include <cstring>

namespace kz {

namespace {

const char* const NAMEN[] = {"start", "knopf", "figur_auf", "figur_ab", "spiel", "ruhe", "abgleich"};
constexpr int ANZAHL = sizeof(NAMEN) / sizeof(NAMEN[0]);

// 2024-01-01T00:00:00Z
constexpr int64_t UHR_GESTELLT_AB = 1704067200;

void schreibe(JsonObject o, const Ereignis& e, bool mit_start) {
    if (mit_start) o["start"] = e.start;
    o["nr"] = e.nr;
    o["ms"] = e.ms;
    if (e.zeit.empty())
        o["zeit"] = nullptr;
    else
        o["zeit"] = e.zeit;
    o["art"] = art_name(e.art);
    switch (e.art) {
        case Art::knopf:
            o["knopf"] = e.knopf;
            break;
        case Art::figur_auf:
        case Art::figur_ab:
            o["uid"] = e.uid;
            break;
        case Art::spiel:
            o["spiel"] = e.spiel;
            break;
        default:
            break;
    }
}

// Tage seit 1970-01-01 -> Jahr, Monat, Tag (Howard Hinnant, civil_from_days).
void datum(int64_t tage, int& jahr, int& monat, int& tag) {
    tage += 719468;
    int64_t era = (tage >= 0 ? tage : tage - 146096) / 146097;
    int64_t doe = tage - era * 146097;
    int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int64_t y = yoe + era * 400;
    int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    int64_t mp = (5 * doy + 2) / 153;
    tag = static_cast<int>(doy - (153 * mp + 2) / 5 + 1);
    monat = static_cast<int>(mp < 10 ? mp + 3 : mp - 9);
    jahr = static_cast<int>(y + (monat <= 2 ? 1 : 0));
}

}  // namespace

const char* art_name(Art art) {
    int i = static_cast<int>(art);
    return i < ANZAHL ? NAMEN[i] : "start";
}

bool art_aus_name(const char* name, Art& art) {
    if (name == nullptr) return false;
    for (int i = 0; i < ANZAHL; ++i) {
        if (std::strcmp(name, NAMEN[i]) == 0) {
            art = static_cast<Art>(i);
            return true;
        }
    }
    return false;
}

Ereignis Protokoll::neu(Art art, uint32_t ms, const std::string& zeit) {
    Ereignis e;
    e.start = start_;
    e.nr = ++nr_;
    e.ms = ms;
    e.zeit = zeit;
    e.art = art;
    return e;
}

std::string sendung(uint32_t start, uint32_t jetzt_ms, const std::string& firmware,
                    const std::string& stand, const std::vector<Ereignis>& ereignisse) {
    JsonDocument doc;
    doc["start"] = start;
    doc["jetzt_ms"] = jetzt_ms;
    doc["firmware"] = firmware;
    if (stand.empty())
        doc["stand"] = nullptr;
    else
        doc["stand"] = stand;
    JsonArray liste = doc["ereignisse"].to<JsonArray>();
    for (const auto& e : ereignisse) schreibe(liste.add<JsonObject>(), e, e.start != start);
    std::string aus;
    serializeJson(doc, aus);
    return aus;
}

bool antwort_lesen(const std::string& json, std::string& stand) {
    JsonDocument doc;
    if (deserializeJson(doc, json)) return false;
    const char* s = doc["stand"];
    if (s == nullptr) return false;
    stand = s;
    return true;
}

std::string als_zeile(const Ereignis& e) {
    JsonDocument doc;
    schreibe(doc.to<JsonObject>(), e, true);
    std::string aus;
    serializeJson(doc, aus);
    return aus;
}

bool aus_zeile(const std::string& zeile, Ereignis& e) {
    JsonDocument doc;
    if (deserializeJson(doc, zeile)) return false;
    if (!doc["start"].is<uint32_t>() || !doc["nr"].is<uint32_t>() || !doc["ms"].is<uint32_t>())
        return false;
    Ereignis neu;
    if (!art_aus_name(doc["art"].as<const char*>(), neu.art)) return false;
    neu.start = doc["start"];
    neu.nr = doc["nr"];
    neu.ms = doc["ms"];
    if (doc["zeit"].is<const char*>()) neu.zeit = doc["zeit"].as<const char*>();
    neu.knopf = doc["knopf"] | 0;
    if (doc["uid"].is<const char*>()) neu.uid = doc["uid"].as<const char*>();
    if (doc["spiel"].is<const char*>()) neu.spiel = doc["spiel"].as<const char*>();
    e = neu;
    return true;
}

std::string iso_utc(int64_t sekunden) {
    if (sekunden < UHR_GESTELLT_AB) return {};
    int64_t tage = sekunden / 86400;
    int64_t rest = sekunden % 86400;
    int jahr, monat, tag;
    datum(tage, jahr, monat, tag);
    char puffer[32];
    std::snprintf(puffer, sizeof(puffer), "%04d-%02d-%02dT%02d:%02d:%02d+00:00", jahr, monat, tag,
                  static_cast<int>(rest / 3600), static_cast<int>((rest / 60) % 60),
                  static_cast<int>(rest % 60));
    return puffer;
}

}  // namespace kz
