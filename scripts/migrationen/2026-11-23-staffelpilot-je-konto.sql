-- Staffelpilot: was bisher allen gehoerte, gehoert einem Konto
--
-- Fuehrt von fd658fb (Regelsatz je Staffelleiter) auf die Trennung der
-- Staffelleiter. Noch auf keiner Anlage gelaufen -- wer es einspielt, traegt
-- Datum und Anlage hier ein.
--
-- Vorgeschichte: Staffeln, Einstellungen, Saetze, DFBnet-Zugang und Auftraege
-- hatten bisher keinen Besitzer. Seit der Trennung sieht jeder nur, was seinem
-- Konto gehoert -- und was keinem gehoert, sieht niemand. Ohne diese Datei
-- waeren die alten Staffeln also nicht weg, aber unsichtbar.
--
-- Alles geht an EIN Konto, denn bis hierher gab es nur einen Staffelleiter.
-- Welches, findet die Datei selbst:
--
--   1. wer als Einziger Staffeln leitet (seit fd658fb),
--   2. sonst das einzige Konto mit einem Recht auf staffelpilot, das des
--      Pruefdienstes ausgenommen.
--
-- Ist das nicht eindeutig, passiert NICHTS, und die Meldung nennt die Konten,
-- die in Frage kommen. Dann sagt man es ihr (konto=...). Geraten wird nicht:
-- mit den Staffeln geht auch ein DFBnet-Zugang an dieses Konto.
--
-- Hat es an einer Stelle schon etwas Eigenes, gewinnt das Eigene. Einzige
-- Ausnahme: wer unter fd658fb eine Staffel uebernommen hatte, behaelt sie.
--
-- Dazu fallen zwei Bedingungen: Staffelname und Aktenzeichen waren je
-- Installation eindeutig. Jetzt hat jeder seine eigenen. Keine Spalte kommt
-- dazu oder faellt weg.
--
-- Reihenfolge: ERST die neuen Tabellen (das Gateway legt sie beim Start an,
-- oder `homepi schema anlegen`), dann diese Datei.
--
-- Einspielen, vorher sichern (siehe README.md in diesem Ordner):
--   docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
--     -f - < scripts/migrationen/2026-11-23-staffelpilot-je-konto.sql
--
-- Nur wenn noetig:
--   -v konto=<benutzername>   welches Konto es wird
--   -v dienst=<benutzername>  wie das Konto des Pruefdienstes heisst,
--                             wenn nicht "pruefdienst"
--
-- Danach kann das Passwort in `staffelpilot_zugang` nirgends mehr gelesen
-- werden; die Zeile wandert mit und verschwindet dort. Die uebrigen alten
-- Zeilen bleiben stehen, es liest sie nur niemand mehr.

\if :{?konto}
\else
\set konto ''
\endif
\if :{?dienst}
\else
\set dienst pruefdienst
\endif

BEGIN;

-- In eine Einstellung der Sitzung: in einem DO-Block gibt es keine
-- psql-Variablen.
SELECT set_config('homepi.konto', :'konto', true) AS konto,
       set_config('homepi.dienst', :'dienst', true) AS dienst;

ALTER TABLE staffelpilot_staffeln
    DROP CONSTRAINT IF EXISTS staffelpilot_staffeln_name_key;
ALTER TABLE staffelpilot_vorgaenge
    DROP CONSTRAINT IF EXISTS staffelpilot_vorgaenge_aktenzeichen_key;

DO $$
DECLARE
    genannt text := current_setting('homepi.konto');
    kandidaten uuid[];
    namen text;
    wer uuid;
BEGIN
    IF genannt <> '' THEN
        SELECT array_agg(id) INTO kandidaten FROM benutzer WHERE name = genannt;
        IF kandidaten IS NULL THEN
            RAISE EXCEPTION 'Es gibt kein Konto namens "%"', genannt;
        END IF;
    ELSE
        IF to_regclass('staffelpilot_staffelleitung') IS NOT NULL THEN
            SELECT array_agg(DISTINCT benutzer_id) INTO kandidaten
            FROM staffelpilot_staffelleitung;
        END IF;
        IF kandidaten IS NULL THEN
            SELECT array_agg(b.id) INTO kandidaten
            FROM benutzer b
            JOIN benutzer_rechte r ON r.benutzer_id = b.id
            WHERE r.artefakt = 'staffelpilot'
              AND b.name <> current_setting('homepi.dienst');
        END IF;
    END IF;

    IF kandidaten IS NULL THEN
        RAISE EXCEPTION 'Kein Konto hat ein Recht auf staffelpilot. Nichts geaendert.';
    END IF;
    SELECT string_agg(name, ', ' ORDER BY name) INTO namen
    FROM benutzer WHERE id = ANY (kandidaten);
    IF array_length(kandidaten, 1) > 1 THEN
        RAISE EXCEPTION 'Nicht eindeutig: %. Nichts geaendert. Noch einmal mit -v konto=<name>.',
            namen;
    END IF;
    wer := kandidaten[1];
    RAISE NOTICE 'Was keinem gehoert, geht an: %', namen;

    -- Wer unter fd658fb schon als Staffelleiter eingetragen war, behaelt sie.
    IF to_regclass('staffelpilot_staffelleitung') IS NOT NULL THEN
        INSERT INTO staffelpilot_staffelkonten (id, staffel_id, benutzer_id)
        SELECT gen_random_uuid(), l.staffel_id, l.benutzer_id
        FROM staffelpilot_staffelleitung l
        ON CONFLICT (staffel_id) DO NOTHING;
    END IF;

    -- Die uebrigen Staffeln
    INSERT INTO staffelpilot_staffelkonten (id, staffel_id, benutzer_id)
    SELECT gen_random_uuid(), s.id, wer
    FROM staffelpilot_staffeln s
    WHERE NOT EXISTS (
        SELECT 1 FROM staffelpilot_staffelkonten k WHERE k.staffel_id = s.id
    );

    -- Laeufe ohne Anforderer
    INSERT INTO staffelpilot_auftraggeber (id, auftrag_id, benutzer_id)
    SELECT gen_random_uuid(), a.id, wer
    FROM staffelpilot_auftraege a
    WHERE NOT EXISTS (
        SELECT 1 FROM staffelpilot_auftraggeber g WHERE g.auftrag_id = a.id
    );

    -- Einstellungen. Die mit Unterstrich sind Vermerke des Programms und
    -- bleiben, wo sie sind.
    INSERT INTO staffelpilot_kontoeinstellungen (id, benutzer_id, schluessel, wert)
    SELECT gen_random_uuid(), wer, e.schluessel, e.wert
    FROM staffelpilot_einstellungen e
    WHERE left(e.schluessel, 1) <> '_'
    ON CONFLICT (benutzer_id, schluessel) DO NOTHING;

    -- Saetze fuers Schreiben
    IF to_regclass('staffelpilot_regeltexte') IS NOT NULL THEN
        INSERT INTO staffelpilot_kontotexte (id, benutzer_id, schluessel, sachverhalt, hinweis)
        SELECT gen_random_uuid(), wer, t.schluessel, t.sachverhalt, t.hinweis
        FROM staffelpilot_regeltexte t
        ON CONFLICT (benutzer_id, schluessel) DO NOTHING;
    END IF;

    -- DFBnet-Zugang, verschluesselt wie er ist
    IF to_regclass('staffelpilot_zugang') IS NOT NULL THEN
        INSERT INTO staffelpilot_kontozugang (id, benutzer_id, benutzer, geheimnis)
        SELECT gen_random_uuid(), wer, z.benutzer, z.geheimnis
        FROM staffelpilot_zugang z
        ON CONFLICT (benutzer_id) DO NOTHING;
        DELETE FROM staffelpilot_zugang;
    END IF;
END $$;

COMMIT;
