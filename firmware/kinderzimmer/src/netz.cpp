#include "netz.h"

#include <Arduino.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <mbedtls/sha256.h>
#include <time.h>

#include <cstring>

#include "abgleich.h"
#include "ablage.h"
#include "versand.h"
#include "zertifikate.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "include/secrets.h fehlt. Vorlage kopieren: cp include/secrets.beispiel.h include/secrets.h"
#endif

namespace netz {

namespace {

const char* const PFAD_STAND = "/kinderzimmer/geraet/stand";
const char* const PFAD_DATEIEN = "/kinderzimmer/geraet/dateien/";
const char* const PFAD_EREIGNISSE = "/kinderzimmer/geraet/ereignisse";

constexpr uint32_t ERSTER_VERSUCH_OFFLINE_MS = 15000;  // so lange darf das WLAN beim Start brauchen
constexpr uint32_t ABGLEICH_WARTEN_MS = 60000;           // nach einem gescheiterten Abgleich
constexpr size_t FLASH_RESERVE = 64 * 1024;              // fuer Puffer und Stand

// Ereignis als festes Paket fuer die Warteschlange (keine std::string darin).
struct Paket {
    uint32_t start, nr, ms;
    kz::Art art;
    uint8_t knopf;
    char zeit[32];
    char uid[24];
    char spiel[44];
};

QueueHandle_t eingang = nullptr;
TaskHandle_t aufgabe_ = nullptr;
SemaphoreHandle_t sperre = nullptr;

ablage::FlashPuffer puffer;
kz::Versand* versand = nullptr;
uint32_t start_ = 0;
uint32_t naechster_versand_ = 0;

// Unter `sperre`:
std::string stand_aktuell_;      // damit spielt das Geraet
std::string stand_vorbereitet_;  // geladen, wartet auf eine Spielpause
kz::Stand bereit_;
bool ist_bereit_ = false;
kz::Stand zum_aufraeumen_;  // der Stand, mit dem jetzt gespielt wird
bool aufraeumen_ = false;

volatile bool darf_ = true;
volatile bool abgleich_noetig_ = true;  // der Start gleicht immer ab
uint32_t abgleich_ab_ = 0;

WiFiClient klar;
WiFiClientSecure sicher;

struct Sperre {
    Sperre() { xSemaphoreTake(sperre, portMAX_DELAY); }
    ~Sperre() { xSemaphoreGive(sperre); }
};

bool ist_https() {
    return std::strncmp(PI_ADRESSE, "https://", 8) == 0;
}

WiFiClient& client() {
    if (ist_https()) return sicher;
    return klar;
}

bool oeffnen(HTTPClient& http, const String& pfad) {
    http.setConnectTimeout(5000);
    http.setTimeout(10000);
    http.setReuse(false);
    if (!http.begin(client(), String(PI_ADRESSE) + pfad)) return false;
    http.addHeader("Authorization", String("Bearer ") + GERAET_TOKEN);
    return true;
}

bool bekannt(const std::string& stand) {
    Sperre s;
    return stand == stand_aktuell_ || stand == stand_vorbereitet_;
}

// Warteschlange -> Versand. Nur diese Aufgabe fasst `versand` an.
void aufnehmen() {
    Paket p;
    while (xQueueReceive(eingang, &p, 0) == pdTRUE) {
        kz::Ereignis e;
        e.start = p.start;
        e.nr = p.nr;
        e.ms = p.ms;
        e.art = p.art;
        e.knopf = p.knopf;
        e.zeit = p.zeit;
        e.uid = p.uid;
        e.spiel = p.spiel;
        versand->neu(e);
    }
}

std::string hex(const uint8_t* b, size_t n) {
    static const char Z[] = "0123456789abcdef";
    std::string s;
    for (size_t i = 0; i < n; ++i) {
        s.push_back(Z[b[i] >> 4]);
        s.push_back(Z[b[i] & 15]);
    }
    return s;
}

// --- Abgleich ------------------------------------------------------------

bool laden(const kz::Datei& d) {
    HTTPClient http;
    if (!oeffnen(http, String(PFAD_DATEIEN) + d.id.c_str())) return false;
    int code = http.GET();
    if (code != 200) {
        Serial.printf("[netz] Datei %s: HTTP %d\n", d.id.c_str(), code);
        http.end();
        return false;
    }
    int laenge = http.getSize();
    std::string ziel = ablage::zwischenpfad(d.sha256);
    File f = LittleFS.open(ziel.c_str(), "w");
    if (!f) {
        http.end();
        return false;
    }
    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);
    mbedtls_sha256_starts_ret(&ctx, 0);
    WiFiClient* strom = http.getStreamPtr();
    uint8_t puffer[1024];
    uint32_t gesamt = 0;
    uint32_t zuletzt = millis();
    bool ok = true;
    while (laenge < 0 || gesamt < static_cast<uint32_t>(laenge)) {
        size_t da = strom->available();
        if (da == 0) {
            if (!http.connected() || millis() - zuletzt > 10000) break;
            delay(2);
            continue;
        }
        size_t n = strom->readBytes(puffer, da < sizeof(puffer) ? da : sizeof(puffer));
        if (f.write(puffer, n) != n) {
            ok = false;
            break;
        }
        mbedtls_sha256_update_ret(&ctx, puffer, n);
        gesamt += n;
        zuletzt = millis();
    }
    uint8_t summe[32];
    mbedtls_sha256_finish_ret(&ctx, summe);
    mbedtls_sha256_free(&ctx);
    f.close();
    http.end();

    ok = ok && gesamt == d.bytes && kz::sha_gleich(hex(summe, 32), d.sha256);
    if (!ok) {
        Serial.printf("[netz] Datei %s unvollstaendig oder falsch (%u Bytes)\n", d.id.c_str(),
                      static_cast<unsigned>(gesamt));
        LittleFS.remove(ziel.c_str());
    }
    return ok;
}

void abgleichen() {
    abgleich_noetig_ = false;
    HTTPClient http;
    if (!oeffnen(http, PFAD_STAND)) return;
    int code = http.GET();
    String rumpf = code == 200 ? http.getString() : String();
    http.end();
    if (code != 200) {
        Serial.printf("[netz] Stand: HTTP %d\n", code);
        abgleich_noetig_ = true;
        abgleich_ab_ = millis() + ABGLEICH_WARTEN_MS;
        return;
    }

    kz::Stand neu;
    std::string json(rumpf.c_str(), rumpf.length());
    kz::LeseErgebnis erg = kz::stand_lesen(json, neu);
    if (erg == kz::LeseErgebnis::format_zu_neu) {
        // Vertrag: alten Stand behalten und melden. Gemeldet wird hier ueber
        // die serielle Schnittstelle; der Pi sieht es am alten Stand im Kopf.
        Serial.println("[netz] Der Pi liefert ein neueres Format. Der alte Stand bleibt.");
        return;
    }
    if (erg != kz::LeseErgebnis::ok) {
        Serial.println("[netz] Stand nicht lesbar");
        abgleich_noetig_ = true;
        abgleich_ab_ = millis() + ABGLEICH_WARTEN_MS;
        return;
    }
    if (bekannt(neu.stand)) return;

    kz::Plan plan = kz::plane_abgleich(neu, [](const std::string& sha) { return ablage::vorhanden(sha); });
    if (plan.bytes + FLASH_RESERVE > ablage::frei()) {
        Serial.printf("[netz] Zu wenig Flash: %u KB noetig, %u KB frei. Der alte Stand bleibt.\n",
                      static_cast<unsigned>(plan.bytes / 1024),
                      static_cast<unsigned>(ablage::frei() / 1024));
        return;
    }
    Serial.printf("[netz] Abgleich auf %s: %u Dateien, %u KB\n", neu.stand.c_str(),
                  static_cast<unsigned>(plan.laden.size()), static_cast<unsigned>(plan.bytes / 1024));

    // Erst alles in den Zwischenordner. Der alte Stand spielt derweil weiter.
    ablage::zwischenordner_leeren();
    for (const auto& d : plan.laden) {
        aufnehmen();
        if (!laden(d)) {
            ablage::zwischenordner_leeren();
            abgleich_noetig_ = true;
            abgleich_ab_ = millis() + ABGLEICH_WARTEN_MS;
            return;
        }
    }
    // Dann umschalten. Neue Dateien stoeren die alten nicht (Name = Pruefsumme).
    for (const auto& d : plan.laden) ablage::uebernehmen(d.sha256);
    if (!ablage::stand_schreiben(json)) {
        Serial.println("[netz] Stand liess sich nicht speichern");
        abgleich_noetig_ = true;
        abgleich_ab_ = millis() + ABGLEICH_WARTEN_MS;
        return;
    }
    Sperre s;
    bereit_ = neu;
    ist_bereit_ = true;
    stand_vorbereitet_ = neu.stand;
}

void aufraeumen(const kz::Stand& stand) {
    for (const auto& sha : kz::ueberfluessig(stand, ablage::vorhandene())) {
        Serial.printf("[netz] weg: %s\n", sha.c_str());
        ablage::entferne(sha);
    }
}

// --- Versand -------------------------------------------------------------

void senden() {
    kz::Stapel stapel = versand->stapel();
    if (stapel.ereignisse.empty()) {
        versand->erfolg(stapel);  // nur kaputte Zeilen
        return;
    }
    std::string stand;
    {
        Sperre s;
        stand = stand_aktuell_;
    }
    std::string rumpf = kz::sendung(start_, millis(), FIRMWARE, stand, stapel.ereignisse);

    HTTPClient http;
    int code = -1;
    String antwort;
    if (oeffnen(http, PFAD_EREIGNISSE)) {
        http.addHeader("Content-Type", "application/json");
        code = http.POST(reinterpret_cast<uint8_t*>(const_cast<char*>(rumpf.data())), rumpf.size());
        if (code == 200) antwort = http.getString();
        http.end();
    }

    if (code == 200) {
        versand->erfolg(stapel);
        std::string neu;
        if (kz::antwort_lesen(antwort.c_str(), neu) && !bekannt(neu)) {
            Serial.printf("[netz] Der Pi hat einen neuen Stand: %s\n", neu.c_str());
            abgleich_noetig_ = true;
            abgleich_ab_ = 0;
        }
    } else if (code == 400 || code == 422) {
        // Der Pi lehnt den Inhalt ab. Ein zweiter Versuch aendert daran nichts,
        // und ein haengender Stapel hielte alle folgenden auf.
        Serial.printf("[netz] Ereignisse abgelehnt (HTTP %d), %u verworfen\n", code,
                      static_cast<unsigned>(stapel.ereignisse.size()));
        versand->erfolg(stapel);
    } else {
        Serial.printf("[netz] Ereignisse: HTTP %d, %u im Flash\n", code,
                      static_cast<unsigned>(puffer.anzahl() + stapel.aus_ram));
        versand->fehlschlag(stapel);
        naechster_versand_ = millis() + versand->wartezeit_ms();
    }
}

// --- Aufgabe -------------------------------------------------------------

bool uhr_gestellt() {
    return time(nullptr) > 1704067200;
}

void aufgabe(void*) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WLAN_NAME, WLAN_PASSWORT);
    bool jemals_verbunden = false;
    bool ntp_gestartet = false;
    uint32_t verbunden_seit = 0;

    for (;;) {
        aufnehmen();

        bool aufraeumen_jetzt = false;
        kz::Stand behalten;
        {
            Sperre s;
            if (aufraeumen_) {
                aufraeumen_ = false;
                aufraeumen_jetzt = true;
                // Was gespielt wird und was schon fuer danach bereitliegt.
                behalten = zum_aufraeumen_;
                if (ist_bereit_)
                    behalten.dateien.insert(behalten.dateien.end(), bereit_.dateien.begin(),
                                            bereit_.dateien.end());
            }
        }
        if (aufraeumen_jetzt) aufraeumen(behalten);

        if (WiFi.status() != WL_CONNECTED) {
            verbunden_seit = 0;
            // Ohne Verbindung sofort in den Flash: Ausschalten kostet dann nichts.
            if (jemals_verbunden || millis() > ERSTER_VERSUCH_OFFLINE_MS) versand->offline();
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000));
            continue;
        }
        if (!jemals_verbunden) {
            Serial.printf("[netz] WLAN verbunden, %s\n", WiFi.localIP().toString().c_str());
        }
        jemals_verbunden = true;
        if (verbunden_seit == 0) verbunden_seit = millis();
        if (!ntp_gestartet) {
            configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
            ntp_gestartet = true;
        }
        // TLS prueft die Gueltigkeit des Zertifikats; ohne Uhr scheitert das.
        // Zehn Sekunden auf NTP warten, dann trotzdem versuchen.
        if (ist_https() && !uhr_gestellt() && millis() - verbunden_seit < 10000) {
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(250));
            continue;
        }

        if (abgleich_noetig_ && darf_ && static_cast<int32_t>(millis() - abgleich_ab_) >= 0)
            abgleichen();

        aufnehmen();
        if (versand->offen() && static_cast<int32_t>(millis() - naechster_versand_) >= 0) {
            senden();
            continue;  // gleich weiter, falls mehr als ein Stapel wartet
        }
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000));
    }
}

}  // namespace

void beginnen(uint32_t start, const kz::Stand& stand) {
    start_ = start;
    stand_aktuell_ = stand.stand;
    sperre = xSemaphoreCreateMutex();
    eingang = xQueueCreate(128, sizeof(Paket));
    versand = new kz::Versand(puffer);
    if (ist_https()) {
#ifdef PI_CA_ZERTIFIKAT
        sicher.setCACert(PI_CA_ZERTIFIKAT);
#else
        sicher.setCACert(LETSENCRYPT_WURZELN);
#endif
    }
    // Reste eines abgebrochenen Abgleichs und Dateien, die keiner mehr braucht.
    ablage::zwischenordner_leeren();
    aufraeumen(stand);
    Serial.printf("[netz] %u Ereignisse warten im Flash\n", static_cast<unsigned>(puffer.anzahl()));
    xTaskCreatePinnedToCore(aufgabe, "netz", 12288, nullptr, 2, &aufgabe_, 0);
}

void melde(const kz::Ereignis& e) {
    Paket p;
    std::memset(&p, 0, sizeof(p));
    p.start = e.start;
    p.nr = e.nr;
    p.ms = e.ms;
    p.art = e.art;
    p.knopf = e.knopf;
    std::strncpy(p.zeit, e.zeit.c_str(), sizeof(p.zeit) - 1);
    std::strncpy(p.uid, e.uid.c_str(), sizeof(p.uid) - 1);
    std::strncpy(p.spiel, e.spiel.c_str(), sizeof(p.spiel) - 1);
    if (xQueueSend(eingang, &p, 0) != pdTRUE) Serial.println("[netz] Warteschlange voll, Ereignis fehlt");
    if (aufgabe_ != nullptr) xTaskNotifyGive(aufgabe_);
}

void darf_abgleichen(bool ja) {
    darf_ = ja;
}

bool neuer_stand(kz::Stand& aus) {
    Sperre s;
    if (!ist_bereit_) return false;
    aus = bereit_;
    ist_bereit_ = false;
    return true;
}

void stand_uebernommen(const kz::Stand& stand) {
    {
        Sperre s;
        stand_aktuell_ = stand.stand;
        if (!ist_bereit_) stand_vorbereitet_.clear();
        zum_aufraeumen_ = stand;
        aufraeumen_ = true;
    }
    if (aufgabe_ != nullptr) xTaskNotifyGive(aufgabe_);
}

std::string uhrzeit() {
    return kz::iso_utc(static_cast<int64_t>(time(nullptr)));
}

}  // namespace netz
