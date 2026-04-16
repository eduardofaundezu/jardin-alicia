import http.server
import socketserver
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Servidor iniciado en http://localhost:{PORT}/")
    print(f"Abre en tu navegador: http://localhost:{PORT}/index.html")
    print(f"Presiona Ctrl+C para detener")
    httpd.serve_forever()
