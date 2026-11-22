// Spiele der Phase 1, Ruhe, Abgleich-Fenster, Entprellen, Figur auf dem Leser.
#include <unity.h>

#include <cstdlib>
#include <string>

#include "entpreller.h"
#include "praesenz.h"
#include "spielgeraet.h"
#include "stand.h"

using namespace kz;

void setUp() {}
void tearDown() {}

static const char* MANIFEST = R"({
  "format": 1, "stand": "s-eins",
  "einstellungen": {
    "lautstaerke_max": 50, "helligkeit_max": 40, "ruhe_nach_min": 10,
    "startspiel": "licht-und-klang",
    "spiele_aktiv": ["licht-und-klang", "stimmen"],
    "knoepfe": [
      {"nummer": 1, "farbe": "#FFB000", "klang": "k1"},
      {"nummer": 2, "farbe": "#3366FF", "klang": null}
    ]
  },
  "figuren": [
    {"uid": "04A1B2C3D4E5F6", "name": "Oma", "art": "familie", "farbe": null,
     "form": null, "menge": null, "stimme": "oma-stimme", "klang": "oma-klang"},
    {"uid": "DEADBEEF", "name": "Ente", "art": "tier", "farbe": null,
     "form": null, "menge": null, "stimme": null, "klang": "quak"}
  ],
  "dateien": []
})";

static Stand stand(const char* json = MANIFEST) {
    Stand s;
    TEST_ASSERT_EQUAL(LeseErgebnis::ok, stand_lesen(json, s));
    return s;
}

static std::string ohne(const char* spiel) {
    std::string json = MANIFEST;
    std::string eintrag = std::string("\"") + spiel + "\"";
    size_t pos = json.find(eintrag, json.find("spiele_aktiv"));
    json.erase(pos, eintrag.size());
    // Das uebrig gebliebene Komma stoert ArduinoJson nicht, aber sauber ist sauber.
    size_t komma = json.find("[, ");
    if (komma != std::string::npos) json.erase(komma + 1, 2);
    komma = json.find(", ]");
    if (komma != std::string::npos) json.erase(komma, 2);
    return json;
}

static bool hat(const Ausgabe& a, Art art) {
    for (const auto& m : a.meldungen)
        if (m.art == art) return true;
    return false;
}

static const uint32_t MINUTE = 60000;

// Die Hauptschleife taktet alle paar Millisekunden. Lange Luecken laesst
// das Geraet nicht zu Spruengen werden, deshalb takten die Tests auch.
static Ausgabe laufe(Spielgeraet& g, uint32_t von, uint32_t bis) {
    Ausgabe alle;
    for (uint32_t t = von; t <= bis; t += 10) {
        Ausgabe a = g.tick(t);
        alle.meldungen.insert(alle.meldungen.end(), a.meldungen.begin(), a.meldungen.end());
        alle.ton_stoppen = alle.ton_stoppen || a.ton_stoppen;
    }
    return alle;
}

// --- Start -------------------------------------------------------------------

void test_start_meldet_start_und_das_startspiel() {
    Spielgeraet g(stand());
    Ausgabe a = g.start(100);
    TEST_ASSERT_EQUAL(2, a.meldungen.size());
    TEST_ASSERT_EQUAL(Art::start, a.meldungen[0].art);
    TEST_ASSERT_EQUAL(Art::spiel, a.meldungen[1].art);
    TEST_ASSERT_EQUAL_STRING("licht-und-klang", a.meldungen[1].spiel.c_str());
    TEST_ASSERT_FALSE(a.ton_starten);
}

void test_das_geraet_ruft_nie_von_sich_aus() {
    Spielgeraet g(stand());
    g.start(0);
    for (uint32_t t = 0; t < 60 * MINUTE; t += 997) {
        Ausgabe a = g.tick(t);
        TEST_ASSERT_FALSE(a.ton_starten);
    }
    for (uint8_t i = 0; i < Spielgeraet::LEDS; ++i) TEST_ASSERT_EQUAL_UINT8(0, g.led(i).r);
}

// --- Licht und Klang ---------------------------------------------------------

void test_knopf_spielt_seinen_klang_und_meldet_sich() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.knopf(1, 1000);
    TEST_ASSERT_TRUE(hat(a, Art::knopf));
    TEST_ASSERT_EQUAL_UINT8(1, a.meldungen.back().knopf);
    TEST_ASSERT_TRUE(a.ton_starten);
    TEST_ASSERT_EQUAL(1, a.ton.size());
    TEST_ASSERT_EQUAL_STRING("k1", a.ton[0].c_str());
}

void test_licht_kommt_sofort() {
    // Kein Warten: schon eine Millisekunde spaeter ist es heller als aus.
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(1, 1000);
    g.tick(1001);
    TEST_ASSERT_GREATER_THAN_UINT8(0, g.led(0).r);
}

void test_licht_hat_die_knopffarbe_und_haelt_die_helligkeitsgrenze() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(1, 1000);
    laufe(g, 1000, 1000 + Spielgeraet::AN_MS);
    Farbe soll = gedimmt({0xFF, 0xB0, 0x00}, 40, 255);
    TEST_ASSERT_EQUAL_UINT8(soll.r, g.led(0).r);
    TEST_ASSERT_EQUAL_UINT8(soll.g, g.led(0).g);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(0).b);
    TEST_ASSERT_LESS_OR_EQUAL_UINT8(102, g.led(0).r);
}

void test_knopf_ohne_klang_leuchtet_nur() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.knopf(2, 1000);
    TEST_ASSERT_FALSE(a.ton_starten);
    laufe(g, 1000, 1000 + Spielgeraet::AN_MS);
    TEST_ASSERT_GREATER_THAN_UINT8(0, g.led(1).b);
}

void test_unbekannter_knopf_wird_nur_protokolliert() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.knopf(5, 1000);
    TEST_ASSERT_TRUE(hat(a, Art::knopf));
    TEST_ASSERT_FALSE(a.ton_starten);
    laufe(g, 1000, 1000 + Spielgeraet::AN_MS);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(4).r);
}

void test_abgeschaltetes_spiel_reagiert_nicht() {
    std::string json = ohne("licht-und-klang");
    Spielgeraet g(stand(json.c_str()));
    g.start(0);
    Ausgabe a = g.knopf(1, 1000);
    TEST_ASSERT_TRUE(hat(a, Art::knopf));
    TEST_ASSERT_FALSE(a.ton_starten);
    laufe(g, 1000, 1000 + Spielgeraet::AN_MS);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(0).r);
}

void test_licht_bleibt_solange_der_klang_laeuft_und_blendet_dann_aus() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.knopf(1, 1000);
    laufe(g, 1000, 20000);  // Klang laeuft noch
    TEST_ASSERT_GREATER_THAN_UINT8(0, g.led(0).r);
    g.wiedergabe_ende(a.ton_nr, 20000);
    laufe(g, 20010, 20000 + Spielgeraet::NACHLEUCHTEN_MS - 10);
    TEST_ASSERT_GREATER_THAN_UINT8(0, g.led(0).r);
    laufe(g, 20000 + Spielgeraet::NACHLEUCHTEN_MS,
          20000 + Spielgeraet::NACHLEUCHTEN_MS + Spielgeraet::AUS_MS + 20);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(0).r);
}

void test_ohne_klang_leuchtet_es_nach_und_geht_aus() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(2, 1000);
    laufe(g, 1000, 1000 + Spielgeraet::NACHLEUCHTEN_MS + Spielgeraet::AUS_MS + 20);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(1).b);
}

void test_neuer_knopf_unterbricht_und_der_alte_blendet_aus() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe erst = g.knopf(1, 1000);
    laufe(g, 1000, 1290);
    Ausgabe dann = g.knopf(2, 1300);
    TEST_ASSERT_TRUE(dann.ton_stoppen);
    TEST_ASSERT_NOT_EQUAL(erst.ton_nr, dann.ton_nr);
    // Das verspaetete Ende des ersten Klangs gilt nicht mehr.
    g.wiedergabe_ende(erst.ton_nr, 1400);
    TEST_ASSERT_FALSE(g.spielt());  // Knopf 2 hat keinen Klang
    laufe(g, 1300, 1300 + Spielgeraet::AUS_MS + 20);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(0).r);
    TEST_ASSERT_GREATER_THAN_UINT8(0, g.led(1).b);
}

void test_verspaetetes_ende_eines_alten_klangs_wird_uebergangen() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe erst = g.knopf(1, 1000);
    Ausgabe zweit = g.knopf(1, 1100);
    g.wiedergabe_ende(erst.ton_nr, 1200);
    TEST_ASSERT_TRUE(g.spielt());
    g.wiedergabe_ende(zweit.ton_nr, 1300);
    TEST_ASSERT_FALSE(g.spielt());
}

void test_gleicher_knopf_nochmal_wird_nicht_dunkel() {
    // Ein Baby drueckt oft mehrmals: Das Licht bleibt an, es flackert nicht.
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(1, 1000);
    laufe(g, 1000, 1000 + Spielgeraet::AN_MS);
    uint8_t hell = g.led(0).r;
    g.knopf(1, 1200);
    g.tick(1210);
    TEST_ASSERT_EQUAL_UINT8(hell, g.led(0).r);
}

void test_licht_aendert_sich_nie_sprunghaft() {
    // Wildes Druecken: Zwischen zwei Takten von 10 ms aendert sich kein
    // Kanal mehr, als die kuerzeste Blende erlaubt. Das ist "nie blinken".
    Spielgeraet g(stand());
    g.start(0);
    std::srand(7);
    Farbe vorher[Spielgeraet::LEDS] = {};
    const int GRENZE = 2 * 255 * 10 / Spielgeraet::AN_MS + 2;
    for (uint32_t t = 10; t < 30000; t += 10) {
        if (std::rand() % 15 == 0) g.knopf(1 + std::rand() % 2, t);
        g.tick(t);
        for (uint8_t i = 0; i < 2; ++i) {
            Farbe f = g.led(i);
            TEST_ASSERT_LESS_OR_EQUAL_INT(GRENZE, std::abs(f.r - vorher[i].r));
            TEST_ASSERT_LESS_OR_EQUAL_INT(GRENZE, std::abs(f.g - vorher[i].g));
            TEST_ASSERT_LESS_OR_EQUAL_INT(GRENZE, std::abs(f.b - vorher[i].b));
            vorher[i] = f;
        }
    }
}

void test_lautstaerke_ist_die_obergrenze_aus_dem_stand() {
    Spielgeraet g(stand());
    TEST_ASSERT_EQUAL_UINT8(50, g.lautstaerke());
}

// --- Stimmen -----------------------------------------------------------------

void test_figur_spielt_erst_die_stimme_dann_den_klang() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("04A1B2C3D4E5F6", 1000);
    TEST_ASSERT_TRUE(hat(a, Art::figur_auf));
    TEST_ASSERT_EQUAL_STRING("04A1B2C3D4E5F6", a.meldungen.back().uid.c_str());
    TEST_ASSERT_TRUE(a.ton_starten);
    TEST_ASSERT_EQUAL(2, a.ton.size());
    TEST_ASSERT_EQUAL_STRING("oma-stimme", a.ton[0].c_str());
    TEST_ASSERT_EQUAL_STRING("oma-klang", a.ton[1].c_str());
}

void test_spielwechsel_wird_vor_der_handlung_gemeldet() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("04A1B2C3D4E5F6", 1000);
    TEST_ASSERT_EQUAL(Art::spiel, a.meldungen[0].art);
    TEST_ASSERT_EQUAL_STRING("stimmen", a.meldungen[0].spiel.c_str());
    TEST_ASSERT_EQUAL(Art::figur_auf, a.meldungen[1].art);
    // Zweite Figur im selben Spiel: kein neuer Wechsel.
    g.figur_ab(2000);
    Ausgabe b = g.figur_auf("DEADBEEF", 3000);
    TEST_ASSERT_FALSE(hat(b, Art::spiel));
    // Zurueck zum Knopf: wieder ein Wechsel.
    Ausgabe c = g.knopf(1, 4000);
    TEST_ASSERT_EQUAL(Art::spiel, c.meldungen[0].art);
    TEST_ASSERT_EQUAL_STRING("licht-und-klang", c.meldungen[0].spiel.c_str());
}

void test_figur_ohne_stimme_spielt_nur_den_klang() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("DEADBEEF", 1000);
    TEST_ASSERT_EQUAL(1, a.ton.size());
    TEST_ASSERT_EQUAL_STRING("quak", a.ton[0].c_str());
}

void test_unbekannte_figur_wird_nur_protokolliert() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("01020304", 1000);
    TEST_ASSERT_TRUE(hat(a, Art::figur_auf));
    TEST_ASSERT_FALSE(hat(a, Art::spiel));
    TEST_ASSERT_FALSE(a.ton_starten);
}

void test_figur_ab_wird_gemeldet() {
    Spielgeraet g(stand());
    g.start(0);
    g.figur_auf("DEADBEEF", 1000);
    Ausgabe a = g.figur_ab(2000);
    TEST_ASSERT_TRUE(hat(a, Art::figur_ab));
    TEST_ASSERT_EQUAL_STRING("DEADBEEF", a.meldungen.back().uid.c_str());
}

void test_stimmen_abgeschaltet_spielt_keine_figur() {
    std::string json = ohne("stimmen");
    Spielgeraet g(stand(json.c_str()));
    g.start(0);
    Ausgabe a = g.figur_auf("04A1B2C3D4E5F6", 1000);
    TEST_ASSERT_TRUE(hat(a, Art::figur_auf));
    TEST_ASSERT_FALSE(a.ton_starten);
}

void test_gleiche_figur_gleiche_reaktion() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("DEADBEEF", 1000);
    g.figur_ab(2000);
    Ausgabe b = g.figur_auf("DEADBEEF", 3000);
    TEST_ASSERT_EQUAL(a.ton.size(), b.ton.size());
    TEST_ASSERT_EQUAL_STRING(a.ton[0].c_str(), b.ton[0].c_str());
}

// --- Ruhe --------------------------------------------------------------------

void test_nach_der_ruhezeit_wird_es_still_und_dunkel() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(2, 1000);
    Ausgabe vorher = g.tick(1000 + 10 * MINUTE - 1);
    TEST_ASSERT_FALSE(hat(vorher, Art::ruhe));
    Ausgabe a = g.tick(1000 + 10 * MINUTE);
    TEST_ASSERT_TRUE(hat(a, Art::ruhe));
    TEST_ASSERT_TRUE(a.ton_stoppen);
    TEST_ASSERT_TRUE(g.ruht());
    laufe(g, 1000 + 10 * MINUTE, 1000 + 10 * MINUTE + Spielgeraet::RUHE_AUS_MS + 20);
    TEST_ASSERT_EQUAL_UINT8(0, g.led(1).b);
}

void test_ruhe_wird_nur_einmal_gemeldet() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(2, 1000);
    g.tick(1000 + 10 * MINUTE);
    Ausgabe a = g.tick(1000 + 20 * MINUTE);
    TEST_ASSERT_FALSE(hat(a, Art::ruhe));
}

void test_ohne_handlung_keine_ruhe_meldung() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.tick(30 * MINUTE);
    TEST_ASSERT_FALSE(hat(a, Art::ruhe));
}

void test_ein_knopf_weckt_aus_der_ruhe() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(2, 1000);
    g.tick(1000 + 10 * MINUTE);
    Ausgabe a = g.knopf(1, 1000 + 11 * MINUTE);
    TEST_ASSERT_TRUE(a.ton_starten);
    TEST_ASSERT_FALSE(g.ruht());
}

// --- Abgleich-Fenster --------------------------------------------------------

void test_nach_dem_start_darf_abgeglichen_werden() {
    Spielgeraet g(stand());
    g.start(0);
    TEST_ASSERT_TRUE(g.darf_abgleichen(10));
}

void test_waehrend_ein_klang_laeuft_kein_abgleich() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(1, 1000);
    TEST_ASSERT_FALSE(g.darf_abgleichen(1000 + 10 * Spielgeraet::ABGLEICH_PAUSE_MS));
}

void test_kurz_nach_einer_handlung_kein_abgleich() {
    Spielgeraet g(stand());
    g.start(0);
    g.knopf(2, 1000);
    TEST_ASSERT_FALSE(g.darf_abgleichen(1000 + Spielgeraet::ABGLEICH_PAUSE_MS - 1));
    TEST_ASSERT_TRUE(g.darf_abgleichen(1000 + Spielgeraet::ABGLEICH_PAUSE_MS));
}

void test_solange_eine_figur_liegt_kein_abgleich() {
    Spielgeraet g(stand());
    g.start(0);
    Ausgabe a = g.figur_auf("DEADBEEF", 1000);
    g.wiedergabe_ende(a.ton_nr, 2000);
    TEST_ASSERT_FALSE(g.darf_abgleichen(1000 + 10 * Spielgeraet::ABGLEICH_PAUSE_MS));
    g.figur_ab(3000);
    TEST_ASSERT_TRUE(g.darf_abgleichen(3000 + Spielgeraet::ABGLEICH_PAUSE_MS));
}

void test_neuer_stand_gilt_sofort_fuer_den_naechsten_knopf() {
    Spielgeraet g(stand());
    g.start(0);
    std::string json = MANIFEST;
    json.replace(json.find("\"k1\""), 4, "\"k9\"");
    g.neuer_stand(stand(json.c_str()));
    Ausgabe a = g.knopf(1, 1000);
    TEST_ASSERT_EQUAL_STRING("k9", a.ton[0].c_str());
}

// --- Entpreller --------------------------------------------------------------

void test_prellen_ergibt_einen_druck() {
    Entpreller e;
    int drucke = 0;
    // 0..9 ms prellt es, dann liegt der Kontakt fest an.
    for (uint32_t t = 0; t < 10; ++t) drucke += e.schritt(t % 2 == 0, t);
    for (uint32_t t = 10; t < 100; ++t) drucke += e.schritt(true, t);
    TEST_ASSERT_EQUAL(1, drucke);
}

void test_kurzer_stoerimpuls_ist_kein_druck() {
    Entpreller e;
    int drucke = 0;
    for (uint32_t t = 0; t < 5; ++t) drucke += e.schritt(true, t);
    for (uint32_t t = 5; t < 100; ++t) drucke += e.schritt(false, t);
    TEST_ASSERT_EQUAL(0, drucke);
}

void test_loslassen_und_wieder_druecken_sind_zwei_drucke() {
    Entpreller e;
    int drucke = 0;
    for (uint32_t t = 0; t < 100; ++t) drucke += e.schritt(true, t);
    for (uint32_t t = 100; t < 200; ++t) drucke += e.schritt(false, t);
    for (uint32_t t = 200; t < 300; ++t) drucke += e.schritt(true, t);
    TEST_ASSERT_EQUAL(2, drucke);
}

// --- Praesenz ----------------------------------------------------------------

void test_figur_wird_beim_ersten_lesen_aufgelegt() {
    Praesenz p;
    Wechsel w = p.melde("DEADBEEF", 100);
    TEST_ASSERT_TRUE(w.auf);
    TEST_ASSERT_FALSE(w.ab);
    TEST_ASSERT_EQUAL_STRING("DEADBEEF", w.uid.c_str());
}

void test_liegende_figur_meldet_sich_nicht_nochmal() {
    Praesenz p;
    p.melde("DEADBEEF", 100);
    Wechsel w = p.melde("DEADBEEF", 200);
    TEST_ASSERT_FALSE(w.auf);
    TEST_ASSERT_FALSE(w.ab);
}

void test_einzelner_fehllesevorgang_ist_kein_abheben() {
    Praesenz p;
    p.melde("DEADBEEF", 100);
    TEST_ASSERT_FALSE(p.melde("", 200).ab);
    TEST_ASSERT_FALSE(p.melde("DEADBEEF", 300).auf);
}

void test_figur_gilt_nach_der_haltezeit_als_abgehoben() {
    Praesenz p;
    p.melde("DEADBEEF", 100);
    TEST_ASSERT_FALSE(p.melde("", 100 + Praesenz::HALTE_MS - 1).ab);
    Wechsel w = p.melde("", 100 + Praesenz::HALTE_MS);
    TEST_ASSERT_TRUE(w.ab);
    TEST_ASSERT_EQUAL_STRING("DEADBEEF", w.uid.c_str());
    TEST_ASSERT_FALSE(p.melde("", 5000).ab);
}

void test_andere_figur_ist_ab_und_auf() {
    Praesenz p;
    p.melde("DEADBEEF", 100);
    Wechsel w = p.melde("04A1B2C3D4E5F6", 200);
    TEST_ASSERT_TRUE(w.ab);
    TEST_ASSERT_TRUE(w.auf);
    TEST_ASSERT_EQUAL_STRING("04A1B2C3D4E5F6", w.uid.c_str());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_start_meldet_start_und_das_startspiel);
    RUN_TEST(test_das_geraet_ruft_nie_von_sich_aus);
    RUN_TEST(test_knopf_spielt_seinen_klang_und_meldet_sich);
    RUN_TEST(test_licht_kommt_sofort);
    RUN_TEST(test_licht_hat_die_knopffarbe_und_haelt_die_helligkeitsgrenze);
    RUN_TEST(test_knopf_ohne_klang_leuchtet_nur);
    RUN_TEST(test_unbekannter_knopf_wird_nur_protokolliert);
    RUN_TEST(test_abgeschaltetes_spiel_reagiert_nicht);
    RUN_TEST(test_licht_bleibt_solange_der_klang_laeuft_und_blendet_dann_aus);
    RUN_TEST(test_ohne_klang_leuchtet_es_nach_und_geht_aus);
    RUN_TEST(test_neuer_knopf_unterbricht_und_der_alte_blendet_aus);
    RUN_TEST(test_verspaetetes_ende_eines_alten_klangs_wird_uebergangen);
    RUN_TEST(test_gleicher_knopf_nochmal_wird_nicht_dunkel);
    RUN_TEST(test_licht_aendert_sich_nie_sprunghaft);
    RUN_TEST(test_lautstaerke_ist_die_obergrenze_aus_dem_stand);
    RUN_TEST(test_figur_spielt_erst_die_stimme_dann_den_klang);
    RUN_TEST(test_spielwechsel_wird_vor_der_handlung_gemeldet);
    RUN_TEST(test_figur_ohne_stimme_spielt_nur_den_klang);
    RUN_TEST(test_unbekannte_figur_wird_nur_protokolliert);
    RUN_TEST(test_figur_ab_wird_gemeldet);
    RUN_TEST(test_stimmen_abgeschaltet_spielt_keine_figur);
    RUN_TEST(test_gleiche_figur_gleiche_reaktion);
    RUN_TEST(test_nach_der_ruhezeit_wird_es_still_und_dunkel);
    RUN_TEST(test_ruhe_wird_nur_einmal_gemeldet);
    RUN_TEST(test_ohne_handlung_keine_ruhe_meldung);
    RUN_TEST(test_ein_knopf_weckt_aus_der_ruhe);
    RUN_TEST(test_nach_dem_start_darf_abgeglichen_werden);
    RUN_TEST(test_waehrend_ein_klang_laeuft_kein_abgleich);
    RUN_TEST(test_kurz_nach_einer_handlung_kein_abgleich);
    RUN_TEST(test_solange_eine_figur_liegt_kein_abgleich);
    RUN_TEST(test_neuer_stand_gilt_sofort_fuer_den_naechsten_knopf);
    RUN_TEST(test_prellen_ergibt_einen_druck);
    RUN_TEST(test_kurzer_stoerimpuls_ist_kein_druck);
    RUN_TEST(test_loslassen_und_wieder_druecken_sind_zwei_drucke);
    RUN_TEST(test_figur_wird_beim_ersten_lesen_aufgelegt);
    RUN_TEST(test_liegende_figur_meldet_sich_nicht_nochmal);
    RUN_TEST(test_einzelner_fehllesevorgang_ist_kein_abheben);
    RUN_TEST(test_figur_gilt_nach_der_haltezeit_als_abgehoben);
    RUN_TEST(test_andere_figur_ist_ab_und_auf);
    return UNITY_END();
}
