#Requires -Version 5.1
<#
.SYNOPSIS
    Create a GitHub release and attach the Nuitka onefile exe in one step.

.DESCRIPTION
    Passes build\nuitka\pdfDiffChecker.exe to gh release create so the asset is not
    omitted by mistake. Run from the repository root after build_nuitka.ps1.

.PARAMETER Tag
    Release tag (e.g. v1.0.9). Must match the intended version.

.PARAMETER Title
    Optional release title; defaults to the tag string.

.EXAMPLE
    .\scripts\gh_release_with_exe.ps1 -Tag v1.0.9
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $Tag,
    [string] $Title = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$exe = Join-Path $root "build\nuitka\pdfDiffChecker.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Error "Executable not found: $exe — run build_nuitka.ps1 first."
}

if (-not $Title) {
    $Title = $Tag
}

gh release create $Tag --title $Title --generate-notes $exe
