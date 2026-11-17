param(
 [Parameter(Mandatory=$true)][string]$PayloadDirectory,
 [Parameter(Mandatory=$true)][string]$OutputDirectory,
 [Parameter(Mandatory=$true)][string]$SigningConfig,
 [Parameter(Mandatory=$true)][ValidateSet('customer','operator')][string]$Profile
)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
$Root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$cfg=Get-Content -LiteralPath $SigningConfig -Raw | ConvertFrom-Json
# Public selectors/tool hashes only. Credentials belong to a dedicated signing runner/HSM.
if ($cfg.approved -ne $true -or -not $cfg.expectedPublisherSubject) { throw 'Signing setup not approved/configured' }
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Fresh signing output directory required' }
foreach ($tool in @('signTool','dlib')) {
 if ($tool -eq 'dlib' -and $cfg.provider -ne 'artifact-signing') { continue }
 $path=$cfg.$tool; $expected=$cfg.toolSha256.$tool
 if ($expected -notmatch '^[a-f0-9]{64}$' -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) { throw "Unpinned signing tool: $tool" }
 if ((Get-AuthenticodeSignature -LiteralPath $path).Status -ne 'Valid') { throw "Untrusted signing tool: $tool" }
}
$OutputDirectory=[IO.Path]::GetFullPath($OutputDirectory)
$PayloadDirectory=(Resolve-Path -LiteralPath $PayloadDirectory).Path
if ($OutputDirectory.StartsWith($PayloadDirectory.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Signing output cannot be inside input payload' }
New-Item $OutputDirectory -ItemType Directory | Out-Null
$payload=Join-Path $OutputDirectory 'payload'
$outer=Join-Path $OutputDirectory 'portable'
New-Item $payload,$outer -ItemType Directory | Out-Null
# Never modify the existing unsigned artifact or its release directory.
if ((Get-Item -LiteralPath $PayloadDirectory).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse source rejected' }
foreach ($file in Get-ChildItem -LiteralPath $PayloadDirectory -Recurse -Force) {
 if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse payload rejected' }
}
Get-ChildItem -LiteralPath $PayloadDirectory -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $payload -Recurse -Force }
$sign=@{Provider=$cfg.provider;SignTool=$cfg.signTool;TimestampUrl=$cfg.timestampUrl}
if ($cfg.provider -eq 'hsm-store') { $sign.CertificateThumbprint=$cfg.certificateThumbprint }
else { $sign.Dlib=$cfg.dlib; $sign.Metadata=$cfg.metadata }
& "$PSScriptRoot/Sign-Stage.ps1" -Directory $payload -Stage payload @sign
& "$PSScriptRoot/Verify-SignedFiles.ps1" -Directory $payload -ExpectedPublisherSubject $cfg.expectedPublisherSubject -SignTool $cfg.signTool -EvidencePath "$OutputDirectory/payload-signatures.json"
$files=@(Get-ChildItem $payload -Recurse -File | ForEach-Object {
 @{path='application/'+[IO.Path]::GetRelativePath($payload,$_.FullName).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
$previousProfile=$env:FIL_PROFILE; $previousTrust=$env:FIL_REQUIRE_AUTHENTICODE
try {
 $env:FIL_PROFILE=$Profile; $env:FIL_REQUIRE_AUTHENTICODE='1'
 Push-Location "$Root/client/libs/portable"
 try { python generate.py -f $payload -o . -e FilDesk.exe } finally { Pop-Location }
 if ($LASTEXITCODE -ne 0) { throw 'Authenticated portable packaging failed' }
} finally { $env:FIL_PROFILE=$previousProfile; $env:FIL_REQUIRE_AUTHENTICODE=$previousTrust }
Copy-Item "$Root/client/target/release/rustdesk-portable-packer.exe" "$outer/FilDesk.exe"
python "$Root/scripts/check-portable-load-flags.py" "$outer/FilDesk.exe"
if ($LASTEXITCODE -ne 0) { throw 'Portable loader policy missing' }
& "$PSScriptRoot/Sign-Stage.ps1" -Directory $outer -Stage launcher @sign
& "$PSScriptRoot/Verify-SignedFiles.ps1" -Directory $outer -ExpectedPublisherSubject $cfg.expectedPublisherSubject -SignTool $cfg.signTool -EvidencePath "$OutputDirectory/launcher-signatures.json"
# Recheck all inner signatures after packing and prove the final signed wrapper contains their exact bytes.
& "$PSScriptRoot/Verify-SignedFiles.ps1" -Directory $payload -ExpectedPublisherSubject $cfg.expectedPublisherSubject -SignTool $cfg.signTool -EvidencePath "$OutputDirectory/payload-signatures-after.json"
$exe=Get-Item "$outer/FilDesk.exe"
$files+=@{path='portable/FilDesk.exe';bytes=$exe.Length;sha256=(Get-FileHash $exe.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$manifest=@{product='FilDesk';profile=$Profile;environment='development';signing='trusted-development-candidate';runtime_testing='NOT RUN';release_gate='BLOCKED';project_commit=(git -C $Root rev-parse HEAD);client_patch_sha256=(Get-FileHash "$Root/branding/patches/client.patch" -Algorithm SHA256).Hash.ToLowerInvariant();run_id=$env:GITHUB_RUN_ID;runner=$env:RUNNER_OS;built_at=(Get-Date).ToUniversalTime().ToString('o');publisher=$cfg.expectedPublisherSubject;signature_status='Valid';client_upstream=(git -C "$Root/client" rev-parse HEAD);client_lock_sha256=(Get-FileHash "$Root/client/Cargo.lock" -Algorithm SHA256).Hash.ToLowerInvariant();public_config_sha256=(Get-FileHash "$Root/client/src/fil_build_config.rs" -Algorithm SHA256).Hash.ToLowerInvariant();files=$files}
$manifest | ConvertTo-Json -Depth 8 | Set-Content "$OutputDirectory/package-manifest.json" -Encoding utf8NoBOM
node "$Root/scripts/verify-portable-payload.mjs" $exe.FullName "$OutputDirectory/package-manifest.json" | Set-Content "$OutputDirectory/portable-integrity.json"
if ($LASTEXITCODE -ne 0) { throw 'Signed wrapper payload verification failed' }
# No auto-publish and no production gate waiver. Partial output on failure is quarantined.
