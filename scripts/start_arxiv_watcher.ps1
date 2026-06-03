param(
  [double]$IntervalMinutes = 10,
  [string]$ContactEmail = "your-email@example.com"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

if (-not $env:ARXIV_USER_AGENT) {
  $env:ARXIV_USER_AGENT = "ai-trend-intel/1.0 (research; contact: $ContactEmail)"
}

Write-Host "Starting arXiv watcher from $repoRoot"
Write-Host "Interval: $IntervalMinutes minutes"
Write-Host "User-Agent: $env:ARXIV_USER_AGENT"
Write-Host "Press Ctrl+C to stop."

python scripts/collect_arxiv.py --watch --interval-minutes $IntervalMinutes
