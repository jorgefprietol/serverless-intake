param([ValidateSet('demo','serve','test')][string]$Mode = 'demo', [int]$Port = 8080)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$virtualPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$projectPython = if ($env:PROJECT_PYTHON) { $env:PROJECT_PYTHON } elseif (Test-Path -LiteralPath $virtualPython) { $virtualPython } else { 'python' }
if ($Mode -eq 'test') { & $projectPython -m unittest discover -s tests -v; exit $LASTEXITCODE }
if ($Mode -eq 'serve') {
    if (-not $env:SERVICE_TOKEN) { $env:SERVICE_TOKEN = [guid]::NewGuid().ToString('N') }
    Write-Host "Consola: http://127.0.0.1:$Port"
    Write-Host "Token para la consola (sólo esta sesión): $env:SERVICE_TOKEN"
    & $projectPython -m app serve --port $Port
} else { & $projectPython -m app demo }
exit $LASTEXITCODE
