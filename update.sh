#!/bin/bash

# Script para actualizar datos (sin pedir credenciales)
# Las credenciales están guardadas en ~/.trading_dashboard_creds

CONFIG_FILE="$HOME/.trading_dashboard_creds"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "❌ Error: Credenciales no configuradas"
  echo ""
  echo "Primero ejecuta:"
  echo "  bash /home/juanitotrader/trading-dashboard/setup_once.sh"
  exit 1
fi

# Cargar credenciales
source "$CONFIG_FILE"

cd /home/juanitotrader/trading-dashboard

echo "📥 Actualizando datos de Alpaca..."
echo ""

python3 performance_analyzer.py

if [ $? -eq 0 ]; then
  echo ""
  echo "📍 Consultando posición actual y próxima señal..."
  BOTS_READ_TOKEN="$(gh auth token 2>/dev/null)" python3 positions_analyzer.py

  echo ""
  echo "💰 Calculando capital..."
  python3 capital_allocator.py

  echo ""
  echo "🎨 Generando dashboard..."
  python3 dashboard_generator.py

  echo ""
  echo "✅ COMPLETADO"
  echo ""
  echo "Abre en navegador:"
  echo "  http://localhost:8000"
else
  echo "❌ Error descargando datos"
  exit 1
fi
