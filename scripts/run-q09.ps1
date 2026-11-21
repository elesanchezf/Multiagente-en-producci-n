<#
.SYNOPSIS
  Valida solo Q09 (variante optimized) con Gemma real: maximo una llamada, sin reintentos.
.DESCRIPTION
  Requiere en ESTA ventana: CF_ACCOUNT_ID y CF_API_TOKEN. CF_GATEWAY_ID (por omision
  'default') y CF_AIG_TOKEN (solo si el gateway tiene autenticacion) son opcionales;
  use -GatewayRequiresAuth para exigir CF_AIG_TOKEN. Nunca imprime valores.
  -Plan solo muestra el plan y el presupuesto, sin red ni llamadas reales.
  AGENT_MAX_STEPS=1 es un ajuste solo de esta validacion. Al terminar el entorno se
  restaura y queda AGENT_MAX_STEPS=3, que es el valor para la comparacion completa.
#>
param(
    [switch]$Plan,
    [switch]$GatewayRequiresAuth
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$script = Join-Path $projectRoot 'scripts\eval_costs.py'
$touched = 'MODEL_SMALL', 'MODEL_LARGE', 'AGENT_MAX_STEPS', 'MODEL_EXTRA_PARAMS',
           'HIDE_INPUTS', 'HIDE_OUTPUTS', 'LANGSMITH_TRACING'
$saved = @{}
foreach ($name in $touched) { $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$code = 1
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Falta .venv: cree el entorno e instale requirements.lock.txt.' }
    $required = @('CF_ACCOUNT_ID', 'CF_API_TOKEN')
    if ($GatewayRequiresAuth) { $required += 'CF_AIG_TOKEN' }
    $status = foreach ($name in @('CF_ACCOUNT_ID', 'CF_GATEWAY_ID', 'CF_API_TOKEN', 'CF_AIG_TOKEN')) {
        $set = [bool][Environment]::GetEnvironmentVariable($name, 'Process')
        "{0}: {1}" -f $name, $(if ($set) { 'definida' } else { 'no definida' })
    }
    $status | ForEach-Object { Write-Host $_ }
    if (-not [Environment]::GetEnvironmentVariable('CF_GATEWAY_ID', 'Process')) {
        Write-Host 'CF_GATEWAY_ID no definida: se usara el gateway "default".'
    }
    if (-not $GatewayRequiresAuth -and -not [Environment]::GetEnvironmentVariable('CF_AIG_TOKEN', 'Process')) {
        Write-Host 'CF_AIG_TOKEN no definida: correcto solo si su gateway NO exige autenticacion.'
    }
    $missing = $required | Where-Object { -not [Environment]::GetEnvironmentVariable($_, 'Process') }
    if ($missing -and -not $Plan) { throw ('Faltan variables: ' + ($missing -join ', ')) }

    $env:MODEL_SMALL = '@cf/google/gemma-4-26b-a4b-it'
    $env:MODEL_LARGE = '@cf/meta/llama-3.3-70b-instruct-fp8-fast'
    $env:AGENT_MAX_STEPS = '1'
    $env:HIDE_INPUTS = 'true'
    $env:HIDE_OUTPUTS = 'true'
    $env:LANGSMITH_TRACING = 'false'
    $env:MODEL_EXTRA_PARAMS = '{"@cf/google/gemma-4-26b-a4b-it":{"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"}}}'

    $arguments = @($script, '--only', 'Q09', '--variants', 'optimized',
                   '--max-calls', '1', '--max-usd', '0.001', '--max-input-tokens', '1500')
    if (-not $Plan) { $arguments = @($script, '--run', 'real') + $arguments[1..($arguments.Count - 1)] }
    $logDir = Join-Path $projectRoot 'evidence\costs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logFile = Join-Path $logDir ("q09-console-$stamp" + $(if ($Plan) { '-plan' } else { '-real' }) + '.txt')
    & $pythonExe @arguments 2>&1 | Tee-Object -FilePath $logFile
    $code = $LASTEXITCODE
}
catch {
    Write-Host ('Error: ' + $_.Exception.Message)
    $code = 2
}
finally {
    foreach ($name in $touched) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    $env:AGENT_MAX_STEPS = '3'
    Pop-Location
    Write-Host 'Entorno restaurado. AGENT_MAX_STEPS=3 para la comparacion completa.'
    Write-Host "Codigo de salida: $code"
}
exit $code
