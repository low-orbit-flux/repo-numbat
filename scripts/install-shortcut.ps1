# Windows: create a Start Menu shortcut with the numbat icon.
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StartMenu = [Environment]::GetFolderPath("Programs")
$Shell = New-Object -ComObject WScript.Shell
$Lnk = $Shell.CreateShortcut((Join-Path $StartMenu "Repo Numbat.lnk"))
$Lnk.TargetPath = Join-Path $Project "scripts\repo-numbat.bat"
$Lnk.WorkingDirectory = $Project
$Lnk.IconLocation = Join-Path $Project "repo_numbat\assets\numbat.ico"
$Lnk.Description = "Status of every git repository under ~\repos"
$Lnk.Save()
Write-Host "created $StartMenu\Repo Numbat.lnk"
