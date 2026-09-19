"""Die Staffelangabe, wie die uebernommenen Tests sie bauen.

In der alten Anwendung war das `StaffelConfig` aus der Konfigurationsdatei --
mit Feldern, die nur sie brauchte (`dfbnet_filter`, `sportrichter_email`).
Die Regeln lesen davon nur vier Felder, und zwar ueber `getattr`. Deshalb
genuegt hier ein Platzhalter, der alles annimmt und nichts behauptet.
"""

from __future__ import annotations

from typing import Any

from homepi_pruefdienst import aufstellung
from homepi_pruefdienst.bericht import MatchReportExtractor, Player
from homepi_pruefdienst.regelwerk.auskunft import Auskunft


class StaffelConfig:
    name: str = ""
    altersklasse: str = ""
    saison: str = ""
    spieltage: int = 0
    hoehere_mannschaften: tuple[str, ...] = ()

    def __init__(self, **felder: Any) -> None:
        self.__dict__.update(felder)


class FakeAuskunft(Auskunft):
    """Was ein Speicher sagen wuerde, ohne Speicher.

    Uebernommen aus `tests/test_regelwerk_auskunft.py` der alten Anwendung.
    """

    def __init__(self, verwarnungen: Any = None, sperren: Any = None) -> None:
        self._verwarnungen = verwarnungen or {}
        self._sperren = sperren or {}
        self.gefragt: list[tuple] = []

    def verwarnungen(self, pass_nr, wettbewerb, seit=None):  # type: ignore[override]
        self.gefragt.append(("verwarnungen", pass_nr, wettbewerb, seit))
        return self._verwarnungen.get((pass_nr, wettbewerb), 0)

    def letzte_sperre(self, pass_nr, wettbewerb):  # type: ignore[override]
        self.gefragt.append(("letzte_sperre", pass_nr, wettbewerb))
        return self._sperren.get((pass_nr, wettbewerb))


def spieler_aus_api(roh_api: dict[str, Any]) -> Player:
    """Den Weg gehen, den ein Spieler im Lauf wirklich nimmt.

    Schnittstelle -> `aufstellung.spieler_aus_api` -> der Extraktor baut den
    `Player`. In der alten Anwendung lag dazwischen die Datenbank (JSON hinein,
    JSON heraus); hier ist es der Extraktor. Beide Male ist die Frage
    dieselbe: kommt das Spielrecht unversehrt an?
    """
    kader = MatchReportExtractor()._parse_raw_team(
        {
            "teamName": "T",
            "sections": [
                {
                    "title": "Startaufstellung (1 Spieler)",
                    "players": [aufstellung.spieler_aus_api(roh_api)],
                }
            ],
        }
    )
    return kader.starting_eleven[0]
