from flask import Flask, jsonify
import os
import json

app = Flask(__name__)

@app.route('/')
def index():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/productos.json')
def productos():
    try:
        with open('productos.json', 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify([]), 200  # Retorna array vacío si no existe
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tema.json')
def tema():
    try:
        with open('tema.json', 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fotos/<filename>')
def serve_foto(filename):
    try:
        with open(f'fotos/{filename}', 'rb') as f:
            return f.read(), 200, {'Content-Type': 'image/jpeg'}
    except Exception as e:
        return f"Error: {str(e)}", 404

@app.route('/fondos_precargados/<filename>')
def serve_fondo(filename):
    try:
        with open(f'fondos_precargados/{filename}', 'rb') as f:
            return f.read(), 200, {'Content-Type': 'image/jpeg'}
    except Exception as e:
        return f"Error: {str(e)}", 404

@app.route('/debug')
def debug():
    fotos = os.listdir('fotos') if os.path.exists('fotos') else []
    return {
        'fotos_en_servidor': fotos,
        'cantidad': len(fotos)
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
