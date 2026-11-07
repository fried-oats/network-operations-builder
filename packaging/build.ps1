$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonExe -m pytest -q --basetemp=.pytest_tmp_build
if ($LASTEXITCODE -ne 0) { throw 'pytest failed; build cancelled' }
$previousPath = $env:PATH
$pythonBase = & $pythonExe -c 'import sys; print(sys.base_prefix)'
try {
    # Prevent unrelated native tools on PATH from supplying incompatible ICU/Qt DLLs.
    $env:PATH = "$projectRoot\.venv\Scripts;$pythonBase;$env:SystemRoot\System32;$env:SystemRoot"
    & $pythonExe -m PyInstaller --noconfirm --clean --onedir --windowed --name NetworkOperationsBuilder --paths $projectRoot --add-data 'definitions;definitions' --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick packaging/launcher.py
} finally {
    $env:PATH = $previousPath
}
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$standaloneFolder = Join-Path $projectRoot 'dist\NetworkOperationsBuilder'
Copy-Item -LiteralPath 'README.md' -Destination $standaloneFolder
Copy-Item -LiteralPath 'docs' -Destination $standaloneFolder -Recurse
Copy-Item -LiteralPath 'requirements-lock.txt' -Destination $standaloneFolder
Copy-Item -LiteralPath 'examples' -Destination $standaloneFolder -Recurse
& $pythonExe packaging/license_manifest.py $standaloneFolder
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
$previousPlatform = $env:QT_QPA_PLATFORM
$previousReport = $env:NOB_SMOKE_REPORT
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:NOB_SMOKE_REPORT = Join-Path $projectRoot 'build\smoke-error.txt'
    $smokeProcess = Start-Process -FilePath (Join-Path $standaloneFolder 'NetworkOperationsBuilder.exe') -ArgumentList '--smoke-test' -WindowStyle Hidden -PassThru
    if (-not $smokeProcess.WaitForExit(30000)) { $smokeProcess.Kill(); throw 'Standalone smoke test timed out' }
    if ($smokeProcess.ExitCode -ne 0) { throw "Standalone smoke test failed: $($smokeProcess.ExitCode)" }
} finally {
    $env:QT_QPA_PLATFORM = $previousPlatform
    $env:NOB_SMOKE_REPORT = $previousReport
}
Compress-Archive -LiteralPath $standaloneFolder -DestinationPath (Join-Path $projectRoot 'dist\NetworkOperationsBuilder-v0.1-preview-win64.zip') -Force
Write-Output 'Preview ZIP built. Golden scope: PTX10008 / 23.4R2-S1.6-EVO / et, unit 0. Other scopes remain gated.'
