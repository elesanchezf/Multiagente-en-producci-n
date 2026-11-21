# Ejecutar desde cualquier carpeta. No carga archivos .env.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
    $pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw 'Crea .venv con uv venv e instala requirements.lock.txt primero.'
    }
    $runDir = Join-Path $projectRoot ('evidence\runs\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null
    & $pythonExe -m pytest tests --cov=app --cov-fail-under=80 2>&1 |
        Tee-Object -FilePath (Join-Path $runDir 'pytest.txt')
    $testsCode = $LASTEXITCODE
    & $pythonExe -m pylint app tests --max-line-length=88 2>&1 |
        Tee-Object -FilePath (Join-Path $runDir 'pylint.txt')
    $styleCode = $LASTEXITCODE
    [ordered]@{
        date = (Get-Date).ToUniversalTime().ToString('o')
        tests_exit = $testsCode
        pylint_exit = $styleCode
        scope = 'Pruebas locales; no acredita proveedor real, despliegue ni LangSmith'
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDir 'result.json') -Encoding utf8
    if ($testsCode -ne 0 -or $styleCode -ne 0) { exit 1 }
} finally {
    Pop-Location
}
