' Startet Streamlit-Watchdog unsichtbar beim Windows-Login
Dim shell
Set shell = CreateObject("WScript.Shell")
Dim proj
proj = "C:\Users\rolan\OneDrive\ROKA Business\ROKA Consulting\Verkauf und KI Konzepte\Dreier Data Enrichment"
shell.Run "cmd /c """ & proj & "\watchdog.bat""", 0, False
Set shell = Nothing
