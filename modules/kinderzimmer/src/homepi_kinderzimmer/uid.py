"""Die UID eines NFC-Tags in einer Schreibweise.

Eigene Datei, weil zwei Seiten sie brauchen: ``schemas`` prueft damit jede
Eingabe, ``dienst`` rechnet damit. Laege sie in ``dienst``, importierten sich
die beiden gegenseitig.
"""

from __future__ import annotations

import re

from homepi_core import ServiceError

#: NFC-Tags haben 4, 7 oder 10 Byte UID (ISO 14443-3). NTAG21x sind 7 Byte.
GUELTIGE_LAENGEN = (4, 7, 10)

_TRENNER = re.compile(r"[\s:\-]")
_HEX = re.compile(r"^[0-9A-F]*$")


class UidUngueltig(ServiceError):
    status = 422
    title = "UID ungültig"


def normalisiere_uid(roh: str) -> str:
    """``04:a1:b2 …`` und ``04A1B2…`` sind dieselbe Figur."""
    uid = _TRENNER.sub("", roh).upper()
    if not _HEX.match(uid) or len(uid) % 2 or len(uid) // 2 not in GUELTIGE_LAENGEN:
        raise UidUngueltig(
            f"„{roh.strip()}“ ist keine UID eines NFC-Tags. Erwartet sind 4, 7 oder 10 Byte "
            "in Hex, etwa 04:A1:B2:C3:D4:E5:F6."
        )
    return uid
