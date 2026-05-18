#!/usr/bin/env bash
# test_apis.sh — Testea todas las APIs IA desde el conf del bot
set -e
cd "$(dirname "$0")"

CONF="../bots/milenium/iabot.conf"

# ── Leer valores del conf ──
read_val() { sed -n "/^\[$1\]/,/^\[/p" "$CONF" | grep "^$2 " | head -1 | cut -d= -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' ; }

# Gemini
G_KEY=$(read_val api api_key)
G_MODEL=$(read_val api model_name)

# OpenRouter
OR_KEY=$(read_val openrouter api_key)
OR_MODEL=$(read_val openrouter model_name)

# Groq
GQ_KEY=$(read_val groq api_key)
GQ_MODEL=$(read_val groq model_name)

# DeepSeek
DS_KEY=$(read_val deepseek api_key)
DS_MODEL=$(read_val deepseek model_name)

PROMPT='di solo OK'
PASS=0
FAIL=0

ok() { echo -e "\033[92m✅ $1\033[0m  $2"; ((PASS++)); }
fail() { echo -e "\033[91m❌ $1\033[0m  $2"; ((FAIL++)); }

echo "============================================================"
echo "  TEST APIs IA — $(date '+%d/%m/%Y %H:%M:%S')"
echo "============================================================"
echo ""

# ── 1. Gemini ──
if [[ -z "$G_KEY" ]]; then
  fail "Gemini" "No configurado"
else
  echo -e "\033[96m🔷 Gemini ($G_MODEL)...\033[0m"
  RESP=$(curl -s -X POST \
    "https://generativelanguage.googleapis.com/v1beta/models/$G_MODEL:generateContent?key=$G_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"contents\":[{\"parts\":[{\"text\":\"$PROMPT\"}]}]}")
  CODE=$(echo "$RESP" | grep -o '"text":"[^"]*"' | head -1 | cut -d\" -f4)
  if [[ -n "$CODE" ]]; then
    ok "Gemini" "$CODE"
  else
    fail "Gemini" "$(echo "$RESP" | head -c 120)"
  fi
fi

# ── 2. OpenRouter ──
if [[ -z "$OR_KEY" ]]; then
  fail "OpenRouter" "No configurado"
else
  echo -e "\033[96m🟠 OpenRouter ($OR_MODEL)...\033[0m"
  RESP=$(curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
    -H "Authorization: Bearer $OR_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$OR_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
  CODE=$(echo "$RESP" | grep -o '"content":"[^"]*"' | head -1 | cut -d\" -f4)
  if [[ -n "$CODE" ]]; then
    ok "OpenRouter" "$CODE"
  else
    fail "OpenRouter" "$(echo "$RESP" | head -c 120)"
  fi
fi

# ── 3. Groq ──
if [[ -z "$GQ_KEY" ]]; then
  fail "Groq" "No configurado"
else
  echo -e "\033[96m🟢 Groq ($GQ_MODEL)...\033[0m"
  RESP=$(curl -s -X POST "https://api.groq.com/openai/v1/chat/completions" \
    -H "Authorization: Bearer $GQ_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$GQ_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
  CODE=$(echo "$RESP" | grep -o '"content":"[^"]*"' | head -1 | cut -d\" -f4)
  if [[ -n "$CODE" ]]; then
    ok "Groq" "$CODE"
  else
    fail "Groq" "$(echo "$RESP" | head -c 120)"
  fi
fi

# ── 4. DeepSeek ──
if [[ -z "$DS_KEY" ]]; then
  fail "DeepSeek" "No configurado"
else
  echo -e "\033[96m🔵 DeepSeek ($DS_MODEL)...\033[0m"
  RESP=$(curl -s -X POST "https://api.deepseek.com/v1/chat/completions" \
    -H "Authorization: Bearer $DS_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$DS_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}]}")
  CODE=$(echo "$RESP" | grep -o '"content":"[^"]*"' | head -1 | cut -d\" -f4)
  if [[ -n "$CODE" ]]; then
    ok "DeepSeek" "$CODE"
  else
    fail "DeepSeek" "$(echo "$RESP" | head -c 120)"
  fi
fi

echo ""
echo "============================================================"
echo "  RESULTADO: $PASS pasados | $FAIL fallidos"
echo "============================================================"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
