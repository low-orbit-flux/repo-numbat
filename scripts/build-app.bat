@echo off
rem Build dist\Repo Numbat\Repo Numbat.exe with PyInstaller (Windows).
setlocal
set "PROJECT=%~dp0.."
for %%I in ("%PROJECT%") do set "PROJECT=%%~fI"
set "VENV_PY=%PROJECT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" call "%PROJECT%\scripts\repo-numbat.bat" --cli >nul
"%VENV_PY%" -c "import PyInstaller" 2>nul || "%VENV_PY%" -m pip install pyinstaller
cd /d "%PROJECT%"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%VENV_PY%" -m PyInstaller --noconfirm --clean packaging\repo-numbat.spec
echo built: %PROJECT%\dist\Repo Numbat\Repo Numbat.exe
endlocal
