@echo off
setlocal
title TOTH Propostas

cd /d "%~dp0"
set "APP_URL=http://127.0.0.1:8765/"
set "SERVER=%~dp0ocr_edital_web\server.py"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%SERVER%" (
  echo ERRO: servidor nao encontrado em:
  echo %SERVER%
  pause
  exit /b 1
)

powershell.exe -NoProfile -Command "try { Invoke-WebRequest -Uri '%APP_URL%' -UseBasicParsing -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
  echo O app ja esta rodando. Abrindo a tela...
  start "" "%APP_URL%"
  exit /b 0
)

set "PYTHON_CMD="
if exist "%BUNDLED_PYTHON%" set "PYTHON_CMD=%BUNDLED_PYTHON%"

if not defined PYTHON_CMD (
  where py.exe >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py.exe -3"
)

if not defined PYTHON_CMD (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python.exe"
)

if not defined PYTHON_CMD (
  echo ERRO: Python 3 nao foi encontrado neste computador.
  echo Instale o Python 3 e tente novamente.
  pause
  exit /b 1
)

echo Iniciando o TOTH Propostas...
echo A tela sera aberta automaticamente quando o servidor estiver pronto.
echo Para desligar o app, feche esta janela ou pressione Ctrl+C.
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$url='%APP_URL%'; foreach ($attempt in 1..60) { try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null; Start-Process $url; exit } catch { Start-Sleep -Milliseconds 500 } }"

%PYTHON_CMD% "%SERVER%"

echo.
echo O servidor foi encerrado.
pause
