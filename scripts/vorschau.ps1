# Lokale Vorschau eines Stands - zum Durchklicken, bevor er auf den Pi geht.
#
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1            # develop
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Zweig feature/ihk
#   powershell -ExecutionPolicy Bypass -File scripts\vorschau.ps1 -Stopp
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
# Bewusst ohne Umlaute: Windows PowerShell 5.1 liest Skripte ohne BOM als
# ANSI, und aus einem "ae" wird dann nichts Falsches.

param(
    [string]$Zweig = "develop",
    [switch]$Stopp
)

# Nicht "Stop": Windows PowerShell 5.1 hielte jede Zeile, die git oder docker
# auf stderr schreiben ("Preparing worktree ..."), fuer einen Fehler. Ob ein
# Schritt geklappt hat, sagt der Exitcode - das prueft Pruefe().
$ErrorActionPreference = "Continue"

$repo = (git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir).Trim()
$repo = Split-Path $repo -Parent
$ordner = Join-Path (Split-Path $repo -Parent) "HomePI-vorschau"

$env:DEV_PROJEKT = "homepi-vorschau"
$env:DEV_WEB_PORT = "5373"
$env:DEV_API_PORT = "18200"
$env:DEV_DB_PORT = "15632"
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
