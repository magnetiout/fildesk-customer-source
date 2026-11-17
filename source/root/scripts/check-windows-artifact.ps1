param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = 'Stop'
$manifest = Get-Content (Join-Path $Directory manifest.json) -Raw | ConvertFrom-Json
$exe = Join-Path $Directory FilDesk.exe
$bytes = [IO.File]::ReadAllBytes($exe)
if ($bytes.Length -lt 256 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) { throw 'Not a PE executable' }
$offset = [BitConverter]::ToInt32($bytes, 0x3c)
if ($offset -lt 0 -or $offset + 26 -gt $bytes.Length) { throw 'Invalid PE header offset' }
if ([BitConverter]::ToUInt32($bytes, $offset) -ne 0x4550) { throw 'Missing PE signature' }
if ([BitConverter]::ToUInt16($bytes, $offset + 4) -ne 0x8664) { throw 'Expected Windows AMD64' }
if ([BitConverter]::ToUInt16($bytes, $offset + 24) -ne 0x20b) { throw 'Expected PE32+' }
if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() -ne $manifest.sha256) { throw 'Artifact hash mismatch' }
if ($bytes.Length -ne $manifest.bytes) { throw 'Artifact size mismatch' }
if ((Get-AuthenticodeSignature $exe).Status -ne 'NotSigned' -or $manifest.signing -ne 'unsigned-test') { throw 'Incorrect signature label' }
foreach ($field in @('upstream', 'project_commit')) {
    if ($manifest.$field -notmatch '^[0-9a-f]{40}$') { throw "Invalid source commit: $field" }
}
foreach ($field in @('client_patch_sha256', 'client_lock_sha256', 'public_config_sha256')) {
    if ($manifest.$field -notmatch '^[0-9a-f]{64}$') { throw "Missing source provenance: $field" }
}
if ($manifest.profile -notin @('customer','operator')) { throw 'Invalid profile' }
if ($manifest.runtime_testing -ne 'NOT RUN') { throw 'Build cannot assert runtime acceptance' }
'PASS PE32+ AMD64, size, SHA256 and unsigned-test label. This does not prove runtime behavior.'
