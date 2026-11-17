[CmdletBinding()]
param(
    [string]$WorkRoot = 'C:\FilDesk74',
    [string]$CacheRun = 'C:\FilDesk74\run-20261030-144938-c2e2d821',
    [string]$PriorKit = 'C:\FilDesk74\FilDesk-1.5.0-77-HelperGuard-TestCount-Local-Kit-20261030',
    [string]$DiagnosticSource = 'C:\FilDesk74\FilDesk-1.5.0-77-Diagnostic-20261116',
    [ValidateRange(1, 2)][int]$Jobs = 2,
    [switch]$ProductionCandidate
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
if (-not $IsWindows) { throw 'Windows build host required' }
function Check-Path([string]$Path) {
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point rejected: $current" }
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if ($parent -eq $current) { break }
        $current = $parent
    }
}
function Run-Native([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit $LASTEXITCODE" }
}
function Copy-Cache([string]$Source, [string]$Destination) {
    Check-Path $Source; Check-Path $Destination
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "Missing cache: $Source" }
    if (Test-Path -LiteralPath $Destination) { throw "Cache destination exists: $Destination" }
    $reparse = Get-ChildItem -LiteralPath $Source -Recurse -Force -Attributes ReparsePoint -ErrorAction Stop | Select-Object -First 1
    if ($reparse) { throw "Reparse point in cache: $($reparse.FullName)" }
    $old = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    try { & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ /NFL /NDL /NP; $code = $LASTEXITCODE }
    finally { $PSNativeCommandUseErrorActionPreference = $old }
    if ($code -ge 8) { throw "Cache copy failed: $code" }
}
$WorkRoot = (Resolve-Path -LiteralPath $WorkRoot).Path
$CacheRun = (Resolve-Path -LiteralPath $CacheRun).Path
$PriorKit = (Resolve-Path -LiteralPath $PriorKit).Path
$DiagnosticSource = (Resolve-Path -LiteralPath $DiagnosticSource).Path
foreach ($path in @($WorkRoot, $CacheRun, $PriorKit, $DiagnosticSource)) { Check-Path $path }
if ([IO.Path]::GetDirectoryName($CacheRun) -cne $WorkRoot) { throw 'Cache run must be direct child of work root' }
$python = Join-Path $WorkRoot 'tools\python\python.exe'
$kitTool = Join-Path $PriorKit 'kit.py'
Run-Native $python @($kitTool, 'verify', $PriorKit)
$receipt = Get-Content -LiteralPath (Join-Path $DiagnosticSource 'SOURCE-RECEIPT.json') -Raw | ConvertFrom-Json
$requiredPurpose = if ($ProductionCandidate) { 'LOCAL_PUBLICATION_CANDIDATE' } else { 'LOCAL_DIAGNOSTIC_BUILD_ONLY' }
if ($receipt.purpose -cne $requiredPurpose -or $receipt.version -cne '1.5.0+77') { throw 'Wrong candidate source receipt' }
$artifactEnvironment = if ($ProductionCandidate) { 'production-candidate' } else { 'staging' }
foreach ($kind in @('root','client')) {
    $archive = Join-Path $DiagnosticSource "$kind-snapshot.zip"
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $receipt."${kind}SnapshotSHA256") { throw "$kind snapshot hash mismatch" }
}
if ((Get-PSDrive ([IO.Path]::GetPathRoot($WorkRoot).Substring(0,1))).Free -lt 60GB) { throw '60 GiB free required; no automatic cleanup' }
$lock = [IO.File]::Open((Join-Path $WorkRoot 'build.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
$run = Join-Path $WorkRoot ('run-' + (Get-Date -Format yyyyMMdd-HHmmss) + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $run | Out-Null
$evidence = Join-Path $run 'evidence'
New-Item -ItemType Directory -Path $evidence | Out-Null
Copy-Item -LiteralPath (Join-Path $DiagnosticSource 'SOURCE-RECEIPT.json') -Destination (Join-Path $evidence 'SOURCE-RECEIPT.json')
$result = [ordered]@{ schema=1; purpose=$requiredPurpose; artifactEnvironment=$artifactEnvironment; version='1.5.0+77'; sourceSHA256=$receipt.clientSnapshotSHA256; status='RUNNING'; roleChecks=@{}; physicalAcceptance='NOT_RUN'; publicRelease='BLOCKED' }
function Save-Result { $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'RESULT.json') -Encoding utf8 }
Start-Transcript -Path (Join-Path $evidence 'build.log')
try {
    Save-Result
    $env:CARGO_HOME = Join-Path $WorkRoot 'cargo'
    $env:RUSTUP_HOME = Join-Path $WorkRoot 'rustup'
    $env:RUSTUP_TOOLCHAIN = '1.90.0-x86_64-pc-windows-msvc'
    $env:CARGO_BUILD_JOBS = "$Jobs"
    $env:CMAKE_BUILD_PARALLEL_LEVEL = "$Jobs"
    $env:VCPKG_MAX_CONCURRENCY = "$Jobs"
    $env:VCPKG_ROOT = Join-Path $WorkRoot 'vcpkg'
    $env:VCPKG_DEFAULT_HOST_TRIPLET = 'x64-windows-static'
    $env:VCPKG_BINARY_SOURCES = "clear;files,$WorkRoot/vcpkg-cache,readwrite"
    $env:LIBCLANG_PATH = "$env:ProgramFiles\LLVM\bin"
    $env:TEMP = Join-Path $run 'temp'; $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    $env:PATH = "$PSHOME;$WorkRoot/tools/git/cmd;$WorkRoot/tools/python;$WorkRoot/tools/node/node-v22.23.3-win-x64;$env:CARGO_HOME/bin;$env:LIBCLANG_PATH;$env:PATH"
    if ((& rustc --version) -notmatch '^rustc 1\.90\.0 ') { throw 'Wrong Rust toolchain' }
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'Existing Visual Studio C++ toolchain missing' }
    $names = 'PATH','INCLUDE','LIB','LIBPATH','VCINSTALLDIR','VCToolsInstallDir','WindowsSdkDir','WindowsSDKVersion','UniversalCRTSdkDir','UCRTVersion','VSINSTALLDIR','VisualStudioVersion'
    $lines = & cmd.exe /d /s /c "`"$vs\Common7\Tools\VsDevCmd.bat`" -arch=x64 -host_arch=x64 >nul && set"
    foreach ($line in $lines) { if ($line -match '^([^=]+)=(.*)$' -and $Matches[1] -in $names) { [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process') } }
    $basePath = "$PSHOME;$WorkRoot/tools/git/cmd;$WorkRoot/tools/python;$WorkRoot/tools/node/node-v22.23.3-win-x64;$env:CARGO_HOME/bin;$env:LIBCLANG_PATH;$env:PATH"
    foreach ($role in @('customer','operator')) {
        $root = Join-Path $run $role
        Run-Native $python @($kitTool,'extract',"$DiagnosticSource/root-snapshot.zip",$root)
        Run-Native $python @($kitTool,'extract',"$DiagnosticSource/client-snapshot.zip","$root/client")
        Run-Native git @('-C',$root,'config','core.autocrlf','false')
        Run-Native git @('-C',"$root/client",'config','core.autocrlf','false')
        $bridge = Join-Path $run "bridge-$role"
        Run-Native $python @($kitTool,'extract',"$PriorKit/fil-bridge.zip",$bridge)
        Run-Native $python @("$PriorKit/merge-bridge.py",$bridge,"$root/client")
        New-Item -ItemType Directory -Path "$root/build" | Out-Null
        $cachedFlutter = "$CacheRun/$role/build/flutter"
        if (-not (Test-Path -LiteralPath "$cachedFlutter/bin/flutter.bat")) { $cachedFlutter = "$CacheRun/customer/build/flutter" }
        if ((& git -C $cachedFlutter rev-parse HEAD) -cne 'dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668') { throw 'Flutter cache source pin mismatch' }
        Run-Native git @('clone','--no-hardlinks','--no-checkout',$cachedFlutter,"$root/build/flutter")
        Run-Native git @('-C',"$root/build/flutter",'config','core.autocrlf','false')
        Run-Native git @('-C',"$root/build/flutter",'checkout','--detach','dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668')
        Copy-Cache "$cachedFlutter/bin/cache" "$root/build/flutter/bin/cache"
        Copy-Cache "$CacheRun/$role/client/target" "$root/client/target"
        $env:PATH = "$root/build/flutter/bin;$basePath"
        $env:FIL_FLUTTER_ROOT = "$root/build/flutter"
        $env:FIL_PROFILE = $role
        $cfg = Get-Content -LiteralPath "$PriorKit/public-config.json" -Raw | ConvertFrom-Json
        $cfg.profile = $role
        if ($ProductionCandidate) { $cfg.environment = 'production' }
        $cfg | ConvertTo-Json | Set-Content -LiteralPath "$root/build/client.local.json" -Encoding utf8
        Push-Location $root
        try {
            & "$root/scripts/build-windows.ps1" -Config "$root/build/client.local.json" -Jobs $Jobs -EngineArchive "$PriorKit/engine.zip" -ReuseNativeDependencies -ProductionCandidate:$ProductionCandidate
            & "$PriorKit/Verify-Runtime-Version.ps1" -Executable "$root/client/flutter/build/windows/x64/runner/Release/FilDesk.exe" -Version '1.5.0+77'
            & "$PriorKit/Verify-Runtime-Version.ps1" -Executable "$root/artifacts/windows/$artifactEnvironment/$role/FilDesk.exe" -Version '1.5.0+77'
            $exe = "$root/artifacts/windows/$artifactEnvironment/$role/FilDesk.exe"
            $result.roleChecks[$role] = [ordered]@{ status='LOCAL_BUILD_PASS_PHYSICAL_NOT_RUN'; exeSHA256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant(); bytes=(Get-Item -LiteralPath $exe).Length }
            Save-Result
        } finally { Pop-Location }
    }
    $result.status = 'LOCAL_DIAGNOSTIC_PAIR_BUILT_PHYSICAL_NOT_RUN'
    Save-Result
    Write-Output "Local diagnostic pair: $run"
} catch {
    $result.status = 'FAILED'
    $result['error'] = $_.Exception.Message
    Save-Result
    throw
} finally {
    Stop-Transcript
    $lock.Dispose()
}
