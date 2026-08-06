#!/bin/bash

# Script para guardar las credenciales UNA SOLA VEZ
# Después de esto, solo ejecutas "bash update.sh" sin pedir keys

echo "🔐 CONFIGURACIÓN INICIAL (Solo una vez)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Archivo de configuración (oculto)
CONFIG_FILE="$HOME/.trading_dashboard_creds"

echo "📊 CUENTA 1 (QQQ, QQQM, TQQQ)"
read -p "API Key: " ACC1_KEY
read -sp "API Secret: " ACC1_SECRET
echo ""

echo ""
echo "📊 CUENTA 2 (SPY)"
read -p "API Key: " ACC2_KEY
read -sp "API Secret: " ACC2_SECRET
echo ""

# Guardar en archivo
cat > "$CONFIG_FILE" << EOF
#!/bin/bash
export APCA_API_KEY_ID="$ACC1_KEY"
export APCA_API_SECRET_KEY="$ACC1_SECRET"
export APCA_BASE_URL="https://paper-api.alpaca.markets"
export SPY_APCA_API_KEY="$ACC2_KEY"
export SPY_APCA_API_SECRET="$ACC2_SECRET"
export SPY_APCA_API_BASE_URL="https://paper-api.alpaca.markets"
EOF

chmod 600 "$CONFIG_FILE"

echo ""
echo "✅ Credenciales guardadas en: $CONFIG_FILE"
echo ""
echo "Próximo paso:"
echo "  bash /home/juanitotrader/trading-dashboard/update.sh"
