// Ton: Lautstaerke hart deckeln, WAV-Kopf pruefen.
#include <unity.h>

#include <cstring>
#include <vector>

#include "pegel.h"
#include "wav.h"

using namespace kz;

void setUp() {}
void tearDown() {}

// --- Pegel -------------------------------------------------------------------

void test_hundert_prozent_laesst_das_sample_fast_unveraendert() {
    uint16_t f = faktor_q15(100);
    TEST_ASSERT_INT16_WITHIN(1, 10000, skaliere(10000, f));
    TEST_ASSERT_INT16_WITHIN(1, -32768, skaliere(-32768, f));
}

void test_fuenfzig_prozent_halbiert() {
    uint16_t f = faktor_q15(50);
    TEST_ASSERT_INT16_WITHIN(1, 5000, skaliere(10000, f));
    TEST_ASSERT_INT16_WITHIN(1, -5000, skaliere(-10000, f));
}

void test_ueber_hundert_wird_auf_hundert_gekappt() {
    TEST_ASSERT_EQUAL_UINT16(faktor_q15(100), faktor_q15(180));
}

void test_null_ist_stumm() {
    TEST_ASSERT_EQUAL_INT16(0, skaliere(32767, faktor_q15(0)));
}

void test_kein_sample_ueberschreitet_die_obergrenze() {
    // Fuer jede Obergrenze und jedes Sample: |aus| <= |ein| * p / 100.
    for (int p = 0; p <= 100; p += 5) {
        uint16_t f = faktor_q15(static_cast<uint8_t>(p));
        for (int s = -32768; s <= 32767; s += 257) {
            int aus = skaliere(static_cast<int16_t>(s), f);
            long grenze = (static_cast<long>(s < 0 ? -s : s) * p) / 100 + 1;
            TEST_ASSERT_TRUE((aus < 0 ? -aus : aus) <= grenze);
        }
    }
}

void test_puffer_wird_ganz_skaliert() {
    int16_t puffer[4] = {1000, -1000, 2000, -2000};
    skaliere_puffer(puffer, 4, faktor_q15(50));
    TEST_ASSERT_INT16_WITHIN(1, 500, puffer[0]);
    TEST_ASSERT_INT16_WITHIN(1, -500, puffer[1]);
    TEST_ASSERT_INT16_WITHIN(1, 1000, puffer[2]);
    TEST_ASSERT_INT16_WITHIN(1, -1000, puffer[3]);
}

// --- WAV ---------------------------------------------------------------------

static void le16(std::vector<uint8_t>& v, uint16_t x) {
    v.push_back(x & 0xFF);
    v.push_back(x >> 8);
}
static void le32(std::vector<uint8_t>& v, uint32_t x) {
    for (int i = 0; i < 4; ++i) v.push_back((x >> (8 * i)) & 0xFF);
}
static void kennung(std::vector<uint8_t>& v, const char* s) {
    v.insert(v.end(), s, s + 4);
}

static std::vector<uint8_t> wav(uint16_t format, uint16_t kanaele, uint32_t rate, uint16_t bits,
                                uint32_t daten, bool mit_list = false) {
    std::vector<uint8_t> v;
    kennung(v, "RIFF");
    le32(v, 36 + daten + (mit_list ? 12 : 0));
    kennung(v, "WAVE");
    kennung(v, "fmt ");
    le32(v, 16);
    le16(v, format);
    le16(v, kanaele);
    le32(v, rate);
    le32(v, rate * kanaele * bits / 8);
    le16(v, kanaele * bits / 8);
    le16(v, bits);
    if (mit_list) {
        kennung(v, "LIST");
        le32(v, 4);
        kennung(v, "INFO");
    }
    kennung(v, "data");
    le32(v, daten);
    return v;
}

void test_passendes_wav_wird_erkannt() {
    auto kopf = wav(1, 1, 22050, 16, 44100);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::keiner, wav_lesen(kopf.data(), kopf.size(), info));
    TEST_ASSERT_EQUAL_UINT32(44, info.daten_ab);
    TEST_ASSERT_EQUAL_UINT32(44100, info.daten_bytes);
}

void test_fremde_bloecke_werden_uebersprungen() {
    auto kopf = wav(1, 1, 22050, 16, 1000, true);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::keiner, wav_lesen(kopf.data(), kopf.size(), info));
    TEST_ASSERT_EQUAL_UINT32(56, info.daten_ab);
}

void test_stereo_wird_abgelehnt() {
    auto kopf = wav(1, 2, 22050, 16, 1000);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::falsches_format, wav_lesen(kopf.data(), kopf.size(), info));
}

void test_andere_rate_wird_abgelehnt() {
    auto kopf = wav(1, 1, 44100, 16, 1000);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::falsches_format, wav_lesen(kopf.data(), kopf.size(), info));
}

void test_kein_pcm_wird_abgelehnt() {
    auto kopf = wav(3, 1, 22050, 16, 1000);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::falsches_format, wav_lesen(kopf.data(), kopf.size(), info));
}

void test_kein_riff_ist_kaputt() {
    auto kopf = wav(1, 1, 22050, 16, 1000);
    kopf[0] = 'X';
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::kaputt, wav_lesen(kopf.data(), kopf.size(), info));
}

void test_abgeschnittener_kopf_ist_kaputt() {
    auto kopf = wav(1, 1, 22050, 16, 1000);
    WavInfo info;
    TEST_ASSERT_EQUAL(WavFehler::kaputt, wav_lesen(kopf.data(), 30, info));
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_hundert_prozent_laesst_das_sample_fast_unveraendert);
    RUN_TEST(test_fuenfzig_prozent_halbiert);
    RUN_TEST(test_ueber_hundert_wird_auf_hundert_gekappt);
    RUN_TEST(test_null_ist_stumm);
    RUN_TEST(test_kein_sample_ueberschreitet_die_obergrenze);
    RUN_TEST(test_puffer_wird_ganz_skaliert);
    RUN_TEST(test_passendes_wav_wird_erkannt);
    RUN_TEST(test_fremde_bloecke_werden_uebersprungen);
    RUN_TEST(test_stereo_wird_abgelehnt);
    RUN_TEST(test_andere_rate_wird_abgelehnt);
    RUN_TEST(test_kein_pcm_wird_abgelehnt);
    RUN_TEST(test_kein_riff_ist_kaputt);
    RUN_TEST(test_abgeschnittener_kopf_ist_kaputt);
    return UNITY_END();
}
