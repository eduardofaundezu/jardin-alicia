from flask import Flask, send_from_directory
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            static_folder=BASE_DIR,
            static_url_path='')

@app.route('/')
def index():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/productos.json')
def get_productos():
    with open('productos.json', 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/tema.json')
def get_tema():
    with open('tema.json', 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
