param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference='Stop'
Get-ChildItem -LiteralPath $Directory -Recurse -File | ForEach-Object {
 if ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse PE rejected' }
 $stream=[IO.File]::OpenRead($_.FullName)
 try { $mz=($stream.ReadByte() -eq 77 -and $stream.ReadByte() -eq 90) } finally { $stream.Dispose() }
 if ($_.Extension -in '.exe','.dll') {
   if (-not $mz) { throw 'Executable extension without PE header' }
   $_
 } elseif ($mz) { throw 'PE under unexpected extension: inventory review required' }
}
