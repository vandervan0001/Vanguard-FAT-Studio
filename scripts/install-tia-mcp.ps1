[CmdletBinding()]
param(
    [string]$ToolDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) '.tools\tia-mcp'),
    [string]$PackageSource = '',
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PinnedVersion = '4.3.0'

if ($env:OS -ne 'Windows_NT') {
    throw 'TIA Portal Openness requires Windows. The FAT demo itself does not require this optional installation.'
}
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw 'Install the stable .NET 10 SDK (10.0.400 or later in the .NET 10 feature bands), then retry.'
}
$SdkFound = @(& dotnet --list-sdks | Where-Object {
    $_ -match '^10\.0\.(\d+) ' -and [int]$Matches[1] -ge 400
}).Count -gt 0
if (-not $SdkFound) {
    throw 'No supported stable .NET 10 SDK found. TiaMcpServer 4.3.0 specifies 10.0.400 or later.'
}
if ($Offline -and -not $PackageSource) {
    throw '-Offline requires -PackageSource pointing to a prepared local NuGet package directory.'
}

$ToolDirectory = [System.IO.Path]::GetFullPath($ToolDirectory)
$Executable = Join-Path $ToolDirectory 'tia-mcp.exe'
if (Test-Path $Executable) {
    $ExistingVersion = (& $Executable --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $ExistingVersion -ne $PinnedVersion) {
        throw "Existing tool is '$ExistingVersion', expected '$PinnedVersion'. Use a different ToolDirectory; do not silently update this audited version."
    }
} else {
    $InstallArgs = @('tool', 'install', 'TiaMcpServer', '--tool-path', $ToolDirectory, '--version', $PinnedVersion)
    $TemporaryConfig = $null
    try {
        if ($Offline) {
            $PackageSource = (Resolve-Path $PackageSource).Path
            $TemporaryConfig = [System.IO.Path]::GetTempFileName()
            $EscapedSource = [System.Security.SecurityElement]::Escape($PackageSource)
            $NugetConfig = "<?xml version=`"1.0`" encoding=`"utf-8`"?><configuration><packageSources><clear /><add key=`"offline`" value=`"$EscapedSource`" /></packageSources></configuration>"
            [System.IO.File]::WriteAllText($TemporaryConfig, $NugetConfig, [System.Text.UTF8Encoding]::new($false))
            $InstallArgs += @('--configfile', $TemporaryConfig)
        } elseif ($PackageSource) {
            $InstallArgs += @('--add-source', $PackageSource)
        }
        & dotnet @InstallArgs
        if ($LASTEXITCODE -ne 0) { throw 'Pinned TiaMcpServer installation failed.' }
    } finally {
        if ($TemporaryConfig -and (Test-Path $TemporaryConfig)) { Remove-Item -LiteralPath $TemporaryConfig }
    }
}

$InstalledVersion = (& $Executable --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $InstalledVersion -ne $PinnedVersion) {
    throw "Installed version '$InstalledVersion' does not match the pinned version '$PinnedVersion'."
}
& $Executable doctor
if ($LASTEXITCODE -ne 0) {
    throw 'The upstream doctor found missing Windows/TIA/Openness prerequisites. Correct the reported items before using the integration.'
}
Write-Host "Pinned engineering server ready: $Executable"
Write-Host 'Register AI clients only with --access-mode read-only and an explicit --project work-copy path.'
Write-Host 'See docs/TIA_MCP.md for policy creation, reviewed imports and explicit human approvals.'
