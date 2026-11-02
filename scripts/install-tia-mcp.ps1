[CmdletBinding()]
param(
    [ValidateSet('V20', 'V21')][string]$TiaVersion,
    [string]$ToolDirectory = '',
    [string]$OpennessDirectory = '',
    [string]$SourceDirectory = '',
    [string]$Python = '',
    [string]$PackageSource = '',
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = Split-Path $PSScriptRoot -Parent
$PinnedVersion = '4.3.0'
$PinnedCommit = '10c5de2eb44c0362792cd141370b3f42f92f6ecd'

if ($env:OS -ne 'Windows_NT') {
    throw 'TIA Portal Openness requires Windows. The FAT demo does not require this optional installation.'
}
if (-not $TiaVersion) {
    if ([Console]::IsInputRedirected) { throw 'Select -TiaVersion V20 or -TiaVersion V21 explicitly.' }
    $TiaVersion = (Read-Host 'Version TIA Portal a utiliser : V20 ou V21').Trim().ToUpperInvariant()
    if ($TiaVersion -notin @('V20', 'V21')) { throw 'Select V20 or V21. No version was installed.' }
}
$TiaVersion = $TiaVersion.ToUpperInvariant()
if ($TiaVersion -eq 'V21' -and $SourceDirectory) {
    throw 'V21 uses the unmodified pinned NuGet package; SourceDirectory is only for the V20 source build.'
}
if ($Offline -and -not $PackageSource) {
    throw '-Offline requires -PackageSource pointing to a prepared local NuGet package directory.'
}
if ($Offline -and $TiaVersion -eq 'V20' -and -not $SourceDirectory) {
    throw 'Offline V20 also requires -SourceDirectory pointing to a clean checkout at the pinned commit.'
}
if ($SourceDirectory) { $SourceDirectory = [IO.Path]::GetFullPath($SourceDirectory) }
if ($Offline) { $PackageSource = (Resolve-Path -LiteralPath $PackageSource -ErrorAction Stop).Path }
elseif ($PackageSource -and (Test-Path -LiteralPath $PackageSource -ErrorAction SilentlyContinue)) {
    $PackageSource = (Resolve-Path -LiteralPath $PackageSource).Path
}
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw 'Install the stable .NET 10 SDK (10.0.400 or later), then retry.'
}
$SdkOutput = @(& dotnet --list-sdks)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect installed .NET SDKs.' }
$SdkFound = @($SdkOutput | Where-Object {
    $_ -match '^10\.0\.(\d+) ' -and [int]$Matches[1] -ge 400
}).Count -gt 0
if (-not $SdkFound) { throw 'TiaMcpServer 4.3.0 requires stable .NET 10 SDK 10.0.400 or later.' }

$FatPythonPrefix = @()
if ($Python) {
    $FatPython = (Get-Command $Python -ErrorAction Stop).Source
} elseif (Test-Path -LiteralPath (Join-Path $Root '.venv\Scripts\python.exe')) {
    $FatPython = Join-Path $Root '.venv\Scripts\python.exe'
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $FatPython = (Get-Command py).Source
    $FatPythonPrefix = @('-3.12')
} else {
    throw 'Install Python 3.12 or pass -Python with its executable path.'
}
function Invoke-FatPython {
    param([string[]]$Arguments)
    & $FatPython @FatPythonPrefix @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'TIA installation validation failed; inspect the Python diagnostic above.' }
}
function Read-OpennessAssemblies {
    $Records = @()
    foreach ($Name in @('Siemens.Engineering.Base', 'Siemens.Engineering.Step7', 'Siemens.Engineering.WinCCUnified')) {
        $Dll = Join-Path $OpennessDirectory ($Name + '.dll')
        if (-not (Test-Path -LiteralPath $Dll -PathType Leaf)) { throw "Missing real Siemens assembly: $Dll" }
        $Identity = [System.Reflection.AssemblyName]::GetAssemblyName($Dll)
        if ($Identity.Name -ne $Name -or $Identity.Version.Major -ne [int]$TiaVersion.Substring(1)) {
            throw "Openness assembly '$Dll' does not match selected $TiaVersion. No fallback to another version is allowed."
        }
        $Records += [PSCustomObject]@{
            name = $Name; path = $Dll; version = $Identity.Version.ToString()
            sha256 = (Get-FileHash -LiteralPath $Dll -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return $Records
}

if (-not $ToolDirectory) { $ToolDirectory = Join-Path $Root ('.tools\tia-mcp-' + $TiaVersion.ToLowerInvariant()) }
$ToolDirectory = [System.IO.Path]::GetFullPath($ToolDirectory)
if (-not $OpennessDirectory) {
    $OpennessDirectory = Join-Path $env:ProgramFiles ('Siemens\Automation\Portal ' + $TiaVersion + '\PublicAPI\' + $TiaVersion + '\net48')
}
$OpennessDirectory = (Resolve-Path -LiteralPath $OpennessDirectory -ErrorAction Stop).Path
if ($OpennessDirectory.StartsWith($ToolDirectory + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Use the real external Siemens installation, not DLLs inside the MCP output directory.'
}
$AssembliesBefore = @(Read-OpennessAssemblies)
$ExecutableName = if ($TiaVersion -eq 'V20') { 'TiaMcpServer.exe' } else { 'tia-mcp.exe' }
$Executable = Join-Path $ToolDirectory $ExecutableName
$ProfilePath = Join-Path $ToolDirectory 'fat-tia-profile.json'
$AlreadyInstalled = Test-Path -LiteralPath $Executable -PathType Leaf
if ((Test-Path -LiteralPath $ToolDirectory) -and -not $AlreadyInstalled) {
    throw 'The destination already exists without its expected server. Use a new ToolDirectory; existing files are preserved.'
}
if ($AlreadyInstalled -and -not (Test-Path -LiteralPath $ProfilePath)) {
    throw 'Existing server has no verified version profile. Use a new ToolDirectory; it will not be adopted or overwritten.'
}

$RecordDirectory = Join-Path $Root ('.local\tia-install-' + $TiaVersion.ToLowerInvariant() + '-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $RecordDirectory -ErrorAction Stop | Out-Null
$OpennessRecord = Join-Path $RecordDirectory 'openness-before-build.json'
[IO.File]::WriteAllText($OpennessRecord, ($AssembliesBefore | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
$SourceReport = $null
$TemporaryConfig = $null
$ApiVariable = 'TiaPortal' + $TiaVersion + 'Dir'
$PreviousApiDirectory = [Environment]::GetEnvironmentVariable($ApiVariable, 'Process')
[Environment]::SetEnvironmentVariable($ApiVariable, $OpennessDirectory, 'Process')
Push-Location $Root
try {
    Invoke-FatPython -Arguments @('-c', 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"')
    if (Test-Path -LiteralPath $ProfilePath) {
        Invoke-FatPython -Arguments @('-m', 'integrations.tia_versions', 'check-profile', '--server', $Executable, '--tia-version', $TiaVersion)
    }
    if (-not $AlreadyInstalled) {
        if ($Offline) {
            $PackageSource = (Resolve-Path -LiteralPath $PackageSource).Path
            $TemporaryConfig = [IO.Path]::GetTempFileName()
            $EscapedSource = [Security.SecurityElement]::Escape($PackageSource)
            $NugetConfig = "<?xml version=`"1.0`" encoding=`"utf-8`"?><configuration><packageSources><clear /><add key=`"offline`" value=`"$EscapedSource`" /></packageSources></configuration>"
            [IO.File]::WriteAllText($TemporaryConfig, $NugetConfig, [Text.UTF8Encoding]::new($false))
        }
        if ($TiaVersion -eq 'V21') {
            $InstallArgs = @('tool', 'install', 'TiaMcpServer', '--tool-path', $ToolDirectory, '--version', $PinnedVersion)
            if ($Offline) { $InstallArgs += @('--configfile', $TemporaryConfig) }
            elseif ($PackageSource) { $InstallArgs += @('--add-source', $PackageSource) }
            & dotnet @InstallArgs
            if ($LASTEXITCODE -ne 0) { throw 'Pinned V21 TiaMcpServer installation failed.' }
        } else {
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required to inspect the pinned V20 source checkout.' }
            if (-not $SourceDirectory) {
                $SourceDirectory = $ToolDirectory + '.source'
                if (Test-Path -LiteralPath $SourceDirectory) { throw 'Source destination exists. Pass a different clean SourceDirectory.' }
                & git clone --depth 1 --branch v4.3.0 --single-branch https://github.com/Czarnak/tia-portal-mcp.git $SourceDirectory
                if ($LASTEXITCODE -ne 0) { throw 'Cannot clone the pinned upstream source.' }
            }
            $SourceDirectory = (Resolve-Path -LiteralPath $SourceDirectory -ErrorAction Stop).Path
            if ($ToolDirectory.StartsWith($SourceDirectory + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Use a publish destination outside the dedicated source checkout.'
            }
            if ($OpennessDirectory.StartsWith($SourceDirectory + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Do not use reference stubs or DLLs from the source checkout as Siemens assemblies.'
            }
            $SourceReport = Join-Path $RecordDirectory 'source-retarget.json'
            Invoke-FatPython -Arguments @('-m', 'integrations.prepare_tia_server', 'prepare-source', '--source', $SourceDirectory, '--tia-version', 'V20', '--report', $SourceReport)
            $ProjectFile = Join-Path $SourceDirectory 'TiaMcpServer\TiaMcpServer.csproj'
            $WorkerProjectFile = Join-Path $SourceDirectory 'TiaMcpServer.OpennessWorker\TiaMcpServer.OpennessWorker.csproj'
            $BuildProperties = @(
                '-p:UseTiaPortalReferenceStubs=false', ('-p:TiaPortalV20Dir=' + $OpennessDirectory), '-p:PackAsTool=false',
                ('-p:Version=' + $PinnedVersion), ('-p:PackageVersion=' + $PinnedVersion),
                ('-p:InformationalVersion=' + $PinnedVersion), '-p:IncludeSourceRevisionInInformationalVersion=false'
            )
            $RestoreSourceArgs = @()
            if ($Offline) { $RestoreSourceArgs = @('--configfile', $TemporaryConfig) }
            elseif ($PackageSource) { $RestoreSourceArgs = @('--source', $PackageSource) }
            $WorkerRestoreArgs = @('restore', $WorkerProjectFile, '-m:1') + $BuildProperties + $RestoreSourceArgs
            $RestoreArgs = @('restore', $ProjectFile, '--runtime', 'win-x64', '-m:1') + $BuildProperties + $RestoreSourceArgs
            Push-Location $SourceDirectory
            try {
                & dotnet @WorkerRestoreArgs
                if ($LASTEXITCODE -ne 0) { throw 'V20 net48 worker restore failed. No stub or V21 fallback was attempted.' }
                & dotnet @RestoreArgs
                if ($LASTEXITCODE -ne 0) { throw 'V20 dependency restore failed. No stub or V21 fallback was attempted.' }
                & dotnet publish $ProjectFile -m:1 --configuration Release --runtime win-x64 --self-contained false --no-restore --output $ToolDirectory @BuildProperties
                if ($LASTEXITCODE -ne 0) {
                    throw 'The native V20 source build failed. The selected Siemens API is not qualified; inspect the compiler diagnostics. No installation profile was written.'
                }
            } finally {
                Pop-Location
            }
        }
    }

    $AssembliesAfter = @(Read-OpennessAssemblies)
    for ($Index = 0; $Index -lt $AssembliesBefore.Count; $Index++) {
        if ($AssembliesBefore[$Index].sha256 -ne $AssembliesAfter[$Index].sha256) {
            throw 'A Siemens assembly changed during installation. No installation profile was written.'
        }
    }
    if (@(Get-ChildItem -LiteralPath $ToolDirectory -Recurse -File -Filter 'Siemens.Engineering.*.dll').Count -gt 0) {
        throw 'The publish output contains Siemens DLLs. Keep those in the external licensed TIA installation.'
    }
    $InstalledVersion = (& $Executable --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $InstalledVersion -ne $PinnedVersion) {
        throw "Installed version '$InstalledVersion' does not match pinned '$PinnedVersion'."
    }
    & $Executable doctor
    if ($LASTEXITCODE -ne 0) { throw 'The upstream doctor failed. Correct Windows/TIA/Openness prerequisites before using this profile.' }
    if (-not (Test-Path -LiteralPath $ProfilePath)) {
        $ProfileArgs = @('-m', 'integrations.tia_versions', 'write-profile', '--server', $Executable, '--tia-version', $TiaVersion, '--openness-record', $OpennessRecord)
        if ($SourceReport) { $ProfileArgs += @('--source-report', $SourceReport) }
        Invoke-FatPython -Arguments $ProfileArgs
    }
    Invoke-FatPython -Arguments @('-m', 'integrations.tia_versions', 'check-profile', '--server', $Executable, '--tia-version', $TiaVersion)
} finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable($ApiVariable, $PreviousApiDirectory, 'Process')
    if ($TemporaryConfig -and (Test-Path -LiteralPath $TemporaryConfig)) { Remove-Item -LiteralPath $TemporaryConfig }
}
Write-Host "$TiaVersion engineering profile installed: $Executable"
Write-Host "Source reference: Czarnak $PinnedVersion / $PinnedCommit. Complete native TIA acceptance on an authorized work copy."
Write-Host 'AI clients remain read-only. Imports, compilation and saving use the human confirmation workflow in docs/TIA_MCP.md.'
