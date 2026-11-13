@echo off
chcp 65001 >nul
rem Gera clipemax.zip para levar o projeto a outro computador.
rem Vao o codigo, o canais.txt, o empresa.json e as posicoes de webcam aprendidas.
rem Ficam de fora: o ambiente (.venv), os videos, o estado do expediente e os segredos
rem (chaves dos apps e tokens das contas). No outro PC as contas sao conectadas de novo.
powershell -NoProfile -Command "$raiz = '%~dp0'.TrimEnd('\'); $fora = '.venv','prontos','aprovados','descartados','estado','tmp','__pycache__','.git','.claude','segredos','chave_api.txt','.pytest_cache','.ruff_cache'; $itens = Get-ChildItem -LiteralPath $raiz -Force | Where-Object { $fora -notcontains $_.Name -and $_.Extension -ne '.zip' }; $zip = Join-Path $raiz 'clipemax.zip'; if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }; Compress-Archive -LiteralPath $itens.FullName -DestinationPath $zip; Write-Host ('Pacote criado: ' + $zip + ' (' + [math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1) + ' MB)')"
if errorlevel 1 ( echo Nao consegui criar o pacote. & pause & exit /b 1 )
echo.
echo No outro computador: extraia o zip numa pasta de caminho curto e rode instalar.bat.
if /i not "%~1"=="/s" pause
