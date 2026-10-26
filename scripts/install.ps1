<#
  Installation du projet sur un nouveau poste (premiere utilisation).
  - cree l'environnement Python 3.12 et installe les dependances
  - cree le fichier .env a partir du modele
  - genere une paire de cles RSA pour Snowflake et l'inscrit dans snowflake/setup.sql
  - telecharge le modele d'IA local si Ollama est installe
#>
param([switch]$SkipPip)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
function Etape($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }

# 1. Python 3.12
Etape "Verification de Python 3.12"
$py312 = $null
try { $py312 = (& py -V:3.12 -c "import sys; print(sys.executable)" 2>$null) } catch {}
if (-not $py312) {
    Write-Host "Python 3.12 est introuvable. Installez-le (https://www.python.org/downloads/) puis relancez." -ForegroundColor Red
    Write-Host "Avec le gestionnaire 'py' recent :  py install 3.12"
    exit 1
}
Write-Host "Python 3.12 : $py312"

# 2. Environnement virtuel + dependances
Etape "Environnement Python (.venv)"
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) { & py -V:3.12 -m venv "$root\.venv" }
$py = "$root\.venv\Scripts\python.exe"
if (-not $SkipPip) {
    Etape "Installation des dependances (plusieurs minutes)"
    & $py -m pip install --upgrade pip --quiet
    & $py -m pip install -r "$root\requirements.txt" --quiet
    if ($LASTEXITCODE -ne 0) { Write-Host "Echec de l'installation des dependances." -ForegroundColor Red; exit 1 }
}

# 3. Fichier de configuration
Etape "Fichier de configuration .env"
if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    (Get-Content "$root\.env") -replace '^SNOWFLAKE_PRIVATE_KEY_PATH=.*$', "SNOWFLAKE_PRIVATE_KEY_PATH=$($root -replace '\\','/')/keys/rsa_key.p8" |
        Set-Content -Encoding ascii "$root\.env"
    Write-Host ".env cree : renseignez SNOWFLAKE_ACCOUNT apres l'execution de snowflake/setup.sql."
} else { Write-Host ".env deja present (conserve)." }

# 4. Cles RSA pour l'utilisateur de service Snowflake
Etape "Cle de securite Snowflake"
if (-not (Test-Path "$root\keys\rsa_key.p8")) {
    New-Item -ItemType Directory -Force "$root\keys" | Out-Null
    $pub = & $py -c @"
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization as s
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open(r'$root\keys\rsa_key.p8', 'wb').write(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
pem = k.public_key().public_bytes(s.Encoding.PEM, s.PublicFormat.SubjectPublicKeyInfo).decode()
print(''.join(pem.strip().splitlines()[1:-1]))
"@
    if ($LASTEXITCODE -ne 0 -or -not $pub -or -not (Test-Path "$root\keys\rsa_key.p8")) {
        Write-Host "Echec de la generation de la cle." -ForegroundColor Red
        Write-Host "Cause frequente : chemin du dossier trop long. Placez le projet dans un dossier court (ex : C:\projet_mdp_wwi)," -ForegroundColor Red
        Write-Host "supprimez le dossier .venv puis relancez l'installation." -ForegroundColor Red
        exit 1
    }
    (Get-Content "$root\snowflake\setup.sql") -replace "^ALTER USER WWI_SVC SET RSA_PUBLIC_KEY = '.*';$", "ALTER USER WWI_SVC SET RSA_PUBLIC_KEY = '$pub';" |
        Set-Content -Encoding utf8 "$root\snowflake\setup.sql"
    Write-Host "Nouvelle cle generee ; snowflake/setup.sql a ete mis a jour avec la cle publique."
} else { Write-Host "Cle deja presente (conservee)." }

# 5. Modele d'IA local
Etape "Modele d'IA local (Ollama)"
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (Test-Path $ollama) {
    & $ollama pull qwen2.5-coder:3b
} else {
    Write-Host "Ollama n'est pas installe : https://ollama.com/download puis relancez cette installation." -ForegroundColor Yellow
}

Write-Host "`nInstallation terminee." -ForegroundColor Green
Write-Host "Etapes restantes (voir LISEZMOI.txt) :"
Write-Host "  1. Executer snowflake/setup.sql dans Snowsight (role ACCOUNTADMIN)."
Write-Host "  2. Copier la valeur 'account' affichee dans .env (SNOWFLAKE_ACCOUNT=)."
Write-Host "     Coller une cle Groq gratuite (https://console.groq.com/keys) dans .env (GROQ_API_KEY=)."
Write-Host "  3. Menu option 4 (pipeline complet), puis option 1 (application)."
