@echo off
rem Launcher for Windows (cmd).  Creates .venv next to the project on first run,
rem installs requirements, then starts the GUI.  Arguments are passed through.
setlocal
set "PROJECT=%~dp0.."
for %%I in ("%PROJECT%") do set "PROJECT=%%~fI"
set "VENV=%PROJECT%\.venv"
set "VENV_PY=%VENV%\Scripts\pythonw.exe"
set "VENV_PYC=%VENV%\Scripts\python.exe"

if not exist "%VENV_PYC%" (
    echo repo-numbat: creating virtualenv in %VENV%
    where py >nul 2>nul && (py -3 -m venv "%VENV%") || (python -m venv "%VENV%")
    if errorlevel 1 (
        echo repo-numbat: could not create a virtualenv. Install Python 3.10+ from python.org and tick "Add to PATH".
        pause
        exit /b 1
    )
)
"%VENV_PYC%" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo repo-numbat: installing requirements
    "%VENV_PYC%" -m pip install --upgrade pip >nul
    "%VENV_PYC%" -m pip install -r "%PROJECT%\requirements.txt"
    if errorlevel 1 ( pause & exit /b 1 )
)

set "PYTHONPATH=%PROJECT%;%PYTHONPATH%"
rem --cli needs a console; everything else runs windowless.
echo %* | find "--cli" >nul
if errorlevel 1 (
    start "" "%VENV_PY%" -m repo_numbat %*
) else (
    "%VENV_PYC%" -m repo_numbat %*
)
endlocal
