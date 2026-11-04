[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$DataDir = "",
    [switch]$NoBrowser,
    [switch]$Repair
)
$ErrorActionPreference = "Stop"
$fatRoot = Split-Path -Parent $PSScriptRoot
$fatPython = Join-Path $fatRoot ".venv\Scripts\python.exe"
$fatCommand = Join-Path $fatRoot ".venv\Scripts\vanguard-fat-studio.exe"
if ($Repair -or !(Test-Path -LiteralPath $fatPython) -or !(Test-Path -LiteralPath $fatCommand)) {
    & (Join-Path $PSScriptRoot "setup.ps1")
}
if (!(Test-Path -LiteralPath $fatCommand)) { throw "Installation incomplete : vanguard-fat-studio.exe est absent." }
$fatArguments = @("-m", "fat_studio", "serve", "--host", "127.0.0.1", "--port", "$Port")
if ($DataDir) { $fatArguments += @("--data-dir", $DataDir) }
if ($NoBrowser) { $fatArguments += "--no-browser" }
Push-Location $fatRoot
try {
    & $fatPython @fatArguments
    if ($LASTEXITCODE -ne 0) { throw "Vanguard FAT Studio s'est termine avec le code $LASTEXITCODE." }
} finally { Pop-Location }
