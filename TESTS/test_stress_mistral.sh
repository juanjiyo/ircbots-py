#!/usr/bin/env bash
# test_stress_mistral.sh — Test de estrés para Mistral AI
# Envía N peticiones secuenciales y mide rendimiento.
# AUTOCONTENIDO — no depende de archivos externos.

set -e
cd "$(dirname "$0")"

MS_KEY="OPENROUTER_API_KEY_OLD"
MS_MODEL="mistral-small-latest"

echo "============================================================"
echo "  TEST DE ESTRÉS — Mistral AI ($MS_MODEL)"
echo "  Fecha: $(date '+%d/%m/%Y %H:%M:%S')"
echo "============================================================"

PROMPTS=(
    "Dilema causal: Describe cocinar un huevo en un universo donde el efecto precede a la causa pero la memoria es lineal."
    "Refactorización: Escribe Quicksort en C sin usar recursividad ni stdlib.h, optimizado para caché L1."
    "Bio-Música: Explica la 5ta Sinfonía de Beethoven usando términos de síntesis de proteínas y replicación de ADN."
    "Geopolítica Ficticia: Impacto en el mercado de futuros del petróleo si la gravedad lunar baja un 15%."
    "Restricción Lipogramática: Explica el ciclo de Carnot sin usar la letra 'e' en español."
    "Lógica Borrosa: Diseña un JSON para una base de datos de recuerdos humanos contradictorios."
    "Lingüística: Inventa un idioma de 5 verbos que explique la Relatividad Especial y traduce E=mc2."
    "Seguridad: Analiza este código hipotético en busca de vulnerabilidades de desbordamiento de buffer: char buf[10]; gets(buf);"
    "Matemática Abstracta: ¿Es el conjunto de todos los conjuntos que no se contienen a sí mismos un miembro de sí mismo?"
    "Teoremas de la Incompletitud de Gödel"
    "Teorema de Pitágoras"
    "Improbabilidad del Axioma de Elección en la Teoría de Conjuntos ZF"
    "Existencia de infinitos primos"
	"Fundamental theorem of calculus"
	"Teorema de Darboux"
	"Teorema de Desargues"
	"Teorema de Dandelin"
	"El principio de Arquímedes"
	"Teoría de la relatividad"
	"Teoría del Big Bang"
)

NUM_REQUESTS=${#PROMPTS[@]}
API_URL="https://api.mistral.ai/v1/chat/completions"
PASS=0
FAIL=0
TOTAL_TIME=0
FASTEST=999
SLOWEST=0

for i in $(seq 0 $((NUM_REQUESTS - 1))); do
    prompt="${PROMPTS[$i]}"
    N=$((i + 1))
    START=$(date +%s%N)

    RESP=$(curl -s --max-time 30 -X POST "$API_URL" \
        -H "Authorization: Bearer $MS_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MS_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$prompt\"}],\"max_tokens\":100,\"temperature\":0}")

    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))  # ms
    TOTAL_TIME=$((TOTAL_TIME + ELAPSED))

    CODE=$(echo "$RESP" | grep -o '"content":"[^"]*"' | head -1 | cut -d\" -f4)

    if [[ -n "$CODE" ]]; then
        PASS=$((PASS + 1))
        STATUS="✅ $ELAPSED ms"
    else
        FAIL=$((FAIL + 1))
        STATUS="❌ $ELAPSED ms  $(echo "$RESP" | head -c 60)"
    fi

    # Track fastest/slowest
    if (( ELAPSED < FASTEST )); then FASTEST=$ELAPSED; fi
    if (( ELAPSED > SLOWEST )); then SLOWEST=$ELAPSED; fi

    printf "  [%2d/%2d] %-40s %s\n" "$N" "$NUM_REQUESTS" "$prompt" "$STATUS"
done

AVG=$((TOTAL_TIME / NUM_REQUESTS))

echo ""
echo "============================================================"
echo "  RESULTADOS"
echo "============================================================"
echo "  ✅ Pasados:  $PASS"
echo "  ❌ Fallidos: $FAIL"
echo "  📊 Total:    $NUM_REQUESTS"
echo "  ⏱️  Promedio:  ${AVG} ms"
echo "  ⚡ Más rápido: ${FASTEST} ms"
echo "  🐌 Más lento:  ${SLOWEST} ms"
echo "  📈 Tiempo total: ${TOTAL_TIME} ms"
echo "============================================================"
