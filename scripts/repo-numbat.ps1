# Launcher for Windows PowerShell:  .\scripts\repo-numbat.ps1 [--cli] [--fetch] [--root DIR]
# If scripts are blocked, run once:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
$ErrorActionPreference = "Stop"
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Venv = Join-Path $Project ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$Pyw = Join-Path $Venv "Scripts\pythonw.exe"

if (-not (Test-Path $Py)) {
    Write-Host "repo-numbat: creating virtualenv in $Venv"
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv $Venv } else { python -m venv $Venv }
}
& $Py -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "repo-numbat: installing requirements"
    & $Py -m pip install --upgrade pip | Out-Null
    & $Py -m pip install -r (Join-Path $Project "requirements.txt")
}
$env:PYTHONPATH = "$Project;$env:PYTHONPATH"
if ($args -contains "--cli") {
    & $Py -m repo_numbat @args
} else {
    Start-Process -FilePath $Pyw -ArgumentList (@("-m", "repo_numbat") + $args) -WorkingDirectory $Project
}
