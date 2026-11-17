param(
 [Parameter(Mandatory=$true)][string]$Directory,
 [Parameter(Mandatory=$true)][ValidateSet('payload','launcher')][string]$Stage,
 [Parameter(Mandatory=$true)][ValidateSet('hsm-store','artifact-signing')][string]$Provider,
 [Parameter(Mandatory=$true)][string]$SignTool,
 [Parameter(Mandatory=$true)][string]$TimestampUrl,
 [string]$CertificateThumbprint,
 [string]$Dlib,
 [string]$Metadata
)
$ErrorActionPreference = 'Stop'
# Run only in a dedicated native Windows signing workspace. No PFX/private-key parameter.
if ($TimestampUrl -notmatch '^https?://') { throw 'Configured CA/RFC3161 timestamp endpoint required' }
$files = @(& "$PSScriptRoot/Get-PayloadPEFiles.ps1" -Directory $Directory)
if ($Stage -eq 'launcher' -and ($files.Count -ne 1 -or $files[0].Name -cne 'FilDesk.exe')) { throw 'Launcher stage requires only final FilDesk.exe' }
if ($files.Count -eq 0) { throw 'No PE files' }
foreach ($file in $files) {
 $signature=Get-AuthenticodeSignature -LiteralPath $file.FullName
 if ($signature.Status -ne 'NotSigned') { throw "Review existing/vendor signatures before signing: $($file.Name)" }
 $arguments=@('sign','/fd','SHA256','/tr',$TimestampUrl,'/td','SHA256')
 if ($Provider -eq 'hsm-store') {
   if ($CertificateThumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Validated HSM-backed certificate selector required' }
   $arguments+=@('/sha1',$CertificateThumbprint)
 } else {
   if (-not (Test-Path -LiteralPath $Dlib) -or -not (Test-Path -LiteralPath $Metadata)) { throw 'Pinned official signing client and public metadata required' }
   $arguments+=@('/dlib',$Dlib,'/dmdf',$Metadata)
 }
 & $SignTool @arguments $file.FullName
 if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.Name)" }
}
# Failures leave a partial staging tree: quarantine it, do not package or publish it.
