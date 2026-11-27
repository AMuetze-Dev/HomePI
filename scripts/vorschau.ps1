# Lokale Vorschau eines Stands - zum Durchklicken, bevor er auf den Pi geht.
#
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1            # develop
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Zweig feature/ihk
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Stopp
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Dev    # auf 5173, mit deinen Daten
#
# Warum nicht einfach "make dev": Der Hauptordner steht oft auf einem anderen
# Zweig, und darin liegen ungesicherte Aenderungen anderer Arbeiten. Die
# Vorschau holt den gewuenschten Stand deshalb in einen EIGENEN Ordner
# (..\HomePI-vorschau) und startet dort eine EIGENE Umgebung:
#
#   Oberflaeche  http://localhost:5373
#   API          http://localhost:18200
#   Postgres     localhost:15632
#
# Die Entwicklungsumgebung auf 5173 bleibt davon unberuehrt. Die Datenbank der
# Vorschau ueberlebt ein erneutes Starten; weggeworfen wird sie nie von hier.
#
# Mit -Dev laeuft derselbe Stand stattdessen als DIE Entwicklungsumgebung
# (5173/18000/15432) - mit ihrer Datenbank, also mit deinem Konto und deinen
# Daten. Neue Tabellen legt das Gateway beim Start an. Zurueck zum Code des
# Hauptordners: dort "make dev" bzw. die Zeile, die das Skript am Ende nennt.
#
# Bewusst ohne Umlaute: Windows PowerShell 5.1 liest Skripte ohne BOM als
# ANSI, und aus einem "ae" wird dann nichts Falsches.

param(
    [string]$Zweig = "develop",
    [switch]$Stopp,
    [switch]$Dev
)

# Nicht "Stop": Windows PowerShell 5.1 hielte jede Zeile, die git oder docker
# auf stderr schreiben ("Preparing worktree ..."), fuer einen Fehler. Ob ein
# Schritt geklappt hat, sagt der Exitcode - das prueft Pruefe().
$ErrorActionPreference = "Continue"

$repo = (git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir).Trim()
$repo = Split-Path $repo -Parent
$ordner = Join-Path (Split-Path $repo -Parent) "HomePI-vorschau"

if ($Dev) {
    # Dieselben Namen wie "make dev": dasselbe Compose-Projekt, also auch
    # dasselbe Datenbank-Band. Nur der Code kommt aus dem Vorschau-Ordner.
    $env:DEV_PROJEKT = "homepi-dev"
    $env:DEV_WEB_PORT = "5173"
    $env:DEV_API_PORT = "18000"
    $env:DEV_DB_PORT = "15432"
} else {
    $env:DEV_PROJEKT = "homepi-vorschau"
    $env:DEV_WEB_PORT = "5373"
    $env:DEV_API_PORT = "18200"
    $env:DEV_DB_PORT = "15632"
}
$env:HOMEPI_MODULE = ""

function Pruefe([string]$schritt) {
    if ($LASTEXITCODE -ne 0) { throw "Abgebrochen bei: $schritt (Exitcode $LASTEXITCODE)" }
}

if ($Stopp) {
    if (Test-Path $ordner) {
        docker compose -f (Join-Path $ordner "compose.dev.yml") down
        Pruefe "Umgebung stoppen"
    }
    Write-Host "Vorschau gestoppt. Die Datenbank bleibt erhalten."
    exit 0
}

# --- 1. Stand holen -------------------------------------------------------
# Der LOKALE Zweig, nicht origin: genau das soll vor dem Push geprueft werden.
git -C $repo rev-parse --verify --quiet "refs/heads/$Zweig" | Out-Null
Pruefe "Zweig '$Zweig' gibt es lokal nicht"

if (-not (Test-Path $ordner)) {
    Write-Host "==> Lege $ordner an"
    git -C $repo worktree add --detach $ordner $Zweig
    Pruefe "Worktree anlegen"
} else {
    Write-Host "==> Stelle $ordner auf $Zweig"
    git -C $ordner checkout --detach --force $Zweig
    Pruefe "Worktree umstellen"
}
$stand = (git -C $ordner log --oneline -1).Trim()
Write-Host "    $stand"

# --- 2. Umgebung bauen und starten ---------------------------------------
# --build: Die Artefaktliste steckt im Gateway-Abbild (uv.lock). Ohne
#          Neubau laeuft ein neues Artefakt in eine Neustartschleife.
# -V:      node_modules liegen in einem anonymen Band. Ohne Erneuern fehlt
#          eine neue npm-Abhaengigkeit, obwohl sie im Abbild ist.
Write-Host "==> Baue und starte die Vorschau (dauert beim ersten Mal einige Minuten)"
if ($Dev) {
    # Alle Dienste, auch der Pruefdienst: Er gehoert zu diesem Projekt und
    # liefe sonst mit dem Code des Hauptordners gegen das neue Gateway.
    docker compose -f (Join-Path $ordner "compose.dev.yml") up -d --build -V --wait
    Pruefe "docker compose up"
    Write-Host ""
    Write-Host "Entwicklungsumgebung laeuft mit $stand"
    Write-Host "    http://localhost:5173  - mit deinem Konto anmelden."
    Write-Host "    Ein neues Artefakt erscheint erst, wenn du dir in der Verwaltung ein Recht darauf gibst."
    Write-Host ""
    Write-Host "Zurueck zum Code des Hauptordners:"
    Write-Host "    docker compose -f `"$(Join-Path $repo 'compose.dev.yml')`" up -d --build -V"
    exit 0
}
docker compose -f (Join-Path $ordner "compose.dev.yml") up -d --build -V --wait postgres gateway web
Pruefe "docker compose up"

# --- 3. Konto zum Durchklicken -------------------------------------------
# Wiederholbar: legt an oder setzt zurueck. Das Recht auf "verwaltung"
# schliesst die Ersteinrichtung - sonst steht statt der Startseite die Maske.
Write-Host "==> Testkonto"
$ausgabe = docker exec -w /app/services/gateway homepi-vorschau-gateway uv run homepi benutzer testkonto tester
Pruefe "Testkonto anlegen"
docker exec -w /app/services/gateway homepi-vorschau-gateway uv run homepi benutzer recht tester verwaltung verwalter | Out-Null
Pruefe "Recht auf verwaltung"

$passwort = ($ausgabe | Select-String -Pattern "^\s{4}\S+$" | Select-Object -Last 1).Line
$artefakte = ($ausgabe | Select-String -Pattern "verwalter auf:" | Select-Object -First 1).Line

Write-Host ""
Write-Host "Vorschau laeuft:  http://localhost:5373"
Write-Host "Stand:            $stand"
Write-Host "Anmelden:         tester / $($passwort.Trim())"
if ($artefakte) { Write-Host "Artefakte:       $($artefakte.Trim())" }
Write-Host ""
Write-Host "Stoppen:          powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Stopp"
