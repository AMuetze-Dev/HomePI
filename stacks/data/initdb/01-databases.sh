#!/bin/bash
# Laeuft EINMALIG beim ersten Start auf leerem Datenverzeichnis.
# Legt getrennte Datenbanken und User an - die App kommt nicht an HA-Daten und
# umgekehrt, und ein geleaktes App-Passwort kostet nicht gleich alles.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
    CREATE ROLE app WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
    CREATE DATABASE app OWNER app;

    CREATE ROLE ha WITH LOGIN PASSWORD '${HA_DB_PASSWORD}';
    CREATE DATABASE homeassistant OWNER ha;

    -- Public-Schema dichtmachen (Postgres 15+ Default ist schon restriktiv,
    -- das hier ist die explizite Variante)
    REVOKE ALL ON DATABASE app FROM PUBLIC;
    REVOKE ALL ON DATABASE homeassistant FROM PUBLIC;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname app <<-SQL
    -- haeufig gebraucht: UUIDs und JSONB-Indizes
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    CREATE EXTENSION IF NOT EXISTS "btree_gin";
SQL

echo "Datenbanken app + homeassistant angelegt."
