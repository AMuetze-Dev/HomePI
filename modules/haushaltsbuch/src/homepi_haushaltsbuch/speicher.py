"""Datenbankzugriff. Hier faellt I/O an, hier stehen keine Entscheidungen."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .dienst import (
    KategorieSicht,
    KategorieUnbekannt,
    KontoSicht,
    KontoUnbekannt,
    NameVergeben,
    NochInBenutzung,
    PersonSicht,
    PersonUnbekannt,
    PostenSicht,
    PostenUnbekannt,
)
from .modelle import Anteil, Kategorie, Konto, Person, Posten
from .schemas import (
    KategorieAendern,
    KategorieAnlegen,
    KontoAendern,
    KontoAnlegen,
    PersonAendern,
    PersonAnlegen,
    PostenAendern,
    PostenAnlegen,
)


async def _anlegen[T](sitzung: AsyncSession, zeile: T, was: str, name: str) -> T:
    """Einfuegen und den Namenskonflikt in einen lesbaren Fehler uebersetzen.

    Die Datenbank ist die einzige Stelle, die zuverlaessig weiss, ob der Name
    frei ist - eine Vorabpruefung waere ein Rennen zwischen zwei Anfragen.
    """
    sitzung.add(zeile)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise NameVergeben(f"{was} '{name}' gibt es bereits") from fehler
    return zeile


async def _loeschen(sitzung: AsyncSession, zeile: object, hinweis: str) -> None:
    await sitzung.delete(zeile)
    try:
        await sitzung.flush()
    except IntegrityError as fehler:
        await sitzung.rollback()
        raise NochInBenutzung(hinweis) from fehler


def _uebernehmen(zeile: object, aenderung: object, *felder: str) -> None:
    """Nur gesetzte Felder uebertragen - None heisst 'nicht angefasst'."""
    for feld in felder:
        wert = getattr(aenderung, feld)
        if wert is not None:
            setattr(zeile, feld, wert)


# --------------------------------------------------------------- Person


async def personen(sitzung: AsyncSession) -> list[Person]:
    ergebnis = await sitzung.execute(select(Person).order_by(Person.reihenfolge, Person.name))
    return list(ergebnis.scalars())


async def person(sitzung: AsyncSession, person_id: uuid.UUID) -> Person:
    zeile = await sitzung.get(Person, person_id)
    if zeile is None:
        raise PersonUnbekannt(f"Es gibt keine Person mit der Kennung {person_id}")
    return zeile


async def person_anlegen(sitzung: AsyncSession, daten: PersonAnlegen) -> Person:
    return await _anlegen(sitzung, Person(**daten.model_dump()), "Eine Person namens", daten.name)


async def person_aendern(
    sitzung: AsyncSession, person_id: uuid.UUID, daten: PersonAendern
) -> Person:
    zeile = await person(sitzung, person_id)
    _uebernehmen(zeile, daten, "name", "reihenfolge")
    await sitzung.flush()
    return zeile


async def person_loeschen(sitzung: AsyncSession, person_id: uuid.UUID) -> None:
    await _loeschen(
        sitzung,
        await person(sitzung, person_id),
        "Diese Person hat noch Konten oder Anteile. Entferne die zuerst.",
    )


# ---------------------------------------------------------------- Konto


async def konten(sitzung: AsyncSession) -> list[Konto]:
    ergebnis = await sitzung.execute(select(Konto).order_by(Konto.reihenfolge, Konto.name))
    return list(ergebnis.scalars())


async def konto(sitzung: AsyncSession, konto_id: uuid.UUID) -> Konto:
    zeile = await sitzung.get(Konto, konto_id)
    if zeile is None:
        raise KontoUnbekannt(f"Es gibt kein Konto mit der Kennung {konto_id}")
    return zeile


async def konto_anlegen(sitzung: AsyncSession, daten: KontoAnlegen) -> Konto:
    if daten.inhaber_id is not None:
        await person(sitzung, daten.inhaber_id)
    return await _anlegen(sitzung, Konto(**daten.model_dump()), "Ein Konto namens", daten.name)


async def konto_aendern(sitzung: AsyncSession, konto_id: uuid.UUID, daten: KontoAendern) -> Konto:
    zeile = await konto(sitzung, konto_id)
    _uebernehmen(zeile, daten, "name", "art", "notiz", "reihenfolge")

    # Zwei Wege zum Inhaber, weil None hier zwei Dinge heissen koennte:
    # "nicht angefasst" und "ab jetzt gemeinschaftlich".
    if daten.gemeinschaftlich:
        zeile.inhaber_id = None
    elif daten.inhaber_id is not None:
        await person(sitzung, daten.inhaber_id)
        zeile.inhaber_id = daten.inhaber_id

    await sitzung.flush()
    return zeile


async def konto_loeschen(sitzung: AsyncSession, konto_id: uuid.UUID) -> None:
    await _loeschen(
        sitzung,
        await konto(sitzung, konto_id),
        "Auf diesem Konto liegen noch Posten. Verschiebe oder entferne die zuerst.",
    )


# ------------------------------------------------------------ Kategorie


async def kategorien(sitzung: AsyncSession) -> list[Kategorie]:
    ergebnis = await sitzung.execute(
        select(Kategorie).order_by(Kategorie.reihenfolge, Kategorie.name)
    )
    return list(ergebnis.scalars())


async def kategorie(sitzung: AsyncSession, kategorie_id: uuid.UUID) -> Kategorie:
    zeile = await sitzung.get(Kategorie, kategorie_id)
    if zeile is None:
        raise KategorieUnbekannt(f"Es gibt keine Kategorie mit der Kennung {kategorie_id}")
    return zeile


async def kategorie_anlegen(sitzung: AsyncSession, daten: KategorieAnlegen) -> Kategorie:
    return await _anlegen(
        sitzung, Kategorie(**daten.model_dump()), "Eine Kategorie namens", daten.name
    )


async def kategorie_aendern(
    sitzung: AsyncSession, kategorie_id: uuid.UUID, daten: KategorieAendern
) -> Kategorie:
    zeile = await kategorie(sitzung, kategorie_id)
    _uebernehmen(zeile, daten, "name", "zaehlt_als_sparen", "reihenfolge")
    await sitzung.flush()
    return zeile


async def kategorie_loeschen(sitzung: AsyncSession, kategorie_id: uuid.UUID) -> None:
    # Ohne Hinweis loeschbar: die Posten bleiben stehen und landen unter
    # "Ohne Kategorie" (ON DELETE SET NULL in modelle.py).
    await sitzung.delete(await kategorie(sitzung, kategorie_id))
    await sitzung.flush()


# --------------------------------------------------------------- Posten


async def posten_alle(sitzung: AsyncSession) -> list[Posten]:
    ergebnis = await sitzung.execute(select(Posten).order_by(Posten.name))
    return list(ergebnis.scalars())


async def posten_eines(sitzung: AsyncSession, posten_id: uuid.UUID) -> Posten:
    zeile = await sitzung.get(Posten, posten_id)
    if zeile is None:
        raise PostenUnbekannt(f"Es gibt keinen Posten mit der Kennung {posten_id}")
    return zeile


async def _anteile_bauen(sitzung: AsyncSession, anteile: Sequence[object]) -> list[Anteil]:
    """Erst alle Personen pruefen, dann bauen.

    Die Fremdschluesselverletzung waere sonst ein 500 mit Datenbanktext -
    statt der Auskunft, welche Person es nicht gibt.
    """
    gebaut = []
    for eintrag in anteile:
        person_id: uuid.UUID = eintrag.person_id  # type: ignore[attr-defined]
        await person(sitzung, person_id)
        gebaut.append(Anteil(person_id=person_id, gewicht=eintrag.gewicht))  # type: ignore[attr-defined]
    return gebaut


async def posten_anlegen(sitzung: AsyncSession, daten: PostenAnlegen) -> Posten:
    await konto(sitzung, daten.konto_id)
    if daten.kategorie_id is not None:
        await kategorie(sitzung, daten.kategorie_id)

    zeile = Posten(
        **daten.model_dump(exclude={"anteile"}),
        anteile=await _anteile_bauen(sitzung, daten.anteile),
    )
    sitzung.add(zeile)
    await sitzung.flush()
    await sitzung.refresh(zeile)
    return zeile


async def posten_aendern(
    sitzung: AsyncSession, posten_id: uuid.UUID, daten: PostenAendern
) -> Posten:
    zeile = await posten_eines(sitzung, posten_id)
    _uebernehmen(
        zeile,
        daten,
        "name",
        "art",
        "betrag",
        "intervall_monate",
        "faelligkeitsmonat",
        "abbuchungstag",
        "variabel",
        "aktiv",
    )

    if daten.tag_loeschen:
        zeile.abbuchungstag = None
    if daten.konto_id is not None:
        await konto(sitzung, daten.konto_id)
        zeile.konto_id = daten.konto_id
    if daten.kategorie_loeschen:
        zeile.kategorie_id = None
    elif daten.kategorie_id is not None:
        await kategorie(sitzung, daten.kategorie_id)
        zeile.kategorie_id = daten.kategorie_id

    # Der Rhythmus kann sich geaendert haben - dann muss der Monat wieder in
    # die Form, in der schemas.PostenBasis ihn ablegt.
    zeile.faelligkeitsmonat = ((zeile.faelligkeitsmonat - 1) % zeile.intervall_monate) + 1

    if daten.anteile is not None:
        # Ersetzen statt abgleichen: eine Aufteilung ist eine Aussage als
        # Ganzes, kein Satz einzeln pflegbarer Zeilen.
        zeile.anteile.clear()
        await sitzung.flush()
        zeile.anteile.extend(await _anteile_bauen(sitzung, daten.anteile))

    await sitzung.flush()
    await sitzung.refresh(zeile)
    return zeile


async def posten_loeschen(sitzung: AsyncSession, posten_id: uuid.UUID) -> None:
    await sitzung.delete(await posten_eines(sitzung, posten_id))
    await sitzung.flush()


# ------------------------------------------------------------- Auswertung


async def sichten(
    sitzung: AsyncSession,
) -> tuple[list[PersonSicht], list[KontoSicht], list[KategorieSicht], list[PostenSicht]]:
    """Alles, was der Dienst zum Rechnen braucht - in einem Rutsch geholt.

    Vier Abfragen fuer den ganzen Haushalt. Das ist genau dann richtig, wenn
    ein Haushalt in Dutzenden und nicht in Millionen Zeilen zaehlt - und
    dieser tut das.
    """
    return (
        [PersonSicht(id=p.id, name=p.name) for p in await personen(sitzung)],
        [
            KontoSicht(id=k.id, name=k.name, art=k.art, inhaber_id=k.inhaber_id)
            for k in await konten(sitzung)
        ],
        [
            KategorieSicht(id=k.id, name=k.name, zaehlt_als_sparen=k.zaehlt_als_sparen)
            for k in await kategorien(sitzung)
        ],
        [
            PostenSicht(
                id=p.id,
                name=p.name,
                art=p.art,
                betrag=p.betrag,
                intervall_monate=p.intervall_monate,
                faelligkeitsmonat=p.faelligkeitsmonat,
                abbuchungstag=p.abbuchungstag,
                konto_id=p.konto_id,
                kategorie_id=p.kategorie_id,
                variabel=p.variabel,
                aktiv=p.aktiv,
                anteile=tuple((a.person_id, a.gewicht) for a in p.anteile),
            )
            for p in await posten_alle(sitzung)
        ],
    )
