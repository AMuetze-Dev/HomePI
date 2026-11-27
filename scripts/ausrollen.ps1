# develop auf den Pi bringen - in einem Durchgang.
#
#   powershell -ExecutionPolicy Bypass -File scripts\ausrollen.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\ausrollen.ps1 -OhnePush   # nur der Pi
#   powershell -ExecutionPolicy Bypass -File scripts\ausrollen.ps1 -Ja         # ohne Rueckfrage
#
# Ablauf:
#   1. zeigen, was mit dem Push auf den Pi ginge - auch Commits anderer
#      Arbeiten, die lokal nach develop gemergt, aber nie gepusht wurden
#   2. nachfragen, dann develop pushen
#   3. warten, bis GitHub die arm64-Images gebaut hat (Workflow "Images")
#   4. per ssh auf "homelab": git pull, dann scripts/pi-ausrollen.sh
#      (sichern, Images ziehen, Container ersetzen, Tabellen anlegen)
#
# Migrationen aus scripts/migrationen/ spielt es NICHT ein, es nennt sie nur.
#
# Bewusst ohne Umlaute: Windows PowerShell 5.1 liest Skripte ohne BOM als ANSI.

param(
    [switch]$OhnePush,
    # Ohne Rueckfrage - fuer einen Aufruf, bei dem niemand tippen kann. Die
    # Liste der Commits steht trotzdem davor.
    [switch]$Ja,
    [string]$Ziel = "homelab",
    [int]$WarteMinuten = 30
)

$ErrorActionPreference = "Continue"
$repo = "AMuetze-Dev/HomePI"

function Pruefe([string]$schritt) {
    if ($LASTEXITCODE -ne 0) { throw "Abgebrochen bei: $schritt (Exitcode $LASTEXITCODE)" }
}

Set-Location (Split-Path $PSScriptRoot -Parent)

git fetch -q origin
Pruefe "git fetch"

$neu = @(git log --oneline origin/develop..develop)
$migrationen = @(git diff --name-only --diff-filter=A origin/develop develop -- scripts/migrationen/ | Where-Object { $_ -like "*.sql" })

if (-not $OhnePush) {
    if ($neu.Count -eq 0) {
        Write-Host "develop ist schon gepusht - es wird nur der Pi aktualisiert."
        $OhnePush = $true
    } else {
        Write-Host "==> Mit dem Push geht auf den Pi ($($neu.Count) Commits):"
        $neu | ForEach-Object { Write-Host "    $_" }
        if ($migrationen.Count -gt 0) {
            Write-Host ""
            Write-Host "    ACHTUNG, neue Migrationen - danach von Hand einspielen:"
            $migrationen | ForEach-Object { Write-Host "      $_" }
        }
        Write-Host ""
        if (-not $Ja) {
            $antwort = Read-Host "Pushen und ausrollen? (j/n)"
            if ($antwort -ne "j") { Write-Host "Nichts getan."; exit 0 }
        }

        git push origin develop
        Pruefe "git push"
    }
}

# --- Auf die Images warten ------------------------------------------------
# Die Laeufe sind oeffentlich lesbar, ohne Anmeldung und ohne gh.
$sha = (git rev-parse origin/develop).Trim()
if (-not $OhnePush) { $sha = (git rev-parse develop).Trim() }
Write-Host "==> Warte auf die Images fuer $($sha.Substring(0,7))"
$bis = (Get-Date).AddMinutes($WarteMinuten)
while ($true) {
    $lauf = $null
    try {
        $antwort = Invoke-RestMethod "https://api.github.com/repos/$repo/actions/runs?branch=develop&per_page=10"
        $lauf = $antwort.workflow_runs | Where-Object { $_.head_sha -eq $sha -and $_.name -eq "Images" } | Select-Object -First 1
    } catch {
        Write-Host "    GitHub nicht erreichbar: $($_.Exception.Message)"
    }
    if ($lauf -and $lauf.status -eq "completed") {
        if ($lauf.conclusion -ne "success") {
            throw "Images: $($lauf.conclusion) - $($lauf.html_url)"
        }
        Write-Host "    Images gebaut."
        break
    }
    if ((Get-Date) -gt $bis) { throw "Nach $WarteMinuten Minuten noch keine Images." }
    $stand = if ($lauf) { $lauf.status } else { "noch nicht gestartet" }
    Write-Host "    $stand ..."
    Start-Sleep -Seconds 20
}

# --- Auf dem Pi -----------------------------------------------------------
$argumente = ($migrationen | ForEach-Object { "'$_'" }) -join " "
Write-Host "==> Pi ($Ziel)"
ssh $Ziel "cd ~/homelab && git pull --ff-only -q && bash scripts/pi-ausrollen.sh $argumente"
Pruefe "Ausrollen auf dem Pi"
