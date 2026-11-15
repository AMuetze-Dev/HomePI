-- Haushaltsbuch: Anlage aus dem Ueberschuss
--
-- Ein Posten kann sich seit diesem Stand auf einen ANTEIL festlegen statt auf
-- einen Betrag: Was nach allen Kosten uebrig bleibt, geht nach Gewichten in
-- die Depots. 10/50/30/10 sind vier Posten mit diesen vier Gewichten.
--
--   haushaltsbuch_personen.sockel        was liegen bleibt, bevor angelegt
--                                        wird - der Puffer auf dem Konto
--   haushaltsbuch_posten.anlage_gewicht  gesetzt heisst: kein fester Betrag,
--                                        sondern dieser Anteil am Ueberschuss
--
-- Gefahrlos: beide Spalten haben eine Vorgabe, und die Vorgabe ist genau das
-- bisherige Verhalten - Sockel null, kein Gewicht. Ein Haushalt ohne
-- Anlageposten rechnet sich danach auf den Cent wie vorher.
--
-- Einspielen (siehe README.md in diesem Ordner):
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-15-haushaltsbuch-anlage.sql

BEGIN;

-- DEFAULT nur zum Nachruesten: im Modell steht der Vorgabewert auf der
-- Python-Seite, in der Datenbank soll danach keiner stehen.
ALTER TABLE haushaltsbuch_personen
    ADD COLUMN IF NOT EXISTS sockel numeric(12, 2) NOT NULL DEFAULT 0;

ALTER TABLE haushaltsbuch_personen
    ALTER COLUMN sockel DROP DEFAULT;

-- Nullable: "kein Gewicht" heisst "fester Betrag", und das ist der Normalfall.
ALTER TABLE haushaltsbuch_posten
    ADD COLUMN IF NOT EXISTS anlage_gewicht integer;

COMMIT;
