#!/bin/bash

echo "🚀 Iniciando servidor local del dashboard..."
echo ""

cd /home/juanitotrader/trading-dashboard

PORT=8000

echo "📍 Dashboard disponible en:"
echo "   http://localhost:${PORT}"
echo ""
echo "Para detener el servidor: presiona Ctrl+C"
echo ""

python3 -m http.server $PORT
