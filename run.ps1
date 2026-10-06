$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$deliveryPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $deliveryPython)) {
    throw 'Environnement Python absent. Suivez la préparation dans README.md.'
}
& $deliveryPython -m flask --app wsgi run --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
