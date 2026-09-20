# Run from any directory. Uses the installed app; does not build or install an APK.
param([string]$DeviceSerial)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
$versionFile = Join-Path $repoRoot 'unity\ProjectSettings\ProjectVersion.txt'
$editorVersion = ((Select-String -LiteralPath $versionFile -Pattern '^m_EditorVersion:').Line -split ':', 2)[1].Trim()
$adbPath = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$editorVersion\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe"
$packageName = 'com.htn26.rfthreatdetection'

if (-not (Test-Path -LiteralPath $adbPath)) { throw "Unity Android SDK adb not found: $adbPath" }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Repository Python environment not found: $pythonPath" }

$devices = @(& $adbPath devices)
if ($LASTEXITCODE -ne 0) { throw 'ADB could not list devices.' }
$authorized = @($devices | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
if ($DeviceSerial) {
    if ($DeviceSerial -notin $authorized) { throw "Device $DeviceSerial is not authorized. Connect it and accept USB debugging inside the headset." }
} elseif ($authorized.Count -eq 1) {
    $DeviceSerial = $authorized[0]
} else {
    throw 'Connect one Quest and accept USB debugging, or specify -DeviceSerial when multiple devices are connected.'
}

$installed = & $adbPath -s $DeviceSerial shell pm path $packageName
if ($LASTEXITCODE -ne 0 -or -not ($installed -match '^package:')) {
    throw "The app $packageName is not installed on $DeviceSerial. Install the Quest APK first."
}

function Get-BackendHealth {
    try { Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3 }
    catch { return $null }
}

$health = Get-BackendHealth
if ($null -eq $health) {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 8000 is occupied but the backend health endpoint is unavailable. Check the existing process.'
    }
    $logDirectory = Join-Path $repoRoot 'unity\Logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $logStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backendProcess = Start-Process -FilePath $pythonPath `
        -ArgumentList '-m', 'uvicorn', 'backend.app.main:app', '--host', '0.0.0.0', '--port', '8000' `
        -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDirectory "backend-$logStamp.out.log") `
        -RedirectStandardError (Join-Path $logDirectory "backend-$logStamp.err.log")
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        $health = Get-BackendHealth
        if ($null -ne $health) { break }
        if ($backendProcess.HasExited) { break }
    }
    if ($null -eq $health) { throw "Backend failed to start. Inspect $logDirectory\backend-$logStamp.err.log" }
    Write-Host "Started backend process $($backendProcess.Id). Logs: $logDirectory"
}
if ($health.status -ne 'ok' -or $null -eq $health.configured_pods) {
    throw 'Port 8000 did not return the expected RF backend health response.'
}

& $adbPath -s $DeviceSerial reverse tcp:8000 tcp:8000
if ($LASTEXITCODE -ne 0) { throw 'Could not establish the USB backend connection.' }
$activity = @(& $adbPath -s $DeviceSerial shell cmd package resolve-activity --brief $packageName) |
    Where-Object { $_ -match ('^' + [regex]::Escape($packageName) + '/') } | Select-Object -Last 1
if (-not $activity) { throw 'The installed APK has no launchable activity.' }
$launch = & $adbPath -s $DeviceSerial shell am start -W -n $activity.Trim()
$launch | Write-Host
if ($LASTEXITCODE -ne 0 -or -not ($launch -match 'Status: ok')) { throw 'Quest app launch failed.' }

Write-Host 'RF Threat Detection launched. Keep the USB cable connected.'
Write-Host 'The app must target ws://127.0.0.1:8000/ws/threats for this USB connection.'
Write-Host 'Backend health:'
Get-BackendHealth | ConvertTo-Json | Write-Host
