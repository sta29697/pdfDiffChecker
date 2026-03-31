param(
    [string]$OutputDir = "build\nuitka",
    [string]$PythonVersion = "3.12",
    [int]$Jobs = 0,
    [switch]$ShowScons,
    [switch]$VerboseBuild,
    [switch]$Clean,
    [switch]$RunAfterBuild,
    # Default: single pdfDiffChecker.exe (--onefile). Use -Standalone for a main.dist folder layout.
    [switch]$Standalone
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$iconRel = "images/icon_multi.ico"
if (-not (Test-Path (Join-Path $projectRoot $iconRel))) {
    throw "Missing icon for Nuitka: $iconRel (required for --windows-icon-from-ico)"
}

if ($Clean -and (Test-Path $OutputDir)) {
    Remove-Item $OutputDir -Recurse -Force
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--assume-yes-for-downloads",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=images/icon_multi.ico",
    "--output-dir=$OutputDir",
    "--output-filename=pdfDiffChecker.exe",
    "--company-name=pdfDiffChecker",
    "--product-name=PDF Diff Checker",
    "--file-version=1.0.6.0",
    "--product-version=1.0.6.0",
    "--enable-plugin=tk-inter",
    "--include-package-data=tkinterdnd2",
    "--include-data-dir=images=images",
    "--include-data-dir=themes=themes",
    "--include-data-file=configurations/message_codes.json=configurations/message_codes.json",
    "--include-data-file=licences.txt=licences.txt",
    "--include-data-file=licences_tree.txt=licences_tree.txt",
    "--report=$OutputDir/nuitka-report.xml",
    "main.py"
)

if (-not $Standalone) {
    $nuitkaArgs += "--onefile"
}

if ($Jobs -gt 0) {
    $nuitkaArgs += "--jobs=$Jobs"
}

if ($ShowScons) {
    $nuitkaArgs += "--show-scons"
}

if ($VerboseBuild) {
    $nuitkaArgs += "--verbose-output"
}

Write-Host "Building PDF Diff Checker with Nuitka..." -ForegroundColor Cyan
Write-Host "Project root: $projectRoot" -ForegroundColor DarkGray
Write-Host "Output dir : $OutputDir" -ForegroundColor DarkGray
Write-Host "Python     : $PythonVersion" -ForegroundColor DarkGray
Write-Host "Jobs       : $(if ($Jobs -gt 0) { $Jobs } else { 'auto' })" -ForegroundColor DarkGray
Write-Host "ShowScons  : $ShowScons" -ForegroundColor DarkGray
Write-Host "Verbose    : $VerboseBuild" -ForegroundColor DarkGray
Write-Host "Layout     : $(if ($Standalone) { 'standalone folder (main.dist)' } else { 'onefile exe' })" -ForegroundColor DarkGray

& uv run --python $PythonVersion --group build python @nuitkaArgs

if ($Standalone) {
    $distDir = Join-Path $projectRoot (Join-Path $OutputDir "main.dist")
    $exePath = Join-Path $distDir "pdfDiffChecker.exe"
} else {
    $exePath = Join-Path $projectRoot (Join-Path $OutputDir "pdfDiffChecker.exe")
}

Write-Host "Build completed." -ForegroundColor Green
Write-Host "Executable: $exePath" -ForegroundColor Green

if ($RunAfterBuild -and (Test-Path $exePath)) {
    Write-Host "Launching built executable..." -ForegroundColor Cyan
    & $exePath
}
