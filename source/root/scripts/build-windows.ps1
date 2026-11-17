param(
    [Parameter(Mandatory=$true)][string]$Config,
    [string]$SigningConfig,
    [ValidateRange(1,2)][int]$Jobs=2,
    [string]$EngineArchive,
    [switch]$ReuseNativeDependencies,
    [switch]$ProductionCandidate
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
function Test-ReviewedPatch([string]$Patch, [switch]$Reverse) {
    # Expected nonzero preimage probe is not a failed build command.
    $PSNativeCommandUseErrorActionPreference = $false
    if ($Reverse) { git apply --reverse --check $Patch 2>$null }
    else { git apply --check $Patch 2>$null }
    return $LASTEXITCODE -eq 0
}
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$SourceIdentity = $null
$sourceIdentityPath = Join-Path $Root 'build/source-input-identity.json'
if (Test-Path -LiteralPath $sourceIdentityPath) {
    $SourceIdentity = Get-Content -LiteralPath $sourceIdentityPath -Raw | ConvertFrom-Json
    if ($SourceIdentity.kind -ne 'BASE_COMMITS_PLUS_REVIEWED_SNAPSHOT') { throw 'Unknown frozen source identity' }
    foreach ($component in @('root','client')) {
        if ($SourceIdentity.sourceBaseCommits.$component -notmatch '^[0-9a-f]{40}$' -or
            $SourceIdentity.sourceSnapshotSHA256.$component -notmatch '^[0-9a-f]{64}$' -or
            $SourceIdentity.reviewedDeltaSHA256.$component -notmatch '^[0-9a-f]{64}$') { throw 'Incomplete frozen source identity' }
    }
    if ($SourceIdentity.lockSHA256 -ne (Get-FileHash client/Cargo.lock -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Frozen Cargo lock mismatch' }
    if ((git rev-parse HEAD) -ne $SourceIdentity.sourceBaseCommits.root -or
        (git -C client rev-parse HEAD) -ne $SourceIdentity.sourceBaseCommits.client) { throw 'Frozen source base mismatch' }
}
if ($SigningConfig) { $SigningConfig=(Resolve-Path -LiteralPath $SigningConfig).Path }
$env:CARGO_BUILD_JOBS = [string]$Jobs
$env:CMAKE_BUILD_PARALLEL_LEVEL = [string]$Jobs
$env:VCPKG_MAX_CONCURRENCY = [string]$Jobs
python scripts/configure-client.py $Config
if ($LASTEXITCODE -ne 0) { throw 'Invalid public configuration' }
$cfg = Get-Content $Config -Raw | ConvertFrom-Json
if ($ProductionCandidate -and ($cfg.environment -ne 'production' -or $SigningConfig)) {
    throw 'ProductionCandidate requires production config and unsigned candidate output'
}
if ($cfg.environment -eq 'production' -and -not $ProductionCandidate) {
    python "$Root/scripts/release-gate.py"
    if ($LASTEXITCODE -ne 0) { throw 'Production release gate blocked' }
}
if (-not $IsWindows) { throw 'Native Windows x64 runner required' }
if (-not $env:VCPKG_ROOT) { throw 'Set VCPKG_ROOT to pinned vcpkg checkout' }
if (-not (Test-Path client/src/bridge_generated.rs)) { throw 'Generate Flutter Rust bridge first' }
$engine = Get-Content config/windows-engine.lock.json -Raw | ConvertFrom-Json
New-Item build -ItemType Directory -Force | Out-Null
if ($EngineArchive) {
    $EngineArchive=(Resolve-Path -LiteralPath $EngineArchive).Path
    if ((Get-FileHash -LiteralPath $EngineArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $engine.sha256) { throw 'Provided engine checksum mismatch' }
    Copy-Item -LiteralPath $EngineArchive -Destination build/engine.zip
} else { Invoke-WebRequest $engine.browser_download_url -OutFile build/engine.zip }
if ((Get-FileHash build/engine.zip -Algorithm SHA256).Hash.ToLower() -ne $engine.sha256) { throw 'Engine checksum mismatch' }
if (-not $ReuseNativeDependencies) {
    flutter precache --windows
    if ($LASTEXITCODE -ne 0) { throw 'Flutter Windows precache failed' }
}
$FlutterRoot = Split-Path (Split-Path (Get-Command flutter).Source -Parent) -Parent
Expand-Archive build/engine.zip build/engine -Force
Copy-Item build/engine/* "$FlutterRoot/bin/cache/artifacts/engine/windows-x64-release/" -Recurse -Force
Push-Location $FlutterRoot
try {
    $patch="$Root/client/.github/patches/flutter_3.24.4_dropdown_menu_enableFilter.diff"
    if (Test-ReviewedPatch $patch) {
        git apply $patch
        if ($LASTEXITCODE -ne 0) { throw 'Flutter dropdown patch failed' }
    } else {
        if (-not (Test-ReviewedPatch $patch -Reverse)) { throw 'Flutter SDK differs from both reviewed patch preimage and postimage' }
    }
} finally { Pop-Location }
Push-Location client
try {
    if ($ReuseNativeDependencies) {
        python "$Root/scripts/verify-native-cache.py" --vcpkg-root "$env:VCPKG_ROOT" --manifest "$Root/client/vcpkg.json"
        if ($LASTEXITCODE -ne 0) { throw 'Existing vcpkg cache incomplete or baseline mismatch; no reinstall attempted' }
    } else {
        & "$env:VCPKG_ROOT/vcpkg.exe" install --triplet x64-windows-static --x-install-root="$env:VCPKG_ROOT/installed"
        if ($LASTEXITCODE -ne 0) { throw 'vcpkg failed' }
    }
    Push-Location flutter
    try {
        flutter pub get --enforce-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'Flutter dependency lock validation failed' }
        flutter analyze --no-fatal-infos --no-fatal-warnings
        if ($LASTEXITCODE -ne 0) { throw 'Flutter analysis failed' }
    } finally { Pop-Location }
    # V1 uses software codecs; no --vram / CUDA / GPU / printer or display driver download.
    python build.py --flutter --portable --skip-portable-pack
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed' }
    $Release = 'flutter/build/windows/x64/runner/Release'
    if (-not (Test-Path "$Release/rustdesk.exe")) { throw 'Expected executable missing' }
    Move-Item "$Release/rustdesk.exe" "$Release/FilDesk.exe"
    Copy-Item LICENCE "$Release/LICENSE-RustDesk.txt"
    Copy-Item ../docs/licensing.md "$Release/SOURCE-NOTICE.md"
    if ($SigningConfig) {
        if ($cfg.environment -ne 'development') { throw 'Signing integration currently creates development candidates only; production gates remain mandatory' }
        & "$Root/scripts/signing/Build-SignedPortable.ps1" -PayloadDirectory "$Root/client/$Release" -OutputDirectory "$Root/artifacts/windows/signed-candidates/$($cfg.profile)" -SigningConfig $SigningConfig -Profile $cfg.profile
        return
    }
    $env:FIL_PROFILE=$cfg.profile
    $env:FIL_REQUIRE_AUTHENTICODE='0'
    Push-Location libs/portable
    try { python generate.py -f ../../flutter/build/windows/x64/runner/Release -o . -e FilDesk.exe } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Portable packer failed' }
    # Compilation precedes device/browser evidence. Candidates never enter the
    # production output path; final publication still requires release-gate.py.
    $outputEnvironment = if ($ProductionCandidate) { 'production-candidate' } else { $cfg.environment }
    $Dest = "$Root/artifacts/windows/$outputEnvironment/$($cfg.profile)"
    New-Item $Dest -ItemType Directory -Force | Out-Null
    Copy-Item target/release/rustdesk-portable-packer.exe "$Dest/FilDesk.exe"
    python "$Root/scripts/check-portable-load-flags.py" "$Dest/FilDesk.exe"
    if ($LASTEXITCODE -ne 0) { throw 'Portable loader policy missing' }
    Compress-Archive "$Release/*" "$Dest/FilDesk-bundle.zip" -Force
    $signature = Get-AuthenticodeSignature "$Dest/FilDesk.exe"
    if ($signature.Status -ne 'NotSigned') { throw 'Unexpected signature state; inspect before labeling' }
    $toolVersions = @{
        rust=(rustc -vV | Out-String); cargo=(cargo --version | Out-String)
        flutter=(flutter --version | Out-String); python=(python --version | Out-String)
        cmake=(cmake --version | Out-String); clang=(clang --version | Out-String)
        windows=(Get-CimInstance Win32_OperatingSystem).Version
    }
    $manifest = @{
        tools=$toolVersions
        product='FilDesk'; version=(([regex]::Match((Get-Content -Raw flutter/pubspec.yaml), '(?m)^version:\s*(\S+)')).Groups[1].Value); environment=$cfg.environment; profile=$cfg.profile
        built_at=(Get-Date).ToUniversalTime().ToString('o'); signing='unsigned-test'
        upstream=(git rev-parse HEAD); runner=$env:RUNNER_OS; runner_image=$env:ImageVersion
        project_commit=(git -C $Root rev-parse HEAD)
        source_input_identity=$SourceIdentity
        client_patch_sha256=(Get-FileHash "$Root/branding/patches/client.patch" -Algorithm SHA256).Hash.ToLower()
        client_lock_sha256=(Get-FileHash Cargo.lock -Algorithm SHA256).Hash.ToLower()
        public_config_sha256=(Get-FileHash src/fil_build_config.rs -Algorithm SHA256).Hash.ToLower()
        runtime_testing='NOT RUN'
        public_release='BLOCKED'
        production_candidate=[bool]$ProductionCandidate
        sha256=(Get-FileHash "$Dest/FilDesk.exe" -Algorithm SHA256).Hash.ToLower()
        bytes=(Get-Item "$Dest/FilDesk.exe").Length
    }
    $manifest | ConvertTo-Json | Set-Content "$Dest/manifest.json"
    "$($manifest.sha256)  FilDesk.exe" | Set-Content "$Dest/SHA256SUMS"
    & "$Root/scripts/check-windows-artifact.ps1" -Directory $Dest
} finally { Pop-Location }
