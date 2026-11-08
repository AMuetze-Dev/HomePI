-- Staffelpilot: sechs Spalten an drei bestehenden Tabellen
--
-- Fuehrt von 0f3e724 auf bceb69c. Eingespielt auf dem Pi am 08.11.2026,
-- vor dem Ausrollen des Tischtennisturniers.
--
-- Vorgeschichte: Der Pi stand fuenfundzwanzig Commits zurueck. Darin steckten
-- die Staffelpilot-Aenderungen, die der Sportgerichtsfall, die Regeldateien
-- und die Auftragsansichten mitgebracht haben. Zwei davon waren neue
-- Tabellen - die legt "homepi schema anlegen" an. Sechs waren Spalten an
-- Tabellen, die es schon gab, und genau die kann create_all nicht
-- nachtragen. Ohne diese Datei haette jede Abfrage auf die betroffenen
-- Tabellen ins Leere gegriffen.
--
-- Die Spalten stehen im Modell alle als NOT NULL mit einem Vorgabewert auf
-- der Python-Seite. Deshalb hier: mit DEFAULT '' anlegen, damit die
-- vorhandenen Zeilen einen Wert bekommen, und den DEFAULT danach entfernen -
-- so steht in der Datenbank genau das, was create_all angelegt haette.
--
-- Einspielen (siehe README.md in diesem Ordner):
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-08-staffelpilot-spalten.sql

BEGIN;

-- staffelpilot_staffeln: das zustaendige Sportgericht und die DFBnet-Kennung
ALTER TABLE staffelpilot_staffeln
    ADD COLUMN IF NOT EXISTS sportgericht varchar(200) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_staffeln
    ALTER COLUMN sportgericht DROP DEFAULT;

ALTER TABLE staffelpilot_staffeln
    ADD COLUMN IF NOT EXISTS dfbnet_kennung varchar(20) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_staffeln
    ALTER COLUMN dfbnet_kennung DROP DEFAULT;
CREATE INDEX IF NOT EXISTS ix_staffelpilot_staffeln_dfbnet_kennung
    ON staffelpilot_staffeln (dfbnet_kennung);

-- staffelpilot_vorgaenge: was die Mail an den Sportrichter braucht
ALTER TABLE staffelpilot_vorgaenge
    ADD COLUMN IF NOT EXISTS dfbnet_aktenzeichen varchar(60) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_vorgaenge
    ALTER COLUMN dfbnet_aktenzeichen DROP DEFAULT;

ALTER TABLE staffelpilot_vorgaenge
    ADD COLUMN IF NOT EXISTS anlagen varchar(300) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_vorgaenge
    ALTER COLUMN anlagen DROP DEFAULT;

ALTER TABLE staffelpilot_vorgaenge
    ADD COLUMN IF NOT EXISTS hinweis varchar(500) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_vorgaenge
    ALTER COLUMN hinweis DROP DEFAULT;

-- staffelpilot_auftraege: worauf sich eine Fallprobe bezieht
ALTER TABLE staffelpilot_auftraege
    ADD COLUMN IF NOT EXISTS referenz varchar(120) NOT NULL DEFAULT '';
ALTER TABLE staffelpilot_auftraege
    ALTER COLUMN referenz DROP DEFAULT;

COMMIT;

-- Danach fehlen noch sechs Tabellen (staffelpilot_ansichten,
-- staffelpilot_regeldateien, tischtennis_gruppen, tischtennis_spiele,
-- tischtennis_teilnehmer, tischtennis_turniere). Die legt
-- "homepi schema anlegen" an - dafuer braucht es kein SQL.
