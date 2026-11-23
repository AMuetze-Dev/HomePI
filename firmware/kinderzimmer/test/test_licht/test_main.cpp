// Licht: Farben lesen, Helligkeit deckeln, sanft ueberblenden, nie springen.
#include <unity.h>

#include "blende.h"
#include "farbe.h"

using namespace kz;

void setUp() {}
void tearDown() {}

// --- Farbe -------------------------------------------------------------------

void test_hexfarbe_wird_gelesen() {
    Farbe f;
    TEST_ASSERT_TRUE(farbe_lesen("#FFB000", f));
    TEST_ASSERT_EQUAL_UINT8(0xFF, f.r);
    TEST_ASSERT_EQUAL_UINT8(0xB0, f.g);
    TEST_ASSERT_EQUAL_UINT8(0x00, f.b);
}

void test_kleinbuchstaben_gehen_auch() {
    Farbe f;
    TEST_ASSERT_TRUE(farbe_lesen("#0a1b2c", f));
    TEST_ASSERT_EQUAL_UINT8(0x0A, f.r);
    TEST_ASSERT_EQUAL_UINT8(0x1B, f.g);
    TEST_ASSERT_EQUAL_UINT8(0x2C, f.b);
}

void test_kaputte_farbe_wird_abgelehnt() {
    Farbe f;
    TEST_ASSERT_FALSE(farbe_lesen("FFB000", f));
    TEST_ASSERT_FALSE(farbe_lesen("#FFB00", f));
    TEST_ASSERT_FALSE(farbe_lesen("#GGB000", f));
    TEST_ASSERT_FALSE(farbe_lesen(nullptr, f));
}

void test_volle_helligkeit_volle_stufe_ergibt_die_farbe() {
    Farbe f = gedimmt({200, 100, 50}, 100, 255);
    TEST_ASSERT_EQUAL_UINT8(200, f.r);
    TEST_ASSERT_EQUAL_UINT8(100, f.g);
    TEST_ASSERT_EQUAL_UINT8(50, f.b);
}

void test_helligkeit_max_ist_eine_obergrenze() {
    // 40 Prozent: kein Kanal darf ueber 40 Prozent seines Werts liegen.
    Farbe f = gedimmt({255, 255, 255}, 40, 255);
    TEST_ASSERT_LESS_OR_EQUAL_UINT8(102, f.r);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT8(100, f.r);
}

void test_helligkeit_ueber_hundert_wird_gekappt() {
    Farbe f = gedimmt({255, 0, 0}, 250, 255);
    TEST_ASSERT_EQUAL_UINT8(255, f.r);
}

void test_stufe_null_ist_aus() {
    Farbe f = gedimmt({255, 255, 255}, 100, 0);
    TEST_ASSERT_EQUAL_UINT8(0, f.r);
    TEST_ASSERT_EQUAL_UINT8(0, f.g);
    TEST_ASSERT_EQUAL_UINT8(0, f.b);
}

void test_stufe_steigt_monoton() {
    // Die Gammakurve darf beim Aufblenden nie einen Schritt zurueck machen.
    uint8_t vorher = 0;
    for (int s = 0; s <= 255; ++s) {
        uint8_t r = gedimmt({255, 0, 0}, 100, static_cast<uint8_t>(s)).r;
        TEST_ASSERT_GREATER_OR_EQUAL_UINT8(vorher, r);
        vorher = r;
    }
}

// --- Blende ------------------------------------------------------------------

void test_blende_beginnt_dunkel() {
    Blende b;
    TEST_ASSERT_EQUAL_UINT8(0, b.stufe());
    TEST_ASSERT_TRUE(b.fertig());
}

void test_blende_erreicht_das_ziel_in_der_dauer() {
    Blende b;
    b.ziel(255, 200);
    b.schritt(100);
    TEST_ASSERT_UINT8_WITHIN(3, 128, b.stufe());
    TEST_ASSERT_FALSE(b.fertig());
    b.schritt(100);
    TEST_ASSERT_EQUAL_UINT8(255, b.stufe());
    TEST_ASSERT_TRUE(b.fertig());
}

void test_blende_schiesst_nicht_ueber() {
    Blende b;
    b.ziel(200, 100);
    b.schritt(5000);
    TEST_ASSERT_EQUAL_UINT8(200, b.stufe());
}

void test_richtungswechsel_springt_nicht() {
    // Halb aufgeblendet, dann aus: Es geht von der halben Stufe abwaerts,
    // nicht erst auf null oder voll. Ein Sprung waere ein Blinken.
    Blende b;
    b.ziel(255, 200);
    b.schritt(100);
    uint8_t mitte = b.stufe();
    b.ziel(0, 1000);
    b.schritt(1);
    TEST_ASSERT_UINT8_WITHIN(2, mitte, b.stufe());
    TEST_ASSERT_LESS_OR_EQUAL_UINT8(mitte, b.stufe());
}

void test_kein_schritt_ist_groesser_als_die_rate_erlaubt() {
    // Auch bei grossen Zeitluecken aendert sich die Stufe je Millisekunde
    // hoechstens so stark, wie die kuerzeste erlaubte Blende vorgibt.
    Blende b;
    b.ziel(255, 0);  // 0 ms ist nicht erlaubt und wird zur kuerzesten Blende
    b.schritt(1);
    TEST_ASSERT_LESS_THAN_UINT8(255, b.stufe());
    TEST_ASSERT_GREATER_THAN_UINT8(0, b.stufe());
}

void test_gleiches_ziel_aendert_nichts() {
    Blende b;
    b.ziel(255, 200);
    b.schritt(200);
    b.ziel(255, 200);
    b.schritt(10);
    TEST_ASSERT_EQUAL_UINT8(255, b.stufe());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_hexfarbe_wird_gelesen);
    RUN_TEST(test_kleinbuchstaben_gehen_auch);
    RUN_TEST(test_kaputte_farbe_wird_abgelehnt);
    RUN_TEST(test_volle_helligkeit_volle_stufe_ergibt_die_farbe);
    RUN_TEST(test_helligkeit_max_ist_eine_obergrenze);
    RUN_TEST(test_helligkeit_ueber_hundert_wird_gekappt);
    RUN_TEST(test_stufe_null_ist_aus);
    RUN_TEST(test_stufe_steigt_monoton);
    RUN_TEST(test_blende_beginnt_dunkel);
    RUN_TEST(test_blende_erreicht_das_ziel_in_der_dauer);
    RUN_TEST(test_blende_schiesst_nicht_ueber);
    RUN_TEST(test_richtungswechsel_springt_nicht);
    RUN_TEST(test_kein_schritt_ist_groesser_als_die_rate_erlaubt);
    RUN_TEST(test_gleiches_ziel_aendert_nichts);
    return UNITY_END();
}
