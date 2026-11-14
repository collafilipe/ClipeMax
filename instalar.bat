@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem instalar.bat /s  = sem pausas (para rodar por outro programa)
set "PAUSA=pause"
if /i "%~1"=="/s" set "PAUSA=rem"
set "REABRIR="

echo == Instalacao da ClipeMax ==
echo.

call :precisa "Python 3.12" "py -3.12 --version" Python.Python.3.12
if errorlevel 1 goto falhou
call :precisa "ffmpeg" "where ffmpeg" Gyan.FFmpeg
if errorlevel 1 goto falhou
if defined REABRIR (
  echo.
  echo Programas instalados. O Windows so enxerga eles numa janela nova:
  echo feche esta janela e rode instalar.bat de novo para terminar.
  %PAUSA%
  exit /b 0
)

echo [1/3] Criando o ambiente do projeto...
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto falhou
echo [2/3] Baixando as bibliotecas (alguns minutos na primeira vez)...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 ( echo Falha ao instalar as bibliotecas. Confira a internet e rode de novo. & goto falhou )

echo [3/3] Criando o atalho na area de trabalho...
powershell -NoProfile -Command "$a = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\ClipeMax.lnk'); $a.TargetPath = '%~dp0iniciar.bat'; $a.WorkingDirectory = '%~dp0'; $a.Save()"
if errorlevel 1 echo Nao consegui criar o atalho; use o iniciar.bat desta pasta.

echo.
where claude >nul 2>&1
if errorlevel 1 (
  echo AVISO: Claude Code nao encontrado. Sem ele os cortes saem sem nota, titulo e legenda da IA,
  echo e a gerencia nao da parecer. Instale em https://claude.com/claude-code e rode "claude" uma vez
  echo para entrar na sua conta.
  echo.
)
echo Pronto. Abra pelo atalho "ClipeMax" na area de trabalho, ou pelo iniciar.bat.
echo Na primeira live o modelo de legenda (cerca de 1,6 GB) e baixado sozinho.
%PAUSA%
exit /b 0

:precisa
rem %1 nome para mostrar, %2 comando que prova que esta instalado, %3 id no winget
%~2 >nul 2>&1
if not errorlevel 1 exit /b 0
echo %~1 nao encontrado.
where winget >nul 2>&1
if errorlevel 1 (
  echo Instale %~1 manualmente e rode instalar.bat de novo.
  exit /b 1
)
if /i "%PAUSA%"=="rem" exit /b 1
choice /C SN /M "Instalar %~1 agora"
if errorlevel 2 exit /b 1
winget install --id %3 -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 exit /b 1
set "REABRIR=1"
exit /b 0

:falhou
echo.
echo A instalacao nao terminou. Corrija o que foi apontado acima e rode instalar.bat de novo.
%PAUSA%
exit /b 1
