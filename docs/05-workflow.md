# 05 — Arbeitsweise: Branches, TDD, CI/CD

## Branch-Modell

```
main        ──○────────────────────○──────────▶   ruht, bis veröffentlicht wird
               ╲                  ╱
develop     ────●───────●────────●────────────▶   Integration UND was auf dem Pi läuft
                 ╲     ╱ ╲      ╱
feature/*         ●───●   ●────●                  eine Aufgabe, ein Branch
```

| Branch            | Rolle                                                                                        | Wer merged hinein     |
| ----------------- | -------------------------------------------------------------------------------------------- | --------------------- |
| `develop`         | Integration. Standardziel für Feature-Branches. **Baut zurzeit auch die Images für den Pi.** | `feature/*`, per PR   |
| `main`            | Release. Ruht, solange nichts veröffentlicht wird.                                           | nur `develop`, per PR |
| `feature/<thema>` | eine Aufgabe                                                                                 | —                     |
| `fix/<thema>`     | Fehlerbehebung                                                                               | —                     |
| `chore/<thema>`   | Abhängigkeiten, CI, Aufräumarbeiten                                                          | —                     |

**Solange nichts veröffentlicht wird, ist `develop` der Zweig, der auf dem Pi
läuft.** Ein Push dorthin baut die arm64-Images und legt sie als
`ghcr.io/…/homepi-gateway:develop` in der GHCR ab; `.env` auf dem Pi zeigt auf
ebendiesen Tag.

`:latest` bleibt dabei `main` vorbehalten. Das ist Absicht: sobald es wieder
Releases gibt, soll der Tag nicht stillschweigend etwas anderes bedeuten als
vorher. Wer umstellt, ändert zwei Zeilen in der `.env` und startet
`make deploy-apps`.

### Eine Aufgabe von Anfang bis Ende

```bash
git checkout develop && git pull
git checkout -b feature/monatsplan

# ... rot, grün, aufräumen (siehe unten) ...

make test                       # was die CI auch prüft
git add -p && git commit
git push -u origin feature/monatsplan
gh pr create --base develop --fill
```

Nach dem Merge:

```bash
git checkout develop && git pull && git branch -d feature/monatsplan
```

### Auf den Pi bringen

Zurzeit genügt der Merge nach `develop` — der Push baut die Images:

```bash
cd ~/homelab && git pull && make deploy-apps
```

Sobald veröffentlicht werden soll, kommt der Release-Zweig dazu:

```bash
git checkout main && git pull
git merge --no-ff develop
git tag -a v0.2.0 -m "Geräteliste"
git push origin main --tags
```

Dann tragen `GATEWAY_IMAGE` und `WEB_IMAGE` in der `.env` auf dem Pi wieder
`:latest`.

## Die TDD-Schleife

```bash
make tdd-api      # pytest, startet bei jeder Dateiänderung neu
make tdd-web      # vitest im Watch-Modus
```

Beide laufen in **unter einer Sekunde**, weil sie nur Unit-Tests ausführen —
Integrationstests sind per Marker ausgeschlossen und die Coverage-Schwelle greift
bewusst nicht. Eine Schleife, die fünf Sekunden braucht, wird nicht benutzt.

**Rot → Grün → Aufräumen:**

1. **Rot.** Schreib den Test für das Verhalten, das du willst. Lass ihn laufen und
   sieh zu, wie er fehlschlägt. Ein Test, den du nie hast scheitern sehen, prüft
   möglicherweise gar nichts.
2. **Grün.** Die einfachste Änderung, die den Test bestehen lässt. Nicht die
   eleganteste — die einfachste.
3. **Aufräumen.** Jetzt umbauen, mit dem Test als Netz. Die Tests bleiben unverändert.

Commit am Ende jedes vollständigen Zyklus, nicht nach jedem Schritt.

### Warum die Logik von I/O getrennt ist

Schau dir [`health.py`](../packages/homepi-core/src/homepi_core/health.py) an:
`evaluate` ist eine reine Funktion — keine Datenbank, kein Eventloop, keine
Fixtures. Deshalb sind ihre Tests in Millisekunden durch.

Das ist kein Zufall, sondern die Bedingung dafür, dass TDD funktioniert. Sobald die
Entscheidungslogik in einem Handler steckt, der nebenbei die Datenbank befragt, brauchst
du für jeden Testfall eine Datenbank — und die Schleife ist zu langsam zum Denken.

Die Faustregel: **Entscheidungen sind rein, Seiteneffekte sind dumm.** `db.ping()` enthält
keine einzige Fallunterscheidung, `evaluate()` kein einziges `await`.

### Testarten

| Ort                                  | Was                                                       | Wann                   |
| ------------------------------------ | --------------------------------------------------------- | ---------------------- |
| `modules/<name>/tests/unit/`         | Logik, Endpunkte mit ersetzten Abhängigkeiten             | bei jeder Änderung     |
| `modules/<name>/tests/integration/`  | echtes Postgres — markiert mit `@pytest.mark.integration` | `make test` und in der CI |
| `packages/homepi-core/tests/`        | das Grundgerüst, das alle Artefakte erben                 | bei jeder Änderung     |
| `services/web/src/**/*.test.tsx`     | Komponenten aus Nutzersicht (Rollen, Texte)               | bei jeder Änderung     |
| `services/web/e2e/*.spec.ts`         | ganze Wege im Browser                                     | `make e2e`             |

Integrationstests laufen **nicht** automatisch mit:

```toml
addopts = "-m 'not integration'"
```

`make test-python` setzt `HOMEPI_TEST_DATABASE_URL` auf die Testdatenbank der
Entwicklungsumgebung. Jeder Lauf legt sich daraus eine **eigene** Datenbank an
(`<projekt>_test`) und wirft sie danach weg; nach einem roten Lauf bleibt sie
zum Hineinsehen stehen. Ausführlich: [12-testen.md](12-testen.md).

### Testen aus Nutzersicht, nicht aus Implementierungssicht

Die Frontend-Tests greifen über `getByRole` und sichtbaren Text zu, nicht über CSS-Klassen
oder `data-testid`. Das ist kein Stilfrage: ein Test, der an der Rolle `heading` hängt,
überlebt jedes Refactoring des Markups — und schlägt fehl, wenn die Überschrift für einen
Screenreader verschwindet. Ein Test, der an `.status-title` hängt, kann beides nicht.

## CI/CD

Drei Workflows, jeder mit einer klaren Aufgabe:

### `ci.yml` — läuft bei jedem Push

Zuerst ermittelt ein `changes`-Job per Pfadfilter, was überhaupt betroffen ist. Eine
Änderung an `docs/` startet keinen einzigen Test.

| Job       | Prüft                                                                                                                |
| --------- | -------------------------------------------------------------------------------------------------------------------- |
| `infra`   | shellcheck, keine CRLF, alle fünf Compose-Dateien validieren, keine echten Werte in `.env.example`                   |
| `api`     | ruff format, ruff check, mypy strict, pytest **inklusive Integration** gegen einen Postgres-Service, Coverage ≥ 85 % |
| `web`     | prettier, eslint, `tsc -b`, vitest mit Schwellen aus `vite.config.ts`, Produktionsbuild                              |
| `docker`  | beide Images für amd64 bauen — fängt Dockerfile-Fehler in ~1 Minute statt im arm64-Build                             |
| `secrets` | gitleaks über die gesamte Historie                                                                                   |
| `ci`      | fasst alles zu **einem** Status zusammen                                                                             |

Der `ci`-Job existiert wegen einer Eigenheit des Branch-Schutzes: Ein übersprungener Job
zählt dort als Erfolg. Ohne diese Zusammenfassung würde ein Pfadfilter, der `api`
überspringt, den Schutz aushebeln. `ci` wertet die Ergebnisse selbst aus.

**Reihenfolge innerhalb der Jobs ist Absicht:** Format, dann Lint, dann Typen, dann Tests.
Jede Stufe gibt eine präzisere Fehlermeldung als die nächste. Ein Tippfehler soll als
Tippfehler gemeldet werden, nicht als fehlgeschlagener Test.

### `images.yml` — bei Push auf `develop` oder `main`

Baut `ghcr.io/amuetze-dev/homepi-gateway` und `homepi-web` für `linux/arm64`.

Das Frontend baut **nativ auf amd64** (`FROM --platform=$BUILDPLATFORM`) und legt nur die
fertigen statischen Dateien in eine arm64-nginx-Schicht. Damit entfällt der komplette
QEMU-Aufwand für `npm ci` — das ist der Unterschied zwischen zwei und fünfzehn Minuten.
Nur die API braucht QEMU, weil ihre Wheels architekturspezifisch sind; kompiliert wird
dabei nichts, alles kommt als fertiges `manylinux-aarch64`-Wheel.

Zu hinterlegen ist nichts mehr: Die Website ruft ihre API unter `/api` auf, unter
derselben Adresse wie sich selbst, und Traefik schneidet das Präfix ab. Früher stand
hier die Repository-Variable `VITE_API_URL = https://api.deine-domain`; mit ihr lief
die Seite unter jedem anderen Port ins Leere — aus dem Internet ist sie unter `:8443`
erreichbar ([14-internet.md](14-internet.md)). Wer die alte Variable noch hat, kann
sie löschen; der Workflow liest sie nicht mehr.

### `deploy.yml` — von Hand ausgelöst

Bewusst über einen **selbst gehosteten Runner auf dem Pi**, nicht über SSH von GitHub aus.
Der Pi holt, GitHub schiebt nicht — damit liegt kein privater Schlüssel und kein
SSH-Zugang bei einem Dritten. Der Job sichert erst, rollt dann aus und prüft danach, ob
Container in einer Neustartschleife hängen.

Bis der Pi da ist, ist der Weg von Hand:

```bash
ssh pi && cd ~/homelab && make deploy-apps
```

## Branch-Schutz einrichten

Einmalig, sobald die erste CI durchgelaufen ist:

```bash
gh api -X PUT repos/AMuetze-Dev/HomePI/branches/main/protection \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=ci' \
  -F 'enforce_admins=false' \
  -F 'required_pull_request_reviews[required_approving_review_count]=0' \
  -F 'restrictions=null'
```

Dasselbe für `develop`. Der einzige geforderte Status ist `ci` — deshalb der
Zusammenfassungsjob.

Bei einem Ein-Personen-Repo ist `required_approving_review_count=0` sinnvoll: Du kannst
deine eigenen PRs mergen, aber nicht an der CI vorbei.

## Lokale Hooks

```bash
uv tool install pre-commit
pre-commit install
```

Die Hooks prüfen nur, was in Sekunden geht: Zeilenenden, YAML- und JSON-Syntax, private
Schlüssel, ruff, shellcheck — und verhindern ein versehentlich eingechecktes `.env`.
Alles Langsame bleibt in der CI. Ein Hook, der nervt, wird mit `--no-verify` umgangen und
schützt dann gar nichts mehr.

## Befehlsübersicht

```bash
make install         # Abhängigkeiten aller Projekte einrichten
make tdd-api         # pytest im Watch-Modus (P=modules/<name>)
make tdd-web         # vitest im Watch-Modus (N=<name>)
make test            # alles, was die CI auch prüft
make test-python     # nur Backend, mit Integrationstests
make test-web        # nur Frontend
make test-modul N=…  # beide Hälften eines Artefakts
make e2e             # Oberflächen-Reisen gegen eine frische Umgebung
make fmt             # formatieren und automatisch behebbare Funde beheben
```

`make test-infra` braucht eine `.env` im Projektwurzelverzeichnis, weil es die
Compose-Dateien tatsächlich auflöst. Für einen reinen Syntaxtest genügt
`cp .env.example .env`.
