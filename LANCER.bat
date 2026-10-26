@echo off
rem ==================================================================
rem  Modern Data Platform WWI - menu de lancement (double-clic)
rem ==================================================================
title Modern Data Platform WWI
cd /d "%~dp0"
set PS=powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mdp.ps1"

:menu
rem ---- Premiere utilisation : installation automatique, sans passer par le menu
if not exist "%~dp0.venv\Scripts\python.exe" (
    cls
    echo.
    echo   ==============================================================
    echo      PREMIERE UTILISATION : INSTALLATION AUTOMATIQUE
    echo   ==============================================================
    echo.
    echo   Le projet n'est pas encore installe sur ce poste.
    echo   Installation en cours : environ 5 a 10 minutes.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
    if errorlevel 1 (
        echo.
        echo   L'installation a echoue : lisez le message ci-dessus.
        pause
        exit /b 1
    )
    echo.
    pause
)

cls
echo.
echo   ==============================================================
echo      MODERN DATA PLATFORM - WIDE WORLD IMPORTERS
echo   ==============================================================
echo.
echo     1. Lancer l'application (assistant IA + tableau de bord)
echo     2. Ouvrir Dagster (orchestration du pipeline)
echo     3. Ouvrir la documentation dbt (lignage des donnees)
echo     4. Executer tout le pipeline (SQL Server - Bronze - Silver - Gold)
echo     5. Verifier les connexions (SQL Server, Snowflake, IA)
echo     6. Quitter
echo.
echo     0. Reinstaller / mettre a jour les dependances
echo.
rem ---- Snowflake pas encore configure : on le signale clairement
findstr /r /c:"^SNOWFLAKE_ACCOUNT=..*" "%~dp0.env" >nul 2>&1
if errorlevel 1 (
    echo   [!] Snowflake n'est pas encore configure : executez snowflake\setup.sql
    echo       dans Snowsight puis renseignez SNOWFLAKE_ACCOUNT dans le fichier .env
    echo       ^(voir LISEZMOI.txt^). En attendant, seule l'option 5 est utile.
    echo.
)
set CHOIX=
set /p CHOIX="  Votre choix (1-6) : "

if "%CHOIX%"=="0" goto install
if "%CHOIX%"=="1" goto app
if "%CHOIX%"=="2" goto dagster
if "%CHOIX%"=="3" goto docs
if "%CHOIX%"=="4" goto pipeline
if "%CHOIX%"=="5" goto test
if "%CHOIX%"=="6" exit /b
goto menu

:install
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
echo.
pause
goto menu

:ollama
rem Demarre le serveur d'IA local s'il ne tourne pas deja
powershell -NoProfile -Command "try { Invoke-RestMethod http://localhost:11434/api/version -TimeoutSec 2 | Out-Null } catch { Start-Process \"$env:LOCALAPPDATA\Programs\Ollama\ollama.exe\" -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep 4 }"
goto :eof

:app
call :ollama
echo.
echo   L'application va s'ouvrir dans le navigateur (http://localhost:8501).
echo   Le modele d'IA se charge en arriere-plan : attendez 2 a 3 minutes
echo   avant la premiere question. Fermez cette fenetre pour arreter l'application.
echo.
%PS% app
pause
goto menu

:dagster
echo.
echo   Dagster demarre... le navigateur s'ouvrira dans environ 30 secondes
echo   sur http://localhost:3000. Fermez cette fenetre pour arreter Dagster.
echo.
start "" /min cmd /c "timeout /t 30 >nul & start http://localhost:3000"
%PS% dagster
pause
goto menu

:docs
echo.
echo   Generation de la documentation dbt, puis ouverture sur http://localhost:8080
echo   Fermez cette fenetre pour arreter le serveur de documentation.
echo.
start "" /min cmd /c "timeout /t 40 >nul & start http://localhost:8080"
%PS% docs
pause
goto menu

:pipeline
echo.
echo   Etape 1/2 : ingestion SQL Server vers Snowflake BRONZE (DLT)...
%PS% ingest
echo.
echo   Etape 2/2 : construction de SILVER et GOLD + tests qualite (dbt)...
%PS% dbt
echo.
echo   Pipeline termine.
pause
goto menu

:test
call :ollama
%PS% test
echo.
pause
goto menu
