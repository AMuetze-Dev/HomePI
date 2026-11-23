#pragma once
// WLAN, Uhrzeit und der Pi. Laeuft als eigene Aufgabe: Ein haengender Pi
// darf nie einen Knopf verzoegern.
//
// Abgeglichen wird beim Start und wenn eine Antwort auf das Protokoll einen
// anderen Stand nennt. Es gibt kein regelmaessiges Abfragen.

#include <cstdint>
#include <string>

#include "protokoll.h"
#include "stand.h"

namespace netz {

constexpr const char* FIRMWARE = "0.1.0";

// `stand`: der Stand, mit dem das Geraet gerade spielt. Dateien, die er nicht
// braucht, raeumt der Start auf.
void beginnen(uint32_t start, const kz::Stand& stand);

// Ereignis zum Pi; ohne Verbindung in den Flash. Blockiert nie.
void melde(const kz::Ereignis& e);

// Die Hauptschleife sagt, ob gerade kein Spiel laeuft. Nur dann beginnt ein
// Abgleich mit dem Laden.
void darf_abgleichen(bool ja);

// Ein vollstaendig geladener Stand, einmal. Die Dateien liegen dann schon im
// Flash; die alten auch noch, bis stand_uebernommen() kommt.
bool neuer_stand(kz::Stand& aus);
void stand_uebernommen(const kz::Stand& stand);

// Uhrzeit fuer Ereignisse, leer bis NTP lief.
std::string uhrzeit();

}  // namespace netz
