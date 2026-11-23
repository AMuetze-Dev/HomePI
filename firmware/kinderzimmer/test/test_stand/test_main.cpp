// Stand: Manifest lesen, Abgleich planen, UIDs schreiben.
#include <unity.h>

#include <set>
#include <string>

#include "abgleich.h"
#include "stand.h"
#include "uid.h"

using namespace kz;

void setUp() {}
void tearDown() {}

static const char* MANIFEST = R"({
  "format": 1,
  "stand": "9f2c4a1b0e7d3c55",
  "einstellungen": {
    "lautstaerke_max": 50, "helligkeit_max": 40, "ruhe_nach_min": 10,
    "startspiel": "licht-und-klang",
    "spiele_aktiv": ["licht-und-klang", "stimmen"],
    "knoepfe": [
      {"nummer": 1, "farbe": "#FFB000", "klang": "a1"},
      {"nummer": 3, "farbe": "#3366FF", "klang": null}
    ]
  },
  "figuren": [
    {"uid": "04A1B2C3D4E5F6", "name": "Oma", "art": "familie",
     "farbe": null, "form": null, "menge": null,
     "stimme": "s1", "klang": "a1"},
    {"uid": "DEADBEEF", "name": "Ente", "art": "tier",
     "farbe": "#FFFF00", "form": null, "menge": null,
     "stimme": null, "klang": null}
  ],
  "dateien": [
    {"id": "a1", "sha256": "AAAA", "bytes": 88244, "dauer_ms": 2000},
    {"id": "s1", "sha256": "bbbb", "bytes": 44144, "dauer_ms": 1000}
  ]
})";

// --- Manifest ----------------------------------------------------------------

void test_manifest_wird_gelesen() {
    Stand s;
    TEST_ASSERT_EQUAL(LeseErgebnis::ok, stand_lesen(MANIFEST, s));
    TEST_ASSERT_EQUAL_STRING("9f2c4a1b0e7d3c55", s.stand.c_str());
    TEST_ASSERT_EQUAL_UINT8(50, s.lautstaerke_max);
    TEST_ASSERT_EQUAL_UINT8(40, s.helligkeit_max);
    TEST_ASSERT_EQUAL_UINT16(10, s.ruhe_nach_min);
    TEST_ASSERT_EQUAL_STRING("licht-und-klang", s.startspiel.c_str());
    TEST_ASSERT_TRUE(s.spiel_aktiv("stimmen"));
    TEST_ASSERT_FALSE(s.spiel_aktiv("kuckuck"));
    TEST_ASSERT_EQUAL(2, s.knoepfe.size());
    TEST_ASSERT_EQUAL(2, s.figuren.size());
    TEST_ASSERT_EQUAL(2, s.dateien.size());
}

void test_knopf_wird_nach_nummer_gefunden() {
    Stand s;
    stand_lesen(MANIFEST, s);
    const Knopf* k = s.knopf(3);
    TEST_ASSERT_NOT_NULL(k);
    TEST_ASSERT_EQUAL_UINT8(0x33, k->farbe.r);
    TEST_ASSERT_TRUE(k->klang.empty());
    TEST_ASSERT_NULL(s.knopf(2));
}

void test_figur_wird_nach_uid_gefunden_auch_klein_geschrieben() {
    Stand s;
    stand_lesen(MANIFEST, s);
    const Figur* f = s.figur("04a1b2c3d4e5f6");
    TEST_ASSERT_NOT_NULL(f);
    TEST_ASSERT_EQUAL_STRING("Oma", f->name.c_str());
    TEST_ASSERT_EQUAL_STRING("s1", f->stimme.c_str());
    TEST_ASSERT_NULL(s.figur("01020304"));
}

void test_datei_wird_nach_id_gefunden() {
    Stand s;
    stand_lesen(MANIFEST, s);
    const Datei* d = s.datei("s1");
    TEST_ASSERT_NOT_NULL(d);
    TEST_ASSERT_EQUAL_STRING("bbbb", d->sha256.c_str());
    TEST_ASSERT_EQUAL_UINT32(44144, d->bytes);
}

void test_sha256_wird_klein_geschrieben() {
    Stand s;
    stand_lesen(MANIFEST, s);
    TEST_ASSERT_EQUAL_STRING("aaaa", s.datei("a1")->sha256.c_str());
}

void test_hoeheres_format_wird_nicht_uebernommen() {
    Stand s;
    s.stand = "alt";
    std::string json = MANIFEST;
    json.replace(json.find("\"format\": 1"), 11, "\"format\": 2");
    TEST_ASSERT_EQUAL(LeseErgebnis::format_zu_neu, stand_lesen(json, s));
    TEST_ASSERT_EQUAL_STRING("alt", s.stand.c_str());
}

void test_kaputtes_json_laesst_den_stand_stehen() {
    Stand s;
    s.stand = "alt";
    TEST_ASSERT_EQUAL(LeseErgebnis::kaputt, stand_lesen("{\"format\": 1, ", s));
    TEST_ASSERT_EQUAL_STRING("alt", s.stand.c_str());
}

void test_ohne_stand_ist_es_kaputt() {
    Stand s;
    TEST_ASSERT_EQUAL(LeseErgebnis::kaputt, stand_lesen("{\"format\": 1}", s));
}

void test_obergrenzen_werden_in_den_erlaubten_bereich_gezogen() {
    // Der Pi prueft 5..100. Kommt trotzdem Unsinn, bleibt das Geraet leise.
    std::string json = MANIFEST;
    json.replace(json.find("\"lautstaerke_max\": 50"), 21, "\"lautstaerke_max\": 900");
    json.replace(json.find("\"helligkeit_max\": 40"), 20, "\"helligkeit_max\": -3");
    Stand s;
    TEST_ASSERT_EQUAL(LeseErgebnis::ok, stand_lesen(json, s));
    TEST_ASSERT_EQUAL_UINT8(100, s.lautstaerke_max);
    TEST_ASSERT_EQUAL_UINT8(5, s.helligkeit_max);
}

void test_fehlende_einstellungen_nehmen_die_leisen_vorgaben() {
    Stand s;
    TEST_ASSERT_EQUAL(LeseErgebnis::ok,
                      stand_lesen(R"({"format":1,"stand":"x","figuren":[],"dateien":[]})", s));
    TEST_ASSERT_EQUAL_UINT8(40, s.lautstaerke_max);
    TEST_ASSERT_EQUAL_UINT8(40, s.helligkeit_max);
    TEST_ASSERT_EQUAL_UINT16(10, s.ruhe_nach_min);
}

void test_vorgabe_ohne_pi_hat_einen_bernsteinfarbenen_knopf() {
    // Erster Start ohne Pi: Licht geht, Ton gibt es noch keinen.
    Stand s = stand_vorgabe();
    TEST_ASSERT_TRUE(s.stand.empty());
    TEST_ASSERT_TRUE(s.spiel_aktiv("licht-und-klang"));
    const Knopf* k = s.knopf(1);
    TEST_ASSERT_NOT_NULL(k);
    TEST_ASSERT_EQUAL_UINT8(0xFF, k->farbe.r);
    TEST_ASSERT_EQUAL_UINT8(0xB0, k->farbe.g);
    TEST_ASSERT_TRUE(k->klang.empty());
    TEST_ASSERT_EQUAL_UINT8(40, s.lautstaerke_max);
}

// --- Abgleich ----------------------------------------------------------------

void test_nur_fehlende_dateien_werden_geladen() {
    Stand s;
    stand_lesen(MANIFEST, s);
    std::set<std::string> da = {"aaaa"};
    Plan p = plane_abgleich(s, [&](const std::string& sha) { return da.count(sha) > 0; });
    TEST_ASSERT_EQUAL(1, p.laden.size());
    TEST_ASSERT_EQUAL_STRING("s1", p.laden[0].id.c_str());
    TEST_ASSERT_EQUAL_UINT32(44144, p.bytes);
}

void test_gleicher_inhalt_wird_nur_einmal_geladen() {
    Stand s;
    stand_lesen(MANIFEST, s);
    s.dateien.push_back({"a2", "aaaa", 88244, 2000});
    Plan p = plane_abgleich(s, [](const std::string&) { return false; });
    TEST_ASSERT_EQUAL(2, p.laden.size());
    TEST_ASSERT_EQUAL_UINT32(88244 + 44144, p.bytes);
}

void test_alles_da_heisst_nichts_laden() {
    Stand s;
    stand_lesen(MANIFEST, s);
    Plan p = plane_abgleich(s, [](const std::string&) { return true; });
    TEST_ASSERT_TRUE(p.laden.empty());
    TEST_ASSERT_EQUAL_UINT32(0, p.bytes);
}

void test_nicht_mehr_benutzte_dateien_werden_aufgeraeumt() {
    Stand s;
    stand_lesen(MANIFEST, s);
    auto weg = ueberfluessig(s, {"aaaa", "cccc", "bbbb", "dddd"});
    TEST_ASSERT_EQUAL(2, weg.size());
    TEST_ASSERT_EQUAL_STRING("cccc", weg[0].c_str());
    TEST_ASSERT_EQUAL_STRING("dddd", weg[1].c_str());
}

void test_pruefsummen_vergleich_ignoriert_gross_klein() {
    TEST_ASSERT_TRUE(sha_gleich("ABCdef", "abcDEF"));
    TEST_ASSERT_FALSE(sha_gleich("abc", "abd"));
    TEST_ASSERT_FALSE(sha_gleich("abc", "abcd"));
}

void test_dateiname_haengt_an_der_pruefsumme() {
    TEST_ASSERT_EQUAL_STRING("aaaa.wav", dateiname("AAAA").c_str());
}

// --- UID ---------------------------------------------------------------------

void test_uid_wird_gross_ohne_trenner_geschrieben() {
    const uint8_t uid[7] = {0x04, 0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0xF6};
    TEST_ASSERT_EQUAL_STRING("04A1B2C3D4E5F6", uid_hex(uid, 7).c_str());
}

void test_vier_byte_uid() {
    const uint8_t uid[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    TEST_ASSERT_EQUAL_STRING("DEADBEEF", uid_hex(uid, 4).c_str());
}

void test_unzulaessige_laenge_ergibt_nichts() {
    const uint8_t uid[5] = {1, 2, 3, 4, 5};
    TEST_ASSERT_TRUE(uid_hex(uid, 5).empty());
    TEST_ASSERT_TRUE(uid_hex(uid, 0).empty());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_manifest_wird_gelesen);
    RUN_TEST(test_knopf_wird_nach_nummer_gefunden);
    RUN_TEST(test_figur_wird_nach_uid_gefunden_auch_klein_geschrieben);
    RUN_TEST(test_datei_wird_nach_id_gefunden);
    RUN_TEST(test_sha256_wird_klein_geschrieben);
    RUN_TEST(test_hoeheres_format_wird_nicht_uebernommen);
    RUN_TEST(test_kaputtes_json_laesst_den_stand_stehen);
    RUN_TEST(test_ohne_stand_ist_es_kaputt);
    RUN_TEST(test_obergrenzen_werden_in_den_erlaubten_bereich_gezogen);
    RUN_TEST(test_fehlende_einstellungen_nehmen_die_leisen_vorgaben);
    RUN_TEST(test_vorgabe_ohne_pi_hat_einen_bernsteinfarbenen_knopf);
    RUN_TEST(test_nur_fehlende_dateien_werden_geladen);
    RUN_TEST(test_gleicher_inhalt_wird_nur_einmal_geladen);
    RUN_TEST(test_alles_da_heisst_nichts_laden);
    RUN_TEST(test_nicht_mehr_benutzte_dateien_werden_aufgeraeumt);
    RUN_TEST(test_pruefsummen_vergleich_ignoriert_gross_klein);
    RUN_TEST(test_dateiname_haengt_an_der_pruefsumme);
    RUN_TEST(test_uid_wird_gross_ohne_trenner_geschrieben);
    RUN_TEST(test_vier_byte_uid);
    RUN_TEST(test_unzulaessige_laenge_ergibt_nichts);
    return UNITY_END();
}
