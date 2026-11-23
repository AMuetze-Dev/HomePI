#pragma once
// Der Stand: alles, was das Geraet vom Pi braucht, um allein zu spielen.
// Er kommt als Manifest (GET /kinderzimmer/geraet/stand, Format 1) und liegt
// im Flash, damit das Geraet ohne Pi mit dem letzten Stand weiterspielt.

#include <cstdint>
#include <string>
#include <vector>

#include "farbe.h"

namespace kz {

constexpr int FORMAT = 1;

struct Knopf {
    uint8_t nummer = 0;
    Farbe farbe;
    std::string klang;  // Aufnahme-ID, leer = kein Klang
};

struct Figur {
    std::string uid;  // gross, ohne Trenner
    std::string name;
    std::string stimme;  // Aufnahme-ID oder leer
    std::string klang;   // Aufnahme-ID oder leer
};

struct Datei {
    std::string id;
    std::string sha256;  // klein geschrieben
    uint32_t bytes = 0;
    uint32_t dauer_ms = 0;
};

struct Stand {
    std::string stand;  // leer = noch nie abgeglichen
    uint8_t lautstaerke_max = 40;
    uint8_t helligkeit_max = 40;
    uint16_t ruhe_nach_min = 10;
    std::string startspiel = "licht-und-klang";
    std::vector<std::string> spiele_aktiv;
    std::vector<Knopf> knoepfe;
    std::vector<Figur> figuren;
    std::vector<Datei> dateien;

    bool spiel_aktiv(const std::string& id) const;
    const Knopf* knopf(uint8_t nummer) const;
    const Figur* figur(const std::string& uid) const;  // gross oder klein
    const Datei* datei(const std::string& id) const;
};

enum class LeseErgebnis { ok, kaputt, format_zu_neu };

// Bei allem ausser `ok` bleibt `aus` unberuehrt: Ein kaputtes oder zu
// neues Manifest ersetzt nie einen guten Stand.
LeseErgebnis stand_lesen(const std::string& json, Stand& aus);

// Erster Start ohne Pi: die Voreinstellungen des Pi (ein Knopf, Bernstein,
// kein Klang). Das Licht geht damit schon, der Ton kommt mit dem Abgleich.
Stand stand_vorgabe();

}  // namespace kz
