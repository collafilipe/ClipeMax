@echo off
chcp 65001 >nul
rem Abre o escritorio no navegador. O expediente (a vigia das lives) e ligado por voce, la dentro.
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo O projeto ainda nao foi instalado neste computador. Rode instalar.bat primeiro.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0cortes.py" --revisar --escritorio
if errorlevel 1 pause
