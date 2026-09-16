-- Eigene Datenbank fuer die Integrationstests.
--
-- Die legen Tabellen an und loeschen sie wieder. Liefen sie auf "app",
-- waeren die Daten der laufenden Entwicklungsumgebung nach jedem Testlauf weg -
-- ein Ueberraschungseffekt, den niemand braucht.
CREATE DATABASE test OWNER app;
