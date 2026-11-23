#pragma once
// Vorlage. Kopieren nach include/secrets.h und ausfuellen:
//
//     cp include/secrets.beispiel.h include/secrets.h
//
// include/secrets.h ist in .gitignore und kommt nie ins Repo.

// WLAN, 2,4 GHz (der ESP32-S3 kann kein 5 GHz).
#define WLAN_NAME "MeinWLAN"
#define WLAN_PASSWORT "geheim"

// Adresse des Gateways, ohne Schraegstrich am Ende. Der Pfad
// /kinderzimmer/geraet/... wird angehaengt.
//   Pi im LAN:          "https://api.example.org"
//   Entwicklung am PC:  "http://192.168.178.20:18000"
#define PI_ADRESSE "https://api.example.org"

// Token des Geraets. Entsteht auf der Website unter Kinderzimmer -> Geraete
// und wird dort genau einmal angezeigt.
#define GERAET_TOKEN "hier-das-token-einfuegen"

// Optional: eigenes Wurzelzertifikat (PEM) statt Let's Encrypt.
// #define PI_CA_ZERTIFIKAT "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
