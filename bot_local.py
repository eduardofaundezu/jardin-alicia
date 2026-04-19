import asyncio
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

BOT_TOKEN        = os.getenv("BOT_TOKEN")
BOT_TOKEN_MAMA   = os.getenv("BOT_TOKEN_MAMA")
CONTACTO_EDUARDO = os.getenv("CONTACTO_EDUARDO", "")
CONTACTO_MAMA    = os.getenv("CONTACTO_MAMA", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Estados ──────────────────────────────────────────────────
ESPERANDO_FOTO          = 1
ESPERANDO_NOMBRE        = 2
ESPERANDO_PRECIO        = 3
ESPERANDO_CATEGORIA     = 4
CAMBIAR_FOTO_ESPERAR    = 5
FONDOS_ESPERAR          = 6
ESPERANDO_COMANDO       = 7
ESPERANDO_OBSERVACIONES = 8

MAPA_CATEGORIAS = {
    "1": "Flores",
    "2": "Plantas",
    "3": "Textil",
    "4": "Crochet",
    "5": "Varios",
}

TEMAS = {
    "1": {"nombre": "Primavera",       "fondo": "primavera"},
    "2": {"nombre": "Verano",          "fondo": "verano"},
    "3": {"nombre": "Otoño",           "fondo": "otono"},
    "4": {"nombre": "Invierno",        "fondo": "invierno"},
    "5": {"nombre": "Día de Madres",   "fondo": "madre"},
    "6": {"nombre": "Fiestas Patrias", "fondo": "patrias"},
    "7": {"nombre": "Navidad",         "fondo": "navidad"},
}


def sugerir_fondo():
    mes = datetime.now().month
    dia = datetime.now().day
    if mes == 12:
        return "7 (Navidad)"
    if mes in (1, 2, 3):
        return "2 (Verano)"
    if mes == 4 or (mes == 5 and dia < 10):
        return "3 (Otoño)"
    if mes == 5:
        return "5 (Día de Madres)"
    if mes in (6, 7, 8):
        return "4 (Invierno)"
    if mes == 9 and 15 <= dia <= 20:
        return "6 (Fiestas Patrias)"
    if mes in (9, 10, 11):
        return "1 (Primavera)"
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
        except Exception as e:
            print(f"WARN: No se pudo borrar {ruta}: {e}")


async def descargar_y_procesar_foto(bot, foto_msg):
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

    return nombre_full, nombre_thumb


def normalizar_categoria(texto):
    return MAPA_CATEGORIAS.get(texto.strip(), None)


# ── /inicio ────────────────────────────────────────────────────
async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message.chat.type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Usa privado: @Jardin_131_bot para subir fotos")
        return ConversationHandler.END
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
    context.user_data["nombre"] = update.message.text.strip()
    await update.message.reply_text("¿Cuál es el precio?")
    return ESPERANDO_PRECIO


async def recibir_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    precio = update.message.text.strip()
    if not precio.replace(".", "").isdigit():
        await update.message.reply_text("❌ El precio debe ser un número. Intenta de nuevo")
        return ESPERANDO_PRECIO
    context.user_data["precio"] = precio
    await update.message.reply_text(
        "¿Cuál es la categoría?\n\n"
        "1️⃣ Flores\n"
        "2️⃣ Plantas\n"
        "3️⃣ Textil\n"
        "4️⃣ Crochet\n"
        "5️⃣ Varios\n\n"
        "Escribe: 1, 2, 3, 4 o 5"
    )
    return ESPERANDO_CATEGORIA


async def recibir_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada   = update.message.text.strip()
    categoria = normalizar_categoria(entrada)

    if categoria is None:
        await update.message.reply_text("❌ Escribe un número del 1 al 5")
        return ESPERANDO_CATEGORIA

    context.user_data["categoria"] = categoria
    await update.message.reply_text(
        "Agrega una descripción u observaciones\n"
        "(cuidados, tamaño, materiales, etc.)\n\n"
        "Envía - para omitir."
    )
    return ESPERANDO_OBSERVACIONES


async def recibir_observaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    observaciones = "" if texto in ("-", ".") else texto

    nombre     = context.user_data.get("nombre", "")
    precio     = context.user_data.get("precio", "")
    categoria  = context.user_data.get("categoria", "")
    foto_full  = context.user_data.get("foto_full", "")
    foto_thumb = context.user_data.get("foto_thumb", "")
    contacto   = context.application.bot_data.get("contacto", "")

    print(f"\n=== GUARDANDO PRODUCTO ===")
    print(f"nombre={nombre}  precio={precio}  cat={categoria}  obs={observaciones[:30]}")

    try:
        productos = leer_productos()
        nuevo = {
            "id":            len(productos) + 1,
            "nombre":        nombre,
            "precio":        precio,
            "categoria":     categoria,
            "contacto":      contacto,
            "observaciones": observaciones,
            "foto_thumb":    foto_thumb,
            "foto_full":     foto_full,
            "fecha":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        productos.append(nuevo)
        guardar_productos_lista(productos)
        print(f"Guardado. Total: {len(productos)}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        await update.message.reply_text(f"❌ Error: {e}\nIntenta de nuevo")
        return ESPERANDO_OBSERVACIONES

    pid = nuevo["id"]
    context.user_data.clear()
    obs_linea = f"\nObs: {observaciones}" if observaciones else ""
    await update.message.reply_text(
        f"✅ {nombre} guardado en {categoria}\n"
        f"Código: {pid}{obs_linea}\n\n"
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
        lineas.append(f"{p['id']}. {nombre} — ${p.get('precio','—')} — {p.get('categoria','—')}")

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
        await update.message.reply_text(f"❌ No existe producto con ID {pid}.")
        return

    borrar_foto(encontrado.get("foto_full"))
    borrar_foto(encontrado.get("foto_thumb"))
    borrar_foto(encontrado.get("foto"))

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
        await update.message.reply_text(f"❌ No existe producto con ID {pid}.")
        return ConversationHandler.END

    context.user_data["cambiar_id"] = pid
    nombre = encontrado.get("nombre") or "este producto"
    await update.message.reply_text(
        f"Enviame la nueva foto para: *{nombre}*\n\n/cancelar para abortar.",
        parse_mode="Markdown",
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
            borrar_foto(p.get("foto_full"))
            borrar_foto(p.get("foto_thumb"))
            borrar_foto(p.get("foto"))
            p["foto_full"]  = nombre_full
            p["foto_thumb"] = nombre_thumb
            p.pop("foto", None)
            break

    guardar_productos_lista(productos)
    context.user_data.clear()
    await update.message.reply_text("✅ Foto actualizada")
    return ConversationHandler.END


# ── /fondos ───────────────────────────────────────────────────
async def cmd_fondos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sugerido   = sugerir_fondo()
    sugerencia = f"\n\nSugerencia: {sugerido}" if sugerido else ""
    texto = (
        "Elige un fondo para la galería:\n\n"
        "1️⃣ Primavera\n"
        "2️⃣ Verano\n"
        "3️⃣ Otoño\n"
        "4️⃣ Invierno\n"
        "5️⃣ Día de Madres\n"
        "6️⃣ Fiestas Patrias\n"
        "7️⃣ Navidad"
        f"{sugerencia}\n\n"
        "Escribe el número:"
    )
    await update.message.reply_text(texto)
    return FONDOS_ESPERAR


async def recibir_fondo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()
    opcion  = TEMAS.get(entrada)

    if opcion is None:
        await update.message.reply_text("❌ Número inválido. Escribe del 1 al 7.")
        return FONDOS_ESPERAR

    try:
        guardar_tema(opcion)
        print(f"DEBUG fondos: Fondo guardado → {opcion['nombre']}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar: {e}")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        f"✅ Fondo '{opcion['nombre']}' aplicado\n"
        f"Recarga la galería (F5) para verlo."
    )
    return ESPERANDO_COMANDO


async def esperando_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Usa un comando:\n"
        "/fondos — cambiar fondo\n"
        "/admin — menú administrador\n"
        "/salir — salir"
    )
    return ESPERANDO_COMANDO


async def fondos_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Selección de fondo cancelada por inactividad.",
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


# ── Factory: crea una Application con sus handlers ───────────
def crear_app(token: str, contacto: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["contacto"] = contacto

    conv_agregar = ConversationHandler(
        entry_points=[CommandHandler("inicio", inicio)],
        states={
            ESPERANDO_FOTO: [
                MessageHandler(filters.PHOTO, recibir_foto),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_espera_foto),
            ],
            ESPERANDO_NOMBRE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)],
            ESPERANDO_PRECIO:        [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio)],
            ESPERANDO_CATEGORIA:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_categoria)],
            ESPERANDO_OBSERVACIONES: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_observaciones)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
        ],
        allow_reentry=True,
    )

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
        ],
        conversation_timeout=300,
        allow_reentry=True,
    )

    conv_fondos = ConversationHandler(
        entry_points=[CommandHandler("fondos", cmd_fondos)],
        states={
            FONDOS_ESPERAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fondo),
            ],
            ESPERANDO_COMANDO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, esperando_comando),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, fondos_timeout),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
            CommandHandler("fondos",   cmd_fondos),
        ],
        conversation_timeout=300,
        allow_reentry=True,
    )

    app.add_handler(conv_agregar)
    app.add_handler(conv_cambiar_foto)
    app.add_handler(conv_fondos)
    app.add_handler(CommandHandler("admin",    admin))
    app.add_handler(CommandHandler("eliminar", cmd_eliminar))
    app.add_handler(CommandHandler("cancelar", cancelar))
    app.add_handler(CommandHandler("salir",    salir))

    return app


# ── main ──────────────────────────────────────────────────────
async def run_bots():
    apps = []

    if BOT_TOKEN:
        apps.append(crear_app(BOT_TOKEN, CONTACTO_EDUARDO))
        print(f"Bot Eduardo listo (contacto: {CONTACTO_EDUARDO or 'no configurado'})")

    if BOT_TOKEN_MAMA:
        apps.append(crear_app(BOT_TOKEN_MAMA, CONTACTO_MAMA))
        print(f"Bot Mamá listo (contacto: {CONTACTO_MAMA or 'no configurado'})")

    if not apps:
        print("ERROR: No hay tokens configurados (BOT_TOKEN / BOT_TOKEN_MAMA)")
        return

    for app in apps:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    print(f"✅ {len(apps)} bot(s) corriendo")
    logger.info(f"{len(apps)} bots iniciados")

    try:
        await asyncio.Event().wait()
    finally:
        for app in apps:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


def main():
    inicializar()
    asyncio.run(run_bots())


if __name__ == "__main__":
    main()
