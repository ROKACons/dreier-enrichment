@echo off
SET PROJ=C:\Users\rolan\OneDrive\ROKA Business\ROKA Consulting\Verkauf und KI Konzepte\Dreier Data Enrichment
SET STREAMLIT=C:\Users\rolan\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe
SET LOG=%APPDATA%\dreier_enrichment.log
SET PORT=8501

cd /d "%PROJ%"
echo %DATE% %TIME% – Watchdog gestartet >> "%LOG%"

:LOOP
  :: Prüfe ob Port aktiv
  netstat -ano | findstr ":%PORT% " >nul 2>&1
  if errorlevel 1 (
    echo %DATE% %TIME% – App nicht aktiv, starte neu... >> "%LOG%"
    start "" /b "%STREAMLIT%" run app.py --server.port %PORT% --server.headless true --browser.gatherUsageStats false >> "%LOG%" 2>&1
  )
  :: Alle 60 Sekunden prüfen
  timeout /t 60 /nobreak >nul
goto LOOP
