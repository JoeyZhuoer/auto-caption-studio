param(
    [string]$Version = "0.1.1"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".buildenv"
$pythonPath = Join-Path $venvPath "Scripts\\python.exe"
$artifactRoot = Join-Path $projectRoot "build_artifacts"
$distPath = Join-Path $artifactRoot "dist"
$workPath = Join-Path $artifactRoot "work"
$zipPath = Join-Path $artifactRoot "AutoCaptionStudio-Windows-x64-v$Version.zip"
$toolsPath = Join-Path $artifactRoot "tools"
$denoPath = Join-Path $toolsPath "deno.exe"
$denoZipPath = Join-Path $toolsPath "deno-x86_64-pc-windows-msvc.zip"
$denoUrl = "https://github.com/denoland/deno/releases/download/v2.9.5/deno-x86_64-pc-windows-msvc.zip"
$denoSha256 = "171efab55ac6b9881fd53ee4c20f8bf3bb1340ffc618483746909014db12216a"

if (-not (Test-Path $pythonPath)) {
    py -3 -m venv $venvPath
}

& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $projectRoot "requirements.txt") pyinstaller

if (-not (Test-Path $denoPath)) {
    New-Item -ItemType Directory -Path $toolsPath -Force | Out-Null
    Invoke-WebRequest -Uri $denoUrl -OutFile $denoZipPath
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $denoZipPath).Hash.ToLowerInvariant()
    if ($actualHash -ne $denoSha256) {
        throw "Deno checksum verification failed. Expected $denoSha256 but received $actualHash."
    }
    Expand-Archive -LiteralPath $denoZipPath -DestinationPath $toolsPath -Force
}

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
    --collect-all yt_dlp_ejs `
    --add-binary "$denoPath;." `
    --distpath $distPath `
    --workpath $workPath `
    (Join-Path $projectRoot "app.py")

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $distPath "AutoCaptionStudio") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
