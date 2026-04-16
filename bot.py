import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ESPERANDO_FOTO = 1
ESPERANDO_NOMBRE = 2
ESPERANDO_PRECIO = 3
ESPERANDO_CATEGORIA = 4

MAPA_CATEGORIAS = {"1": "Flores", "2": "Tejidos"}


def inicializar():
    os.makedirs("fotos", exist_ok=True)
    if not os.path.exists("productos.json"):
        with open("productos.json", "w", encoding="utf-8") as f:
            json.dump([], f)
    print("INFO: Carpeta /fotos OK")
    print("INFO: productos.json OK")


def normalizar_categoria(texto):
    return MAPA_CATEGORIAS.get(texto.strip(), None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Hola! Envía una foto de tu producto")
    return ESPERANDO_FOTO


async def texto_en_espera_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Primero envía una foto del producto.")
    return ESPERANDO_FOTO


async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Foto recibida")
    try:
        foto = update.message.photo[-1]
        file = await context.bot.get_file(foto.file_id)

        os.makedirs("fotos", exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        nombre_full  = f"foto_{ts}_full.jpg"
        nombre_thumb = f"foto_{ts}_thumb.jpg"
        ruta_full    = f"fotos/{nombre_full}"
        ruta_thumb   = f"fotos/{nombre_thumb}"

        # Descargar original
        await file.download_to_drive(ruta_full)
        print(f"DEBUG: Original guardado en: {ruta_full}")

        # Crear miniatura 300x300
        with Image.open(ruta_full) as img:
            img = img.convert("RGB")
            img.thumbnail((300, 300), Image.LANCZOS)
            img.save(ruta_thumb, "JPEG", quality=85)
        print(f"DEBUG: Miniatura guardada en: {ruta_thumb}")

        context.user_data["foto_full"]  = nombre_full
        context.user_data["foto_thumb"] = nombre_thumb
        await update.message.reply_text("¿Cuál es el nombre del producto?")
        return ESPERANDO_NOMBRE
    except Exception as e:
        print(f"ERROR en recibir_foto: {type(e).__name__}: {e}")
        await update.message.reply_text("❌ Error al guardar la foto. Intenta de nuevo.")
        return ESPERANDO_FOTO


async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    print(f"DEBUG: Nombre recibido = '{nombre}'")
    context.user_data["nombre"] = nombre
    await update.message.reply_text("¿Cuál es el precio?")
    return ESPERANDO_PRECIO


async def recibir_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    precio = update.message.text.strip()
    print(f"DEBUG: Precio recibido = '{precio}'")
    if not precio.replace(".", "").isdigit():
        await update.message.reply_text("❌ El precio debe ser un número. Intenta de nuevo")
        return ESPERANDO_PRECIO

    context.user_data["precio"] = precio
    await update.message.reply_text(
        "¿Cuál es la categoría?\n"
        "1\u20e3 Flores\n"
        "2\u20e3 Tejidos\n\n"
        "Escribe: 1 o 2"
    )
    return ESPERANDO_CATEGORIA


async def recibir_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()
    print(f"DEBUG: Categoría recibida = '{entrada}'")
    categoria = normalizar_categoria(entrada)
    print(f"DEBUG: Categoría normalizada = '{categoria}'")

    if categoria is None:
        if entrada.isdigit():
            msg = "❌ Opción no válida. Escribe 1 o 2"
        else:
            msg = "❌ Debes escribir 1 o 2"
        await update.message.reply_text(msg)
        return ESPERANDO_CATEGORIA

    nombre     = context.user_data.get("nombre", "")
    precio     = context.user_data.get("precio", "")
    foto_full  = context.user_data.get("foto_full", "")
    foto_thumb = context.user_data.get("foto_thumb", "")

    print(f"\n=== GUARDANDO PRODUCTO ===")
    print(f"nombre: {nombre}")
    print(f"precio: {precio}")
    print(f"categoria: {categoria}")
    print(f"foto_full: {foto_full}")
    print(f"foto_thumb: {foto_thumb}")

    try:
        if os.path.exists("productos.json"):
            with open("productos.json", "r", encoding="utf-8") as f:
                productos = json.load(f)
        else:
            productos = []

        nuevo_producto = {
            "id": len(productos) + 1,
            "nombre": nombre,
            "precio": precio,
            "categoria": categoria,
            "foto_thumb": foto_thumb,
            "foto_full":  foto_full,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        productos.append(nuevo_producto)

        with open("productos.json", "w", encoding="utf-8") as f:
            json.dump(productos, f, indent=2, ensure_ascii=False)

        print(f"JSON guardado correctamente. Total productos: {len(productos)}")
    except Exception as e:
        print(f"ERROR ESPECÍFICO: {type(e).__name__}: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}\nIntenta de nuevo")
        return ESPERANDO_CATEGORIA

    context.user_data.clear()

    await update.message.reply_text(
        f"✅ ¡{nombre} guardado en {categoria}!\n\nEnvía otra foto para agregar un nuevo producto."
    )
    return ESPERANDO_FOTO


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Operación cancelada. Usa /start para comenzar.")
    return ConversationHandler.END


def main():
    inicializar()

    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ESPERANDO_FOTO: [
                MessageHandler(filters.PHOTO, recibir_foto),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_espera_foto),
            ],
            ESPERANDO_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre),
            ],
            ESPERANDO_PRECIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio),
            ],
            ESPERANDO_CATEGORIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_categoria),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(conv_handler)

    print("Bot iniciado correctamente")
    logger.info("Bot iniciado correctamente")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
