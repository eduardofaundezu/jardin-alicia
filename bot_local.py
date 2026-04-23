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
CONTACTO_EDUARDO = os.getenv("CONTACTO_EDUARDO", "")

BOT_TOKEN_MAMA = os.getenv("BOT_TOKEN_MAMA")
CONTACTO_MAMA  = os.getenv("CONTACTO_MAMA", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Estados ──────────────────────────────────────────────────
ESPERANDO_CANTIDAD_FOTOS = 0
ESPERANDO_FOTO           = 1
ESPERANDO_NOMBRE         = 2
ESPERANDO_PRECIO         = 3
ESPERANDO_CATEGORIA      = 4
CAMBIAR_FOTO_ESPERAR     = 5
FONDOS_ESPERAR           = 6
ESPERANDO_OBSERVACIONES  = 8
ESPERANDO_FOTOS_EXTRA    = 9
# ESPERANDO_COMANDO (7) eliminado: conv_fondos ahora termina al seleccionar fondo

MAPA_CATEGORIAS = {
    "1": "Flores",
    "2": "Plantas",
    "3": "Textil",
    "4": "Crochet",
    "5": "Varios",
}

TEMAS = {
    "1": {"nombre": "Verano",          "fondo": "verano"},
    "2": {"nombre": "Otoño",           "fondo": "otono"},
    "3": {"nombre": "Invierno",        "fondo": "invierno"},
    "4": {"nombre": "Fiestas Patrias", "fondo": "patrias"},
    "5": {"nombre": "Navidad",         "fondo": "navidad"},
}


def sugerir_fondo():
    mes = datetime.now().month
    dia = datetime.now().day
    if mes == 12:
        return "5 (Navidad)"
    if mes in (1, 2, 3):
        return "1 (Verano)"
    if mes == 4 or (mes == 5 and dia < 10):
        return "2 (Otoño)"
    if mes in (6, 7, 8):
        return "3 (Invierno)"
    if mes == 9 and 15 <= dia <= 20:
        return "4 (Fiestas Patrias)"
    if mes in (9, 10, 11):
        return "1 (Verano)"
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
    # Detectar extensión real del archivo en fondos_precargados
    fondo_nombre = opcion["fondo"]
    extensions = ['.avif', '.png', '.jpg', '.jpeg', '.webp']
    archivo_encontrado = None
    for ext in extensions:
        ruta = f"fondos_precargados/{fondo_nombre}{ext}"
        if os.path.exists(ruta):
            archivo_encontrado = f"{fondo_nombre}{ext}"
            break
    
    if archivo_encontrado is None:
        archivo_encontrado = f"{fondo_nombre}.jpg"  # fallback
    
    data = {
        "fondo_actual": fondo_nombre,
        "archivo": archivo_encontrado,
    }
    with open("tema.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def borrar_foto(nombre, motivo="sin motivo especificado"):
    if not nombre:
        return
    ruta = f"fotos/{nombre}"
    try:
        if os.path.exists(ruta):
            tam = os.path.getsize(ruta)
            os.remove(ruta)
            print(f"[BORRAR_FOTO] OK  archivo={ruta}  tamaño={tam}B  motivo={motivo}")
        else:
            print(f"[BORRAR_FOTO] SKIP archivo={ruta} no existe  motivo={motivo}")
    except Exception as e:
        print(f"[BORRAR_FOTO] ERROR archivo={ruta}  motivo={motivo}  error={e}")


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


async def descargar_foto_extra(bot, foto_msg, indice: int) -> str:
    """Descarga foto adicional sin generar thumbnail. Retorna nombre del archivo."""
    file = await bot.get_file(foto_msg.file_id)
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
    nombre = f"foto_{ts}_extra{indice}.jpg"
    await file.download_to_drive(f"fotos/{nombre}")
    return nombre


def normalizar_categoria(texto):
    return MAPA_CATEGORIAS.get(texto.strip(), None)


# ── /inicio ────────────────────────────────────────────────────
async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message.chat.type in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Usa privado: @Jardin_131_bot para subir fotos")
        return ConversationHandler.END
    await update.message.reply_text(
        "¿Cuántas fotos tiene este producto?\n"
        "Responde con un número del 1 al 5"
    )
    return ESPERANDO_CANTIDAD_FOTOS


async def recibir_cantidad_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if not texto.isdigit() or not (1 <= int(texto) <= 5):
        await update.message.reply_text("❌ Escribe un número del 1 al 5")
        return ESPERANDO_CANTIDAD_FOTOS

    n = int(texto)
    context.user_data["fotos_total"] = n
    context.user_data["fotos_extra"] = []

    if n == 1:
        await update.message.reply_text("Envía la foto del producto")
    else:
        await update.message.reply_text(
            f"Producto con {n} fotos.\n\n"
            "Envía la foto de PORTADA (foto principal)"
        )
    return ESPERANDO_FOTO


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # limpia cualquier flujo activo al entrar al menú
    await update.message.reply_text(
        "Menu administrador:\n\n"
        "/eliminar <ID> — borrar producto\n"
        "/modificar <ID> — cambiar foto\n"
        "/fondos — cambiar tema galería\n"
        "/salir — salir del menú"
    )
    return ConversationHandler.END


# ── Flujo principal: agregar producto ────────────────────────
async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Rechazar álbumes: Telegram envía cada foto del álbum como mensaje separado
    # con el mismo media_group_id. Solo mostramos aviso para la primera y
    # silenciamos las siguientes para no spamear.
    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if context.user_data.get("_mgid_portada") == mgid:
            return ESPERANDO_FOTO  # duplicado silencioso del mismo álbum
        context.user_data["_mgid_portada"] = mgid
        await update.message.reply_text(
            "⚠️ Envía las fotos de una en una, no como álbum.\n"
            "Intenta de nuevo con una sola foto."
        )
        return ESPERANDO_FOTO
    print("DEBUG: Foto portada recibida")
    try:
        os.makedirs("fotos", exist_ok=True)
        nombre_full, nombre_thumb = await descargar_y_procesar_foto(
            context.bot, update.message.photo[-1]
        )
        context.user_data["foto_full"]  = nombre_full
        context.user_data["foto_thumb"] = nombre_thumb
    except Exception as e:
        print(f"ERROR en recibir_foto: {type(e).__name__}: {e}")
        await update.message.reply_text("❌ Error al guardar la foto. Intenta de nuevo.")
        return ESPERANDO_FOTO

    fotos_total = context.user_data.get("fotos_total", 1)
    if fotos_total > 1:
        restantes = fotos_total - 1
        plural = "foto" if restantes == 1 else "fotos"
        await update.message.reply_text(
            f"✓ Portada guardada\n\n"
            f"Ahora envía las {restantes} {plural} restantes\n"
            f"(puedes enviarlas todas juntas como álbum)"
        )
        return ESPERANDO_FOTOS_EXTRA

    await update.message.reply_text("¿Cuál es el nombre del producto?")
    return ESPERANDO_NOMBRE


async def texto_en_espera_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Primero envía una foto del producto.")
    return ESPERANDO_FOTO


async def texto_en_espera_fotos_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fotos_extra = context.user_data.get("fotos_extra", [])
    fotos_total = context.user_data.get("fotos_total", 1)
    recibidas   = 1 + len(fotos_extra)
    restantes   = fotos_total - recibidas
    await update.message.reply_text(
        f"Faltan {restantes} foto(s). Envíalas como foto o álbum."
    )
    return ESPERANDO_FOTOS_EXTRA


async def recibir_fotos_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Los álbumes son bienvenidos aquí: Telegram envía cada foto del álbum
    # como mensaje separado; la lógica de conteo las procesa en orden.
    fotos_extra = context.user_data.get("fotos_extra", [])
    fotos_total = context.user_data.get("fotos_total", 1)
    indice      = len(fotos_extra) + 1

    try:
        os.makedirs("fotos", exist_ok=True)
        nombre = await descargar_foto_extra(context.bot, update.message.photo[-1], indice)
        fotos_extra.append(nombre)
        context.user_data["fotos_extra"] = fotos_extra
        print(f"DEBUG: foto extra {indice} guardada: fotos/{nombre}")
    except Exception as e:
        print(f"ERROR en recibir_fotos_extra: {type(e).__name__}: {e}")
        await update.message.reply_text("❌ Error al guardar la foto. Intenta de nuevo.")
        return ESPERANDO_FOTOS_EXTRA

    fotos_recibidas = 1 + len(fotos_extra)  # portada + extras
    if fotos_recibidas < fotos_total:
        await update.message.reply_text(
            f"✓ Foto {fotos_recibidas} guardada\n"
            f"Envía foto {fotos_recibidas + 1} de {fotos_total}"
        )
        return ESPERANDO_FOTOS_EXTRA

    await update.message.reply_text(
        f"✓ Todas las fotos guardadas ({fotos_total})\n\n"
        "¿Cuál es el nombre del producto?"
    )
    return ESPERANDO_NOMBRE


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

    fotos_extra = context.user_data.get("fotos_extra", [])
    print(f"\n=== GUARDANDO PRODUCTO ===")
    print(f"nombre={nombre}  precio={precio}  cat={categoria}  fotos_extra={len(fotos_extra)}")

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
            "fotos_extra":   fotos_extra,
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
    obs_linea   = f"\nObs: {observaciones}" if observaciones else ""
    extra_linea = f"\nFotos: {1 + len(fotos_extra)}" if fotos_extra else ""
    await update.message.reply_text(
        f"✅ {nombre} guardado en {categoria}\n"
        f"Código: {pid}{obs_linea}{extra_linea}\n\n"
        f"¿Cuántas fotos tiene el siguiente producto? (1-5)\n"
        f"O /salir para terminar"
    )
    return ESPERANDO_CANTIDAD_FOTOS


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

    motivo = f"/eliminar id={pid}"
    borrar_foto(encontrado.get("foto_full"),  motivo)
    borrar_foto(encontrado.get("foto_thumb"), motivo)
    borrar_foto(encontrado.get("foto"),       motivo)
    for extra in encontrado.get("fotos_extra", []):
        borrar_foto(extra, motivo)

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
        print("[MODIFICAR] recibir_nueva_foto sin cambiar_id — sesión perdida, abortando sin borrar nada")
        await update.message.reply_text("❌ Sesión perdida. Usa /modificar <id> de nuevo.")
        return ConversationHandler.END

    # Verificar que el producto existe ANTES de descargar ni borrar nada
    productos = leer_productos()
    producto = next((p for p in productos if p.get("id") == pid), None)
    if producto is None:
        print(f"[MODIFICAR] producto id={pid} no existe — abortando sin borrar nada")
        await update.message.reply_text(f"❌ Producto {pid} no encontrado. Operación cancelada.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        os.makedirs("fotos", exist_ok=True)
        nombre_full, nombre_thumb = await descargar_y_procesar_foto(
            context.bot, update.message.photo[-1]
        )
    except Exception as e:
        print(f"[MODIFICAR] ERROR descargando nueva foto: {e}")
        await update.message.reply_text("❌ Error al guardar la foto. Intenta de nuevo.")
        return CAMBIAR_FOTO_ESPERAR

    # Borrar fotos viejas solo si el producto fue confirmado arriba
    motivo = f"/modificar id={pid}"
    borrar_foto(producto.get("foto_full"),  motivo)
    borrar_foto(producto.get("foto_thumb"), motivo)
    borrar_foto(producto.get("foto"),       motivo)

    producto["foto_full"]  = nombre_full
    producto["foto_thumb"] = nombre_thumb
    producto.pop("foto", None)

    guardar_productos_lista(productos)
    context.user_data.clear()
    print(f"[MODIFICAR] foto actualizada para id={pid}: {nombre_full}")
    await update.message.reply_text("✅ Foto actualizada")
    return ConversationHandler.END


# ── /fondos ───────────────────────────────────────────────────
async def cmd_fondos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sugerido   = sugerir_fondo()
    sugerencia = f"\n\nSugerencia: {sugerido}" if sugerido else ""
    texto = (
        "Elige un fondo para la galería:\n\n"
        "1️⃣ Verano\n"
        "2️⃣ Otoño\n"
        "3️⃣ Invierno\n"
        "4️⃣ Fiestas Patrias\n"
        "5️⃣ Navidad\n"
        "0️⃣ Salir (no cambiar)"
        f"{sugerencia}\n\n"
        "Escribe el número:"
    )
    await update.message.reply_text(texto)
    return FONDOS_ESPERAR


async def recibir_fondo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()

    if entrada == "0":
        await update.message.reply_text("↩️ Fondo sin cambios.")
        return ConversationHandler.END

    opcion  = TEMAS.get(entrada)

    if opcion is None:
        await update.message.reply_text("❌ Número inválido. Escribe del 0 al 5.")
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
        f"Recarga la galería (F5) para verlo.\n\n"
        f"Escribe /fondos para cambiar de nuevo."
    )
    return ConversationHandler.END


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
            ESPERANDO_CANTIDAD_FOTOS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_fotos),
            ],
            ESPERANDO_FOTO: [
                MessageHandler(filters.PHOTO, recibir_foto),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_espera_foto),
            ],
            ESPERANDO_FOTOS_EXTRA: [
                MessageHandler(filters.PHOTO, recibir_fotos_extra),
                MessageHandler(filters.TEXT & ~filters.COMMAND, texto_en_espera_fotos_extra),
            ],
            ESPERANDO_NOMBRE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)],
            ESPERANDO_PRECIO:        [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio)],
            ESPERANDO_CATEGORIA:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_categoria)],
            ESPERANDO_OBSERVACIONES: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_observaciones)],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
            # /admin y /fondos terminan conv_agregar limpiamente antes de su propio flujo
            CommandHandler("admin",    admin),
            CommandHandler("fondos",   cancelar),
        ],
        conversation_timeout=600,   # 10 min: evita que el flujo quede zombie
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
            # /admin y /fondos terminan este flujo limpiamente
            # evita que una foto enviada después llegue a recibir_nueva_foto por error
            CommandHandler("admin",   admin),
            CommandHandler("fondos",  cancelar),
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
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, fondos_timeout),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            CommandHandler("salir",    salir),
            CommandHandler("admin",    admin),
            # /fondos en fallback permite reiniciar sin escribirlo dos veces
            CommandHandler("fondos",   cmd_fondos),
        ],
        conversation_timeout=120,   # 2 min: si no elige número, expira
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
    else:
        print("INFO: BOT_TOKEN_MAMA no configurado, bot mamá desactivado")

    if not apps:
        print("ERROR: No hay tokens configurados (BOT_TOKEN)")
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
