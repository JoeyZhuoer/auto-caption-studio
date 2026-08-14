param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".buildenv"
$pythonPath = Join-Path $venvPath "Scripts\\python.exe"
$artifactRoot = Join-Path $projectRoot "build_artifacts"
$distPath = Join-Path $artifactRoot "dist"
$workPath = Join-Path $artifactRoot "work"
$zipPath = Join-Path $artifactRoot "AutoCaptionStudio-Windows-x64-v$Version.zip"

if (-not (Test-Path $pythonPath)) {
    py -3 -m venv $venvPath
}

& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $projectRoot "requirements.txt") pyinstaller

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "AutoCaptionStudio" `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all av `
    --collect-all yt_dlp `
    --distpath $distPath `
    --workpath $workPath `
    (Join-Path $projectRoot "app.py")

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $distPath "AutoCaptionStudio") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
