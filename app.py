import os
import sqlite3
import requests
from io import BytesIO
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fumilab_clave_secreta_segura_2026")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Fumilab2026!")

# Credenciales Meta
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "1281507521716481")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "mi_token_secreto_plagas_2026")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "525586406475")
GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL", "")

DB_NAME = "plagas.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Tabla de prospectos (Web y WhatsApp)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prospectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono TEXT,
                nombre TEXT,
                plaga TEXT,
                inmueble TEXT,
                origen TEXT,
                fecha TEXT
            )
        ''')
        # Tabla de servicios para certificados PDF y cobros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio TEXT,
                cliente TEXT,
                direccion TEXT,
                plaga TEXT,
                metodo TEXT,
                quimico TEXT,
                ingrediente_activo TEXT,
                dosis TEXT,
                fecha_servicio TEXT,
                proxima_visita TEXT,
                tecnico TEXT,
                precio_cobrado REAL DEFAULT 0.0
            )
        ''')
        # Tabla de gastos / egresos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                categoria TEXT,
                concepto TEXT,
                monto REAL DEFAULT 0.0,
                comprobante TEXT
            )
        ''')
        # Tabla de ingresos adicionales
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingresos_extra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                concepto TEXT,
                monto REAL DEFAULT 0.0
            )
        ''')
        conn.commit()

init_db()

user_sessions = {}

def send_whatsapp_message(to_number, text):
    if not WHATSAPP_TOKEN:
        print("[AVISO] WHATSAPP_TOKEN no configurado en entorno.")
        return False
    
    clean_number = to_number.replace("+", "").replace(" ", "").strip()
    if clean_number.startswith("521") and len(clean_number) == 13:
        clean_number = "52" + clean_number[3:]

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "text",
        "text": {"body": text}
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[ERROR WHATSAPP] {e}")
        return False

def sync_google_sheets(datos):
    if not GOOGLE_SHEETS_URL:
        return
    try:
        requests.post(GOOGLE_SHEETS_URL, json=datos, timeout=5)
    except Exception as e:
        print(f"[ERROR SHEETS] {e}")

# ================= RUTAS PÚBLICAS =================

@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/solicitar_cotizacion", methods=["POST"])
def solicitar_cotizacion():
    nombre = request.form.get("nombre", "Cliente Web")
    telefono = request.form.get("telefono", "")
    plaga = request.form.get("plaga", "No especificada")
    inmueble = request.form.get("inmueble", "No especificado")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO prospectos (telefono, nombre, plaga, inmueble, origen, fecha) VALUES (?, ?, ?, ?, ?, ?)",
                  (telefono, nombre, plaga, inmueble, "Landing Page", fecha))
        conn.commit()

    sync_google_sheets({
        "fecha": fecha,
        "nombre": nombre,
        "telefono": telefono,
        "plaga": plaga,
        "inmueble": inmueble,
        "origen": "Landing Page"
    })

    alerta = f"🚨 *NUEVO PROSPECTO WEB*\n\n👤 *Cliente:* {nombre}\n📱 *Tel:* {telefono}\n🪳 *Plaga:* {plaga}\n🏠 *Inmueble:* {inmueble}\n📅 *Fecha:* {fecha}"
    send_whatsapp_message(ADMIN_PHONE, alerta)

    return redirect("/?enviado=1#cotizador")

# ================= SEGURIDAD Y LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    next_page = request.args.get("next") or url_for("dashboard")
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect(next_page)
        else:
            error = "Contraseña incorrecta."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("admin_logged", None)
    return redirect(url_for("login"))

def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged"):
            return redirect(url_for("login", next=request.url))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# ================= DASHBOARD & FINANZAS =================

@app.route("/dashboard")
@login_required
def dashboard():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Cantidad de servicios y suma de cobros
        c.execute("SELECT COUNT(*) as total_servicios, COALESCE(SUM(precio_cobrado), 0) as ingreso_servicios FROM servicios")
        servicios_stat = c.fetchone()
        
        # Ingresos adicionales
        c.execute("SELECT COALESCE(SUM(monto), 0) as total_extra FROM ingresos_extra")
        extra_stat = c.fetchone()
        
        # Gastos totales y por categoría
        c.execute("SELECT COALESCE(SUM(monto), 0) as total_gastos FROM gastos")
        gastos_stat = c.fetchone()

        c.execute("SELECT categoria, COALESCE(SUM(monto), 0) as total FROM gastos GROUP BY categoria")
        gastos_por_cat = {row["categoria"]: row["total"] for row in c.fetchall()}

        # Últimos gastos
        c.execute("SELECT * FROM gastos ORDER BY id DESC LIMIT 10")
        ultimos_gastos = c.fetchall()

        # Últimos ingresos extra
        c.execute("SELECT * FROM ingresos_extra ORDER BY id DESC LIMIT 10")
        ultimos_ingresos_extra = c.fetchall()

    ingresos_totales = servicios_stat["ingreso_servicios"] + extra_stat["total_extra"]
    gastos_totales = gastos_stat["total_gastos"]
    utilidad_neta = ingresos_totales - gastos_totales

    metricas = {
        "total_servicios": servicios_stat["total_servicios"],
        "ingresos_servicios": servicios_stat["ingreso_servicios"],
        "ingresos_extra": extra_stat["total_extra"],
        "ingresos_totales": ingresos_totales,
        "gastos_totales": gastos_totales,
        "utilidad_neta": utilidad_neta,
        "gastos_por_cat": gastos_por_cat
    }

    return render_template("dashboard.html", m=metricas, gastos=ultimos_gastos, extras=ultimos_ingresos_extra)

@app.route("/guardar_gasto", methods=["POST"])
@login_required
def guardar_gasto():
    fecha = request.form.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    categoria = request.form.get("categoria")
    concepto = request.form.get("concepto")
    monto = float(request.form.get("monto", 0.0))

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO gastos (fecha, categoria, concepto, monto) VALUES (?, ?, ?, ?)",
                  (fecha, categoria, concepto, monto))
        conn.commit()

    return redirect(url_for("dashboard"))

@app.route("/guardar_ingreso_extra", methods=["POST"])
@login_required
def guardar_ingreso_extra():
    fecha = request.form.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    concepto = request.form.get("concepto")
    monto = float(request.form.get("monto", 0.0))

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO ingresos_extra (fecha, concepto, monto) VALUES (?, ?, ?)",
                  (fecha, concepto, monto))
        conn.commit()

    return redirect(url_for("dashboard"))

# ================= RUTAS ADMINISTRATIVAS SEPARADAS =================

@app.route("/prospectos")
@login_required
def prospectos():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM prospectos ORDER BY id DESC")
        prospectos_list = c.fetchall()
    return render_template("prospectos.html", prospectos=prospectos_list)

@app.route("/panel")
@login_required
def panel():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM servicios ORDER BY id DESC")
        servicios = c.fetchall()
    return render_template("panel.html", servicios=servicios)

@app.route("/guardar_servicio", methods=["POST"])
@login_required
def guardar_servicio():
    folio = f"FUM-{datetime.now().strftime('%y%m%d%H%M')}"
    cliente = request.form.get("cliente")
    direccion = request.form.get("direccion")
    plaga = request.form.get("plaga")
    metodo = request.form.get("metodo")
    quimico = request.form.get("quimico")
    ingrediente_activo = request.form.get("ingrediente_activo")
    dosis = request.form.get("dosis")
    fecha_servicio = request.form.get("fecha_servicio")
    proxima_visita = request.form.get("proxima_visita")
    tecnico = request.form.get("tecnico")
    precio_cobrado = float(request.form.get("precio_cobrado", 0.0) or 0.0)

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO servicios (folio, cliente, direccion, plaga, metodo, quimico, ingrediente_activo, dosis, fecha_servicio, proxima_visita, tecnico, precio_cobrado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (folio, cliente, direccion, plaga, metodo, quimico, ingrediente_activo, dosis, fecha_servicio, proxima_visita, tecnico, precio_cobrado))
        conn.commit()

    return redirect(url_for("panel"))

@app.route("/reporte_pdf/<int:servicio_id>")
@login_required
def reporte_pdf(servicio_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM servicios WHERE id = ?", (servicio_id,))
        s = c.fetchone()

    if not s:
        return "Servicio no encontrado", 404

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Encabezado
    p.setFillColor(colors.HexColor("#14532d"))
    p.rect(0, height - 90, width, 90, fill=1, stroke=0)

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(40, height - 50, "FUMILAB CONTROL DE PLAGAS")
    p.setFont("Helvetica", 10)
    p.drawString(40, height - 70, "CERTIFICADO Y REPORTE TÉCNICO DE APLICACIÓN | MIP")

    p.drawRightString(width - 40, height - 50, f"FOLIO: {s['folio']}")
    p.drawRightString(width - 40, height - 68, f"Fecha: {s['fecha_servicio']}")

    # Cuerpo
    y = height - 130
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "DATOS DEL INMUEBLE Y SERVICIO")
    p.line(40, y - 5, width - 40, y - 5)

    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Cliente / Razón Social:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['cliente']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Ubicación del Servicio:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['direccion']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Plaga Objetivo Tratada:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['plaga']))

    y -= 40
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "DETALLE TÉCNICO DE MANEJO INTEGRADO")
    p.line(40, y - 5, width - 40, y - 5)

    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Método de Aplicación:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['metodo']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Producto Químico / Marca:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['quimico']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Ingrediente Activo:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['ingrediente_activo']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Dosis / Concentración:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['dosis']))

    y -= 40
    p.setFont("Helvetica-Bold", 12)
    p.drawString(40, y, "VALIDACIÓN Y SEGUIMIENTO SANITARIO")
    p.line(40, y - 5, width - 40, y - 5)

    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Técnico Responsable:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['tecnico']))

    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Próximo Servicio Sugerido:")
    p.setFont("Helvetica", 10)
    p.drawString(180, y, str(s['proxima_visita']))

    # Pie
    p.setFont("Helvetica", 8)
    p.setFillColor(colors.gray)
    p.drawString(40, 60, "Este reporte avala la aplicación técnica bajo normas oficiales y lineamientos de bioseguridad COFEPRIS.")
    p.drawRightString(width - 40, 60, "FUMILAB - CDMX y Edomex")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"Certificado_{s['folio']}.pdf", mimetype="application/pdf")

# ================= WEBHOOK DE WHATSAPP =================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token invalido", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "NO DATA", 200

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return "EVENT_RECEIVED", 200

        msg = messages[0]
        from_number = msg.get("from")
        text = msg.get("text", {}).get("body", "").strip().lower()

        if from_number not in user_sessions or text in ["hola", "menu", "inicio", "empezar"]:
            user_sessions[from_number] = {"step": "MENU"}
            menu = (
                "🌿 *Bienvenido a FUMILAB Control Profesional de Plagas*\n\n"
                "¿En qué podemos ayudarte hoy?\n\n"
                "1️⃣ Cotizar servicio residencial (Hogar)\n"
                "2️⃣ Cotizar servicio comercial / empresas\n"
                "3️⃣ Identificar una plaga (enviar fotos)\n"
                "4️⃣ Hablar con un asesor técnico\n\n"
                "👉 Responde con el número de tu opción."
            )
            send_whatsapp_message(from_number, menu)
            return "OK", 200

        state = user_sessions[from_number]
        step = state.get("step")

        if step == "MENU":
            if text == "1":
                state["inmueble"] = "Residencial"
                state["step"] = "PLAGA"
                send_whatsapp_message(from_number, "Indícanos qué plaga deseas controlar:\n\n1. Cucarachas\n2. Roedores\n3. Chinches\n4. Hormigas\n5. Otra")
            elif text == "2":
                state["inmueble"] = "Comercial / Empresa"
                state["step"] = "PLAGA"
                send_whatsapp_message(from_number, "Indícanos el tipo de plaga en tu establecimiento:\n\n1. Cucarachas\n2. Roedores\n3. Moscas / Voladores\n4. Otra")
            elif text == "3":
                state["step"] = "FOTOS"
                send_whatsapp_message(from_number, "Por favor envía fotos o video de la plaga o de las áreas con actividad para realizar el diagnóstico técnico.")
            elif text == "4":
                send_whatsapp_message(from_number, "Un asesor técnico se comunicará contigo por este mismo chat en breve.")
                send_whatsapp_message(ADMIN_PHONE, f"⚠️ *ATENCIÓN REQUERIDA*: El número +{from_number} solicita hablar con un asesor.")
                user_sessions.pop(from_number, None)
            else:
                send_whatsapp_message(from_number, "Por favor selecciona una opción válida (1 al 4) o escribe *menu*.")

        elif step == "PLAGA":
            plagas_dict = {"1": "Cucarachas", "2": "Roedores", "3": "Chinches/Voladores", "4": "Hormigas/Otra", "5": "Otra"}
            state["plaga"] = plagas_dict.get(text, text.capitalize())
            state["step"] = "NOMBRE"
            send_whatsapp_message(from_number, "Excelente. ¿A nombre de quién registramos la cotización?")

        elif step == "NOMBRE":
            state["nombre"] = text.title()
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with sqlite3.connect(DB_NAME) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO prospectos (telefono, nombre, plaga, inmueble, origen, fecha) VALUES (?, ?, ?, ?, ?, ?)",
                          (from_number, state["nombre"], state["plaga"], state["inmueble"], "WhatsApp Bot", fecha))
                conn.commit()

            sync_google_sheets({
                "fecha": fecha,
                "nombre": state["nombre"],
                "telefono": from_number,
                "plaga": state["plaga"],
                "inmueble": state["inmueble"],
                "origen": "WhatsApp Bot"
            })

            alerta = f"📲 *NUEVO LEAD POR WHATSAPP*\n\n👤 *Cliente:* {state['nombre']}\n📱 *Tel:* +{from_number}\n🪳 *Plaga:* {state['plaga']}\n🏠 *Inmueble:* {state['inmueble']}\n📅 *Fecha:* {fecha}"
            send_whatsapp_message(ADMIN_PHONE, alerta)

            send_whatsapp_message(from_number, f"¡Gracias, {state['nombre']}! Registramos tu solicitud para control de *{state['plaga']}*. En unos minutos nuestro técnico te enviará la propuesta detallada.")
            user_sessions.pop(from_number, None)

    except Exception as e:
        print(f"[ERROR WEBHOOK GENERAL] {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)