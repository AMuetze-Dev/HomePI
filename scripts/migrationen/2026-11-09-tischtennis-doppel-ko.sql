-- Tischtennis: zweite Chance im KO-Raster, und Spiele verschieben
--
-- Wer einmal verliert, spielt im Verliererzweig weiter und ist erst nach der
-- zweiten Niederlage aus. Dafuer drei Spalten:
--
--   tischtennis_turniere.doppel_ko        der Schalter, je Turnier
--   tischtennis_spiele.heim_aus_verlierer  deutet der Verweis in
--   tischtennis_spiele.gast_aus_verlierer  heim_/gast_aus_spiel auf den
--                                          VERLIERER jenes Spiels?
--
-- Die beiden Flaggen sind der Grund, dass das Raster vollstaendig an der Wand
-- stehen kann, bevor gespielt wird: an einem Platz steht dann "Verlierer aus
-- Spiel 7" und nicht "Sieger aus Spiel 7".
--
-- Gefahrlos: alle drei haben eine Vorgabe, und false ist genau das bisherige
-- Verhalten. Laufende Turniere aendern sich dadurch nicht.
--
-- Einspielen (siehe README.md in diesem Ordner):
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-09-tischtennis-doppel-ko.sql

BEGIN;

ALTER TABLE tischtennis_turniere
    ADD COLUMN IF NOT EXISTS doppel_ko boolean NOT NULL DEFAULT false;

ALTER TABLE tischtennis_spiele
    ADD COLUMN IF NOT EXISTS heim_aus_verlierer boolean NOT NULL DEFAULT false;

ALTER TABLE tischtennis_spiele
    ADD COLUMN IF NOT EXISTS gast_aus_verlierer boolean NOT NULL DEFAULT false;

-- Und die Warteschlange als eigene Spalte, damit die Turnierleitung Spiele
-- schieben kann, ohne dass "Sieger aus Spiel 7" etwas anderes bedeutet:
-- nummer traegt die Verweise des Rasters, reihenfolge nur die Reihenfolge.
-- Fuer vorhandene Spiele sind beide gleich - das ist der Stand von bisher.
ALTER TABLE tischtennis_spiele
    ADD COLUMN IF NOT EXISTS reihenfolge integer NOT NULL DEFAULT 0;

UPDATE tischtennis_spiele SET reihenfolge = nummer WHERE reihenfolge = 0;

COMMIT;
