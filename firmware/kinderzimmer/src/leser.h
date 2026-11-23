#pragma once
// PN532 ueber I2C. Eine eigene Aufgabe fragt den Leser ab, damit ein
// Leseversuch nie die Knoepfe aufhaelt. Fehlt der Leser, spielt das Geraet
// ohne Figuren weiter.

#include "praesenz.h"

namespace leser {

void beginnen();
// Naechster Wechsel (Figur auf / ab). true, solange es welche gibt.
bool wechsel(kz::Wechsel& w);

}  // namespace leser
