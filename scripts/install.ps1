# Install Repo Numbat on Windows (no admin rights needed).
#
#   .\scripts\install.ps1               install for the current user
#   .\scripts\install.ps1 -Uninstall    remove it again
#   .\scripts\install.ps1 -Prefix DIR   install the program files into DIR
#
# Copies the program to %LOCALAPPDATA%\Programs\Repo Numbat, creates its own
# virtualenv there, adds a Start Menu shortcut with the numbat icon, and puts a
# 'repo-numbat' command on the user PATH.
# If PowerShell refuses to run scripts:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param(
    [switch]$Uninstall,
    [string]$Prefix = (Join-Path $env:LOCALAPPDATA "Programs\Repo Numbat")
)
$ErrorActionPreference = "Stop"
$Src = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StartMenu = [Environment]::GetFolderPath("Programs")
$Shortcut = Join-Path $StartMenu "Repo Numbat.lnk"
$BinDir = Join-Path $Prefix "bin"

function Set-UserPath([string]$dir, [bool]$add) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @($current -split ";" | Where-Object { $_ -and $_ -ne $dir })
    if ($add) { $parts += $dir }
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
}

if ($Uninstall) {
    Write-Host "removing Repo Numbat"
    if (Test-Path $Prefix) { Remove-Item -Recurse -Force $Prefix }
    if (Test-Path $Shortcut) { Remove-Item -Force $Shortcut }
    Set-UserPath $BinDir $false
    Write-Host "done (settings in the registry under HKCU\Software\repo-numbat were kept)"
    exit 0
}

Write-Host "installing program files to $Prefix"
New-Item -ItemType Directory -Force $Prefix | Out-Null
foreach ($item in @("repo_numbat", "scripts", "tools", "packaging", "requirements.txt", "pyproject.toml", "README.md", "LICENSE")) {
    $dest = Join-Path $Prefix $item
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Copy-Item -Recurse (Join-Path $Src $item) $dest
}
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $Prefix | Remove-Item -Recurse -Force

Write-Host "creating the virtualenv"
$Venv = Join-Path $Prefix ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $Venv } else { python -m venv $Venv }
    if (-not (Test-Path $Py)) { throw "could not create a virtualenv; install Python 3.10+ from python.org and tick 'Add to PATH'" }
}
& $Py -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Py -m pip install --upgrade pip | Out-Null
    & $Py -m pip install -r (Join-Path $Prefix "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

Write-Host "creating the repo-numbat command"
New-Item -ItemType Directory -Force $BinDir | Out-Null
@"
@echo off
rem Repo Numbat command-line entry (installed by install.ps1)
set "PYTHONPATH=$Prefix;%PYTHONPATH%"
echo %* | find "--cli" >nul
if errorlevel 1 (
    start "" "$Venv\Scripts\pythonw.exe" -m repo_numbat %*
) else (
    "$Py" -m repo_numbat %*
)
"@ | Set-Content -Encoding ASCII (Join-Path $BinDir "repo-numbat.cmd")
Set-UserPath $BinDir $true

Write-Host "creating the Start Menu shortcut"
$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut($Shortcut)
$Lnk.TargetPath = Join-Path $Venv "Scripts\pythonw.exe"
$Lnk.Arguments = "-m repo_numbat"
$Lnk.WorkingDirectory = $Prefix
$Lnk.IconLocation = Join-Path $Prefix "repo_numbat\assets\numbat.ico"
$Lnk.Description = "Status of every git repository under ~\repos"
$Lnk.Save()

Write-Host "installed: $Prefix"
Write-Host "           $Shortcut"
Write-Host "           $BinDir\repo-numbat.cmd  (open a new terminal for PATH to update)"
