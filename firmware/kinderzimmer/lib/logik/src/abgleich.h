#pragma once
// Abgleich: Welche Dateien fehlen, welche duerfen weg.
//
// Aufnahmen liegen im Flash unter ihrer Pruefsumme. Gleicher Inhalt liegt
// so nur einmal da, und der alte Stand bleibt spielbar, bis der neue ganz
// geladen ist: Die neuen Dateien stoeren die alten nicht.

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "stand.h"

namespace kz {

struct Plan {
    std::vector<Datei> laden;  // je Pruefsumme hoechstens einmal
    uint32_t bytes = 0;
};

Plan plane_abgleich(const Stand& neu, const std::function<bool(const std::string& sha)>& vorhanden);

// Pruefsummen aus `vorhandene`, die `neu` nicht mehr braucht, in der
// Reihenfolge von `vorhandene`.
std::vector<std::string> ueberfluessig(const Stand& neu, const std::vector<std::string>& vorhandene);

bool sha_gleich(const std::string& a, const std::string& b);

// Dateiname einer Aufnahme im Flash.
std::string dateiname(const std::string& sha);

}  // namespace kz
