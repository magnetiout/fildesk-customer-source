param(
 [Parameter(Mandatory=$true)][ValidateSet('chrome','edge','firefox','opera','brave')][string]$Browser,
 [Parameter(Mandatory=$true)][string]$BrowserVersion,
 [Parameter(Mandatory=$true)][string]$DownloadedFile,
 [Parameter(Mandatory=$true)][string]$ExpectedSha256,
 [Parameter(Mandatory=$true)][uri]$DownloadUrl,
 [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Output) { throw 'Refusing to overwrite evidence' }
if ($DownloadUrl.Scheme -ne 'https' -or $DownloadUrl.Query -or $DownloadUrl.UserInfo) { throw 'HTTPS release URL without credentials/query required' }
if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'Expected release SHA256 required' }
$file=Get-Item -LiteralPath $DownloadedFile
if ($file.Name -cne 'FilDesk.exe') { throw 'Expected unambiguous FilDesk.exe filename' }
$signature=Get-AuthenticodeSignature -LiteralPath $file.FullName
$hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$zone=Get-Content -LiteralPath $file.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue
$os=Get-CimInstance Win32_OperatingSystem
$defender=$null
try { $defender=Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureVersion,AntivirusSignatureLastUpdated } catch { }
[pscustomobject]@{
 browser=$Browser; browser_version=$BrowserVersion; observed_at=(Get-Date).ToUniversalTime().ToString('o');
 windows_version=$os.Version; windows_build=$os.BuildNumber; source_url=$DownloadUrl.AbsoluteUri;
 filename=$file.Name; bytes=$file.Length; sha256=$hash; expected_sha256=$ExpectedSha256; hash_matches=($hash -eq $ExpectedSha256.ToLowerInvariant());
 authenticode_status=[string]$signature.Status; signer_subject=$signature.SignerCertificate.Subject; signer_thumbprint=$signature.SignerCertificate.Thumbprint;
 zone_identifier=$zone; defender_observation=$defender;
 browser_download_warning='NOT RUN - record manually'; smartscreen='NOT RUN - record manually'; smart_app_control='NOT RUN - record manually';
 double_click='NOT RUN'; customer_screen='NOT RUN'; id_password='NOT RUN'; operator_connection='NOT RUN'; persistence_check='NOT RUN'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Output -Encoding utf8
# Read-only observation of a file downloaded through the real browser. No download,
# launch, service installation, Unblock-File, exclusion, or protection setting change.
