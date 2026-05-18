@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================================
echo   TEST DE ESTRIS - Mistral AI
echo   Fecha: %date% %time%
echo ============================================================
echo.

set MS_KEY=OPENROUTER_API_KEY_OLD
set MS_MODEL=mistral-small-latest
set API_URL=https://api.mistral.ai/v1/chat/completions

set PASS=0
set FAIL=0
set TOTAL=10
set TOTAL_TIME=0
set FASTEST=99999
set SLOWEST=0

set PROMPTS[0]=Di solo OK
set PROMPTS[1]=Cual es la capital de Francia?
set PROMPTS[2]=Traduce hello world al espanol
set PROMPTS[3]=Escribe un haiku sobre el mar
set PROMPTS[4]=Cuanto es 2+2?
set PROMPTS[5]=Nombra 3 colores primarios
set PROMPTS[6]=Que es un bot IRC?
set PROMPTS[7]=Di una frase motivadora corta
set PROMPTS[8]=En que ano llego el hombre a la luna?
set PROMPTS[9]=Resume en una palabra: programacion

for /L %%i in (0,1,9) do (
    set /A N=%%i+1
    set P=!PROMPTS[%%i]!

    for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
    set /A START_MS=%dt:~0,14%

    curl -s --max-time 30 -X POST "%API_URL%" ^
        -H "Authorization: Bearer %MS_KEY%" ^
        -H "Content-Type: application/json" ^
        -d "{\"model\":\"%MS_MODEL%\",\"messages\":[{\"role\":\"user\",\"content\":\"!P!\"}],\"max_tokens\":100,\"temperature\":0}" > "%TEMP%\resp_%%i.json" 2>nul

    for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
    set /A END_MS=%dt:~0,14%
    set /A ELAPSED=!END_MS!-!START_MS!
    set /A ELAPSED=!ELAPSED!*1000

    set /A TOTAL_TIME+=!ELAPSED!

    findstr /c:"content" "%TEMP%\resp_%%i.json" >nul 2>nul
    if !errorlevel! equ 0 (
        set STATUS=✅ !ELAPSED! ms
        set /A PASS+=1
    ) else (
        set STATUS=❌ !ELAPSED! ms
        set /A FAIL+=1
    )

    if !ELAPSED! LSS !FASTEST! set FASTEST=!ELAPSED!
    if !ELAPSED! GTR !SLOWEST! set SLOWEST=!ELAPSED!

    echo   [!N!/%TOTAL%] !P:~0,40!                                    !STATUS!
    del "%TEMP%\resp_%%i.json" >nul 2>nul
)

if %TOTAL% GTR 0 set /A AVG=%TOTAL_TIME%/%TOTAL%

echo.
echo ============================================================
echo   RESULTADOS
echo ============================================================
echo   ✅ Pasados:    %PASS%
echo   ❌ Fallidos:   %FAIL%
echo   📊 Total:      %TOTAL%
echo   ⏱️  Promedio:   %AVG% ms
echo   ⚡ Mas rapido:  %FASTEST% ms
echo   🐌 Mas lento:   %SLOWEST% ms
echo   📈 Tiempo total: %TOTAL_TIME% ms
echo ============================================================
echo.
pause
