@echo off
setlocal EnableExtensions DisableDelayedExpansion
title KMJ TECHNO - Main Website P520 Connect

echo KMJ TECHNO ^| P520 ONE-CLICK ^| OFFICIAL KMJTECHNO.COM
echo Domain-only delivery. Existing verified local CodeBridge reused.
echo Browser owner approval required. No GitHub downloads, no admin rights.
echo.
if /I not "%OS%"=="Windows_NT" goto :blocked
if /I not "%COMPUTERNAME%"=="DESKTOP-5FVJMET" goto :wronghost
where powershell.exe >nul 2>&1
if errorlevel 1 goto :blocked
set "KMJ_SCRIPT_URL=https://kmjtechno.com/KMJ-CodeBridge-P520-Connect.ps1"
set "KMJ_SCRIPT_SHA256=07a9478695172587f01bc28076880a845cd7b7917ec6025a13c9316abe0a3e11"
set "KMJ_TMP_FILE=%TEMP%\KMJ-P520-DomainConnect-%RANDOM%-%RANDOM%.ps1"
if exist "%KMJ_TMP_FILE%" goto :blocked

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -Command "$ErrorActionPreference='Stop'; $u='%KMJ_SCRIPT_URL%'; $f='%KMJ_TMP_FILE%'; Invoke-WebRequest -UseBasicParsing -Uri $u -Method Get -MaximumRedirection 0 -TimeoutSec 20 -OutFile $f; $h=(Get-FileHash -Algorithm SHA256 -LiteralPath $f).Hash.ToLowerInvariant(); if ($h -cne '%KMJ_SCRIPT_SHA256%') { throw 'KMJ_DOMAIN_INSTALLER_HASH_MISMATCH' }; Unblock-File -LiteralPath $f; Write-Output 'KMJ_DOMAIN_SCRIPT_SHA256=PASS'"
if errorlevel 1 goto :downloadblocked
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%KMJ_TMP_FILE%"
set "KMJ_EXIT=%ERRORLEVEL%"
if exist "%KMJ_TMP_FILE%" del /q "%KMJ_TMP_FILE%" >nul 2>&1
echo.
echo KMJ_DOMAIN_CONNECT_EXIT=%KMJ_EXIT%
echo Account-side authenticated READY verification remains mandatory.
echo Never share private agent.json, enrollment.json, bearer [REDACTED] or private logs.
pause
exit /b %KMJ_EXIT%

:downloadblocked
if exist "%KMJ_TMP_FILE%" del /q "%KMJ_TMP_FILE%" >nul 2>&1
echo KMJ_DOMAIN_CONNECT=BLOCKED:OFFICIAL_DOMAIN_DOWNLOAD_OR_HASH
pause
exit /b 2
:wronghost
echo KMJ_DOMAIN_CONNECT=BLOCKED:WRONG_WINDOWS_HOST
pause
exit /b 2
:blocked
echo KMJ_DOMAIN_CONNECT=BLOCKED:WINDOWS_OR_POWERSHELL_REQUIRED
pause
exit /b 2
