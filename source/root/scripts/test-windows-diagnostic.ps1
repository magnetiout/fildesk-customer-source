# Compile the actual changed diagnostic literal under MSVC's legacy source code page.
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
$Root=$PWD.Path
$source=Get-Content client/flutter/windows/runner/main.cpp -Raw
$literal=[regex]::Match($source,'MessageBoxW\(nullptr,\s*(L"(?:[^"\\]|\\.)*")').Groups[1].Value
if (-not $literal) { throw 'Secure DLL diagnostic literal missing' }
@"
#include <wchar.h>
int main() {
 const wchar_t *actual = $literal;
 return wcscmp(actual,L"FilDesk g\u00fcvenli DLL aramas\u0131n\u0131 ba\u015flatamad\u0131.") != 0;
}
"@ | Set-Content build/portable-diagnostic.cpp -Encoding utf8NoBOM
$vs= & "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
@"
@echo off
call "$vs/Common7/Tools/VsDevCmd.bat" -arch=x64 >nul
if errorlevel 1 exit /b 1
pushd "$Root/client/flutter/windows/runner"
rc /nologo /fo "$Root/build/portable-inner-resource.res" Runner.rc
if errorlevel 1 exit /b 1
popd
cl /nologo /MT /source-charset:.1252 "$Root/build/portable-diagnostic.cpp" /Fo"$Root/build/portable-diagnostic.obj" /Fe"$Root/build/portable-diagnostic.exe"
if errorlevel 1 exit /b 1
cl /nologo /MT /EHsc "$Root/tests/fildesk-window-identity.cpp" /Fo"$Root/build/fildesk-window-identity.obj" /Fe"$Root/build/fildesk-window-identity.exe" /link user32.lib
if errorlevel 1 exit /b 1
"$Root/build/fildesk-window-identity.exe"
if errorlevel 1 exit /b 1
"$Root/build/portable-diagnostic.exe"
"@ | Set-Content build/portable-diagnostic.cmd
& cmd /d /c '.\build\portable-diagnostic.cmd' 2>&1 | Tee-Object build/portable-diagnostic.log
if ($LASTEXITCODE -ne 0) { throw 'Turkish diagnostic differs from expected UTF16 codepoints' }
'PASS exact source diagnostic compiles to intended Turkish UTF16 under MSVC CP1252' | Add-Content build/portable-diagnostic.log

$resource=[Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes((Join-Path $Root 'build/portable-inner-resource.res')))
if (-not $resource.Contains('FilDesk development build') -or $resource.Contains('unsigned development build')) { throw 'Signature-neutral inner metadata not present' }
'PASS compiled inner version resource describes development build; signature status remains separate evidence' | Add-Content build/portable-diagnostic.log

'PASS native hidden window lookup isolates four profile/environment identities with friendly titles' | Add-Content build/portable-diagnostic.log
