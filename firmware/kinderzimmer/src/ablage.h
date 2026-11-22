#pragma once
// Flash (LittleFS). Hier wird nur gelesen und geschrieben, entschieden wird
// in lib/logik.
//
//   /stand.json         letzter vollstaendiger Stand (das Manifest, roh)
//   /dateien/<sha>.wav  Aufnahmen, benannt nach ihrer Pruefsumme
//   /neu/<sha>.part     Zwischenordner waehrend eines Abgleichs
//   /puffer.jsonl       Ereignisse, die noch nicht beim Pi sind

#include <string>
#include <vector>

#include "stand.h"
#include "versand.h"

namespace ablage {

bool beginnen();

bool stand_laden(kz::Stand& aus);
// Schreibt erst /stand.neu und benennt dann um: Ein Stromausfall dazwischen
// laesst den alten Stand stehen.
bool stand_schreiben(const std::string& json);

std::string pfad(const std::string& sha);       // /dateien/<sha>.wav
std::string zwischenpfad(const std::string& sha);  // /neu/<sha>.part
bool vorhanden(const std::string& sha);
std::vector<std::string> vorhandene();
void entferne(const std::string& sha);
// Aus dem Zwischenordner an seinen Platz.
bool uebernehmen(const std::string& sha);
void zwischenordner_leeren();
size_t frei();

class FlashPuffer : public kz::Puffer {
   public:
    void anhaengen(const std::vector<std::string>& zeilen) override;
    std::vector<std::string> erste(size_t n) override;
    void entferne_erste(size_t n) override;
    size_t anzahl() override;

   private:
    bool gezaehlt_ = false;
    size_t anzahl_ = 0;
};

}  // namespace ablage
