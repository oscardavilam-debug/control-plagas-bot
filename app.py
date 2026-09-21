import os
import io
import json
import base64
import urllib.request
import urllib.parse
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
OFFICIAL_PHONE = os.environ.get('OFFICIAL_PHONE', '5649643758')
OFFICIAL_WA = '52' + OFFICIAL_PHONE
app.secret_key = os.environ.get('SECRET_KEY', 'fumilab_corp_saas_secure_token_987654321_2026')

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400 * 7
)

DB_FILE = 'fumilab.db'
SHEETS_WEBHOOK_URL = os.environ.get('GOOGLE_SHEETS_URL', 'https://script.google.com/macros/s/AKfycbzJx5hM_CWeZ_tlFen9owTybNeyOQnpjxHsuQVHpmq1ZbfasmfDPmwCNi5vVkqTZpO1/exec')

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'Fumilab2026*')

def login_requerido(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        if not session.get('admin_autenticado'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorador

def enviar_a_google_sheets(datos):
    webhook_url = os.environ.get('GOOGLE_SHEETS_URL', 'https://script.google.com/macros/s/AKfycbzJx5hM_CWeZ_tlFen9owTybNeyOQnpjxHsuQVHpmq1ZbfasmfDPmwCNi5vVkqTZpO1/exec').strip()
    if not webhook_url:
        return
    try:
        import requests
        resp = requests.post(webhook_url, json=datos, timeout=12, allow_redirects=True)
        print(f"Respuesta Sheets Webhook: {resp.status_code}")
    except Exception as e:
        try:
            payload = json.dumps(datos).encode('utf-8')
            req = urllib.request.Request(webhook_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=12) as response:
                print(f"Respuesta fallback Sheets: {response.getcode()}")
        except Exception as err:
            print(f"Error final envio Sheets: {err}")

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def asegurar_columna(conn, tabla, columna, tipo_def):
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({tabla})")
        columnas = [fila[1] for fila in cur.fetchall()]
        if columna not in columnas:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_def}")
            conn.commit()
    except Exception as err:
        print(f"Asegurar columna {columna} en {tabla}: {err}")

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        
        # 1. Tabla Clientes
        cur.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_comercial TEXT NOT NULL,
                contacto TEXT,
                telefono TEXT,
                direccion TEXT,
                tipo_inmueble TEXT
            )
        ''')
        conn.commit()
        asegurar_columna(conn, "clientes", "tipo_inmueble", "TEXT")

        # 2. Tabla Servicios
        cur.execute('''
            CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio TEXT UNIQUE,
                cliente_id INTEGER,
                tipo_servicio TEXT,
                fecha_servicio TEXT,
                hora_inicio TEXT,
                hora_fin TEXT,
                costo REAL DEFAULT 1400.0,
                gasto_quimicos REAL DEFAULT 250.0,
                gasto_gasolina REAL DEFAULT 180.0,
                gasto_nomina REAL DEFAULT 350.0,
                gasto_equipo REAL DEFAULT 80.0,
                quimico_utilizado TEXT,
                ingrediente_activo TEXT,
                dosis_aplicada TEXT,
                equipo_utilizado TEXT,
                tiempo_reentrada TEXT,
                actividades_realizadas TEXT,
                recomendaciones TEXT,
                firma_cliente TEXT,
                estatus TEXT DEFAULT 'Terminado'
            )
        ''')
        conn.commit()

        # Asegurar todas las columnas necesarias en servicios
        columnas_servicios = [
            ("folio", "TEXT"),
            ("cliente_id", "INTEGER DEFAULT 1"),
            ("tipo_servicio", "TEXT"),
            ("fecha_servicio", "TEXT"),
            ("hora_inicio", "TEXT"),
            ("hora_fin", "TEXT"),
            ("costo", "REAL DEFAULT 1400.0"),
            ("gasto_quimicos", "REAL DEFAULT 250.0"),
            ("gasto_gasolina", "REAL DEFAULT 180.0"),
            ("gasto_nomina", "REAL DEFAULT 350.0"),
            ("gasto_equipo", "REAL DEFAULT 80.0"),
            ("quimico_utilizado", "TEXT"),
            ("ingrediente_activo", "TEXT"),
            ("dosis_aplicada", "TEXT"),
            ("equipo_utilizado", "TEXT"),
            ("tiempo_reentrada", "TEXT"),
            ("actividades_realizadas", "TEXT"),
            ("recomendaciones", "TEXT"),
            ("firma_cliente", "TEXT"),
            ("estatus", "TEXT DEFAULT 'Terminado'")
        ]
        for col, tipo in columnas_servicios:
            asegurar_columna(conn, "servicios", col, tipo)

                # 3. Tabla Prospectos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS prospectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio TEXT,
                nombre TEXT,
                telefono TEXT,
                tipo_inmueble TEXT,
                plaga TEXT,
                fecha_solicitud TEXT,
                estatus TEXT DEFAULT 'Pendiente',
                notas TEXT
            )
        ''')
        conn.commit()
        asegurar_columna(conn, "prospectos", "folio", "TEXT")
        asegurar_columna(conn, "prospectos", "nombre", "TEXT")
        asegurar_columna(conn, "prospectos", "telefono", "TEXT")
        asegurar_columna(conn, "prospectos", "tipo_inmueble", "TEXT")
        asegurar_columna(conn, "prospectos", "plaga", "TEXT")
        asegurar_columna(conn, "prospectos", "fecha_solicitud", "TEXT")
        asegurar_columna(conn, "prospectos", "estatus", "TEXT DEFAULT 'Pendiente'")
        asegurar_columna(conn, "prospectos", "notas", "TEXT")

        # 4. Tabla Inventario
        cur.execute('''
            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,
                nombre TEXT NOT NULL,
                registro_cofepris TEXT,
                stock_actual REAL,
                unidad TEXT,
                costo_unitario REAL,
                estado TEXT DEFAULT 'Disponible'
            )
        ''')
        conn.commit()

        # 5. Tabla Fotos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS servicio_fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                servicio_id INTEGER,
                ruta_imagen TEXT
            )
        ''')
        conn.commit()

        # Siembra de Clientes si está vacía
        c_count = cur.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        if c_count == 0:
            cur.executemany('''
                INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion, tipo_inmueble) VALUES (?, ?, ?, ?, ?)
            ''', [
                ('Farmacia Similares 3509 Ecatepec', 'Nancy Padilla Garcia', '5541419369', 'Av. Jardines de Morelos Mz. 316', 'Comercial'),
                ('Purificadora Hidropura', 'Elizabeth Carbajal', '5534842783', 'Cuautitlan Izcalli EdoMex', 'Industrial'),
                ('Restaurante Aloha Mar y Tierra', 'Mauricio Garduño', '5632326172', 'Blvd. Valle San Felipe', 'Alimentos')
            ])
            conn.commit()

        # Siembra de Inventario si está vacío
        inv_count = cur.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]
        if inv_count == 0:
            cur.executemany('''
                INSERT INTO inventario (tipo, nombre, registro_cofepris, stock_actual, unidad, costo_unitario, estado) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                ('Quimico', 'DEMAND DUO (Syngenta)', 'RSCO-URB-INAC-111-315-009-0.02', 12.5, 'Litros', 850.0, 'Disponible'),
                ('Quimico', 'RODILON BLOQUE (Bayer)', 'RSCO-URB-ROD-0101-322-005-0.0025', 18.0, 'Kg', 420.0, 'Disponible'),
                ('Quimico', 'BIOCIDAL PLUS 5TA GEN', 'RSCO-DOM-DES-0102-301-002-10', 25.0, 'Litros', 310.0, 'Disponible'),
                ('Equipo', 'Aspersora Manual Swissmex 15L', 'NOM-STPS', 4.0, 'Piezas', 1200.0, 'Disponible'),
                ('Equipo', 'Termonebulizador en Frío ULV', 'CE-ISO', 2.0, 'Piezas', 4800.0, 'Disponible')
            ])
            conn.commit()

        # Siembra de Servicio #3501 si está vacío
        srv_count = cur.execute("SELECT COUNT(*) FROM servicios").fetchone()[0]
        if srv_count == 0:
            cur.execute('''
                INSERT INTO servicios (
                    folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin,
                    costo, gasto_quimicos, gasto_gasolina, gasto_nomina, gasto_equipo,
                    quimico_utilizado, ingrediente_activo, dosis_aplicada, equipo_utilizado, tiempo_reentrada,
                    actividades_realizadas, recomendaciones, estatus
                ) VALUES (
                    '3501', 1, 'MANEJO INTEGRAL DE CUCARACHAS (MIP)', '2026-09-20', '08:30 AM', '09:45 AM',
                    1400.0, 180.0, 150.0, 350.0, 50.0,
                    'DEMAND DUO', 'LAMBDA CYHALOTRINA 9.7%', '4 ml / L de agua', 'Aspersora Manual Swissmex', '2 Horas',
                    'Aspersión perimetral focalizada y colocación de gel cucarachicida en zoclos y contactos.',
                    'No realizar aseo profundo en áreas tratadas por 24 horas. Mantener ventilación previa al reingreso.',
                    'Terminado'
                )
            ''')
            conn.commit()

    except Exception as e:
        print(f"Error critico en init_db: {e}")
    finally:
        conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip().lower()
        password = request.form.get('password', '').strip()

        if usuario == ADMIN_USER.lower() and password == ADMIN_PASS:
            session.permanent = True
            session['admin_autenticado'] = True
            session['admin_user'] = usuario
            next_url = request.args.get('next') or url_for('dashboard_financiero')
            return redirect(next_url)
        else:
            error = "Credenciales incorrectas. Verifique su usuario y contraseña."

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/panel')
@login_requerido
def panel_redirect():
    return redirect(url_for('dashboard_financiero'))

@app.route('/tecnico')
def tecnico():
    return render_template('tecnico_home.html')

@app.route('/reporte_campo')
@app.route('/reporte_campo/')
def reporte_campo():
    try:
        init_db()
        with get_db() as conn:
            clientes = [dict(c) for c in conn.execute("SELECT * FROM clientes").fetchall()]
            quimicos = [dict(q) for q in conn.execute("SELECT * FROM inventario WHERE tipo = 'Quimico'").fetchall()]
        return render_template('reporte_campo.html', clientes=clientes, quimicos=quimicos)
    except Exception as e:
        return f"Error en Reporte: {str(e)}", 500

@app.route('/escaner_qr')
def escaner_qr():
    return render_template('escaner_qr.html')

@app.route('/solicitar_cotizacion', methods=['GET', 'POST'])
def solicitar_cotizacion():
    if request.method == 'POST':
        try:
            nombre = (
                request.form.get('nombre') or 
                request.form.get('nombre_completo') or 
                request.form.get('nombre_cliente') or 
                request.form.get('name') or 
                'Cliente Web'
            ).strip()

            telefono = (
                request.form.get('telefono') or 
                request.form.get('celular') or 
                request.form.get('whatsapp') or 
                request.form.get('numero') or 
                ''
            ).strip()

            tipo_inmueble = (
                request.form.get('tipo_inmueble') or 
                request.form.get('inmueble') or 
                'Hogar'
            ).strip()

            plaga = (
                request.form.get('plaga') or 
                request.form.get('plaga_tratar') or 
                'Cucarachas'
            ).strip()

            notas = request.form.get('notas', '')
            fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with get_db() as conn:
                conteo = conn.execute('SELECT COUNT(*) FROM prospectos').fetchone()[0]
                folio = f"COT-{901 + conteo}"

                conn.execute('''
                    INSERT INTO prospectos (folio, nombre, telefono, tipo_inmueble, plaga, fecha_solicitud, estatus, notas)
                    VALUES (?, ?, ?, ?, ?, ?, 'Pendiente', ?)
                ''', (folio, nombre, telefono, tipo_inmueble, plaga, fecha_str, notas))
                conn.commit()

            contacto_formateado = f"{nombre} - {telefono}" if telefono else nombre
            datos_sheet = {
                "fecha": fecha_str,
                "contacto": contacto_formateado,
                "nombre": contacto_formateado,
                "cliente": contacto_formateado,
                "telefono": telefono,
                "plaga": plaga,
                "inmueble": tipo_inmueble,
                "origen": "Formulario Web"
            }
            enviar_a_google_sheets(datos_sheet)

            return redirect(url_for('cotizacion_exitosa', folio=folio))
        except Exception as e:
            return f"Error al procesar cotización: {str(e)}", 500

    return render_template('solicitar_cotizacion.html')

@app.route('/cotizacion_exitosa')
def cotizacion_exitosa():
    folio = request.args.get('folio', 'COT-901')
    return render_template('cotizacion_exitosa.html', folio=folio)

@app.route('/dashboard')
@app.route('/dashboard_financiero')
@login_requerido
def dashboard_financiero():
    try:
        init_db()
        hoy = datetime.now().date()
        with get_db() as conn:
            filas = conn.execute("SELECT * FROM servicios ORDER BY id DESC").fetchall()
            servicios = [dict(f) for f in filas]

            ingresos_totales = sum([float(s.get('costo') or 0) for s in servicios if s.get('estatus') in ['Terminado', 'Atendido']])
            gasto_quimicos = sum([float(s.get('gasto_quimicos') or 0) for s in servicios])
            gasto_gasolina = sum([float(s.get('gasto_gasolina') or 0) for s in servicios])
            gasto_nomina = sum([float(s.get('gasto_nomina') or 0) for s in servicios])
            gasto_equipo = sum([float(s.get('gasto_equipo') or 0) for s in servicios])
            egresos_totales = gasto_quimicos + gasto_gasolina + gasto_nomina + gasto_equipo
            utilidad_neta = ingresos_totales - egresos_totales

            clientes_count = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            inv_count = conn.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]

            clientes_raw = conn.execute("SELECT * FROM clientes").fetchall()
            polizas_control = []
            for cl in clientes_raw:
                c_dict = dict(cl)
                ult_srv = conn.execute(
                    "SELECT folio, fecha_servicio FROM servicios WHERE cliente_id = ? ORDER BY id DESC LIMIT 1",
                    (c_dict['id'],)
                ).fetchone()

                if ult_srv and ult_srv['fecha_servicio']:
                    folio_ult = ult_srv['folio']
                    try:
                        fecha_srv = datetime.strptime(ult_srv['fecha_servicio'][:10], "%Y-%m-%d").date()
                        dias_pasados = (hoy - fecha_srv).days
                    except Exception:
                        dias_pasados = 15
                else:
                    folio_ult = "S/N"
                    dias_pasados = 32

                dias_restantes = max(0, 30 - dias_pasados)
                if dias_pasados <= 22:
                    estado_vigencia = "Vigente"
                    badge_color = "emerald"
                elif dias_pasados <= 30:
                    estado_vigencia = "Por Vencer"
                    badge_color = "amber"
                else:
                    estado_vigencia = "Vencido"
                    badge_color = "rose"

                tel_raw = "".join([d for d in str(c_dict.get('telefono') or '5649643758') if d.isdigit()])
                wa_tel = f"52{tel_raw}" if len(tel_raw) == 10 else (tel_raw or "525649643758")
                contacto_nom = c_dict.get('contacto') or c_dict.get('nombre_comercial')

                if estado_vigencia == "Vencido":
                    txt_wa = (
                        f"Hola {contacto_nom}, le saludamos de Fumilab Control Integral. Le informamos que "
                        f"la vigencia sanitaria de su establecimiento ({c_dict.get('nombre_comercial')}) "
                        f"ha concluido (hace {dias_pasados} días). Para mantener su cumplimiento ante auditorías sanitarias, "
                        f"¿le agendamos su servicio de renovación esta semana?"
                    )
                else:
                    txt_wa = (
                        f"Hola {contacto_nom}, le saludamos de Fumilab Control Integral. Le recordamos que "
                        f"restan {dias_restantes} días de vigencia de su Certificado #{folio_ult} ({c_dict.get('nombre_comercial')}). "
                        f"¿Gusta que reservemos fecha para su refuerzo preventivo?"
                    )

                polizas_control.append({
                    'id': c_dict['id'],
                    'nombre': c_dict['nombre_comercial'],
                    'contacto': contacto_nom,
                    'telefono': c_dict.get('telefono'),
                    'folio_ultimo': folio_ult,
                    'dias_pasados': dias_pasados,
                    'dias_restantes': dias_restantes,
                    'estado': estado_vigencia,
                    'badge_color': badge_color,
                    'wa_link': f"https://wa.me/{wa_tel}?text={urllib.parse.quote(txt_wa)}"
                })

        return render_template('dashboard_financiero.html',
                               servicios=servicios,
                               polizas=polizas_control,
                               ingresos_totales=f"{ingresos_totales:,.2f}",
                               gasto_quimicos=f"{gasto_quimicos:,.2f}",
                               gasto_gasolina=f"{gasto_gasolina:,.2f}",
                               gasto_nomina=f"{gasto_nomina:,.2f}",
                               gasto_equipo=f"{gasto_equipo:,.2f}",
                               egresos_totales=f"{egresos_totales:,.2f}",
                               utilidad_neta=f"{utilidad_neta:,.2f}",
                               total_servicios=len(servicios),
                               clientes_activos=clientes_count,
                               items_inventario=inv_count)
    except Exception as e:
        return f"Error en Dashboard: {str(e)}", 500

@app.route('/inventarios')
@login_requerido
def inventarios():
    try:
        init_db()
        with get_db() as conn:
            items = [dict(i) for i in conn.execute("SELECT * FROM inventario ORDER BY tipo DESC, nombre ASC").fetchall()]
        return render_template('inventarios.html', items=items)
    except Exception as e:
        return f"Error en Inventarios: {str(e)}", 500

@app.route('/prospectos')
@login_requerido
def prospectos():
    try:
        init_db()
        with get_db() as conn:
            leads = [dict(f) for f in conn.execute("SELECT * FROM prospectos ORDER BY id DESC").fetchall()]
        return render_template('prospectos.html', leads=leads)
    except Exception as e:
        return f"Error en Prospectos: {str(e)}", 500

@app.route('/certificados')
@login_requerido
def certificados():
    try:
        init_db()
        with get_db() as conn:
            filas = conn.execute('''
                SELECT s.*, 
                       coalesce(c.nombre_comercial, 'Cliente General') as cliente_nombre,
                       coalesce(c.telefono, '5649643758') as cliente_telefono,
                       coalesce(c.direccion, 'CDMX y EdoMex') as cliente_direccion
                FROM servicios s 
                LEFT JOIN clientes c ON s.cliente_id = c.id 
                ORDER BY s.id DESC
            ''').fetchall()
            servicios = [dict(f) for f in filas]
        return render_template('certificados.html', servicios=servicios)
    except Exception as e:
        return f"Error en Certificados: {str(e)}", 500

@app.route('/api/inventario/agregar', methods=['POST'])
@login_requerido
def agregar_inventario():
    try:
        tipo = request.form.get('tipo', 'Quimico')
        nombre = request.form.get('nombre', '').strip()
        registro = request.form.get('registro_cofepris', '').strip()
        stock = float(request.form.get('stock_actual') or 0)
        unidad = request.form.get('unidad', 'Piezas').strip()
        costo = float(request.form.get('costo_unitario') or 0)

        with get_db() as conn:
            conn.execute('''
                INSERT INTO inventario (tipo, nombre, registro_cofepris, stock_actual, unidad, costo_unitario, estado)
                VALUES (?, ?, ?, ?, ?, ?, 'Disponible')
            ''', (tipo, nombre, registro, stock, unidad, costo))
            conn.commit()

        return redirect('/inventarios')
    except Exception as e:
        return f"Error al guardar insumo: {str(e)}", 500

@app.route('/api/guardar_reporte_servicio', methods=['POST'])
def guardar_reporte():
    try:
        data = request.get_json() or {}
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        producto_nombre = data.get('producto', 'DEMAND DUO').strip()

        with get_db() as conn:
            c = conn.execute('SELECT COUNT(*) FROM servicios').fetchone()[0]
            folio = f"{3501 + c}"

            cur = conn.cursor()
            cur.execute('''
                INSERT INTO servicios (
                    folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin,
                    costo, gasto_quimicos, gasto_gasolina, gasto_nomina, gasto_equipo,
                    quimico_utilizado, dosis_aplicada, tiempo_reentrada,
                    actividades_realizadas, recomendaciones, firma_cliente, estatus
                ) VALUES (?, ?, ?, ?, ?, ?, 1400.0, 180.0, 150.0, 350.0, 50.0, ?, ?, '2 Horas', ?, 'No lavar en 24h y mantener ventilado', ?, 'Terminado')
            ''', (
                folio,
                data.get('cliente_id', 1),
                data.get('tipo_visita', 'Manejo Integral de Plagas'),
                fecha_hoy,
                data.get('hora_inicio', '08:00 AM'),
                data.get('hora_fin', '09:00 AM'),
                producto_nombre,
                data.get('dosis', '4 ml / Litro'),
                data.get('actividades', 'Aspersión focalizada y colocación de cebo específico.'),
                data.get('firma', '')
            ))
            srv_id = cur.lastrowid

            for f in data.get('fotos', []):
                cur.execute('INSERT INTO servicio_fotos (servicio_id, ruta_imagen) VALUES (?, ?)', (srv_id, f))

            conn.execute('''
                UPDATE inventario 
                SET stock_actual = MAX(0, ROUND(stock_actual - 0.25, 2)) 
                WHERE tipo = 'Quimico' AND nombre LIKE ?
            ''', (f"%{producto_nombre}%",))
            conn.commit()

        return jsonify({'status': 'ok', 'servicio_id': srv_id, 'folio': folio})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/servicio_exitoso/<folio>')
def servicio_exitoso(folio):
    try:
        with get_db() as conn:
            srv_row = conn.execute("SELECT * FROM servicios WHERE folio = ?", (folio,)).fetchone()
            if not srv_row:
                return redirect('/tecnico')
            srv = dict(srv_row)
            
            c_row = conn.execute("SELECT * FROM clientes WHERE id = ?", (srv.get('cliente_id', 1),)).fetchone()
            cliente = dict(c_row) if c_row else {'nombre_comercial': 'Cliente General', 'contacto': 'Responsable', 'telefono': '5649643758'}

        tel_limpio = "".join([c for c in str(cliente.get('telefono') or '5649643758') if c.isdigit()])
        if len(tel_limpio) == 10:
            wa_tel = f"52{tel_limpio}"
        else:
            wa_tel = tel_limpio or "525649643758"

        url_certificado = f"https://control-plagas-bot.onrender.com/ver_certificado/{folio}"
        mensaje_texto = (
            f"Hola {cliente.get('contacto') or cliente.get('nombre_comercial')}, le compartimos su "
            f"Certificado Oficial de Manejo Integral de Plagas (Folio #{folio}) emitido por Fumilab Control Integral "
            f"bajo Licencia Sanitaria COFEPRIS: {url_certificado}"
        )
        wa_mensaje_encoded = urllib.parse.quote(mensaje_texto)

        return render_template('servicio_exitoso.html', 
                               folio=folio,
                               cliente_nombre=cliente.get('nombre_comercial'),
                               cliente_telefono=cliente.get('telefono'),
                               wa_telefono=wa_tel,
                               wa_mensaje=wa_mensaje_encoded)
    except Exception as e:
        return f"Error en confirmación de servicio: {str(e)}", 500

@app.route('/ver_certificado/<folio>')
def ver_certificado_publico(folio):
    try:
        with get_db() as conn:
            srv_row = conn.execute("SELECT id FROM servicios WHERE folio = ?", (folio,)).fetchone()
            if not srv_row:
                srv_first = conn.execute("SELECT id FROM servicios ORDER BY id ASC LIMIT 1").fetchone()
                if srv_first:
                    srv_id = srv_first['id']
                else:
                    return "Certificado sanitario no encontrado.", 404
            else:
                srv_id = srv_row['id']
        return descargar_reporte_pdf(srv_id)
    except Exception as e:
        return f"Error al recuperar certificado: {str(e)}", 500

@app.route('/imprimir_stickers_qr/<int:cliente_id>')
@login_requerido
def imprimir_stickers_qr(cliente_id):
    try:
        import qrcode

        with get_db() as conn:
            c_row = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
            if not c_row:
                return "Cliente no encontrado", 404
            cliente = dict(c_row)

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(f"Stickers_QR_{cliente.get('nombre_comercial')}")

        qr_url = f"https://control-plagas-bot.onrender.com/reporte_campo?cliente_id={cliente_id}"
        qr = qrcode.QRCode(box_size=1, border=0)
        qr.add_data(qr_url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        matrix_size = len(matrix)

        posiciones = [
            (35, 410),
            (315, 410),
            (35, 40),
            (315, 40)
        ]

        w_box = 260
        h_box = 345

        for idx, (x, y) in enumerate(posiciones, start=1):
            pdf.setFillColor(colors.HexColor("#f8fafc"))
            pdf.setStrokeColor(colors.HexColor("#064e3b"))
            pdf.roundRect(x, y, w_box, h_box, 8, stroke=1, fill=1)

            pdf.setFillColor(colors.HexColor("#064e3b"))
            pdf.roundRect(x, y + h_box - 50, w_box, 50, 6, stroke=0, fill=1)

            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(x + 10, y + h_box - 20, "FUMILAB CONTROL INTEGRAL")
            pdf.setFont("Helvetica", 7.5)
            pdf.drawString(x + 10, y + h_box - 32, "LICENCIA COFEPRIS: 2009-15A013")
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawRightString(x + w_box - 10, y + h_box - 32, f"ESTACIÓN #{idx:02d}")

            pdf.setFillColor(colors.HexColor("#0f172a"))
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.drawString(x + 10, y + h_box - 65, str(cliente.get('nombre_comercial'))[:36])
            pdf.setFont("Helvetica", 7)
            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.drawString(x + 10, y + h_box - 75, f"Ubicación: {str(cliente.get('direccion'))[:40]}")

            qr_display_size = 110.0
            scale = qr_display_size / matrix_size
            qr_origin_x = x + (w_box - qr_display_size) / 2.0
            qr_origin_y = y + 140

            pdf.setFillColor(colors.HexColor("#064e3b"))
            for r_idx, row in enumerate(matrix):
                for c_idx, val in enumerate(row):
                    if val:
                        pdf.rect(
                            qr_origin_x + (c_idx * scale),
                            qr_origin_y + ((matrix_size - 1 - r_idx) * scale),
                            scale,
                            scale,
                            stroke=0,
                            fill=1
                        )

            pdf.setFillColor(colors.HexColor("#e2e8f0"))
            pdf.setStrokeColor(colors.HexColor("#94a3b8"))
            pdf.rect(x + 10, y + 42, w_box - 20, 88, fill=0, stroke=1)

            pdf.setFillColor(colors.HexColor("#0f172a"))
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(x + 15, y + 116, "BITÁCORA DE REVISIÓN EN SITIO")
            pdf.setFont("Helvetica", 6.5)
            pdf.drawString(x + 15, y + 102, "Fecha: ____/____/2026   | Consumo: [ ] 0%  [ ] 50%  [ ] 100%")
            pdf.drawString(x + 15, y + 86, "Fecha: ____/____/2026   | Consumo: [ ] 0%  [ ] 50%  [ ] 100%")
            pdf.drawString(x + 15, y + 70, "Fecha: ____/____/2026   | Consumo: [ ] 0%  [ ] 50%  [ ] 100%")
            pdf.drawString(x + 15, y + 54, "Fecha: ____/____/2026   | Consumo: [ ] 0%  [ ] 50%  [ ] 100%")

            pdf.setFillColor(colors.HexColor("#b91c1c"))
            pdf.setFont("Helvetica-Bold", 6.5)
            pdf.drawCentredString(x + (w_box / 2.0), y + 26, "DISPOSITIVO DE MONITOREO SANITARIO • NO RETIRAR")
            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.setFont("Helvetica", 6)
            pdf.drawCentredString(x + (w_box / 2.0), y + 14, "Escanea con la App Técnico para registrar visita")

        pdf.save()
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Stickers_QR_Fumilab_{cliente_id}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        return f"Error al generar Stickers QR: {str(e)}", 500

@app.route('/api/descargar_backup_db')
@login_requerido
def descargar_backup_db():
    try:
        if os.path.exists(DB_FILE):
            fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            return send_file(DB_FILE, as_attachment=True, download_name=f"fumilab_backup_{fecha_str}.db")
        return "Archivo de base de datos no encontrado", 404
    except Exception as e:
        return f"Error al exportar base de datos: {str(e)}", 500

@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
@login_requerido
def marcar_atendido(lead_id):
    try:
        with get_db() as conn:
            conn.execute("UPDATE prospectos SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/descargar_reporte_pdf/<int:servicio_id>')
def descargar_reporte_pdf(servicio_id):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM servicios WHERE id = ?", (servicio_id,)).fetchone()
            if not row:
                return "Servicio no encontrado", 404
            srv = dict(row)

            c_row = conn.execute("SELECT * FROM clientes WHERE id = ?", (srv.get('cliente_id', 1),)).fetchone()
            cliente = dict(c_row) if c_row else {'nombre_comercial': 'Cliente Comercial', 'contacto': 'Responsable', 'direccion': 'CDMX y EdoMex'}

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        folio_str = str(srv.get('folio') or srv.get('id', '3501'))
        pdf.setTitle(f"Certificado_Fumilab_{folio_str}")

        pdf.setFillColor(colors.HexColor("#064e3b"))
        pdf.rect(0, 715, 612, 77, fill=True, stroke=False)
        pdf.setFillColor(colors.HexColor("#10b981"))
        pdf.rect(0, 710, 612, 5, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(40, 755, "FUMILAB CONTROL INTEGRAL")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(40, 738, "Manejo Integral de Plagas Urbanas & Desinfección")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(40, 723, "LICENCIA SANITARIA COFEPRIS: 2009-15A013")

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(572, 755, f"CERTIFICADO #{folio_str}")
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(572, 738, f"FECHA: {srv.get('fecha_servicio') or '2026-09-20'}")

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
        pdf.roundRect(35, 605, 542, 90, 6, stroke=1, fill=1)

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 675, "Razón Social / Cliente:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(150, 675, str(cliente.get('nombre_comercial'))[:45])
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 655, "Dirección Inmueble:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(150, 655, str(cliente.get('direccion'))[:60])
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 635, "Servicio Realizado:")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#047857"))
        pdf.drawString(150, 635, str(srv.get('tipo_servicio') or 'MANEJO INTEGRAL DE PLAGAS'))

        y_tbl = 560
        pdf.setFillColor(colors.HexColor("#064e3b"))
        pdf.rect(35, y_tbl, 542, 18, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(42, y_tbl + 5, "PRODUCTO COMERCIAL")
        pdf.drawString(180, y_tbl + 5, "INGREDIENTE ACTIVO")
        pdf.drawString(350, y_tbl + 5, "DOSIS APLICADA")
        pdf.drawString(465, y_tbl + 5, "TIEMPO REENTRADA")

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(42, y_tbl - 18, str(srv.get('quimico_utilizado') or 'DEMAND DUO'))
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(180, y_tbl - 18, str(srv.get('ingrediente_activo') or 'LAMBDA CYHALOTRINA 9.7%'))
        pdf.drawString(350, y_tbl - 18, str(srv.get('dosis_aplicada') or '4 ml / Litro'))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#b91c1c"))
        pdf.drawString(465, y_tbl - 18, str(srv.get('tiempo_reentrada') or '2 Horas'))

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
        pdf.roundRect(35, 385, 542, 130, 6, stroke=1, fill=1)

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 495, "ACTIVIDADES TÉCNICAS EJECUTADAS:")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(45, 480, str(srv.get('actividades_realizadas') or 'Aspersión perimetral focalizada y colocación de cebo específico.')[:110])

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 455, "RECOMENDACIONES SANITARIAS & MEDIDAS PREVENTIVAS:")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(45, 440, str(srv.get('recomendaciones') or 'No realizar aseo profundo en áreas tratadas por 24 horas. Mantener ventilación previa al reingreso.')[:110])

        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.setFillColor(colors.HexColor("#047857"))
        pdf.drawString(45, 405, "NORMATIVA SANITARIA: Tratamiento y aplicación validados bajo la Norma Oficial Mexicana NOM-256-SSA1-2012.")

        firma_data = srv.get('firma_cliente')
        if firma_data and ',' in firma_data:
            try:
                fb = base64.b64decode(firma_data.split(',')[1])
                pdf.drawImage(ImageReader(io.BytesIO(fb)), 360, 270, width=150, height=60, mask='auto')
            except Exception:
                pass

        pdf.setStrokeColor(colors.HexColor("#64748b"))
        pdf.line(60, 270, 230, 270)
        pdf.line(350, 270, 520, 270)
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(145, 258, "Jonathan Dávila")
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(145, 248, "Técnico Especialista COFEPRIS")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(435, 258, str(cliente.get('contacto') or 'Responsable')[:30])
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(435, 248, "Firma de Conformidad del Cliente")

        pdf.setFillColor(colors.HexColor("#064e3b"))
        pdf.rect(35, 175, 542, 24, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawCentredString(306, 185, "FUMILAB CONTROL • TEL/WHATSAPP: 56 4964 3758 • MATRIZ: LOS REYES IZTACALA, TLALNEPANTLA, EDOMEX")

        pdf.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{folio_str}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error al generar Certificado: {str(e)}", 500

@app.route('/manifest.json')
def pwa_manifest():
    return send_file('static/manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def pwa_service_worker():
    response = send_file('static/service-worker.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response


# ============================================================
# WEBHOOK OFICIAL DE WHATSAPP META CLOUD API
# ============================================================
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'fumilab_token_seguro_2026')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1335257003001244')

def responder_whatsapp(telefono_destino, mensaje):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Falta WHATSAPP_TOKEN o PHONE_NUMBER_ID")
        return
    try:
        import requests
        url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono_destino,
            "type": "text",
            "text": {"body": mensaje}
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print("Envio WhatsApp status:", r.status_code, r.text)
    except Exception as err:
        print("Error al responder mensaje por WhatsApp:", err)

@app.route('/webhook/whatsapp', methods=['GET', 'POST'])
@app.route('/webhook', methods=['GET', 'POST'])
def webhook_whatsapp():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
        return challenge or 'Token invalido', 200

    if request.method == 'POST':
        data = request.get_json() or {}
        try:
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            if messages:
                msg = messages[0]
                remitente = msg.get('from')
                texto = msg.get('text', {}).get('body', '').strip().lower()

                contacts = value.get('contacts', [])
                nombre = contacts[0].get('profile', {}).get('name', '') if contacts else ''
                saludo = ('Estimado(a) ' + nombre + ',') if nombre else 'Estimado cliente,'

                if texto in ['1', 'cotizar', 'cotizacion', 'costo', 'precio', 'presupuesto']:
                    lineas = [
                        saludo,
                        '',
                        'Con gusto le compartimos los detalles para la cotizacion de su servicio.',
                        '',
                        'En *Fumilab Control Integral* implementamos programas de Manejo Integral de Plagas bajo normativa *NOM-256-SSA1-2012*, utilizando insumos autorizados por COFEPRIS y emitiendo certificado con validez oficial.',
                        '',
                        'Para generar su propuesta tecnica formal y cotizacion con folio inmediato, ingrese a nuestro portal institucional:',
                        'https://control-plagas-bot.onrender.com/solicitar_cotizacion',
                        '',
                        'Si requiere atencion directa, compartanos:',
                        '- Giro del inmueble (Residencial, Restaurante, Industria, Comercio)',
                        '- Tipo de plaga a tratar',
                        '- Ubicacion (Municipio o Alcaldia)'
                    ]
                elif texto in ['2', 'poliza', 'certificado', 'reporte', 'vigencia']:
                    lineas = [
                        saludo,
                        '',
                        'Para validar la vigencia de su poliza, solicitar copia de Certificado Sanitario o programar su servicio preventivo mensual, proporcionenos:',
                        '',
                        '- Razon Social o Nombre comercial del establecimiento',
                        '- Numero de Folio o Certificado anterior (si cuenta con el)',
                        '',
                        'Nuestro departamento de control sanitario validara su expediente a la brevedad.'
                    ]
                elif texto in ['3', 'asesor', 'humano', 'contacto', 'urgente', 'tecnico']:
                    lineas = [
                        saludo,
                        '',
                        'Su solicitud ha sido turnada al area tecnica especializada.',
                        '',
                        'Un asesor tomara el control de esta conversacion a la brevedad para brindarle asistencia personalizada.',
                        '',
                        'Línea directa: *56 4964 3758*',
                        'Licencia Sanitaria COFEPRIS: *2009-15A013*',
                        'Horario de atencion: Lunes a Sabado de 8:00 a 19:00 hrs.'
                    ]
                else:
                    lineas = [
                        saludo,
                        'Bienvenido al canal corporativo de atencion de *Fumilab Control Integral*.',
                        '',
                        'Especialistas en Manejo Integral de Plagas Urbanas, Desinfeccion y Bioseguridad institucional bajo *Licencia Sanitaria COFEPRIS: 2009-15A013*.',
                        '',
                        'Por favor elija una de las siguientes opciones indicando el numero:',
                        '',
                        '*[ 1 ]* Solicitar cotizacion o propuesta de servicio',
                        '*[ 2 ]* Seguimiento de polizas y certificados sanitarios',
                        '*[ 3 ]* Contactar a un asesor tecnico',
                        '',
                        'Portal en linea de cotizaciones inmediatas:',
                        'https://control-plagas-bot.onrender.com/solicitar_cotizacion'
                    ]

                respuesta = '\n'.join(lineas)
                responder_whatsapp(remitente, respuesta)
        except Exception as e:
            print('Error procesando mensaje webhook:', e)

        return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

