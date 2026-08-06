#!/bin/bash

echo "🚀 Iniciando servidor local (SIN CACHÉ)..."
echo ""

cd /home/juanitotrader/trading-dashboard

PORT=8000

cat > /tmp/server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import os

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Agregar headers para NO cachear
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        print(f"📥 GET {self.path}")
        super().do_GET()

os.chdir('/home/juanitotrader/trading-dashboard')

with socketserver.TCPServer(("", 8000), NoCacheHandler) as httpd:
    print("📍 Dashboard disponible en: http://localhost:8000")
    print("")
    print("🔄 Datos se actualizan en TIEMPO REAL")
    print("   (Sin caché del navegador)")
    print("")
    print("Para detener: presiona Ctrl+C")
    print("")
    httpd.serve_forever()
EOF

python3 /tmp/server.py
