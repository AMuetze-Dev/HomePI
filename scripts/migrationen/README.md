# Migrationen

Hier liegt, was `homepi schema` nicht kann.

`homepi schema anlegen` ist ein Startwerkzeug und kein Migrationssystem: es
legt **fehlende Tabellen** an und ändert **keine vorhandene**. Kommt in einer
bestehenden Tabelle eine Spalte dazu, meldet es das und endet mit Fehler —
und dieselbe Prüfung hängt als `schema` im `/health`, setzt die Instanz auf
`degraded` und macht die Rauchtests rot. Begründet in
[../../docs/04-runbook.md](../../docs/04-runbook.md).

Genau dort, wo dieser Befehl aufhört, fängt dieser Ordner an: eine Datei je
Schemaänderung, von Hand geschrieben, auf dem Pi von Hand eingespielt.

## Warum von Hand und nicht Alembic

Weil es bisher drei solcher Änderungen gab und Alembic eine Maschinerie ist,
die selbst gewartet werden will. Sobald es regelmäßig wird, gehört Alembic
hierher — die Dateien hier sind dann die Vorgeschichte, die man beim
Einrichten als erste Revision festklopft.

Bis dahin gilt: **lieber eine Datei, die nur erzählt, was jemand getan hat,
als gar keine.** Ohne sie steht beim nächsten Mal jemand vor derselben
Handarbeit, ohne Vorlage und ohne zu wissen, was auf dem Pi schon lief.

## Eine Migration schreiben

Dateiname: `JJJJ-MM-TT-worum-es-geht.sql`. Das Datum ist das des Einspielens,
nicht das des Schreibens.

Im Kopf der Datei steht, von welchem Commit auf welchen sie führt und auf
welcher Anlage sie gelaufen ist. Das ist der eigentliche Zweck: wer später
in eine halb migrierte Datenbank sieht, muss erkennen können, was fehlt.

Drei Regeln, alle aus dem Betrieb und nicht aus einem Lehrbuch:

1. **`IF NOT EXISTS`, wo es geht.** Eine Migration wird öfter zweimal
   ausgeführt, als man denkt — nach einem abgebrochenen Deploy etwa.
2. **Alles in eine Transaktion.** Postgres kann DDL zurückrollen; eine zur
   Hälfte eingespielte Schemaänderung ist schlimmer als keine.
3. **Spalten so anlegen, wie `create_all` sie angelegt hätte.** Im Modell
   steht der Vorgabewert auf der Python-Seite, in der Datenbank also kein
   `DEFAULT`. Beim Nachrüsten braucht es ihn trotzdem kurz, damit die
   vorhandenen Zeilen einen Wert bekommen — danach wieder weg damit:

   ```sql
   ALTER TABLE t ADD COLUMN IF NOT EXISTS c varchar(200) NOT NULL DEFAULT '';
   ALTER TABLE t ALTER COLUMN c DROP DEFAULT;
   ```

   Sonst steht auf einer frisch aufgesetzten Anlage etwas anderes in der
   Datenbank als auf der gewachsenen, und der Unterschied fällt erst auf,
   wenn er weh tut.

## Einspielen

Auf dem Pi, vorher sichern:

```bash
cd ~/homelab
./scripts/backup.sh
docker exec -i postgres psql -U app -d app -v ON_ERROR_STOP=1 \
  -f - < scripts/migrationen/JJJJ-MM-TT-worum-es-geht.sql
```

`ON_ERROR_STOP=1` ist nicht schmückend: ohne es läuft `psql` nach einem
Fehler weiter und meldet am Ende Erfolg.

Danach die fehlenden **Tabellen** nachziehen — dafür ist das Werkzeug da:

```bash
docker exec gateway homepi schema anlegen --trocken
docker exec gateway homepi schema anlegen
docker exec gateway homepi schema zeigen
```

Erst der Trockenlauf, dann der Ernstfall.
