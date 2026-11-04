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
if ([Environment]::OSVersion.Platform -ne "Win32NT") { throw "Sous Linux/macOS, utiliser scripts/start.sh." }
$fatCheckArguments = @((Join-Path $PSScriptRoot "check-kit.py"), "--root", $fatRoot)
if ($Engineering) { $fatCheckArguments += "--engineering" }
if (!(Test-Path -LiteralPath $fatVenvPython)) {
    $fatPython = $Python
    if (!$fatPython -and (Get-Command py -ErrorAction SilentlyContinue)) {
        try {
            $fatPython = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -ne 0) { $fatPython = "" }
        } catch { $fatPython = "" }
    }
    if (!$fatPython -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $fatPython = & python -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0) { $fatPython = "" }
    }
    if (!$fatPython) { throw "Python 3.12 x64 est requis. Installer Python puis relancer Start-FAT.cmd." }
    & $fatPython @fatCheckArguments
    if ($LASTEXITCODE -ne 0) { throw "Verification du Python ou du kit echouee. Voir le diagnostic ci-dessus." }
    & $fatPython -m venv $fatVenv
    if ($LASTEXITCODE -ne 0) { throw "Creation de l'environnement Python impossible." }
}
& $fatVenvPython @fatCheckArguments
if ($LASTEXITCODE -ne 0) { throw "Verification de l'environnement ou du kit echouee. Voir le diagnostic ci-dessus." }
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
    if ($LASTEXITCODE -ne 0) { throw "Installation du paquet Vanguard FAT Studio impossible." }
    & $fatVenvPython -m fat_studio doctor
    if ($LASTEXITCODE -ne 0) { throw "Le diagnostic local a detecte une installation incomplete." }
} finally { Pop-Location }
Write-Host "Installation terminee. Lancer Start-FAT.cmd."
