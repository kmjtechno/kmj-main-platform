<?php

use Illuminate\Support\Facades\Route;

// Public downloads contain NO account credentials or device-specific grants.
// An authenticated CodeBridge customer downloads the CMD from their dashboard.
// The CMD verifies SHA-256 of the second, first-party hosted script before use.
Route::get('install-codebridge-windows.ps1', function () {
    $script = file_get_contents(resource_path('codebridge/install-windows-device.ps1'));
    abort_unless(is_string($script) && $script !== '', 503);

    return response($script, 200, [
        'Content-Type' => 'text/plain; charset=UTF-8',
        'Content-Disposition' => 'attachment; filename="KMJ-CodeBridge-Windows-Connector.ps1"',
        'Cache-Control' => 'public, max-age=300',
        'X-Content-Type-Options' => 'nosniff',
    ]);
})->name('codebridge.windows.installer.script');

Route::get('install-codebridge-windows.cmd', function () {
    $script = file_get_contents(resource_path('codebridge/install-windows-device.ps1'));
    abort_unless(is_string($script) && $script !== '', 503);
    $expectedSha256 = strtoupper(hash('sha256', $script));

    $launcher = <<<'CMD'
@echo off
setlocal EnableExtensions DisableDelayedExpansion
title KMJ TECHNO - Connect Windows Device
echo KMJ TECHNO ^| DEVICE CONNECTION
echo The installer will verify its first-party source before running.
echo No password or private token is embedded in this file.
echo.
where powershell.exe >nul 2>&1
if errorlevel 1 goto :blocked
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -Command "$ErrorActionPreference='Stop'; $p=Join-Path $env:TEMP ('kmj-connect-'+[guid]::NewGuid().ToString('N')+'.ps1'); try { Invoke-WebRequest -UseBasicParsing -Uri 'https://kmjtechno.com/install-codebridge-windows.ps1' -OutFile $p; if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -cne '%%EXPECTED_SHA256%%') { throw 'KMJ_INSTALLER_HASH_MISMATCH' }; & $p; if (!$?) { exit 2 } } finally { Remove-Item -LiteralPath $p -ErrorAction SilentlyContinue }"
set "RC=%ERRORLEVEL%"
echo.
echo KMJ Setup exit code: %RC%
echo Verify actual READY in the KMJ CodeBridge dashboard after connection.
pause
exit /b %RC%
:blocked
echo KMJ_SETUP=BLOCKED:POWERSHELL_REQUIRED
pause
exit /b 2
CMD;

    $launcher = str_replace('%%EXPECTED_SHA256%%', $expectedSha256, $launcher);

    return response($launcher."\r\n", 200, [
        'Content-Type' => 'application/octet-stream',
        'Content-Disposition' => 'attachment; filename="KMJ-CodeBridge-Connect-Windows.cmd"',
        'Cache-Control' => 'no-store',
        'X-Content-Type-Options' => 'nosniff',
    ]);
})->name('codebridge.windows.installer');
