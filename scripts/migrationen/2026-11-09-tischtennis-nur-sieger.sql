-- Tischtennis: Saetze und Punktgrenze fallen weg, phase wird breiter
--
-- Fuehrt von bceb69c auf den Umbau "nur noch der Sieger". Ein Ergebnis ist
-- seitdem ein Name und keine Zahlenreihe: eingetragen wird, wer gewonnen
-- hat, und bei Punktgleichheit entscheidet ein Spiel statt einer Differenz.
--
-- Damit verlieren zwei Spalten ihren Sinn:
--   tischtennis_turniere.punkte_bis  - diente nur der Satzpruefung
--   tischtennis_spiele.saetze        - das Zahlenfeld selbst
--
-- Und eine wird zu eng: phase traegt jetzt auch "entscheidung" (12 Zeichen).
--
-- Gefahrlos, weil auf dem Pi noch kein Turnier gespielt wurde - die vier
-- Tabellen sind leer. Waeren sie es nicht, gehoerte vor das DROP ein Blick
-- darauf, ob jemand die Satzstaende noch braucht.
--
-- Einspielen (siehe README.md in diesem Ordner):
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-09-tischtennis-nur-sieger.sql

BEGIN;

ALTER TABLE tischtennis_spiele
    ALTER COLUMN phase TYPE varchar(20);

ALTER TABLE tischtennis_spiele
    DROP COLUMN IF EXISTS saetze;

ALTER TABLE tischtennis_turniere
    DROP COLUMN IF EXISTS punkte_bis;

COMMIT;
