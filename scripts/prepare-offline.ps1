[CmdletBinding()]
param([string]$Destination = "", [string]$Python = "", [switch]$Engineering)
$ErrorActionPreference = "Stop"
$fatRoot = Split-Path -Parent $PSScriptRoot
if ([Environment]::OSVersion.Platform -ne "Win32NT") { throw "Preparer le kit Windows sur un poste Windows x64 avec Python 3.12 x64." }
if (!(Test-Path -LiteralPath (Join-Path $fatRoot "fat_studio\web\index.html"))) { throw "Compiler et integrer l'interface avant de preparer le kit." }
if (!$Destination) { $Destination = Join-Path (Split-Path -Parent $fatRoot) "fat-studio-offline-windows" }
$fatDestination = [IO.Path]::GetFullPath($Destination)
if ($fatDestination.StartsWith($fatRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $fatDestination -eq $fatRoot) {
    throw "Le dossier du kit doit etre en dehors du depot source."
}
if (Test-Path -LiteralPath $fatDestination) { throw "Le dossier destination existe deja ; choisir un nouveau dossier pour ne rien ecraser." }
$fatPython = $Python
if (!$fatPython -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $fatPython = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0) { $fatPython = "" }
}
if (!$fatPython) { throw "Python 3.12 x64 est requis ; utiliser -Python CHEMIN si necessaire." }
& $fatPython -c "import struct,sys,sysconfig; sys.exit(0 if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 and sysconfig.get_platform() == 'win-amd64' else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 x64 est requis pour generer les wheels Windows correspondantes." }
New-Item -ItemType Directory -Path $fatDestination | Out-Null
$fatFolders = @("fat_studio", "frontend", "integrations", "scripts", "docs", "evidence", "examples", "siemens", "tests", ".github")
foreach ($fatFolder in $fatFolders) {
    $fatSource = Join-Path $fatRoot $fatFolder
    if (!(Test-Path -LiteralPath $fatSource)) { continue }
    foreach ($fatFile in Get-ChildItem -LiteralPath $fatSource -Recurse -File -Force) {
        $fatRelative = $fatFile.FullName.Substring($fatRoot.Length + 1)
        if ($fatRelative -match '(^|[\\/])(__pycache__|node_modules|\.venv|\.pytest_cache|\.ruff_cache|test-results|playwright-report|\.local|\.tools)([\\/]|$)' -or $fatRelative -match '^frontend[\\/]dist([\\/]|$)' -or $fatFile.Extension -in @(".pyc", ".tsbuildinfo", ".pem", ".key", ".pfx", ".cer") -or $fatFile.Name -match '^\.env($|\.)' -or ($fatFile.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        $fatTarget = Join-Path $fatDestination $fatRelative
        New-Item -ItemType Directory -Path (Split-Path -Parent $fatTarget) -Force | Out-Null
        Copy-Item -LiteralPath $fatFile.FullName -Destination $fatTarget
    }
}
foreach ($fatFile in Get-ChildItem -LiteralPath $fatRoot -File -Force) {
    if ($fatFile.Name -match '^(README.*|LICENSE.*|NOTICE.*|THIRD_PARTY.*|pyproject\.toml|MANIFEST\.in|requirements.*\.lock|Start-FAT\.cmd|\.gitignore|\.gitattributes)$') {
        Copy-Item -LiteralPath $fatFile.FullName -Destination (Join-Path $fatDestination $fatFile.Name)
    }
}
$fatWheelhouse = Join-Path $fatDestination "wheelhouse"
New-Item -ItemType Directory -Path $fatWheelhouse | Out-Null
$fatLocks = @("requirements.lock")
if ($Engineering) { $fatLocks += "requirements-engineering.lock" }
foreach ($fatLock in $fatLocks) {
    & $fatPython -m pip download --disable-pip-version-check --only-binary=:all: --dest $fatWheelhouse -r (Join-Path $fatRoot $fatLock)
    if ($LASTEXITCODE -ne 0) { throw "Telechargement impossible pour $fatLock ; le kit est incomplet, ne pas le distribuer." }
}
$fatFiles = @()
foreach ($fatFile in Get-ChildItem -LiteralPath $fatDestination -Recurse -File -Force | Sort-Object FullName) {
    $fatFiles += [ordered]@{
        path = $fatFile.FullName.Substring($fatDestination.Length + 1).Replace('\','/')
        size = $fatFile.Length
        sha256 = (Get-FileHash -LiteralPath $fatFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$fatManifest = [ordered]@{
    schema = 1
    platform = "Windows-x64"
    python = "3.12"
    engineering = [bool]$Engineering
    created_utc = [DateTime]::UtcNow.ToString("o")
    files = $fatFiles
}
$fatManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $fatDestination "offline-manifest.json") -Encoding UTF8
Write-Host "Kit pret : $fatDestination"
Write-Host "Copier aussi l'installateur officiel Python 3.12 x64 valide par l'IT si le poste cible n'en dispose pas."
Write-Host "Le runtime FAT demarre sans Internet. Siemens et tia-portal-mcp restent des installations distinctes."
