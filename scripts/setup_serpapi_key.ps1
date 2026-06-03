param(
  [string]$EnvPath = ".env"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

$target = Join-Path $repoRoot $EnvPath
$apiKey = Read-Host "Enter SERPAPI_API_KEY"

if (-not $apiKey.Trim()) {
  throw "SERPAPI_API_KEY cannot be empty."
}

$lines = @()
if (Test-Path $target) {
  $lines = Get-Content $target
}

$updated = $false
$newLines = foreach ($line in $lines) {
  if ($line -match '^\s*SERPAPI_API_KEY\s*=') {
    $updated = $true
    "SERPAPI_API_KEY=$apiKey"
  } else {
    $line
  }
}

if (-not $updated) {
  $newLines += "SERPAPI_API_KEY=$apiKey"
}

Set-Content -Path $target -Value $newLines -Encoding UTF8
Write-Host "Saved SERPAPI_API_KEY to $target"
Write-Host "The .env file is ignored by git and will not be committed."
