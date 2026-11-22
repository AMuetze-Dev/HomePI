#include "ablage.h"

#include <Arduino.h>
#include <LittleFS.h>

#include "abgleich.h"

namespace ablage {

namespace {

const char* const STAND = "/stand.json";
const char* const STAND_NEU = "/stand.neu";
const char* const DATEIEN = "/dateien";
const char* const NEU = "/neu";
const char* const PUFFER = "/puffer.jsonl";
const char* const PUFFER_NEU = "/puffer.neu";

bool lies_zeile(File& f, std::string& zeile) {
    zeile.clear();
    if (!f.available()) return false;
    while (f.available()) {
        int c = f.read();
        if (c < 0 || c == '\n') break;
        zeile.push_back(static_cast<char>(c));
    }
    return true;
}

}  // namespace

bool beginnen() {
    // Beim allerersten Start ist der Bereich leer: dann formatieren.
    if (!LittleFS.begin(true)) {
        Serial.println("[ablage] LittleFS laesst sich nicht einhaengen");
        return false;
    }
    if (!LittleFS.exists(DATEIEN)) LittleFS.mkdir(DATEIEN);
    if (!LittleFS.exists(NEU)) LittleFS.mkdir(NEU);
    Serial.printf("[ablage] %u von %u KB frei\n", static_cast<unsigned>(frei() / 1024),
                  static_cast<unsigned>(LittleFS.totalBytes() / 1024));
    return true;
}

bool stand_laden(kz::Stand& aus) {
    File f = LittleFS.open(STAND, "r");
    if (!f) return false;
    std::string json;
    json.reserve(f.size());
    while (f.available()) {
        char puffer[256];
        size_t n = f.readBytes(puffer, sizeof(puffer));
        json.append(puffer, n);
    }
    f.close();
    return kz::stand_lesen(json, aus) == kz::LeseErgebnis::ok;
}

bool stand_schreiben(const std::string& json) {
    File f = LittleFS.open(STAND_NEU, "w");
    if (!f) return false;
    size_t n = f.write(reinterpret_cast<const uint8_t*>(json.data()), json.size());
    f.close();
    if (n != json.size()) {
        LittleFS.remove(STAND_NEU);
        return false;
    }
    return LittleFS.rename(STAND_NEU, STAND);
}

std::string pfad(const std::string& sha) {
    return std::string(DATEIEN) + "/" + kz::dateiname(sha);
}

std::string zwischenpfad(const std::string& sha) {
    return std::string(NEU) + "/" + kz::dateiname(sha) + ".part";
}

bool vorhanden(const std::string& sha) {
    return LittleFS.exists(pfad(sha).c_str());
}

std::vector<std::string> vorhandene() {
    std::vector<std::string> shas;
    File ordner = LittleFS.open(DATEIEN);
    if (!ordner) return shas;
    for (File f = ordner.openNextFile(); f; f = ordner.openNextFile()) {
        std::string name = f.name();
        size_t schraeg = name.rfind('/');
        if (schraeg != std::string::npos) name = name.substr(schraeg + 1);
        if (name.size() > 4 && name.compare(name.size() - 4, 4, ".wav") == 0)
            shas.push_back(name.substr(0, name.size() - 4));
    }
    return shas;
}

void entferne(const std::string& sha) {
    LittleFS.remove(pfad(sha).c_str());
}

bool uebernehmen(const std::string& sha) {
    return LittleFS.rename(zwischenpfad(sha).c_str(), pfad(sha).c_str());
}

void zwischenordner_leeren() {
    File ordner = LittleFS.open(NEU);
    if (!ordner) return;
    std::vector<std::string> weg;
    for (File f = ordner.openNextFile(); f; f = ordner.openNextFile())
        weg.push_back(std::string(NEU) + "/" + f.name());
    ordner.close();
    for (const auto& p : weg) LittleFS.remove(p.c_str());
}

size_t frei() {
    return LittleFS.totalBytes() - LittleFS.usedBytes();
}

// --- Ereignispuffer ------------------------------------------------------

void FlashPuffer::anhaengen(const std::vector<std::string>& zeilen) {
    size_t vorher = anzahl();
    File f = LittleFS.open(PUFFER, "a");
    if (!f) return;
    for (const auto& z : zeilen) {
        f.write(reinterpret_cast<const uint8_t*>(z.data()), z.size());
        f.write('\n');
    }
    f.close();
    anzahl_ = vorher + zeilen.size();
}

std::vector<std::string> FlashPuffer::erste(size_t n) {
    std::vector<std::string> aus;
    File f = LittleFS.open(PUFFER, "r");
    if (!f) return aus;
    std::string zeile;
    while (aus.size() < n && lies_zeile(f, zeile))
        if (!zeile.empty()) aus.push_back(zeile);
    return aus;
}

void FlashPuffer::entferne_erste(size_t n) {
    File alt = LittleFS.open(PUFFER, "r");
    if (!alt) return;
    File neu = LittleFS.open(PUFFER_NEU, "w");
    std::string zeile;
    size_t uebrig = 0, uebersprungen = 0;
    while (lies_zeile(alt, zeile)) {
        if (zeile.empty()) continue;
        if (uebersprungen < n) {
            ++uebersprungen;
            continue;
        }
        neu.write(reinterpret_cast<const uint8_t*>(zeile.data()), zeile.size());
        neu.write('\n');
        ++uebrig;
    }
    alt.close();
    neu.close();
    if (uebrig == 0) {
        LittleFS.remove(PUFFER_NEU);
        LittleFS.remove(PUFFER);
    } else {
        LittleFS.rename(PUFFER_NEU, PUFFER);
    }
    anzahl_ = uebrig;
    gezaehlt_ = true;
}

size_t FlashPuffer::anzahl() {
    if (gezaehlt_) return anzahl_;
    anzahl_ = 0;
    File f = LittleFS.open(PUFFER, "r");
    std::string zeile;
    if (f)
        while (lies_zeile(f, zeile))
            if (!zeile.empty()) ++anzahl_;
    gezaehlt_ = true;
    return anzahl_;
}

}  // namespace ablage
