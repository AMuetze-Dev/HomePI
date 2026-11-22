// Protokoll: Ereignisse nummerieren, als JSON senden, ohne Verbindung puffern.
#include <unity.h>

#include <ArduinoJson.h>
#include <string>

#include "protokoll.h"
#include "versand.h"

using namespace kz;

void setUp() {}
void tearDown() {}

static JsonDocument lies(const std::string& json) {
    JsonDocument doc;
    TEST_ASSERT_FALSE(deserializeJson(doc, json));
    return doc;
}

// --- Protokoll ---------------------------------------------------------------

void test_nummern_laufen_ab_eins() {
    Protokoll p(17);
    TEST_ASSERT_EQUAL_UINT32(1, p.neu(Art::start, 1200, "").nr);
    TEST_ASSERT_EQUAL_UINT32(2, p.neu(Art::knopf, 5400, "").nr);
    TEST_ASSERT_EQUAL_UINT32(17, p.neu(Art::knopf, 5500, "").start);
}

void test_sendung_hat_den_vertragskopf() {
    Protokoll p(17);
    Ereignis a = p.neu(Art::start, 1200, "2026-11-20T07:15:02+00:00");
    Ereignis b = p.neu(Art::knopf, 5400, "");
    b.knopf = 1;
    Ereignis c = p.neu(Art::figur_auf, 9100, "");
    c.uid = "04A1B2C3D4E5F6";
    auto doc = lies(sendung(17, 912345, "0.1.0", "9f2c", {a, b, c}));

    TEST_ASSERT_EQUAL(17, doc["start"].as<int>());
    TEST_ASSERT_EQUAL(912345, doc["jetzt_ms"].as<long>());
    TEST_ASSERT_EQUAL_STRING("0.1.0", doc["firmware"]);
    TEST_ASSERT_EQUAL_STRING("9f2c", doc["stand"]);
    JsonArray e = doc["ereignisse"];
    TEST_ASSERT_EQUAL(3, e.size());

    TEST_ASSERT_EQUAL(1, e[0]["nr"].as<int>());
    TEST_ASSERT_EQUAL(1200, e[0]["ms"].as<int>());
    TEST_ASSERT_EQUAL_STRING("2026-11-20T07:15:02+00:00", e[0]["zeit"]);
    TEST_ASSERT_EQUAL_STRING("start", e[0]["art"]);
    // Ereignisse aus dem laufenden Start tragen kein eigenes "start".
    TEST_ASSERT_FALSE(e[0]["start"].is<int>());

    TEST_ASSERT_TRUE(e[1]["zeit"].isNull());
    TEST_ASSERT_EQUAL_STRING("knopf", e[1]["art"]);
    TEST_ASSERT_EQUAL(1, e[1]["knopf"].as<int>());

    TEST_ASSERT_EQUAL_STRING("figur_auf", e[2]["art"]);
    TEST_ASSERT_EQUAL_STRING("04A1B2C3D4E5F6", e[2]["uid"]);
    TEST_ASSERT_FALSE(e[2]["knopf"].is<int>());
}

void test_zeit_ist_null_wenn_unbekannt() {
    // "zeit": null muss im JSON stehen, nicht fehlen.
    Protokoll p(1);
    std::string json = sendung(1, 10, "0.1.0", "", {p.neu(Art::ruhe, 5, "")});
    TEST_ASSERT_NOT_EQUAL(std::string::npos, json.find("\"zeit\":null"));
}

void test_ohne_stand_steht_null_im_kopf() {
    Protokoll p(1);
    auto doc = lies(sendung(1, 10, "0.1.0", "", {p.neu(Art::start, 5, "")}));
    TEST_ASSERT_TRUE(doc["stand"].isNull());
}

void test_nachgereichtes_aus_frueherem_start_traegt_seinen_start() {
    Protokoll alt(16);
    Ereignis e = alt.neu(Art::knopf, 300, "");
    e.knopf = 2;
    auto doc = lies(sendung(17, 50, "0.1.0", "x", {e}));
    TEST_ASSERT_EQUAL(16, doc["ereignisse"][0]["start"].as<int>());
}

void test_spiel_ereignis_traegt_das_spiel() {
    Protokoll p(1);
    Ereignis e = p.neu(Art::spiel, 5, "");
    e.spiel = "stimmen";
    auto doc = lies(sendung(1, 10, "0.1.0", "x", {e}));
    TEST_ASSERT_EQUAL_STRING("spiel", doc["ereignisse"][0]["art"]);
    TEST_ASSERT_EQUAL_STRING("stimmen", doc["ereignisse"][0]["spiel"]);
}

void test_alle_arten_haben_ihren_vertragsnamen() {
    TEST_ASSERT_EQUAL_STRING("start", art_name(Art::start));
    TEST_ASSERT_EQUAL_STRING("knopf", art_name(Art::knopf));
    TEST_ASSERT_EQUAL_STRING("figur_auf", art_name(Art::figur_auf));
    TEST_ASSERT_EQUAL_STRING("figur_ab", art_name(Art::figur_ab));
    TEST_ASSERT_EQUAL_STRING("spiel", art_name(Art::spiel));
    TEST_ASSERT_EQUAL_STRING("ruhe", art_name(Art::ruhe));
    TEST_ASSERT_EQUAL_STRING("abgleich", art_name(Art::abgleich));
}

void test_zeile_im_flash_kommt_unveraendert_zurueck() {
    Protokoll p(16);
    Ereignis e = p.neu(Art::figur_ab, 777, "2026-11-20T07:15:02+00:00");
    e.uid = "DEADBEEF";
    Ereignis zurueck;
    TEST_ASSERT_TRUE(aus_zeile(als_zeile(e), zurueck));
    TEST_ASSERT_EQUAL_UINT32(16, zurueck.start);
    TEST_ASSERT_EQUAL_UINT32(1, zurueck.nr);
    TEST_ASSERT_EQUAL_UINT32(777, zurueck.ms);
    TEST_ASSERT_EQUAL(Art::figur_ab, zurueck.art);
    TEST_ASSERT_EQUAL_STRING("DEADBEEF", zurueck.uid.c_str());
    TEST_ASSERT_EQUAL_STRING("2026-11-20T07:15:02+00:00", zurueck.zeit.c_str());
}

void test_zeile_hat_keinen_zeilenumbruch() {
    Protokoll p(1);
    Ereignis e = p.neu(Art::spiel, 1, "");
    e.spiel = "licht-und-klang";
    TEST_ASSERT_EQUAL(std::string::npos, als_zeile(e).find('\n'));
}

void test_kaputte_zeile_wird_erkannt() {
    Ereignis e;
    TEST_ASSERT_FALSE(aus_zeile("{\"nr\":1,", e));
    TEST_ASSERT_FALSE(aus_zeile("{\"start\":1,\"nr\":1,\"ms\":1,\"art\":\"unsinn\"}", e));
}

void test_antwort_liefert_den_stand() {
    std::string stand;
    TEST_ASSERT_TRUE(antwort_lesen(R"({"neu": 2, "doppelt": 1, "stand": "abc"})", stand));
    TEST_ASSERT_EQUAL_STRING("abc", stand.c_str());
    TEST_ASSERT_FALSE(antwort_lesen("<html>", stand));
}

void test_uhrzeit_als_iso_in_utc() {
    TEST_ASSERT_EQUAL_STRING("2026-11-20T07:15:02+00:00", iso_utc(1795158902).c_str());
}

void test_uhr_vor_ntp_ergibt_keine_zeit() {
    // Ohne NTP steht die Uhr kurz nach 1970.
    TEST_ASSERT_TRUE(iso_utc(12345).empty());
}

// --- Versand -----------------------------------------------------------------

static Ereignis ereignis(uint32_t start, uint32_t nr) {
    Ereignis e;
    e.start = start;
    e.nr = nr;
    e.ms = nr * 100;
    e.art = Art::knopf;
    e.knopf = 1;
    return e;
}

void test_neues_ereignis_geht_live_raus() {
    SpeicherPuffer puffer;
    Versand v(puffer, 3);
    v.neu(ereignis(1, 1));
    TEST_ASSERT_TRUE(v.offen());
    Stapel s = v.stapel();
    TEST_ASSERT_EQUAL(1, s.ereignisse.size());
    v.erfolg(s);
    TEST_ASSERT_FALSE(v.offen());
    TEST_ASSERT_EQUAL(0, puffer.anzahl());
}

void test_fehlschlag_legt_ereignisse_in_den_flash() {
    SpeicherPuffer puffer;
    Versand v(puffer, 3);
    v.neu(ereignis(1, 1));
    v.neu(ereignis(1, 2));
    Stapel s = v.stapel();
    v.fehlschlag(s);
    TEST_ASSERT_EQUAL(2, puffer.anzahl());
    TEST_ASSERT_TRUE(v.offen());
}

void test_gepuffertes_geht_vor_neuem_und_der_stapel_ist_begrenzt() {
    SpeicherPuffer puffer;
    Versand v(puffer, 3);
    v.neu(ereignis(1, 1));
    v.neu(ereignis(1, 2));
    v.fehlschlag(v.stapel());
    v.neu(ereignis(1, 3));
    v.neu(ereignis(1, 4));

    Stapel s = v.stapel();
    TEST_ASSERT_EQUAL(3, s.ereignisse.size());
    TEST_ASSERT_EQUAL_UINT32(1, s.ereignisse[0].nr);
    TEST_ASSERT_EQUAL_UINT32(2, s.ereignisse[1].nr);
    TEST_ASSERT_EQUAL_UINT32(3, s.ereignisse[2].nr);
    v.erfolg(s);
    TEST_ASSERT_EQUAL(0, puffer.anzahl());

    s = v.stapel();
    TEST_ASSERT_EQUAL(1, s.ereignisse.size());
    TEST_ASSERT_EQUAL_UINT32(4, s.ereignisse[0].nr);
}

void test_waehrend_des_sendens_neues_geht_nicht_verloren() {
    SpeicherPuffer puffer;
    Versand v(puffer, 10);
    v.neu(ereignis(1, 1));
    Stapel s = v.stapel();
    v.neu(ereignis(1, 2));  // kommt an, waehrend der erste unterwegs ist
    v.erfolg(s);
    Stapel rest = v.stapel();
    TEST_ASSERT_EQUAL(1, rest.ereignisse.size());
    TEST_ASSERT_EQUAL_UINT32(2, rest.ereignisse[0].nr);
}

void test_offline_wandert_alles_sofort_in_den_flash() {
    // Ohne WLAN soll ein Ausschalten nichts kosten.
    SpeicherPuffer puffer;
    Versand v(puffer, 10);
    v.neu(ereignis(1, 1));
    v.neu(ereignis(1, 2));
    v.offline();
    TEST_ASSERT_EQUAL(2, puffer.anzahl());
    TEST_ASSERT_EQUAL(2, v.stapel().ereignisse.size());
}

void test_gepuffertes_aus_frueherem_start_behaelt_seinen_start() {
    SpeicherPuffer puffer;
    {
        Versand alt(puffer, 10);
        alt.neu(ereignis(16, 5));
        alt.offline();
    }
    Versand v(puffer, 10);
    Stapel s = v.stapel();
    TEST_ASSERT_EQUAL_UINT32(16, s.ereignisse[0].start);
    TEST_ASSERT_EQUAL_UINT32(5, s.ereignisse[0].nr);
}

void test_kaputte_zeilen_im_puffer_werden_uebergangen() {
    SpeicherPuffer puffer;
    puffer.anhaengen({"murks", als_zeile(ereignis(1, 7))});
    Versand v(puffer, 10);
    Stapel s = v.stapel();
    TEST_ASSERT_EQUAL(1, s.ereignisse.size());
    TEST_ASSERT_EQUAL_UINT32(7, s.ereignisse[0].nr);
    v.erfolg(s);
    TEST_ASSERT_EQUAL(0, puffer.anzahl());
}

void test_puffer_hat_eine_obergrenze_und_wirft_das_aelteste_weg() {
    SpeicherPuffer puffer;
    Versand v(puffer, 10, 4);
    for (uint32_t i = 1; i <= 6; ++i) v.neu(ereignis(1, i));
    v.offline();
    TEST_ASSERT_EQUAL(4, puffer.anzahl());
    TEST_ASSERT_EQUAL_UINT32(3, v.stapel().ereignisse[0].nr);
}

void test_wartezeit_waechst_bei_fehlschlaegen_und_faellt_bei_erfolg() {
    SpeicherPuffer puffer;
    Versand v(puffer, 10);
    TEST_ASSERT_EQUAL_UINT32(0, v.wartezeit_ms());
    v.neu(ereignis(1, 1));
    v.fehlschlag(v.stapel());
    uint32_t erste = v.wartezeit_ms();
    TEST_ASSERT_GREATER_THAN_UINT32(0, erste);
    v.fehlschlag(v.stapel());
    TEST_ASSERT_GREATER_THAN_UINT32(erste, v.wartezeit_ms());
    for (int i = 0; i < 30; ++i) v.fehlschlag(v.stapel());
    TEST_ASSERT_LESS_OR_EQUAL_UINT32(300000, v.wartezeit_ms());
    v.erfolg(v.stapel());
    TEST_ASSERT_EQUAL_UINT32(0, v.wartezeit_ms());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_nummern_laufen_ab_eins);
    RUN_TEST(test_sendung_hat_den_vertragskopf);
    RUN_TEST(test_zeit_ist_null_wenn_unbekannt);
    RUN_TEST(test_ohne_stand_steht_null_im_kopf);
    RUN_TEST(test_nachgereichtes_aus_frueherem_start_traegt_seinen_start);
    RUN_TEST(test_spiel_ereignis_traegt_das_spiel);
    RUN_TEST(test_alle_arten_haben_ihren_vertragsnamen);
    RUN_TEST(test_zeile_im_flash_kommt_unveraendert_zurueck);
    RUN_TEST(test_zeile_hat_keinen_zeilenumbruch);
    RUN_TEST(test_kaputte_zeile_wird_erkannt);
    RUN_TEST(test_antwort_liefert_den_stand);
    RUN_TEST(test_uhrzeit_als_iso_in_utc);
    RUN_TEST(test_uhr_vor_ntp_ergibt_keine_zeit);
    RUN_TEST(test_neues_ereignis_geht_live_raus);
    RUN_TEST(test_fehlschlag_legt_ereignisse_in_den_flash);
    RUN_TEST(test_gepuffertes_geht_vor_neuem_und_der_stapel_ist_begrenzt);
    RUN_TEST(test_waehrend_des_sendens_neues_geht_nicht_verloren);
    RUN_TEST(test_offline_wandert_alles_sofort_in_den_flash);
    RUN_TEST(test_gepuffertes_aus_frueherem_start_behaelt_seinen_start);
    RUN_TEST(test_kaputte_zeilen_im_puffer_werden_uebergangen);
    RUN_TEST(test_puffer_hat_eine_obergrenze_und_wirft_das_aelteste_weg);
    RUN_TEST(test_wartezeit_waechst_bei_fehlschlaegen_und_faellt_bei_erfolg);
    return UNITY_END();
}
