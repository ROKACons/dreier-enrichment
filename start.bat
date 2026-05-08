@echo off
SET PROJ=C:\Users\rolan\OneDrive\ROKA Business\ROKA Consulting\Verkauf und KI Konzepte\Dreier Data Enrichment
SET PY=C:\Users\rolan\AppData\Local\Programs\Python\Python312\python.exe
SET STREAMLIT=C:\Users\rolan\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe
SET LOG=%APPDATA%\dreier_enrichment.log
SET PORT=8501

cd /d "%PROJ%"

:: Prüfe ob schon läuft
netstat -ano | findstr ":%PORT% " >nul 2>&1
if not errorlevel 1 (
    echo App läuft bereits auf Port %PORT%. >> "%LOG%"
    exit /b 0
)

echo %DATE% %TIME% – Starte Firmen Enrichment App... >> "%LOG%"
"%STREAMLIT%" run app.py --server.port %PORT% --server.headless true --browser.gatherUsageStats false >> "%LOG%" 2>&1
