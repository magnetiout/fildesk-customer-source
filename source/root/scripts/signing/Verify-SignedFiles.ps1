param(
  [Parameter(Mandatory=$true)][string]$Directory,
  [Parameter(Mandatory=$true)][string]$ExpectedPublisherSubject,
  [Parameter(Mandatory=$true)][string]$SignTool,
  [Parameter(Mandatory=$true)][string]$EvidencePath
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $EvidencePath) { throw 'Refusing to overwrite signature evidence' }
$files = @(& "$PSScriptRoot/Get-PayloadPEFiles.ps1" -Directory $Directory)
if ($files.Count -eq 0) { throw 'No executable payload files' }
$rows = @()
foreach ($file in $files) {
    & $SignTool verify /pa /all /tw /v $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed: $($file.Name)" }
    $s = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -cne $ExpectedPublisherSubject -or -not $s.TimeStamperCertificate) {
        throw "Unexpected publisher, invalid signature or missing timestamp: $($file.Name)"
    }
    $rows += [pscustomobject]@{path=$file.FullName;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$file.Length;status=[string]$s.Status;subject=$s.SignerCertificate.Subject;thumbprint=$s.SignerCertificate.Thumbprint;timestampSubject=$s.TimeStamperCertificate.Subject}
}
$rows | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
# Does not certify public CA membership, SAC, browser reputation or real-device acceptance.
