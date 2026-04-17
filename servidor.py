from flask import Flask, send_from_directory
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Servidor iniciado en http://localhost:{port}/")
    app.run(host='0.0.0.0', port=port, debug=False)
