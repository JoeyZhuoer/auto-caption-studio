param(
    [string]$Version = "0.1.2"
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
$ytDlpPath = Join-Path $toolsPath "yt-dlp.exe"
$ytDlpUrl = "https://github.com/yt-dlp/yt-dlp/releases/download/2026.08.19/yt-dlp.exe"
$ytDlpSha256 = "66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a"

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

if (-not (Test-Path $ytDlpPath)) {
    New-Item -ItemType Directory -Path $toolsPath -Force | Out-Null
    Invoke-WebRequest -Uri $ytDlpUrl -OutFile $ytDlpPath
}
$actualYtDlpHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ytDlpPath).Hash.ToLowerInvariant()
if ($actualYtDlpHash -ne $ytDlpSha256) {
    throw "yt-dlp checksum verification failed. Expected $ytDlpSha256 but received $actualYtDlpHash."
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
    --add-binary "$denoPath;." `
    --add-binary "$ytDlpPath;." `
    --distpath $distPath `
    --workpath $workPath `
    (Join-Path $projectRoot "app.py")

Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination (Join-Path $distPath "AutoCaptionStudio\README.md") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md") -Destination (Join-Path $distPath "AutoCaptionStudio\THIRD_PARTY_NOTICES.md") -Force

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $distPath "AutoCaptionStudio") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
