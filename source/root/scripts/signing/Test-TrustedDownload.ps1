<# Read-only real Windows observation. Does not download, launch, sign, unblock,
change protections, inspect private keys, or certify public CA membership/reputation.
Use after signing+RFC3161 timestamping; expected publisher comes from owner/legal CA.
#>
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$File,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedSha256,
 [Parameter(Mandatory=$true)][string]$ExpectedPublisher,
 [Parameter(Mandatory=$true)][string]$TesterId,
 [Parameter(Mandatory=$true)][string]$SignTool,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$SignToolSha256,
 [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Actual Windows execution required' }
if (Test-Path -LiteralPath $Output) { throw 'Refusing evidence overwrite' }
if ($ExpectedPublisher.Trim().Length -lt 3 -or $ExpectedPublisher -match '^(?i:unknown|unverified|todo|fixture|test)$') { throw 'Owner-confirmed legal publisher required' }
if ($TesterId.Trim().Length -lt 3) { throw 'Named tester required' }
$f=Get-Item -LiteralPath $File
if ($f.Length -le 0 -or $f.Length -gt 1GB -or $f.PSIsContainer -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Regular non-reparse EXE required' }
if ($f.Name -notin @('FilDesk.exe','FilDesk-Support.exe')) { throw 'Unexpected file name' }
$hash=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -cne $ExpectedSha256) { throw 'Artifact SHA256 mismatch' }
$tool=Get-Item -LiteralPath $SignTool
if ($tool.PSIsContainer -or ($tool.Attributes -band [IO.FileAttributes]::ReparsePoint) -or (Get-FileHash -LiteralPath $tool.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -cne $SignToolSha256) { throw 'Pinned SignTool mismatch' }
$sig=Get-AuthenticodeSignature -LiteralPath $f.FullName
if ($sig.Status -ne 'Valid' -or $sig.SignatureType -ne 'Authenticode' -or $null -eq $sig.SignerCertificate -or $sig.SignerCertificate.Subject -cne $ExpectedPublisher -or $null -eq $sig.TimeStamperCertificate) { throw 'Signature/publisher/timestamp invalid' }
if (-not ($sig.SignerCertificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | ForEach-Object { $_.EnhancedKeyUsages } | Where-Object { $_.Value -eq '1.3.6.1.5.5.7.3.3' })) { throw 'Explicit code-signing EKU required' }
# Online revocation is intentional; unavailable revocation fails closed.
function Test-Chain($Certificate) {
 $chain=New-Object Security.Cryptography.X509Certificates.X509Chain
 try {
  $chain.ChainPolicy.RevocationMode=[Security.Cryptography.X509Certificates.X509RevocationMode]::Online
  $chain.ChainPolicy.RevocationFlag=[Security.Cryptography.X509Certificates.X509RevocationFlag]::ExcludeRoot
  $chain.ChainPolicy.UrlRetrievalTimeout=[TimeSpan]::FromSeconds(20)
  if (-not $chain.Build($Certificate)) { throw 'Certificate chain/revocation check failed' }
  return $chain.ChainElements[$chain.ChainElements.Count-1].Certificate.Thumbprint
 } finally { $chain.Dispose() }
}
$signerRoot=Test-Chain $sig.SignerCertificate
$timestampRoot=Test-Chain $sig.TimeStamperCertificate
& $tool.FullName verify /pa /all /tw /v $f.FullName | Out-Null
$verifyExit=$LASTEXITCODE
if ($verifyExit -ne 0) { throw 'SignTool verification failed' }
if ((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedSha256) { throw 'Artifact changed during observation' }
$build=[Environment]::OSVersion.Version.ToString()
$result=[ordered]@{
 schema_version=1;kind='fildesk-trusted-download-verification';execution='windows-device';
 sha256=$hash;signature_status='Valid';publisher=$sig.SignerCertificate.Subject;
 code_signing_eku_valid=$true;timestamp_present=$true;signer_chain_valid=$true;timestamp_chain_valid=$true;
 signer_root_thumbprint=$signerRoot;timestamp_root_thumbprint=$timestampRoot;
 signtool_sha256=$SignToolSha256;signtool_exit_code=$verifyExit;
 tester_id=$TesterId;windows_build=$build;tested_at=[DateTimeOffset]::UtcNow.ToString('o');
 public_ca_membership='REQUIRES_INDEPENDENT_REVIEW';timestamp_protocol='REQUIRES_SIGNING_LOG_REVIEW';browser_reputation='NOT_TESTED';
 limitations='Windows trust stores may contain enterprise roots. Independent public CA review and browser/device acceptance remain mandatory.'
}
$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Depth 5))
$stream=[IO.File]::Open($Output,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)} finally {$stream.Dispose()}
