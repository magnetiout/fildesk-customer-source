# Native test only: copies a Windows-supplied signed PE. Never executes/redistributes it.
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
New-Item build/portable-fixture -ItemType Directory -Force | Out-Null
Get-ChildItem scripts/signing/*.ps1 | ForEach-Object {
 $tokens=$null; $errors=$null
 [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$tokens,[ref]$errors) | Out-Null
 if ($errors.Count) { throw $errors }
}
# Catalog-valid Windows system files are not embedded Authenticode fixtures.
# Fil release PE files require their own embedded signatures.
$source=$null; $before=$null
$candidates=@("$PSHOME/pwsh.exe", "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe")
foreach ($candidate in $candidates) {
 if (-not (Test-Path -LiteralPath $candidate)) { continue }
 $signature=Get-AuthenticodeSignature -LiteralPath $candidate
 if ($signature.Status -eq 'Valid' -and [string]$signature.SignatureType -eq 'Authenticode') {
   $source=$candidate; $before=$signature; break
 }
}
if (-not $source) { throw 'No trusted embedded Authenticode fixture; do not substitute catalog trust' }
"Fixture=$source; SignatureType=$($before.SignatureType); Subject=$($before.SignerCertificate.Subject)" | Set-Content build/portable-fixture-signature.log
Copy-Item $source build/portable-fixture/FilDesk.exe
python scripts/signing/packaging-fixture.py
if ($LASTEXITCODE -ne 0) { throw 'Fixture packing failed' }
$after=Get-AuthenticodeSignature build/portable-restored.exe
if ($after.Status -ne 'Valid' -or $after.SignerCertificate.Thumbprint -ne $before.SignerCertificate.Thumbprint) { throw 'Signature lost after Brotli roundtrip' }
if ((Get-FileHash $source).Hash -ne (Get-FileHash build/portable-restored.exe).Hash) { throw 'Signed bytes changed' }
"PASS native signature remains Valid after lossless payload packaging. Fixture only; no Fil trusted signature, GUI, installer or E2E acceptance." | Set-Content build/portable-signed-roundtrip.log
$blocked=$false
try { ./scripts/signing/Build-SignedPortable.ps1 -PayloadDirectory build/portable-fixture -OutputDirectory build/portable-must-not-exist -SigningConfig config/signing.example.json -Profile customer }
catch { if ($_.Exception.Message -ne 'Signing setup not approved/configured') { throw }; $blocked=$true }
if (-not $blocked -or (Test-Path build/portable-must-not-exist)) { throw 'Unconfigured signing did not fail closed' }
'PASS unconfigured signing rejected before output/signing mutation' | Add-Content build/portable-signed-roundtrip.log

# Direct/manual build must enforce the same production gate as Actions.
# Reserved test-only hostname and public key; execution must stop before any build/download.
$originalConfig=[IO.File]::ReadAllBytes((Join-Path $PWD 'client/src/fil_build_config.rs'))
$production=@{environment='production';profile='customer';id_server='support.example.net:21116';relay_server='support.example.net:21117';public_key=[Convert]::ToBase64String([byte[]](0..31))}
$production | ConvertTo-Json | Set-Content build/portable-production-fixture.local.json -Encoding utf8NoBOM
$blocked=$false
try { ./scripts/build-windows.ps1 -Config build/portable-production-fixture.local.json *> build/portable-production-gate.log }
catch { $blocked=$true }
finally { [IO.File]::WriteAllBytes((Join-Path $PWD 'client/src/fil_build_config.rs'),$originalConfig) }
if (-not $blocked -or -not (Select-String -Path build/portable-production-gate.log -Pattern 'BLOCKED: client: known vulnerabilities remain' -Quiet)) { throw 'Direct production build did not enforce the release gate' }
'PASS direct production build blocked by the real release gate before downloads/build' | Add-Content build/portable-signed-roundtrip.log

# The negative test above intentionally ran a failing native command. All assertions
# passed; do not leak that expected exit status into the next Actions step.
$global:LASTEXITCODE=0
