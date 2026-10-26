<#
  Point d'entree unique de la Modern Data Platform WWI.
  Usage :  .\mdp.ps1 <commande>
    test       verifie la connexion a SQL Server et a Snowflake
    ingest     charge SQL Server -> Snowflake BRONZE (DLT)
    dbt        construit SILVER et GOLD + tests qualite (dbt build)
    docs       genere et ouvre la documentation dbt (lignage)
    dagster    ouvre l'interface Dagster (http://localhost:3000)
    app        lance l'application Streamlit (http://localhost:8501)
#>
param([Parameter(Mandatory = $true)][ValidateSet("test", "ingest", "dbt", "docs", "dagster", "app")][string]$cmd)

$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$dbt = Join-Path $root ".venv\Scripts\dbt.exe"

# Charge le fichier .env dans l'environnement (dbt ne le lit pas seul)
Get-Content (Join-Path $root ".env") | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
    $name, $value = $_ -split '=', 2
    [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"'), "Process")
}
$env:DAGSTER_HOME = Join-Path $root ".dagster_home"
New-Item -ItemType Directory -Force $env:DAGSTER_HOME | Out-Null
$env:PYTHONIOENCODING = "utf-8"

Push-Location $root
try {
    switch ($cmd) {
        "test"    { & $py (Join-Path $root "scripts\check_connections.py") }
        "ingest"  { & $py (Join-Path $root "ingestion\pipeline_wwi.py") }
        "dbt"     { Push-Location dbt_wwi; & $dbt build --profiles-dir .; Pop-Location }
        "docs"    { Push-Location dbt_wwi; & $dbt docs generate --profiles-dir .; & $dbt docs serve --profiles-dir . --port 8080; Pop-Location }
        "dagster" { & $py -m dagster dev -f (Join-Path $root "orchestration\definitions.py") }
        "app"     { & $py -m streamlit run (Join-Path $root "app\streamlit_app.py") }
    }
} finally { Pop-Location }
