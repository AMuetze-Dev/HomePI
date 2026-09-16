"""Tests, die gegen eine laufende Instanz sprechen - egal welche.

Dasselbe Testpaket laeuft gegen den Dienst auf dem eigenen Rechner, gegen einen
Container in der CI und gegen den Pi. Was sich unterscheidet, ist genau eine
Angabe: die Basis-URL.

Aufloesung in dieser Reihenfolge:

    1. HOMEPI_BASIS_URL          direkte Angabe, schlaegt alles andere
    2. HOMEPI_ZIEL=<name>        benennt ein Ziel aus homepi.toml
    3. das Ziel [ziele.standard] aus homepi.toml
    4. http://127.0.0.1:8000     Notnagel

homepi.toml im Wurzelverzeichnis:

    [ziele.lokal]
    basis_url = "http://127.0.0.1:8000"

    [ziele.pi]
    basis_url = "https://api.home.example.com"
    timeout = 10
"""

from .ziel import Ziel, ziel_aus_umgebung, ziele_lesen

__all__ = ["Ziel", "ziel_aus_umgebung", "ziele_lesen"]
