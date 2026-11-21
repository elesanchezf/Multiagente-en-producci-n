<#
.SYNOPSIS
  Compara baseline (70B) y optimized (Gemma con enrutamiento) con las mismas 12 preguntas.
.DESCRIPTION
  Sin -ConfirmRealCalls solo muestra el plan (sin red ni inferencia). Con -ConfirmRealCalls
  hace llamadas reales: maximo 96 entre ambas variantes, sin reintentos automaticos.
  Requiere en ESTA ventana CF_ACCOUNT_ID y CF_API_TOKEN (CF_GATEWAY_ID por omision
  'default'; CF_AIG_TOKEN opcional, obligatoria con -GatewayRequiresAuth). Nunca imprime
  valores. Cada ejecucion crea una carpeta nueva en evidence\costs; si se detiene, conserva
  los resultados parciales (results.json con "complete": false). Los totales incluyen el
  consumo y el costo del revisor. Ambas variantes usan la misma tabla de precios
  (resultados con 0,05/0,30 para Gemma; 0,10 solo como reserva de presupuesto).
  -Only (ids, p. ej. Q05,Q06), -Variants (baseline,optimized) y -MaxCalls permiten continuar
  una comparacion parcial sin repetir lo ya ejecutado.
  AGENT_MAX_STEPS=3. HIDE_INPUTS/HIDE_OUTPUTS=true y trazas apagadas. El entorno se
  restaura al final.
#>
param(
    [switch]$ConfirmRealCalls,
    [switch]$GatewayRequiresAuth,
    [double]$MaxUsd = 0.08,
    [int]$MaxCalls = 96,
    [string]$Only = '',
    [string]$Variants = ''
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
    if ($MaxUsd -le 0) { throw 'MaxUsd debe ser mayor que 0.' }
    $required = @('CF_ACCOUNT_ID', 'CF_API_TOKEN')
    if ($GatewayRequiresAuth) { $required += 'CF_AIG_TOKEN' }
    foreach ($name in @('CF_ACCOUNT_ID', 'CF_GATEWAY_ID', 'CF_API_TOKEN', 'CF_AIG_TOKEN')) {
        $set = [bool][Environment]::GetEnvironmentVariable($name, 'Process')
        Write-Host ("{0}: {1}" -f $name, $(if ($set) { 'definida' } else { 'no definida' }))
    }
    if (-not [Environment]::GetEnvironmentVariable('CF_GATEWAY_ID', 'Process')) {
        Write-Host 'CF_GATEWAY_ID no definida: se usara el gateway "default".'
    }
    if (-not $GatewayRequiresAuth -and -not [Environment]::GetEnvironmentVariable('CF_AIG_TOKEN', 'Process')) {
        Write-Host 'CF_AIG_TOKEN no definida: correcto solo si su gateway NO exige autenticacion.'
    }
    $missing = $required | Where-Object { -not [Environment]::GetEnvironmentVariable($_, 'Process') }
    if ($missing -and $ConfirmRealCalls) { throw ('Faltan variables: ' + ($missing -join ', ')) }

    $env:MODEL_SMALL = '@cf/google/gemma-4-26b-a4b-it'
    $env:MODEL_LARGE = '@cf/meta/llama-3.3-70b-instruct-fp8-fast'
    $env:AGENT_MAX_STEPS = '3'
    $env:HIDE_INPUTS = 'true'
    $env:HIDE_OUTPUTS = 'true'
    $env:LANGSMITH_TRACING = 'false'
    $env:MODEL_EXTRA_PARAMS = '{"@cf/google/gemma-4-26b-a4b-it":{"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"}}}'

    $arguments = @($script)
    if ($ConfirmRealCalls) { $arguments += @('--run', 'real') }
    else { Write-Host 'Modo plan: sin llamadas reales. Use -ConfirmRealCalls para ejecutar.' }
    if ($MaxCalls -lt 1) { throw 'MaxCalls debe ser al menos 1.' }
    $arguments += @('--max-calls', ([string]$MaxCalls), '--max-usd', ([string]$MaxUsd), '--max-input-tokens', '3000')
    if ($Only) { $arguments += @('--only', $Only) }
    if ($Variants) { $arguments += @('--variants', $Variants) }
    $logDir = Join-Path $projectRoot 'evidence\costs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logFile = Join-Path $logDir ("comparison-console-$stamp" + $(if ($ConfirmRealCalls) { '-real' } else { '-plan' }) + '.txt')
    & $pythonExe @arguments 2>&1 | Tee-Object -FilePath $logFile
    $code = $LASTEXITCODE
}
catch {
    Write-Host ('Error: ' + $_.Exception.Message)
    $code = 2
}
finally {
    foreach ($name in $touched) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
    Pop-Location
    Write-Host 'Entorno restaurado.'
    Write-Host "Codigo de salida: $code (0 = completa; 1 = parcial o detenida; 2 = error previo)"
}
exit $code
