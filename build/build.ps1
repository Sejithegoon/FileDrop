# Builds FileDrop: runs the tests, the PyInstaller app folder, then the installer if Inno Setup is present.
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"

& $py -m pytest -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "Tests failed; not building." }

# Open-source notices for exactly the packages being bundled.
& $py build
otices.py
if ($LASTEXITCODE -ne 0) { throw "Could not write the open-source notices." }

$version = (& $py -c "import app; print(app.__version__)").Trim()
Write-Host "Building FileDrop $version"

& (Join-Path $root ".venv\Scripts\pyinstaller.exe") build\filedrop.spec --distpath build\out --workpath build\work --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
Remove-Item -Recurse -Force build\work -ErrorAction SilentlyContinue

# Smoke test the frozen EXE: catches missing DLLs/modules that the source tests can't see.
if (Get-Process FileDrop -ErrorAction SilentlyContinue) { throw "Quit the running FileDrop first; the smoke test needs to start its own copy." }
$smokeDir = Join-Path $env:TEMP "filedrop-smoke-$(Get-Random)"
$env:FILEDROP_CONSOLE_PORT = "8452"
$proc = Start-Process build\out\FileDrop\FileDrop.exe -ArgumentList "--headless", "--no-server", "--data-dir", "`"$smokeDir`"" -PassThru
$ok = $false
foreach ($i in 1..30) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    try { Invoke-RestMethod http://127.0.0.1:8452/api/lock -TimeoutSec 2 | Out-Null; $ok = $true; break } catch { }
}
try { Invoke-RestMethod -Method Post http://127.0.0.1:8452/api/quit -Headers @{ "X-FileDrop" = "1" } -TimeoutSec 2 | Out-Null } catch { }
Start-Sleep -Seconds 2
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
Remove-Item Env:FILEDROP_CONSOLE_PORT
if (-not $ok) {
    Get-Content (Join-Path $smokeDir "logs\filedrop.log") -ErrorAction SilentlyContinue | Select-Object -Last 20
    throw "The built EXE did not start. See the log above."
}
Remove-Item -Recurse -Force $smokeDir -ErrorAction SilentlyContinue
Write-Host "Smoke test passed: the EXE starts and answers."

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Warning "Inno Setup 6 not found, so no installer was made. Install it from https://jrsoftware.org/isdl.php"
    Write-Host "App folder: build\out\FileDrop\FileDrop.exe"
    exit 0
}
& $iscc "/DMyAppVersion=$version" build\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$setup = "build\out\FileDrop-Setup-$version.exe"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash
Write-Host "Installer: $setup"
Write-Host "SHA-256:   $hash"
