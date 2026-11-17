$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
$Root=$PWD.Path
$env:VCPKG_MAX_CONCURRENCY='2'
$env:CMAKE_BUILD_PARALLEL_LEVEL='2'
$env:VCPKG_BINARY_SOURCES='clear'
git clone https://github.com/microsoft/vcpkg.git build/opus-vcpkg
git -C build/opus-vcpkg checkout 9e593bb18ea69cc5095e012465dcd675a822ed0d
& ./build/opus-vcpkg/bootstrap-vcpkg.bat -disableMetrics
& ./build/opus-vcpkg/vcpkg.exe install opus:x64-windows-static --classic "--overlay-ports=$Root/client/res/vcpkg" "--x-install-root=$Root/build/opus-installed" 2>&1 | Tee-Object build/opus-native-build.log
if ($LASTEXITCODE -ne 0) { throw 'Opus native build failed' }
if (Select-String -Path build/opus-native-build.log -Pattern 'incorrect CRT linkage|Expected.*crt linkage' -Quiet) { throw 'Opus CRT mismatch remains' }
$vs= & "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$dump=Get-ChildItem "$vs/VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe" | Sort-Object FullName -Descending | Select-Object -First 1
foreach ($mode in @('release','debug')) {
 $lib=if ($mode -eq 'debug') {"$Root/build/opus-installed/x64-windows-static/debug/lib/opus.lib"} else {"$Root/build/opus-installed/x64-windows-static/lib/opus.lib"}
 & $dump.FullName /directives $lib | Set-Content "build/opus-$mode-directives.log"
 $text=Get-Content "build/opus-$mode-directives.log" -Raw
 $expected=if ($mode -eq 'debug') {'LIBCMTD'} else {'LIBCMT'}
 if ($text -match 'DEFAULTLIB:[" ]*MSVCRT' -or $text -notmatch "DEFAULTLIB:[`" ]*$expected\b") { throw "Wrong $mode CRT directives" }
 $flag=if ($mode -eq 'debug') {'/MTd'} else {'/MT'}
 @"
@echo off
call "$vs/Common7/Tools/VsDevCmd.bat" -arch=x64 >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c11 $flag /I"$Root/build/opus-installed/x64-windows-static/include/opus" "$Root/tests/opus-crt-smoke.c" /Fo"$Root/build/opus-$mode.obj" /Fe"$Root/build/opus-$mode.exe" /link "$lib"
if errorlevel 1 exit /b 1
"$Root/build/opus-$mode.exe"
"@ | Set-Content "build/opus-$mode-test.cmd"
 & cmd /d /c ".\build\opus-$mode-test.cmd" 2>&1 | Tee-Object "build/opus-$mode-smoke.log"
 if ($LASTEXITCODE -ne 0) { throw "Opus $mode runtime smoke failed" }
}
