"""Die Entscheidungen der Verwaltung.

Rein: keine Datenbank, kein await. Alles, was hier steht, lässt sich in
Millisekunden vollständig durchtesten - und genau das ist der Grund, warum die
Regeln, die einen Verwalter aussperren könnten, hierher gehören und nicht in
den Router.

Das Rechtemodell selbst kommt aus ``homepi_core.auth``: eine Rolle je Artefakt,
kein globaler Administrator. Wer ``verwaltung`` verwalten darf, ist das, was
man sonst Administrator nennt - und darf damit trotzdem nicht automatisch an
die Geräte im Haus.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from homepi_core import ServiceError
from homepi_core.auth import VERWALTUNG, Rolle
from homepi_core.auth.dienst import LetzterVerwalter, pruefe_letzter_verwalter


class BenutzerUnbekannt(ServiceError):
    status = 404
    title = "Benutzer nicht gefunden"


class SelbstSchutz(ServiceError):
    """Was ein Verwalter mit dem eigenen Konto nicht tun darf.

    Nicht aus Bevormundung: ein Fehlgriff am eigenen Konto wirkt sofort und
    nimmt einem die Möglichkeit, ihn zurückzunehmen.
    """

    status = 409
    title = "Nicht am eigenen Konto"


def pruefe_nicht_selbst(eigene_id: uuid.UUID, ziel_id: uuid.UUID, was: str) -> None:
    if eigene_id == ziel_id:
        raise SelbstSchutz(f"{was} geht nicht am eigenen Konto.")


def pruefe_rollenwechsel(
    *,
    eigene_id: uuid.UUID,
    ziel_id: uuid.UUID,
    artefakt: str,
    neue_rolle: Rolle | None,
    anzahl_verwalter: int,
    ziel_ist_verwalter: bool,
) -> None:
    """Darf dieses Recht so gesetzt oder entzogen werden?

    ``neue_rolle=None`` heißt: entziehen. Zwei Regeln, und beide gelten nur für
    das Artefakt ``verwaltung``:

    1. Niemand nimmt sich selbst die Verwaltung. Wer das täte, könnte es nicht
       zurücknehmen - und säße vor einer Oberfläche, die ihn nicht mehr
       hineinlässt.
    2. Der letzte Verwalter bleibt. Sonst kann diese Installation niemand mehr
       verwalten, und es bliebe nur die Kommandozeile.
    """
    if artefakt != VERWALTUNG:
        return

    verliert_die_verwaltung = neue_rolle is None or neue_rolle is not Rolle.VERWALTER
    if not verliert_die_verwaltung:
        return

    pruefe_nicht_selbst(eigene_id, ziel_id, "Die Verwaltung abzugeben")
    pruefe_letzter_verwalter(anzahl_verwalter, ziel_ist_verwalter, "Diese Änderung")


def pruefe_loeschen(
    *,
    eigene_id: uuid.UUID,
    ziel_id: uuid.UUID,
    anzahl_verwalter: int,
    ziel_ist_verwalter: bool,
) -> None:
    pruefe_nicht_selbst(eigene_id, ziel_id, "Löschen")
    pruefe_letzter_verwalter(anzahl_verwalter, ziel_ist_verwalter, "Das Konto zu löschen")


def pruefe_sperren(
    *,
    eigene_id: uuid.UUID,
    ziel_id: uuid.UUID,
    aktiv: bool,
    anzahl_verwalter: int,
    ziel_ist_verwalter: bool,
) -> None:
    """Entsperren ist immer harmlos - gesperrt wird geprüft."""
    if aktiv:
        return
    pruefe_nicht_selbst(eigene_id, ziel_id, "Sperren")
    pruefe_letzter_verwalter(anzahl_verwalter, ziel_ist_verwalter, "Das Konto zu sperren")


def sichtbare_rechte(rechte: Mapping[str, Rolle]) -> dict[str, str]:
    """Für die Ausgabe: Artefakt -> Rollenname, alphabetisch."""
    return {artefakt: rolle.value for artefakt, rolle in sorted(rechte.items())}


__all__ = [
    "BenutzerUnbekannt",
    "LetzterVerwalter",
    "SelbstSchutz",
    "pruefe_loeschen",
    "pruefe_nicht_selbst",
    "pruefe_rollenwechsel",
    "pruefe_sperren",
    "sichtbare_rechte",
]
