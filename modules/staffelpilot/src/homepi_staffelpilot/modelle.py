"""Die Tabellen. Das Gateway legt sie beim Start an (DB_SCHEMA_ANLEGEN)."""

from __future__ import annotations

import datetime as dt
import uuid

from homepi_core import Base, ZeitstempelMixin
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Staffel(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_staffeln"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    altersklasse: Mapped[str] = mapped_column(String(20), nullable=False)
    # Die Spielklasse, wie sie in DFBnet heisst -- "1.Kreisklasse". Sie ist
    # nicht eindeutig: dieselbe Klasse gibt es fuer Herren und fuer Ue35.
    spielklasse: Mapped[str] = mapped_column(String(120), nullable=False)
    saison: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    # Wie viele Spieltage die Saison hat. 0 heisst *nicht bekannt* und nicht
    # "keine": an den letzten vier Spieltagen faellt die U23-Ausnahme nach
    # Paragraf 68 (2) c) weg, und ohne diese Zahl laesst sie sich nicht
    # aufheben. Die Regel sagt das dann selbst, statt still weiterzurechnen.
    spieltage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    spiele: Mapped[list[Spielbericht]] = relationship(
        back_populates="staffel", cascade="all, delete-orphan"
    )


class Spielbericht(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_spielberichte"
    # Dieselbe DFBnet-Kennung darf in zwei Staffeln vorkommen, in einer nicht
    # zweimal. Geprueft von der Datenbank, nicht vom Code: eine Vorabpruefung
    # waere ein Rennen zwischen zwei gleichzeitigen Importen.
    __table_args__ = (UniqueConstraint("staffel_id", "dfbnet_id", name="uq_spiel_je_staffel"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dfbnet_id: Mapped[str] = mapped_column(String(120), nullable=False)
    datum: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    heim: Mapped[str] = mapped_column(String(120), nullable=False)
    gast: Mapped[str] = mapped_column(String(120), nullable=False)
    ergebnis: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    # ── Was auf dem Mahnungsformular steht ────────────────────────────────
    #
    # Der Vordruck des Verbandes verlangt mehr als Datum und Paarung:
    # Spielnummer, Anstoss, Spielort, Spieltag, Mannschaftsart, Wettkampftyp.
    # Sie stehen im Spielbericht bei DFBnet und nirgends sonst -- ohne sie
    # muesste der Staffelleiter sie von Hand nachtragen, auf einem Schreiben,
    # das an einen Verein geht.
    #
    # Leer heisst: nicht bekannt. Das Formular nennt die fehlenden Felder,
    # statt sie mit einem Platzhalter zu fuellen -- ein Schriftstueck mit
    # erfundenen Angaben ist schlimmer als eine Luecke.

    #: Die Nummer, unter der DFBnet das Spiel fuehrt ("633203177"). Nicht
    #: dieselbe wie `dfbnet_id`: die ist die Kennung des Verweises.
    spielnummer: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    anstoss: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    spielort: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    spieltag: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    mannschaftsart: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    #: "Meisterschaft", "Kreispokal Herren" -- wie DFBnet ihn nennt.
    wettbewerb: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    abgehakt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abgehakt_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    staffel: Mapped[Staffel] = relationship(back_populates="spiele")
    befunde: Mapped[list[Befund]] = relationship(
        back_populates="spiel", cascade="all, delete-orphan", lazy="selectin"
    )
    # Ohne `back_populates`: eine Karte zeigt auf ihr Spiel ueber die
    # Fremdschluesselspalte und braucht keinen Rueckweg. Mit `delete-orphan`,
    # damit ein erneuter Import die Karten desselben Spiels ersetzt statt sie
    # zu verdoppeln.
    karten: Mapped[list[Karte]] = relationship(cascade="all, delete-orphan")


class Karte(Base, ZeitstempelMixin):
    """Eine Karte aus einem Spielbericht.

    Gespeichert, obwohl sie kein Befund ist: § 58 SpO rechnet ueber die
    Saison -- die fuenfte Verwarnung sperrt, und nach jeder Sperre faengt der
    Zaehler von vorn an. Nichts davon steht im einzelnen Spielbericht.

    Ohne diese Tabelle meldet die Regel "Verwarnungszaehler nicht verfuegbar"
    -- einmal je Karte. Am ersten echten Lauf waren das 78 von 108 Befunden,
    und die Warteschlange war nicht mehr zu lesen.
    """

    __tablename__ = "staffelpilot_karten"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"), index=True
    )
    spielbericht_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_spielberichte.id", ondelete="CASCADE"),
        index=True,
    )
    #: Der Spieltag. Danach wird gezaehlt: "seit der letzten Sperre".
    datum: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: Der Wettbewerb, wie DFBnet ihn nennt. Pokal und Meisterschaft werden
    #: nach § 58 (2) **getrennt** gezaehlt -- deshalb steht er an der Karte
    #: und nicht nur am Spiel.
    wettbewerb: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    person: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    #: Die Passnummer ist der Schluessel ueber Vereine und Mannschaften
    #: hinweg. Fehlt sie, laesst sich nichts zaehlen -- dann sagt die Regel
    #: das auch.
    pass_nr: Mapped[str] = mapped_column(String(40), nullable=False, default="", index=True)
    #: "Gelbe Karte", "Gelb-Rote Karte", "Rote Karte" -- die Schreibweise von
    #: DFBnet, nicht umgedeutet.
    art: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    minute: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    mannschaft: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class Befund(Base, ZeitstempelMixin):
    __tablename__ = "staffelpilot_befunde"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spiel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_spielberichte.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    regel: Mapped[str] = mapped_column(String(120), nullable=False)
    schwere: Mapped[str] = mapped_column(String(20), nullable=False)
    titel: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    person: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mannschaft: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Wohin der Befund fuehrt, wenn er stehen bleibt. Kommt vom Prueflauf:
    # dieses Artefakt kennt die Spielordnung nicht.
    weg: Mapped[str] = mapped_column(String(20), nullable=False, default="kein")
    entscheidung: Mapped[str] = mapped_column(String(20), nullable=False, default="offen")
    grund: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    entschieden_am: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Die Reihenfolge, in der der Prueflauf sie gemeldet hat. Ohne sie ist die
    # Reihenfolge innerhalb einer Schwere zufaellig und springt bei jedem Laden.
    rang: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    spiel: Mapped[Spielbericht] = relationship(back_populates="befunde")


class Einstellung(Base, ZeitstempelMixin):
    """Was fuer die ganze Installation gilt, als Schluessel und Wert.

    Eine Zeile je Schluessel und keine Tabelle mit festen Spalten: eine
    Einstellung dazuzunehmen soll keine Wanderung der Datenbank kosten.
    Gelesen wird sie ueber `dienst.einstellungen_aus`, das aus den rohen
    Zeichenketten geprueft Werte macht -- die Pruefung steht damit an einer
    Stelle und nicht bei jedem Aufrufer.
    """

    __tablename__ = "staffelpilot_einstellungen"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schluessel: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    wert: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class Mannschaft(Base, ZeitstempelMixin):
    """Eine Mannschaft einer Staffel, mit den hoeherklassigen dahinter.

    Welche Mannschaft eines Vereins ueber welcher steht, liefert DFBnet nicht
    mit -- es wird aus dem Namenszusatz geraten. Ein falscher Schluss faellt
    nicht laut auf: er aendert still, wessen Einsaetze als Stammspieler
    zaehlen. Deshalb steht die Zuordnung hier und ist von Hand korrigierbar.
    """

    __tablename__ = "staffelpilot_mannschaften"
    __table_args__ = (UniqueConstraint("staffel_id", "name", name="uq_mannschaft_je_staffel"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staffel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    verein: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    nummer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ist_sg: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Namen der hoeherklassigen Mannschaften desselben Vereins.
    hoehere: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: True, sobald jemand die Zuordnung von Hand bestaetigt oder geaendert
    #: hat. Danach ueberschreibt kein Ratevorgang sie mehr.
    bestaetigt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Vorgang(Base, ZeitstempelMixin):
    """Was aus einem Befund nach aussen geht: Mahnung oder Sportgerichtsfall.

    **Hier wird nichts versendet.** Der Vorgang ist ein Entwurf mit einem
    Text, der aus einer Vorlage entsteht -- Wort fuer Wort vorhersagbar, ohne
    erzeugte Sprache. Wer ihn abschickt, ist ein Mensch, und er tut es in
    seinem Mailprogramm.
    """

    __tablename__ = "staffelpilot_vorgaenge"
    # Ein Befund traegt genau einen Vorgang. Zwei Mahnungen zu demselben
    # Vorfall waeren fuer den Verein nicht unterscheidbar.
    __table_args__ = (UniqueConstraint("befund_id", name="uq_vorgang_je_befund"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    befund_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_befunde.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Fortlaufend je Saison, vergeben beim Anlegen. Steht auf jedem Schreiben.
    aktenzeichen: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    verein: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    betroffener: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    grund: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    empfaenger: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    betreff: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    zustand: Mapped[str] = mapped_column(String(20), nullable=False, default="entwurf")
    #: Wann ein Mensch gesagt hat, dass er es abgeschickt hat. Nicht, wann das
    #: Programm etwas gesendet haette -- das tut es nie.
    versandt_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    befund: Mapped[Befund] = relationship()


class Regel(Base, ZeitstempelMixin):
    """Was der Pruefdienst prueft, und ob der Staffelleiter das will.

    Der Katalog kommt von aussen: dieses Artefakt kennt die Spielordnung
    nicht. Was es haelt, ist die eine Entscheidung, die dem Staffelleiter
    gehoert -- `aktiv`. Ein erneutes Einspielen des Katalogs laesst sie
    stehen, sonst waere jedes Abschalten bis zum naechsten Start haltbar.
    """

    __tablename__ = "staffelpilot_regeln"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Die technische Kennung, wie sie auch am Befund steht.
    schluessel: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    beschreibung: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    schwere: Mapped[str] = mapped_column(String(20), nullable=False, default="hinweis")
    weg: Mapped[str] = mapped_column(String(20), nullable=False, default="kein")
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Auftrag(Base, ZeitstempelMixin):
    """Ein langlaufender Browservorgang - als Datensatz, nicht als Thread.

    Der Prueflauf faehrt minutenlang einen echten Browser. Er laeuft deshalb
    in einem eigenen Dienst (docs/06-artefakte.md), und was hier steht, ist
    der Auftrag dafuer: wer ihn angefordert hat, wie weit er ist, was
    herausgekommen ist.

    Ein Datensatz und kein laufender Prozess - das ist der ganze Punkt: das
    Gateway darf neu starten, ohne dass der Staffelleiter vor einer Anzeige
    steht, die nie wieder weiterzaehlt.
    """

    __tablename__ = "staffelpilot_auftraege"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Leer heisst: alle aktiven Staffeln.
    staffel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_staffeln.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    zustand: Mapped[str] = mapped_column(
        String(20), nullable=False, default="angefordert", index=True
    )
    #: Was er gerade tut, in einem Satz. Ein Wartekreisel sagt nichts.
    schritt: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    fortschritt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gepruefte: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    befunde: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Woran er gescheitert ist. Leer, solange nichts schiefging.
    meldung: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    #: Was er mitgeschrieben hat: [{"zeit": ..., "text": ...}].
    protokoll: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    gestartet_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    beendet_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Uebertragung(Base, ZeitstempelMixin):
    """Was nach DFBnet hinaus soll - eine Zeile je Vorgang.

    Getrennt von :class:`Auftrag`, weil es eine andere Sache ist: ein Auftrag
    ist ein langer Lauf mit Fortschritt, eine Uebertragung ist ein kurzer
    Handgriff, der klappt oder scheitert und dann wiederholt wird.

    **Hier wird nichts uebertragen.** Die Zeile sagt nur, was zu tun waere.
    Getan wird es vom DFBnet-Dienst, und der laeuft nur, wenn die Uebertragung
    nicht pausiert ist -- und auf einer frischen Installation ist sie das.
    """

    __tablename__ = "staffelpilot_uebertragungen"
    # Idempotent ueber den natuerlichen Schluessel: abhaken, Haken entfernen
    # und wieder abhaken darf keine zwei Freigaben erzeugen.
    __table_args__ = (UniqueConstraint("aktion", "referenz", name="uq_uebertragung"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aktion: Mapped[str] = mapped_column(String(30), nullable=False)
    #: Worauf sie sich bezieht - die Kennung des Spielberichts oder des
    #: Vorgangs, als Text. Zwei Vorgaenge an einem Bericht sind zwei Zeilen.
    referenz: Mapped[str] = mapped_column(String(120), nullable=False)
    spiel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staffelpilot_spielberichte.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    zustand: Mapped[str] = mapped_column(String(20), nullable=False, default="offen", index=True)
    versuche: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    letzter_fehler: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    erledigt_am: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Zugang(Base, ZeitstempelMixin):
    """Die Anmeldedaten fuer DFBnet.

    Der Benutzername steht im Klartext -- er steht ohnehin in jedem Protokoll
    des Pruefdienstes. Das Passwort liegt **verschluesselt**, mit einem
    Schluessel, der nicht in der Datenbank steht, sondern in der Umgebung
    (``STAFFELPILOT_SCHLUESSEL``). Ein Datenbankabzug allein ist damit
    wertlos.

    Der Preis dafuer steht in der README: wer den Schluessel verliert, muss
    die Zugangsdaten neu eintragen. Das ist der richtige Preis -- die
    Alternative waere ein Passwort, das jeder lesen kann, der einmal an eine
    Sicherung kommt.
    """

    __tablename__ = "staffelpilot_zugang"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Es gibt genau einen DFBnet-Zugang je Installation.
    dienst: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, default="dfbnet")
    benutzer: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Der Fernet-Token. Nie im Klartext, nie in einer Antwort.
    geheimnis: Mapped[str] = mapped_column(Text, nullable=False)
