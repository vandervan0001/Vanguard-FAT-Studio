@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0scripts\start.ps1" %*
if errorlevel 1 (
  echo.
  echo Le lancement a echoue. Voir le message ci-dessus et docs\INSTALLATION.md.
  pause
)
endlocal
