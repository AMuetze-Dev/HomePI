SHELL   := /bin/bash
ROOT    := $(shell pwd)
ENVFILE := $(ROOT)/.env
DC       = docker compose --env-file $(ENVFILE)
STACKS  := core dns data home apps

# Nur die wenigen Werte lesen, die make selbst braucht. Ein "include .env"
# waere anfaellig: Passwoerter mit $ oder # bringen make durcheinander.
getenv    = $(shell sed -n 's/^$(1)=//p' $(ENVFILE) | head -1 | tr -d "'\"")
PI_IP    := $(call getenv,PI_IP)
DOMAIN   := $(call getenv,DOMAIN)
APP_PW   := $(call getenv,APP_DB_PASSWORD)

.DEFAULT_GOAL := help

## help: diese Uebersicht
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  make /' | column -t -s ':'

# ---------------------------------------------------------------- Lifecycle

## up: alle Stacks starten (Reihenfolge beachtet Abhaengigkeiten)
up: render up-core up-dns up-data up-home up-apps

## up-core: Traefik, Dozzle, Uptime-Kuma
up-core: render
	$(DC) -f stacks/core/docker-compose.yml up -d

## up-dns: Pi-hole
up-dns:
	$(DC) -f stacks/dns/docker-compose.yml up -d

## up-data: Postgres, pgAdmin, Redis
up-data:
	$(DC) -f stacks/data/docker-compose.yml up -d

## up-home: Home Assistant, Mosquitto
up-home:
	$(DC) -f stacks/home/docker-compose.yml up -d

## up-apps: Python-Backend + React-Frontend
up-apps:
	$(DC) -f stacks/apps/docker-compose.yml up -d

## down: alles stoppen (Daten bleiben erhalten)
down:
	@for s in $(STACKS); do $(DC) -f stacks/$$s/docker-compose.yml down; done

## render: core/dynamic/*.tmpl mit Werten aus .env rendern
render:
	@./scripts/40-render-config.sh

# ---------------------------------------------------------------- Deployment

## deploy-apps: neue Images ziehen und Anwendungs-Container ersetzen
deploy-apps:
	$(DC) -f stacks/apps/docker-compose.yml pull
	$(DC) -f stacks/apps/docker-compose.yml up -d --remove-orphans
	@docker image prune -f

## pull: Images aller Stacks aktualisieren (ohne Neustart)
pull:
	@for s in $(STACKS); do $(DC) -f stacks/$$s/docker-compose.yml pull; done

## update: Backup, dann alle Images aktualisieren und neu starten
update: backup pull up
	@docker image prune -af

# ---------------------------------------------------------------- Betrieb

## ps: Zustand aller Container
ps:
	@docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

## logs: Logs eines Containers folgen, z.B. make logs C=traefik
logs:
	@docker logs -f --tail 100 $(C)

## stats: RAM- und CPU-Verbrauch
stats:
	@docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

## psql: psql-Shell in der App-Datenbank
psql:
	@docker exec -it -e PGPASSWORD=app homepi-dev-postgres psql -U app -d app

## pg-tunnel: Befehl fuer den SSH-Tunnel vom Desktop ausgeben
pg-tunnel:
	@echo "Auf dem Desktop ausfuehren, dann auf localhost:5432 verbinden:"
	@echo "  ssh -N -L 5432:127.0.0.1:5432 $(USER)@$(PI_IP)"

## backup: Postgres-Dump + Konfigurationen sichern
backup:
	@./scripts/backup.sh

## check: NVMe, PCIe-Geschwindigkeit, Temperatur, Throttling
check:
	@./scripts/check-nvme.sh

## verify: Konfiguration aller Stacks validieren, ohne etwas zu starten
verify:
	@for s in $(STACKS); do \
		echo "--- $$s"; \
		$(DC) -f stacks/$$s/docker-compose.yml config -q && echo "    ok"; \
	done

## cert: Status des Wildcard-Zertifikats anzeigen
cert:
	@echo | openssl s_client -connect $(PI_IP):443 -servername traefik.$(DOMAIN) 2>/dev/null \
		| openssl x509 -noout -subject -issuer -dates

# ---------------------------------------------------------------- Entwicklung
WEB    := services/web
# Die Integrationstests laufen gegen die Datenbank der Dev-Umgebung -
# aber gegen "test", nicht gegen "app": sie legen Tabellen an und loeschen sie wieder.
# Ueber HOMEPI_TEST_DATABASE_URL, nicht ueber DATABASE_URL: so kann daneben
# die Arbeitsdatenbank gesetzt sein, ohne dass ein Testlauf sie trifft.
#
# "test" ist dabei nur die Vorlage. Das pytest-Plugin legt beim Start jedes
# Laufs eine eigene Datenbank an ("<projekt>_test") und wirft sie am Ende
# wieder weg - damit sieht kein Lauf, was der vorige hinterlassen hat.
TESTDB := postgresql+asyncpg://app:app@127.0.0.1:15432/test

## test: alles pruefen, was die CI auch prueft
test: test-infra test-python test-web

## lint-ci: GitHub-Workflows pruefen, bevor sie einen Lauf kosten
lint-ci:
	docker run --rm -v "$(CURDIR):/repo" -w /repo rhysd/actionlint:latest -color

## test-infra: Shell-Skripte und Compose-Dateien validieren
test-infra: render verify lint-ci
	@shellcheck --severity=warning scripts/*.sh stacks/data/initdb/*.sh 		&& echo "shellcheck ok"

## test-python: Format, Lint, Typen und Tests aller drei Python-Projekte
test-python:
	@for p in packages/homepi-core modules/geraete modules/staffelpilot modules/verwaltung services/gateway; do 		echo "=== $$p"; 		( cd $$p 		  && uv run ruff format --check . 		  && uv run ruff check . 		  && uv run mypy 		  && HOMEPI_TEST_DATABASE_URL=$(TESTDB) uv run pytest -m 'not smoke' --cov --cov-report=term ) 		|| exit 1; 	done

## test-web: Format, Lint, Typen und Tests des Frontends
test-web:
	cd $(WEB) && npx prettier --check src e2e *.ts *.js
	cd $(WEB) && npx eslint .
	cd $(WEB) && npm run typecheck
	cd $(WEB) && npm run test:coverage

## tdd-api: pytest im Watch-Modus (Verzeichnis ueber P=..., Standard: geraete)
tdd-api:
	cd $(or $(P),modules/geraete) && uv run ptw . --now

## tdd-web: vitest im Watch-Modus; mit N=<modul> nur dessen Oberflaeche
tdd-web:
	cd $(WEB) && npm run test:watch -- $(if $(N),src/module/$(N),)

## modul: zeigt beide Haelften eines Artefakts, z.B. make modul N=geraete
modul:
	@test -n "$(N)" || { echo "Aufruf: make modul N=<name>"; exit 1; }
	@echo "Backend   modules/$(N)/"
	@ls modules/$(N)/src/homepi_*/ 2>/dev/null | sed 's/^/            /' || echo "            fehlt"
	@echo "Frontend  $(WEB)/src/module/$(N)/"
	@ls $(WEB)/src/module/$(N)/ 2>/dev/null | sed 's/^/            /' || echo "            keine eigene Oberflaeche"
	@echo "Register  $$(grep -c '\"$(N)\"' $(WEB)/src/module/register.ts) Eintrag/Eintraege"

## test-modul: ein Artefakt vollstaendig pruefen, beide Haelften
test-modul:
	@test -n "$(N)" || { echo "Aufruf: make test-modul N=<name>"; exit 1; }
	cd modules/$(N) && uv run ruff format --check .
	cd modules/$(N) && uv run ruff check .
	cd modules/$(N) && uv run mypy
	cd modules/$(N) && HOMEPI_TEST_DATABASE_URL=$(TESTDB) uv run pytest -m 'not smoke' --cov
	@test -d $(WEB)/src/module/$(N) || { echo "(keine eigene Oberflaeche)"; exit 0; }
	cd $(WEB) && npx vitest run src/module/$(N)

## fmt: Quellcode formatieren und automatisch behebbare Funde beheben
fmt:
	@for p in packages/homepi-core modules/geraete modules/staffelpilot modules/verwaltung services/gateway; do 		( cd $$p && uv run ruff format . && uv run ruff check --fix . ); 	done
	cd $(WEB) && npm run format && npm run lint:fix

## install: Entwicklungsabhaengigkeiten aller Projekte einrichten
install:
	@for p in packages/homepi-core modules/geraete modules/staffelpilot modules/verwaltung services/gateway; do 		echo "=== $$p"; ( cd $$p && uv sync --all-extras ) || exit 1; 	done
	cd $(WEB) && npm ci

# ---------------------------------------------------------------- Entwicklung (lokal)
DEV := docker compose -f compose.dev.yml

## artefakt: neues Artefakt anlegen, z.B. make artefakt N=messwerte
artefakt:
	@test -n "$(N)" || { echo "Aufruf: make artefakt N=<name> [T=\"Titel\"]"; exit 1; }
	uv run --project packages/homepi-core homepi new $(N) $(if $(T),--titel "$(T)",)

## dev: lokale Umgebung starten; mit N=<modul> nur dieses Artefakt laden
dev:
	HOMEPI_MODULE=$(N) $(DEV) up -d --build
	@test -z "$(N)" || echo "  Nur geladen: $(N)"
	@echo
	@echo "  Frontend  http://localhost:5173"
	@echo "  API       http://localhost:18000/docs"
	@echo "  Postgres  localhost:15432  (app/app/app, Testdatenbank: test)"

## dev-stop: lokale Umgebung stoppen (Daten bleiben)
dev-stop:
	$(DEV) down

## dev-reset: lokale Umgebung samt Datenbank wegwerfen
dev-reset:
	$(DEV) down -v

## dev-logs: Logs der lokalen Umgebung folgen
dev-logs:
	$(DEV) logs -f

## dev-ps: Zustand der lokalen Container
dev-ps:
	$(DEV) ps

## e2e: Oberflaechentests gegen eine EIGENE, frische Umgebung
#
# Eigene Datenbank, eigene Ports, eigener Projektname: die Tests legen Konten
# an und loeschen sie wieder, und das darf niemals die Umgebung treffen, in
# der gerade jemand arbeitet. Am Ende wird sie samt Volume weggeworfen, damit
# der naechste Lauf wieder bei der Ersteinrichtung beginnt.
E2E_WEB_PORT ?= 5273
E2E_API_PORT ?= 18100
E2E_DB_PORT ?= 15532
E2E := DEV_PROJEKT=homepi-e2e DEV_WEB_PORT=$(E2E_WEB_PORT) DEV_API_PORT=$(E2E_API_PORT) DEV_DB_PORT=$(E2E_DB_PORT) docker compose -f compose.dev.yml

e2e: e2e-hoch
	@cd services/web && E2E_URL=http://127.0.0.1:$(E2E_WEB_PORT) 	  E2E_EINRICHTUNGSTOKEN="$$(cd ../.. && $(MAKE) --no-print-directory e2e-token)" 	  npm run test:e2e; 	  ergebnis=$$?; 	  cd ../.. && $(MAKE) --no-print-directory e2e-runter; 	  exit $$ergebnis

## e2e-hoch: die Testumgebung starten, mit frischer Datenbank
e2e-hoch:
	-@$(E2E) down -v >/dev/null 2>&1
	$(E2E) up -d --build --wait --wait-timeout 300

## e2e-token: Einrichtungstoken der Testumgebung ausgeben
e2e-token:
	@$(E2E) logs gateway 2>/dev/null | grep "Einrichtungstoken:" | tail -1 | sed 's/.*Einrichtungstoken:[[:space:]]*//' | tr -d '
'

## e2e-runter: die Testumgebung samt Datenbank wegwerfen
e2e-runter:
	$(E2E) down -v

## smoke: Rauchtests gegen die laufende lokale Umgebung
# Die Tests, die GET /module auswerten, brauchen ein Konto - ohne Anmeldung ist
# die Liste berechtigterweise leer. Setze HOMEPI_SMOKE_BENUTZER und
# HOMEPI_SMOKE_PASSWORT, sonst ueberspringen sie sich.
smoke:
	cd services/gateway && uv run pytest -m smoke -v

.PHONY: artefakt backup cert check deploy-apps dev dev-logs dev-ps dev-reset dev-stop down e2e e2e-hoch e2e-runter e2e-token fmt help install lint-ci logs modul pg-tunnel ps psql pull render smoke stats tdd-api tdd-web test test-infra test-modul test-python test-web up up-apps up-core up-data up-dns up-home update verify
