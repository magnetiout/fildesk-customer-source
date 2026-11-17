$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$script=Join-Path $root 'deployment/windows-lab/package/Copy-FilRemoteProfile.ps1'
$base=Join-Path $root ('build/migration-fixture-'+[Guid]::NewGuid().ToString('N'))
$old=Join-Path $base 'FilRemote-Dev/config'
New-Item $old -ItemType Directory -Force | Out-Null
$original=Join-Path $old 'FilRemote-Dev.toml'
Set-Content -LiteralPath $original -Value 'id = "synthetic-test-only"'
$hash=(Get-FileHash $original).Hash
$target=Join-Path $base 'FilDesk-Dev/config/FilDesk-Dev.toml'
& $script -RoamingRoot $base | Out-Null
if (Test-Path $target) { throw 'Plan mutated destination' }
& $script -RoamingRoot $base -Apply -ApplicationsClosed | Out-Null
if ((Get-FileHash $target).Hash -ne $hash -or (Get-FileHash $original).Hash -ne $hash) { throw 'Source/destination bytes changed' }
$rejected=$false
try { & $script -RoamingRoot $base -Apply -ApplicationsClosed | Out-Null } catch { $rejected=$_.Exception.Message -like '*Destination exists*' }
if (-not $rejected -or (Get-FileHash $target).Hash -ne $hash) { throw 'Existing profile was not protected' }
$other=Join-Path $base 'junction-fixture'
New-Item $other -ItemType Directory | Out-Null
New-Item (Join-Path $other 'FilRemote-Dev') -ItemType Junction -Target (Join-Path $base 'FilRemote-Dev') | Out-Null
$rejected=$false
try { & $script -RoamingRoot $other -Apply -ApplicationsClosed | Out-Null } catch { $rejected=$_.Exception.Message -like '*Reparse*' }
if (-not $rejected) { throw 'Reparse source accepted' }
'PASS explicit migration: dry plan, byte-preserving named copy/source retention, existing target refusal, junction refusal. Synthetic config only; real ID/password/GUI NOT RUN.' | Tee-Object (Join-Path $root 'build/portable-migration.log')
