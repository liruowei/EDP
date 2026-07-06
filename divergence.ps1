param(
    [string]$Python = "",
    [switch]$Intraday,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    param([string]$RequestedPython)
    if ($RequestedPython) {
        return $RequestedPython
    }

    $SmartQuantPython = Join-Path $env:USERPROFILE ".conda\envs\smart-quant\python.exe"
    if (Test-Path -LiteralPath $SmartQuantPython) {
        return $SmartQuantPython
    }

    return "python"
}

function Invoke-Step {
    param(
        [string[]]$Command
    )

    Write-Host ">>> $($Command -join ' ')" -ForegroundColor Cyan

    & $Command[0] @($Command | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$PythonExe = Resolve-Python $Python
$env:PYTHONPATH = "src\python"
$Dashboard = Join-Path $RepoRoot "data\divergence_turning_point\edp_divergence_dashboard\dashboard.md"
$IntradayDashboard = Join-Path $RepoRoot "data\divergence_turning_point\edp_intraday_dashboard\dashboard.md"

if ($Intraday) {
    $IntradayCommand = @(
        $PythonExe,
        "-m", "edp_cli",
        "divergence", "intraday"
    )
    Invoke-Step -Command $IntradayCommand
    $Dashboard = $IntradayDashboard
} else {
    $DailyCommand = @(
        $PythonExe,
        "-m", "edp_cli",
        "divergence", "daily"
    )
    Invoke-Step -Command $DailyCommand
}

Write-Host ""
Write-Host "Done. Dashboard:" -ForegroundColor Green
Write-Host $Dashboard

if ($Open -and (Test-Path -LiteralPath $Dashboard)) {
    Invoke-Item $Dashboard
}
