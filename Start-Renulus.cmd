@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-renulus.ps1" %*
exit /b %ERRORLEVEL%
