<#
.SYNOPSIS
    Active le venv adapte a la tache et charge le .env du projet.

.DESCRIPTION
    A lancer en "dot-sourcing" (avec un point) pour que le venv et les variables
    restent actifs dans le terminal courant :

        . .\scripts\activate_env.ps1 ingestion   # ingestion\.venv (scripts Python, pytest)
        . .\scripts\activate_env.ps1 dbt         # .venv racine (dbt)

    Sans le point, le script s'execute dans une portee temporaire et rien ne persiste.
    Les variables du .env ecrasent celles deja definies dans la session. Leurs valeurs
    ne sont jamais affichees.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('ingestion', 'dbt')]
    [string]$Task
)

$projectRoot = Split-Path -Parent $PSScriptRoot

$profiles = @{
    ingestion = @{
        Venv     = Join-Path $projectRoot 'ingestion\.venv'
        Workdir  = 'ingestion'
        Packages = @('requests', 'tenacity', 'python-dotenv', 'databricks-sql-connector', 'pytest')
    }
    dbt       = @{
        Venv     = Join-Path $projectRoot '.venv'
        Workdir  = 'dbt'
        Packages = @('dbt-core', 'dbt-databricks', 'dbt-adapters')
    }
}
$selected = $profiles[$Task]

function Import-DotEnv {
    param([string]$Path)

    $loaded = @()
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $text = $line.Trim()
        if ($text -eq '' -or $text.StartsWith('#')) { continue }
        if ($text -match '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            Set-Item -LiteralPath "Env:$name" -Value $value
            $loaded += [pscustomobject]@{ Name = $name; IsSet = ($value -ne '') }
        }
    }
    return $loaded
}

$activateScript = Join-Path $selected.Venv 'Scripts\Activate.ps1'
if (-not (Test-Path -LiteralPath $activateScript)) {
    Write-Error "Venv introuvable : $($selected.Venv)"
    Write-Host "Creation : python -m venv `"$($selected.Venv)`"" -ForegroundColor Yellow
    return
}

if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
. $activateScript

$envFile = Join-Path $projectRoot '.env'
$envVars = @()
if (Test-Path -LiteralPath $envFile) {
    $envVars = @(Import-DotEnv -Path $envFile)
}

$installed = @{}
try {
    foreach ($pkg in (python -m pip list --format=json 2>$null | ConvertFrom-Json)) {
        $installed[$pkg.name.ToLower().Replace('_', '-')] = $pkg.version
    }
} catch {
    Write-Warning "Impossible de lister les packages : $($_.Exception.Message)"
}

$pythonVersion = (python --version 2>&1 | Out-String).Trim()
$pythonPath = (Get-Command python).Source

Write-Host ''
Write-Host "=== Environnement actif : $Task ===" -ForegroundColor Cyan
Write-Host "Venv     : $($selected.Venv)"
Write-Host "Python   : $pythonVersion ($pythonPath)"
Write-Host "Dossier  : cd $($selected.Workdir)"
Write-Host 'Packages :'
foreach ($name in $selected.Packages) {
    if ($installed.ContainsKey($name)) {
        Write-Host ("  {0,-26} {1}" -f $name, $installed[$name])
    } else {
        Write-Host ("  {0,-26} ABSENT" -f $name) -ForegroundColor Red
    }
}
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host '.env     : introuvable a la racine (copier .env.example en .env)' -ForegroundColor Yellow
} else {
    $empty = @($envVars | Where-Object { -not $_.IsSet })
    Write-Host ".env     : $($envVars.Count) variables chargees, $($empty.Count) vide(s)"
    foreach ($variable in $envVars) {
        if ($variable.IsSet) {
            Write-Host ("  {0,-26} defini" -f $variable.Name)
        } else {
            Write-Host ("  {0,-26} VIDE" -f $variable.Name) -ForegroundColor Yellow
        }
    }
}
Write-Host ''
