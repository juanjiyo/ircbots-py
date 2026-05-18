# Log de errores para depuración
$logFile = Join-Path $PSScriptRoot "stress_test.log"
Start-Transcript -Path $logFile -Force -Append | Out-Null

try {

$MS_KEY   = "OPENROUTER_API_KEY_OLD"
$MS_MODEL = "mistral-small-latest"
$API_URL  = "https://api.mistral.ai/v1/chat/completions"

$prompts = @(
    "Di solo OK"
    "¿Cuál es la capital de Francia?"
    "Traduce 'hello world' al español"
    "Escribe un haiku sobre el mar"
    "¿Cuánto es 2+2?"
    "Nombra 3 colores primarios"
    "¿Qué es un bot IRC?"
    "Di una frase motivadora corta"
    "¿En qué año llegó el hombre a la luna?"
    "Resume en una palabra: programación"
)

Write-Host "============================================================"
Write-Host "  TEST DE ESTRÉS — Mistral AI ($MS_MODEL)" -ForegroundColor Cyan
Write-Host "  Fecha: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"
Write-Host "============================================================`n"

$pass = 0; $fail = 0; $times = @()
$headers = @{ "Authorization" = "Bearer $MS_KEY"; "Content-Type" = "application/json" }

foreach ($p in $prompts) {
    $n = $prompts.IndexOf($p) + 1
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $body  = @{ model = $MS_MODEL; messages = @(@{ role = "user"; content = $p }); max_tokens = 100; temperature = 0 } | ConvertTo-Json -Compress
        $resp = Invoke-RestMethod -Uri $API_URL -Headers $headers -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 30
        $sw.Stop()
        $ms = $sw.ElapsedMilliseconds
        $times += $ms
        $content = $resp.choices[0].message.content.Trim()
        if ($content) { $pass++; $status = "✅ $ms ms  | $content" }
        else          { $fail++; $status = "❌ $ms ms  | respuesta vacía" }
    } catch {
        $sw.Stop(); $ms = $sw.ElapsedMilliseconds; $times += $ms
        $fail++; $status = "❌ $ms ms  | $($_.Exception.Message)"
    }
    $display = if ($p.Length -gt 40) { $p.Substring(0,40) + "..." } else { $p }
    Write-Host ("  [{0,2}/{1}] {2,-42} {3}" -f $n, $prompts.Count, $display, $status)
}

$avg    = [math]::Round(($times | Measure-Object -Average).Average)
$fast   = ($times | Measure-Object -Minimum).Minimum
$slow   = ($times | Measure-Object -Maximum).Maximum
$total  = ($times | Measure-Object -Sum).Sum

Write-Host "`n============================================================"
Write-Host "  RESULTADOS" -ForegroundColor Cyan
Write-Host "============================================================"
Write-Host "  ✅ Pasados:    $pass"
Write-Host "  ❌ Fallidos:   $fail"
Write-Host "  📊 Total:      $($prompts.Count)"
Write-Host "  ⏱️  Promedio:   $avg ms"
Write-Host "  ⚡ Más rápido:  $fast ms"
Write-Host "  🐌 Más lento:   $slow ms"
Write-Host "  📈 Tiempo total: $total ms"
Write-Host "============================================================"

} catch {
    Write-Host "`n❌ ERROR CRÍTICO: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    $_ | Out-File -FilePath $logFile -Append -Encoding utf8
} finally {
    Stop-Transcript
    Write-Host "`n📝 Log guardado en: $logFile" -ForegroundColor Gray
    Read-Host "Presiona Enter para cerrar"
}
