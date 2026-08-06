#!/bin/bash

set -e

echo "================================"
echo "🔐 CONFIGURAR CREDENCIALES ALPACA"
echo "================================"
echo ""

# Cuenta 1: QQQ, QQQM, TQQQ
echo "📊 CUENTA 1 (QQQ, QQQM, TQQQ)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "API Key (Cuenta 1): " ACCOUNT1_KEY
read -sp "API Secret (Cuenta 1): " ACCOUNT1_SECRET
echo ""
read -p "API Base URL (Cuenta 1) [https://paper-api.alpaca.markets]: " ACCOUNT1_URL
ACCOUNT1_URL=${ACCOUNT1_URL:-https://paper-api.alpaca.markets}

echo ""
echo "📊 CUENTA 2 (SPY)"
echo "━━━━━━━━━━━━━━━━━"
echo ""

read -p "API Key (Cuenta 2): " ACCOUNT2_KEY
read -sp "API Secret (Cuenta 2): " ACCOUNT2_SECRET
echo ""
read -p "API Base URL (Cuenta 2) [https://paper-api.alpaca.markets]: " ACCOUNT2_URL
ACCOUNT2_URL=${ACCOUNT2_URL:-https://paper-api.alpaca.markets}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Verificando credenciales..."
echo ""

# Verificar Cuenta 1
echo -n "Verificando Cuenta 1... "
RESPONSE1=$(curl -s -X GET "${ACCOUNT1_URL}/v2/account" \
  -H "APCA-API-KEY-ID: ${ACCOUNT1_KEY}" \
  -H "APCA-API-SECRET-KEY: ${ACCOUNT1_SECRET}")

if echo "$RESPONSE1" | grep -q "unauthorized"; then
  echo "❌ FALLO"
  echo "Respuesta: $RESPONSE1"
  exit 1
elif echo "$RESPONSE1" | grep -q "account_number"; then
  echo "✅ OK"
else
  echo "⚠️ RESPUESTA INESPERADA"
  echo "Respuesta: $RESPONSE1"
  exit 1
fi

# Verificar Cuenta 2
echo -n "Verificando Cuenta 2... "
RESPONSE2=$(curl -s -X GET "${ACCOUNT2_URL}/v2/account" \
  -H "APCA-API-KEY-ID: ${ACCOUNT2_KEY}" \
  -H "APCA-API-SECRET-KEY: ${ACCOUNT2_SECRET}")

if echo "$RESPONSE2" | grep -q "unauthorized"; then
  echo "❌ FALLO"
  echo "Respuesta: $RESPONSE2"
  exit 1
elif echo "$RESPONSE2" | grep -q "account_number"; then
  echo "✅ OK"
else
  echo "⚠️ RESPUESTA INESPERADA"
  echo "Respuesta: $RESPONSE2"
  exit 1
fi

echo ""
echo "✅ Credenciales verificadas correctamente"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📥 Descargando operaciones reales..."
echo ""

# Exportar variables de entorno
export APCA_API_KEY_ID="$ACCOUNT1_KEY"
export APCA_API_SECRET_KEY="$ACCOUNT1_SECRET"
export APCA_BASE_URL="$ACCOUNT1_URL"
export SPY_APCA_API_KEY="$ACCOUNT2_KEY"
export SPY_APCA_API_SECRET="$ACCOUNT2_SECRET"
export SPY_APCA_API_BASE_URL="$ACCOUNT2_URL"

# Ejecutar performance analyzer
cd "$(dirname "$0")"
python3 performance_analyzer.py

if [ $? -eq 0 ]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "✅ ÉXITO"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "📊 Datos guardados en: performance.json"
  echo ""
  echo "Próximos pasos:"
  echo "1. python3 capital_allocator.py"
  echo "2. python3 dashboard_generator.py"
  echo ""
else
  echo ""
  echo "❌ Error descargando datos"
  exit 1
fi
