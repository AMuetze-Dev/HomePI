// Spielgeraet fuer das HomePI-Artefakt "kinderzimmer", Phase 1.
//
// Diese Datei verbindet nur: Knoepfe und Leser liefern Eingaben an das
// Spielgeraet (lib/logik), dessen Ausgaben gehen an Licht, Ton und Netz.
// Entscheidungen fallen in lib/logik und sind dort getestet.
//
// Reihenfolge je Eingabe: erst reagieren (Ton, Licht), dann protokollieren.
// Ein Baby wartet nicht auf das WLAN.

#include <Arduino.h>
#include <Preferences.h>

#include <memory>

#include "ablage.h"
#include "entpreller.h"
#include "leser.h"
#include "licht.h"
#include "netz.h"
#include "pins.h"
#include "protokoll.h"
#include "spielgeraet.h"
#include "ton.h"

namespace {

std::unique_ptr<kz::Spielgeraet> geraet;
std::unique_ptr<kz::Protokoll> protokoll;
kz::Entpreller knoepfe[KNOPF_ANZAHL];

// Startzaehler im NVS, steigt bei jedem Einschalten.
uint32_t naechster_start() {
    Preferences p;
    p.begin("kinderzimmer", false);
    uint32_t start = p.getUInt("start", 0) + 1;
    p.putUInt("start", start);
    p.end();
    return start;
}

void melde(kz::Art art, uint8_t knopf = 0, const std::string& uid = "", const std::string& spiel = "") {
    kz::Ereignis e = protokoll->neu(art, millis(), netz::uhrzeit());
    e.knopf = knopf;
    e.uid = uid;
    e.spiel = spiel;
    netz::melde(e);
}

void verarbeite(const kz::Ausgabe& a) {
    if (a.ton_stoppen) ton::stoppen();
    if (a.ton_starten) {
        std::vector<std::string> pfade;
        for (const auto& id : a.ton) {
            const kz::Datei* d = geraet->stand().datei(id);
            if (d != nullptr) pfade.push_back(ablage::pfad(d->sha256));
        }
        // Auch ohne Datei geht der Auftrag an den Ton: Er meldet dann gleich
        // das Ende, und das Licht blendet wie gewohnt aus.
        ton::spielen(a.ton_nr, pfade, geraet->lautstaerke());
    }
    for (const auto& m : a.meldungen) melde(m.art, m.knopf, m.uid, m.spiel);
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(50);
    uint32_t start = naechster_start();
    Serial.printf("\n[kinderzimmer] Firmware %s, Start %u\n", netz::FIRMWARE, static_cast<unsigned>(start));

    for (int pin : PIN_KNOPF) pinMode(pin, INPUT_PULLUP);
    licht::beginnen();
    ablage::beginnen();
    ton::beginnen();

    // Ohne Pi mit dem letzten Stand; ohne jeden Stand mit den Vorgaben.
    kz::Stand stand;
    if (ablage::stand_laden(stand)) {
        Serial.printf("[kinderzimmer] Stand %s aus dem Flash\n", stand.stand.c_str());
    } else {
        stand = kz::stand_vorgabe();
        Serial.println("[kinderzimmer] Noch kein Stand, spiele mit den Vorgaben");
    }

    protokoll.reset(new kz::Protokoll(start));
    geraet.reset(new kz::Spielgeraet(stand));
    netz::beginnen(start, stand);
    leser::beginnen();
    verarbeite(geraet->start(millis()));
}

void loop() {
    uint32_t jetzt = millis();

    for (uint8_t i = 0; i < KNOPF_ANZAHL; ++i)
        if (knoepfe[i].schritt(digitalRead(PIN_KNOPF[i]) == LOW, jetzt))
            verarbeite(geraet->knopf(i + 1, jetzt));

    kz::Wechsel w;
    while (leser::wechsel(w)) {
        if (w.ab) verarbeite(geraet->figur_ab(jetzt));
        if (w.auf) verarbeite(geraet->figur_auf(w.uid, jetzt));
    }

    uint32_t nr;
    while (ton::fertig(nr)) geraet->wiedergabe_ende(nr, jetzt);

    verarbeite(geraet->tick(jetzt));
    licht::zeigen(*geraet);

    // Neuer Stand nur in einer Spielpause, nie mitten im Spiel.
    bool pause = geraet->darf_abgleichen(jetzt);
    netz::darf_abgleichen(pause);
    kz::Stand neu;
    if (pause && netz::neuer_stand(neu)) {
        Serial.printf("[kinderzimmer] Spiele ab jetzt mit Stand %s\n", neu.stand.c_str());
        geraet->neuer_stand(neu);
        netz::stand_uebernommen(neu);
        melde(kz::Art::abgleich);
    }

    delay(5);
}
