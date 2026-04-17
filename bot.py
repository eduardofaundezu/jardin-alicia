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

# ── Estados ──────────────────────────────────────────────────
ESPERANDO_FOTO      = 1
ESPERANDO_NOMBRE    = 2
ESPERANDO_PRECIO    = 3
ESPERANDO_CATEGORIA = 4
CAMBIAR_FOTO_ESPERAR = 5
FONDOS_ESPERAR       = 6

MAPA_CATEGORIAS = {"1": "Flores", "2": "Tejidos"}

TEMAS = {
    "1":  {"nombre": "Verano",          "fondo": "verano"},
    "2":  {"nombre": "Primavera",       "fondo": "primavera"},
    "3":  {"nombre": "Otoño",           "fondo": "otono"},
    "4":  {"nombre": "Invierno",        "fondo": "invierno"},
    "5":  {"nombre": "Día del amor",    "fondo": "amor"},
    "6":  {"nombre": "Día de la madre", "fondo": "madre"},
    "7":  {"nombre": "Día del padre",   "fondo": "padre"},
    "8":  {"nombre": "Fiestas patrias", "fondo": "patrias"},
    "9":  {"nombre": "Navidad",         "fondo": "navidad"},
    "10": {"nombre": "Año nuevo",       "fondo": "ano_nuevo"},
    "11": {"nombre": "Minimalista",     "fondo": "minimalista"},
    "12": {"nombre": "Oscuro",          "fondo": "oscuro"},
}


def sugerir_fondo():
    """Sugiere un fondo según el mes actual (Chile, hemisferio sur)."""
    mes = datetime.now().month
    dia = datetime.now().day
    if mes == 12:
        return "9 (Navidad)"
    if mes == 1:
        return "10 (Año nuevo) o 1 (Verano)"
    if mes in (2, 3):
        return "1 (Verano)"
    if mes == 4 or (mes == 5 and dia < 15):
        return "3 (Otoño)"
    if mes == 5:
        return "6 (Día de la madre)"
    if mes in (6, 7):
        return "4 (Invierno)"
    if mes == 8:
        return "4 (Invierno)"
    if mes == 9 and 15 <= dia <= 20:
        return "8 (Fiestas patrias)"
    if mes in (9, 10, 11):
        return "2 (Primavera)"
    return ""


# ── Helpers ───────────────────────────────────────────────────
def inicializar():
    os.makedirs("fotos", exist_ok=True)
    if not os.path.exists("productos.json"):
        with open("productos.json", "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists("tema.json"):
        guardar_tema(TEMAS["1"])
    print("INFO: Carpeta /fotos OK")
    print("INFO: productos.json OK")
    print("INFO: tema.json OK")


def leer_productos():
    if not os.path.exists("productos.json"):
        return []
    with open("productos.json", "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_productos_lista(productos):
    with open("productos.json", "w", encoding="utf-8") as f:
        json.dump(productos, f, indent=2, ensure_ascii=False)


def reasignar_ids(productos):
    for i, p in enumerate(productos, start=1):
        p["id"] = i
    return productos


def guardar_tema(opcion):
    data = {
        "fondo_actual": opcion["fondo"],
        "archivo": f"{opcion['fondo']}.jpg",
    }
    with open("tema.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def borrar_foto(nombre):
    if nombre:
        ruta = f"fotos/{nombre}"
        try:
            if os.path.exists(ruta):
                os.remove(ruta)
                print(f"DEBUG: Foto eliminada: {ruta}")
        except Exception as e:
            print(f"WARN: No se pudo borrar {ruta}: {e}")


async def descargar_y_procesar_foto(bot, foto_msg):
    """Descarga foto de Telegram, guarda _full y _thumb. Retorna (nombre_full, nombre_thumb)."""
    file = await bot.get_file(foto_msg.file_id)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    nombre_full  = f"foto_{ts}_full.jpg"
    nombre_thumb = f"foto_{ts}_thumb.jpg"
    ruta_full    = f"fotos/{nombre_full}"
    ruta_thumb   = f"fotos/{nombre_thumb}"

    await file.download_to_drive(ruta_full)
    with Image.open(ruta_full) as img:
        img = img.convert("RGB")
        img.thumbnail((300, 300), Image.LANCZOS)
        img.save(ruta_thumb, "JPEG", quality=85)

    print(f"DEBUG: full={ruta_full}  thumb={ruta_thumb}")
    return nombre_full, nombre_thumb


def normalizar_categoria(texto):
    return MAPA_CATEGORIAS.get(texto.strip(), None)


# ── /start ────────────────────────────────────────────────────
async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Hola! Envía una foto de tu producto")
    return ESPERANDO_FOTO


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Menu administrador:\n\n"
        "/eliminar <ID> — borrar producto\n"
        "/modificar <ID> — cambiar foto\n"
        "/fondos — cambiar tema galería\n"
        "/salir — salir del menú"
    )


# ── Flujo principal: agregar producto ────────────────────────
async def texto_en_espera_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Primero envía una foto del producto.")
    return ESPERANDO_FOTO


async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Foto recibida (nuevo producto)")
    try:
        os.makedirs("fotos", exist_ok=True)
        nombre_full, nombre_thumb = await descargar_y_procesar_foto(
            context.bot, update.message.photo[-1]
        )
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
    print(f"DEBUG: Nombre = '{nombre}'")
    context.user_data["nombre"] = nombre
    await update.message.reply_text("¿Cuál es el precio?")
    return ESPERANDO_PRECIO


async def recibir_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    precio = update.message.text.strip()
    print(f"DEBUG: Precio = '{precio}'")
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
    entrada  = update.message.text.strip()
    categoria = normalizar_categoria(entrada)

    if categoria is None:
        msg = "❌ Opción no válida. Escribe 1 o 2" if entrada.isdigit() else "❌ Debes escribir 1 o 2"
        await update.message.reply_text(msg)
        return ESPERANDO_CATEGORIA

    nombre     = context.user_data.get("nombre", "")
    precio     = context.user_data.get("precio", "")
    foto_full  = context.user_data.get("foto_full", "")
    foto_thumb = context.user_data.get("foto_thumb", "")

    print(f"\n=== GUARDANDO PRODUCTO ===")
    print(f"nombre={nombre}  precio={precio}  cat={categoria}")
    print(f"foto_full={foto_full}  foto_thumb={foto_thumb}")

    try:
        productos = leer_productos()
        nuevo = {
            "id": len(productos) + 1,
            "nombre": nombre,
            "precio": precio,
            "categoria": categoria,
            "foto_thumb": foto_thumb,
            "foto_full":  foto_full,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        productos.append(nuevo)
        guardar_productos_lista(productos)
        print(f"Guardado. Total: {len(productos)}")
    except Exception as e:
        print(f"ERROR ESPECÍFICO: {type(e).__name__}: {e}")
        await update.message.reply_text(f"❌ Error: {e}\nIntenta de nuevo")
        return ESPERANDO_CATEGORIA

    pid = nuevo["id"]
    context.user_data.clear()
    await update.message.reply_text(
        f"✅ {nombre} guardado en {categoria}\n"
        f"Código: {pid} (guárdalo para modificar o eliminar)\n\n"
        f"Envía otra foto para agregar un nuevo producto."
    )
    return ESPERANDO_FOTO


# ── /listar ───────────────────────────────────────────────────
async def cmd_listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    productos = leer_productos()
    if not productos:
        await update.message.reply_text("No hay productos guardados.")
        return

    lineas = []
    for p in productos:
        nombre = p.get("nombre") or p.get("descripcion") or "Sin nombre"
        precio = p.get("precio", "—")
        cat    = p.get("categoria", "—")
        lineas.append(f"{p['id']}. {nombre} — ${precio} — {cat}")

    await update.message.reply_text("📋 Productos:\n\n" + "\n".join(lineas))


# ── /eliminar ─────────────────────────────────────────────────
async def cmd_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /eliminar <id>\nEjemplo: /eliminar 2")
        return

    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    productos = leer_productos()
    encontrado = next((p for p in productos if p.get("id") == pid), None)

    if not encontrado:
        await update.message.reply_text(f"❌ No existe producto con ID {pid}. Usa /listar para ver los IDs.")
        return

    # Borrar fotos
    borrar_foto(encontrado.get("foto_full"))
    borrar_foto(encontrado.get("foto_thumb"))
    borrar_foto(encontrado.get("foto"))          # formato viejo

    productos = [p for p in productos if p.get("id") != pid]
    productos = reasignar_ids(productos)
    guardar_productos_lista(productos)

    await update.message.reply_text(f"✅ Producto {pid} eliminado")


# ── /modificar ────────────────────────────────────────────────
async def cmd_cambiar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /modificar <id>\nEjemplo: /modificar 2")
        return ConversationHandler.END

    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return ConversationHandler.END

    productos = leer_productos()
    encontrado = next((p for p in productos if p.get("id") == pid), None)

    if not encontrado:
        await update.message.reply_text(f"❌ No existe producto con ID {pid}. Usa /listar.")
        return ConversationHandler.END

    context.user_data["cambiar_id"] = pid
    nombre = encontrado.get("nombre") or encontrado.get("descripcion") or "este producto"
    await update.message.reply_text(
        f"Enviame la nueva foto para: *{nombre}*\n\n/cancelar para abortar.",
        parse_mode="Markdown"
    )
    return CAMBIAR_FOTO_ESPERAR


async def recibir_nueva_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = context.user_data.get("cambiar_id")
    if pid is None:
        await update.message.reply_text("❌ Sesión perdida. Usa /modificar <id> de nuevo.")
        return ConversationHandler.END

    try:
        os.makedirs("fotos", exist_ok=True)
        nombre_full, nombre_thumb = await descargar_y_procesar_foto(
            context.bot, update.message.photo[-1]
        )
    except Exception as e:
        print(f"ERROR descargando nueva foto: {e}")
        await update.message.reply_text("❌ Error al guardar la foto. Intenta de nuevo.")
        return CAMBIAR_FOTO_ESPERAR

    productos = leer_productos()
    for p in productos:
        if p.get("id") == pid:
            # Borrar fotos viejas
            borrar_foto(p.get("foto_full"))
            borrar_foto(p.get("foto_thumb"))
            borrar_foto(p.get("foto"))
            # Asignar nuevas
            p["foto_full"]  = nombre_full
            p["foto_thumb"] = nombre_thumb
            p.pop("foto", None)   # quitar campo viejo si existía
            nombre = p.get("nombre") or p.get("descripcion") or "Producto"
            break

    guardar_productos_lista(productos)
    context.user_data.clear()
    await update.message.reply_text("✅ Foto actualizada")
    return ConversationHandler.END


# ── /fondos ───────────────────────────────────────────────────
async def cmd_fondos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sugerido = sugerir_fondo()
    sugerencia = f"\n\nSugerencia para esta época: {sugerido}" if sugerido else ""
    texto = (
        "Elige un fondo para la galería web:\n\n"
        "1\u20e3 Verano\n"
        "2\u20e3 Primavera\n"
        "3\u20e3 Otoño\n"
        "4\u20e3 Invierno\n"
        "5\u20e3 Día del amor\n"
        "6\u20e3 Día de la madre\n"
        "7\u20e3 Día del padre\n"
        "8\u20e3 Fiestas patrias\n"
        "9\u20e3 Navidad\n"
        "\U0001F51F Año nuevo\n"
        "11. Minimalista\n"
        "12. Oscuro"
        f"{sugerencia}\n\n"
        "Escribe el número:"
    )
    await update.message.reply_text(texto)
    return FONDOS_ESPERAR


async def recibir_fondo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()
    print(f"DEBUG fondos: Usuario escribió '{entrada}'")

    opcion = TEMAS.get(entrada)

    if opcion is None:
        print(f"DEBUG fondos: '{entrada}' no está en TEMAS. Claves: {list(TEMAS.keys())}")
        await update.message.reply_text("❌ Número inválido. Escribe un número del 1 al 12.")
        return FONDOS_ESPERAR

    try:
        guardar_tema(opcion)
        print(f"DEBUG fondos: Fondo guardado → {opcion['nombre']} ({opcion['fondo']}.jpg)")
    except Exception as e:
        print(f"ERROR fondos al guardar: {type(e).__name__}: {e}")
        await update.message.reply_text(f"❌ Error al guardar: {e}")
        return ConversationHandler.END

    context.user_data.clear()
    print("DEBUG fondos: Estado limpiado")

    await update.message.reply_text(f"✅ Fondo '{opcion['nombre']}' aplicado\nRecarga la galería (F5) para verlo.")
    return ConversationHandler.END


async def fondos_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG fondos: Timeout — conversación terminada por inactividad")
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selección de fondo cancelada por inactividad."
        )
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END


# ── /cancelar y /salir ───────────────────────────────────────
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Operación cancelada.\n"
        "Escribe /inicio para agregar producto o /admin para opciones."
    )
    return ConversationHandler.END


async def salir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Saliste del menú.\n"
        "Escribe /inicio para agregar producto."
    )
    return ConversationHandler.END


# ── main ──────────────────────────────────────────────────────
def main():
    inicializar()

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversación principal: agregar producto
    conv_agregar = ConversationHandler(
        entry_points=[CommandHandler("inicio", inicio)],
        states={
            ESPERANDO_FOTO: [
                MessageHandler(filters.PHOTO, recibir_foto),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_espera_foto),
            ],
            ESPERANDO_NOMBRE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)],
            ESPERANDO_PRECIO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio)],
            ESPERANDO_CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_categoria)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
        ],
        allow_reentry=True,
    )

    # Conversación: cambiar foto
    async def texto_en_cambiar_foto(u, c):
        await u.message.reply_text("Envía una foto, no texto. /salir para cancelar.")
        return CAMBIAR_FOTO_ESPERAR

    conv_cambiar_foto = ConversationHandler(
        entry_points=[CommandHandler("modificar", cmd_cambiar_foto)],
        states={
            CAMBIAR_FOTO_ESPERAR: [
                MessageHandler(filters.PHOTO, recibir_nueva_foto),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_cambiar_foto),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
            CommandHandler("admin",    admin),
            CommandHandler("inicio",   inicio),
        ],
        conversation_timeout=300,
        allow_reentry=True,
    )

    # Conversación: fondos
    conv_fondos = ConversationHandler(
        entry_points=[CommandHandler("fondos", cmd_fondos)],
        states={
            FONDOS_ESPERAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fondo),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, fondos_timeout),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar",  cancelar),
            CommandHandler("salir",     salir),
            CommandHandler("admin",     admin),
            CommandHandler("inicio",    inicio),
            CommandHandler("fondos",    cmd_fondos),
            CommandHandler("eliminar",  cmd_eliminar),
            CommandHandler("modificar", cmd_cambiar_foto),
        ],
        conversation_timeout=300,
        allow_reentry=True,
    )

    app.add_handler(conv_agregar)
    app.add_handler(conv_cambiar_foto)
    app.add_handler(conv_fondos)
    app.add_handler(CommandHandler("admin",    admin))
    app.add_handler(CommandHandler("eliminar", cmd_eliminar))
    # Registrar globalmente para que respondan fuera de cualquier flujo
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CommandHandler("salir",    salir))

    print("Bot iniciado correctamente")
    logger.info("Bot iniciado correctamente")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
