@echo off
chcp 65001 >nul
rem Links com o caractere & precisam vir entre aspas: cortes.bat "https://...&t=10"
"%~dp0.venv\Scripts\python.exe" "%~dp0cortes.py" %*
if errorlevel 1 pause
