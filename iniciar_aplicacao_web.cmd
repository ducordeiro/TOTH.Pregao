@echo off
cd /d "%~dp0"
start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:8765'"

set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PYTHON%" (
  "%BUNDLED_PYTHON%" "%~dp0ocr_edital_web\server.py"
  goto :finished
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0ocr_edital_web\server.py"
  goto :finished
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0ocr_edital_web\server.py"
  goto :finished
)

echo Python nao foi encontrado. Instale o Python 3 para iniciar a aplicacao.

:finished
pause
