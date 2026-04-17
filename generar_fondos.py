"""
Genera las 12 imágenes de fondo para la galería.
Ejecutar una sola vez: python generar_fondos.py
"""
from PIL import Image, ImageFilter, ImageDraw
import os

FONDOS = [
    # (archivo,       color_arriba, color_abajo)
    ("verano",        "#F4A233", "#E05A1A"),
    ("primavera",     "#A8D5A2", "#E8B4CB"),
    ("otono",         "#C96A1F", "#7B3B0D"),
    ("invierno",      "#7EB8D4", "#BDD9F0"),
    ("amor",          "#C0392B", "#8E0045"),
    ("madre",         "#9B59B6", "#E91E8C"),
    ("padre",         "#1A3A5C", "#2471A3"),
    ("patrias",       "#CC1414", "#002FA7"),
    ("navidad",       "#1A6B30", "#8B0000"),
    ("ano_nuevo",     "#0D0D2B", "#4A0080"),
    ("minimalista",   "#DCDCDC", "#B0B0B0"),
    ("oscuro",        "#0D0D0D", "#1A1A2E"),
]

W, H = 1280, 720


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def crear_imagen(color1_hex, color2_hex):
    c1 = hex_to_rgb(color1_hex)
    c2 = hex_to_rgb(color2_hex)

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    img = img.filter(ImageFilter.GaussianBlur(radius=22))
    return img


os.makedirs("fondos_precargados", exist_ok=True)

for nombre, c1, c2 in FONDOS:
    ruta = f"fondos_precargados/{nombre}.jpg"
    img = crear_imagen(c1, c2)
    img.save(ruta, "JPEG", quality=85, optimize=True)
    size_kb = os.path.getsize(ruta) // 1024
    print(f"  {ruta}  ({size_kb} KB)")

print(f"\nListo. {len(FONDOS)} fondos generados en fondos_precargados/")
