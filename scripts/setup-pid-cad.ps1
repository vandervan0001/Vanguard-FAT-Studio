<# Install optional GNU LibreDWG locally. No administrator rights or global PATH change.
   GPL-3.0-or-later binaries and matching source stay outside public FAT packages. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$pidCadRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.tools/pid-cad'))
$pidCadVersion = '0.14'
$pidCadCommit = 'd9468ae948b8f07a08efa756c19f8916052358c0'
$pidCadArchiveName = 'libredwg-0.14-win64.zip'
$pidCadUrl = 'https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14-win64.zip'
$pidCadHash = '1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8'
$pidCadSourceUrl = 'https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14.tar.gz'
$pidCadSourceHash = 'cb6ee0b078c6d9e0f09d66f1feac33ba6342df88ae544e9f9335fab475218351'
if (-not [Environment]::Is64BitOperatingSystem) { throw 'LibreDWG sélectionné requiert Windows x64.' }
New-Item -ItemType Directory -Force -Path (Join-Path $pidCadRoot 'downloads') | Out-Null
$pidCadArchive = Join-Path $pidCadRoot "downloads/$pidCadArchiveName"
$pidCadSources = Join-Path $pidCadRoot 'downloads/libredwg-0.14.tar.gz'
foreach ($pidCadDownload in @(
    @{Path=$pidCadArchive; Url=$pidCadUrl; Hash=$pidCadHash},
    @{Path=$pidCadSources; Url=$pidCadSourceUrl; Hash=$pidCadSourceHash}
)) {
    if (-not (Test-Path -LiteralPath $pidCadDownload.Path)) {
        Invoke-WebRequest -Uri $pidCadDownload.Url -OutFile $pidCadDownload.Path
    }
    $pidCadActualHash = (Get-FileHash -LiteralPath $pidCadDownload.Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($pidCadActualHash -ne $pidCadDownload.Hash) { throw "SHA-256 inattendu : $($pidCadDownload.Path). Fichier conservé pour inspection." }
}
$pidCadInstall = Join-Path $pidCadRoot 'libredwg-0.14-win64'
if (-not (Test-Path -LiteralPath $pidCadInstall)) {
    Expand-Archive -LiteralPath $pidCadArchive -DestinationPath $pidCadInstall
}
$pidCadTools = @{}
$pidCadExpectedTools = @{
    'dwg2dxf.exe'='955f5f2855bc0c5a8bd7a93424ea259ab14405799638b889b2b3c5918c529e3e'
    'dxf2dwg.exe'='83ec3ab0227dc203169fe42fa5d396f3f314e76446ad499b70aa9dadeab2aa61'
}
foreach ($pidCadTool in @('dwg2dxf.exe', 'dxf2dwg.exe')) {
    $pidCadExecutable = Join-Path $pidCadInstall $pidCadTool
    if (-not (Test-Path -LiteralPath $pidCadExecutable)) { throw "Exécutable absent : $pidCadTool" }
    $pidCadTools[$pidCadTool] = (Get-FileHash -LiteralPath $pidCadExecutable -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($pidCadTools[$pidCadTool] -ne $pidCadExpectedTools[$pidCadTool]) {
        throw "L'exécutable local $pidCadTool ne correspond pas à la release épinglée. Installation conservée pour inspection."
    }
    & $pidCadExecutable --version
    if ($LASTEXITCODE -ne 0) { throw "Échec du contrôle $pidCadTool" }
}
@{
    engine='GNU LibreDWG'; version=$pidCadVersion; commit=$pidCadCommit
    license='GPL-3.0-or-later'; release='https://github.com/LibreDWG/libredwg/releases/tag/0.14'
    binary_url=$pidCadUrl; binary_sha256=$pidCadHash; source_url=$pidCadSourceUrl
    source_sha256=$pidCadSourceHash; tools_sha256=$pidCadTools
    installed_at=[DateTime]::UtcNow.ToString('o')
    distribution='Local optional installation only; do not include in a public FAT Studio package without a separate GPL compliance review.'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $pidCadRoot 'provenance.json') -Encoding utf8
Write-Output "LibreDWG local prêt : $pidCadInstall. Export DWG R2000 expérimental."
