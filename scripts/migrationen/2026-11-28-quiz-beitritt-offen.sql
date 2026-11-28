-- Quiz: die Leitung kann den Beitritt zu einer Runde schliessen.
--
-- Neue Spalte an einer Tabelle, die schon laeuft - das kann
-- `homepi schema anlegen` nicht. Die neuen Tabellen dieses Standes
-- (quiz_medien, quiz_teams, quiz_teammitglieder) legt es dagegen selbst an.
--
-- Reihenfolge auf dem Pi: erst diese Datei, dann `homepi schema anlegen`.
--
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-28-quiz-beitritt-offen.sql

BEGIN;

ALTER TABLE quiz_runden
    ADD COLUMN IF NOT EXISTS beitritt_offen boolean NOT NULL DEFAULT true;

COMMIT;
