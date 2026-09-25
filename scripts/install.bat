@echo off
rem Windows: double-click to install Repo Numbat for the current user.
rem Runs install.ps1 with the execution policy bypassed for this one call.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
