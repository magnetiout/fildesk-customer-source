param([Parameter(Mandatory=$true)][string]$Manifest,[Parameter(Mandatory=$true)][string]$Exe)
$ErrorActionPreference='Stop'
$c=Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
if ($c.environment -ne 'staging' -or $c.endpoint_verified -ne $true -or $c.runtime_verified -ne $true) {throw 'Verified staging endpoint/runtime manifest required'}
if ($c.profile -notin @('customer','operator')) {throw 'Unknown profile'}
if ([Convert]::FromBase64String($c.public_key).Length -ne 32) {throw 'Invalid public key'}
if ($c.server_host -notin @('129.212.237.210','destek.filteknoloji.com')) {throw 'Unexpected target'}
$hash=(Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $c.exe_sha256) {throw 'EXE hash mismatch'}
$sig=Get-AuthenticodeSignature -LiteralPath $Exe
if ($c.signing -ne 'unsigned-development' -or $sig.Status -ne 'NotSigned') {throw 'Unexpected signature/provenance state; review'}
foreach ($port in @(21115,21116,21117)) {
 if (-not (Test-NetConnection -ComputerName $c.server_host -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue)) {throw "TCP $port failed"}
}
Write-Output 'TCP/hash/signature checks completed. UDP registration and Windows GUI/auth/relay/E2E NOT RUN.'
Write-Output ('Expected independent profile: FilDesk-Staging'+$(if($c.profile -eq 'operator'){'-Operator'}else{''}))
# Never disable security products or start a service/installer automatically.
