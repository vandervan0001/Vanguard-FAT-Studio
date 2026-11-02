[CmdletBinding()]
param([string]$Python = "", [switch]$Engineering)
$ErrorActionPreference = "Stop"
$fatRoot = Split-Path -Parent $PSScriptRoot
$fatVenv = Join-Path $fatRoot ".venv"
$fatVenvPython = Join-Path $fatVenv "Scripts\python.exe"
$fatWheelhouse = Join-Path $fatRoot "wheelhouse"
$fatManifestPath = Join-Path $fatRoot "offline-manifest.json"
if (!(Test-Path -LiteralPath (Join-Path $fatRoot "fat_studio\web\index.html"))) {
    throw "Interface compilee absente. Utiliser l'archive complete ou compiler frontend puis executer scripts/build-web.py."
}
if (Test-Path -LiteralPath $fatManifestPath) {
    Write-Host "Verification des fichiers du kit hors ligne..."
    $fatManifest = Get-Content -LiteralPath $fatManifestPath -Raw | ConvertFrom-Json
    if ($fatManifest.schema -ne 1 -or $fatManifest.python -ne "3.12") { throw "Format de kit hors ligne incompatible." }
    $fatKnownFiles = @{}
    foreach ($fatItem in $fatManifest.files) {
        $fatRelative = [string]$fatItem.path
        $fatFullPath = [IO.Path]::GetFullPath((Join-Path $fatRoot $fatRelative))
        if (!$fatFullPath.StartsWith($fatRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Chemin invalide dans le manifeste." }
        if (!(Test-Path -LiteralPath $fatFullPath -PathType Leaf)) { throw "Fichier du kit absent : $fatRelative" }
        $fatHash = (Get-FileHash -LiteralPath $fatFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($fatHash -ne $fatItem.sha256) { throw "Empreinte incorrecte : $fatRelative" }
        $fatKnownFiles[$fatRelative.Replace('\','/')] = $true
    }
    foreach ($fatWheel in Get-ChildItem -LiteralPath $fatWheelhouse -File) {
        if (!$fatKnownFiles.ContainsKey("wheelhouse/" + $fatWheel.Name)) { throw "Wheel non repertoriee dans le kit : $($fatWheel.Name)" }
    }
}
if (!(Test-Path -LiteralPath $fatVenvPython)) {
    $fatPython = $Python
    if (!$fatPython -and (Get-Command py -ErrorAction SilentlyContinue)) {
        $fatPython = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0) { $fatPython = "" }
    }
    if (!$fatPython -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $fatPython = & python -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0) { $fatPython = "" }
    }
    if (!$fatPython) { throw "Python 3.12 x64 est requis. Installer Python puis relancer Start-FAT.cmd." }
    & $fatPython -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Ce lanceur est prevu pour Python 3.12. Choisir ce Python avec setup.ps1 -Python CHEMIN." }
    & $fatPython -m venv $fatVenv
    if ($LASTEXITCODE -ne 0) { throw "Creation de l'environnement Python impossible." }
}
& $fatVenvPython -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)"
if ($LASTEXITCODE -ne 0) { throw "L'environnement .venv existant n'utilise pas Python 3.12. Le renommer puis relancer." }
$fatPipOptions = @("--disable-pip-version-check")
if (Test-Path -LiteralPath $fatWheelhouse) {
    if (!(Test-Path -LiteralPath $fatManifestPath)) { throw "wheelhouse presente sans offline-manifest.json : kit incomplet." }
    $fatPipOptions += @("--no-index", "--find-links", $fatWheelhouse)
    Write-Host "Installation hors ligne, sans acces a un index externe."
} else { Write-Host "Installation des versions verrouillees ; un acces a PyPI est necessaire cette premiere fois." }
Push-Location $fatRoot
try {
    & $fatVenvPython -m pip install @fatPipOptions -r (Join-Path $fatRoot "requirements.lock")
    if ($LASTEXITCODE -ne 0) { throw "Installation des dependances runtime impossible." }
    if ($Engineering) {
        & $fatVenvPython -m pip install @fatPipOptions -r (Join-Path $fatRoot "requirements-engineering.lock")
        if ($LASTEXITCODE -ne 0) { throw "Installation du composant d'ingenierie impossible." }
    }
    & $fatVenvPython -m pip install @fatPipOptions --no-deps --no-build-isolation .
    if ($LASTEXITCODE -ne 0) { throw "Installation du paquet FAT Studio impossible." }
    & $fatVenvPython -m fat_studio doctor
    if ($LASTEXITCODE -ne 0) { throw "Le diagnostic local a detecte une installation incomplete." }
} finally { Pop-Location }
Write-Host "Installation terminee. Lancer Start-FAT.cmd."
