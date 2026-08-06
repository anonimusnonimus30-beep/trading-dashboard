#!/bin/bash

# Script para ver el dashboard localmente

cd /home/juanitotrader/trading-dashboard

PORT=8000

echo "🌐 Abriendo Dashboard..."
echo ""
echo "   Dirección: http://localhost:$PORT"
echo ""
echo "Presiona Ctrl+C para detener"
echo ""

# Intentar abrir en navegador automáticamente
if command -v xdg-open > /dev/null; then
  xdg-open "http://localhost:$PORT" 2>/dev/null &
elif command -v open > /dev/null; then
  open "http://localhost:$PORT" 2>/dev/null &
fi

# Servir archivos SIN CACHÉ
python3 << 'EOF'
import http.server
import socketserver
import os

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

os.chdir('/home/juanitotrader/trading-dashboard')
with socketserver.TCPServer(("", 8000), NoCacheHandler) as httpd:
    httpd.serve_forever()
EOF
