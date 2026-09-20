import os
import io
import json
import base64
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "fumilab_control_pro_secret_key_2026"

DB_FILE = 'fumilab.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    try:
        with get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_comercial TEXT NOT NULL,
                    contacto TEXT,
                    telefono TEXT,
                    direccion TEXT,
                    tipo_inmueble TEXT
                )
            ''')

            conn.execute('''
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

            conn.execute('''
                CREATE TABLE IF NOT EXISTS prospectos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folio TEXT UNIQUE,
                    nombre TEXT NOT NULL,
                    telefono TEXT NOT NULL,
                    tipo_inmueble TEXT,
                    plaga TEXT,
                    fecha_solicitud TEXT,
                    estatus TEXT DEFAULT 'Pendiente',
                    notas TEXT
                )
            ''')

            conn.execute('''
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

            conn.execute('''
                CREATE TABLE IF NOT EXISTS servicio_fotos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    servicio_id INTEGER,
                    ruta_imagen TEXT
                )
            ''')

            # Migraciones defensivas
            migraciones = [
                ("clientes", "tipo_inmueble", "TEXT"),
                ("servicios", "gasto_quimicos", "REAL DEFAULT 250.0"),
                ("servicios", "gasto_gasolina", "REAL DEFAULT 180.0"),
                ("servicios", "gasto_nomina", "REAL DEFAULT 350.0"),
                ("servicios", "gasto_equipo", "REAL DEFAULT 80.0"),
                ("servicios", "equipo_utilizado", "TEXT"),
                ("servicios", "cliente_id", "INTEGER"),
                ("prospectos", "folio", "TEXT"),
                ("prospectos", "tipo_inmueble", "TEXT"),
                ("prospectos", "plaga", "TEXT"),
                ("prospectos", "fecha_solicitud", "TEXT"),
                ("prospectos", "estatus", "TEXT DEFAULT 'Pendiente'"),
                ("prospectos", "notas", "TEXT")
            ]
            for tabla, col, tipo in migraciones:
                try:
                    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
                except Exception:
                    pass

            # Precarga inicial
            c_count = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            if c_count == 0:
                conn.execute('''
                    INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion, tipo_inmueble) VALUES 
                    ('Farmacia Similares 3509 Ecatepec', 'Nancy Padilla Garcia', '5541419369', 'Av. Jardines de Morelos Mz. 316', 'Comercial'),
                    ('Purificadora Hidropura', 'Elizabeth Carbajal', '5534842783', 'Cuautitlan Izcalli EdoMex', 'Industrial'),
                    ('Restaurante Aloha Mar y Tierra', 'Mauricio Garduño', '5632326172', 'Blvd. Valle San Felipe', 'Alimentos')
                ''')

            p_count = conn.execute("SELECT COUNT(*) FROM prospectos").fetchone()[0]
            if p_count == 0:
                conn.execute('''
                    INSERT INTO prospectos (folio, nombre, telefono, tipo_inmueble, plaga, fecha_solicitud, estatus, notas) VALUES
                    ('COT-901', 'Bodega Abarrotes Central', '5511223344', 'Bodega Industrial', 'Roedores y Cucarachas', '2026-09-19', 'Pendiente', 'Cotización urgente servicio perimetral'),
                    ('COT-902', 'Panificadora La Espiga', '5598765432', 'Alimentos', 'Cucaracha Germánica', '2026-09-19', 'Atendido', 'Póliza acordada lunes 8am')
                ''')

            inv_count = conn.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]
            if inv_count == 0:
                conn.execute('''
                    INSERT INTO inventario (tipo, nombre, registro_cofepris, stock_actual, unidad, costo_unitario, estado) VALUES
                    ('Quimico', 'DEMAND DUO (Syngenta)', 'RSCO-URB-INAC-111-315-009-0.02', 12.5, 'Litros', 850.0, 'En Stock'),
                    ('Quimico', 'RODILON BLOQUE (Bayer)', 'RSCO-URB-ROD-0101-322-005-0.0025', 18.0, 'Kg', 420.0, 'En Stock'),
                    ('Quimico', 'BIOCIDAL PLUS 5TA GEN', 'RSCO-DOM-DES-0102-301-002-10', 25.0, 'Litros', 310.0, 'En Stock'),
                    ('Equipo', 'Aspersora Manual Swissmex 15L', 'NOM-STPS', 4.0, 'Piezas', 1200.0, 'Operativa'),
                    ('Equipo', 'Termonebulizador en Frío ULV', 'CE-ISO', 2.0, 'Piezas', 4800.0, 'Operativa')
                ''')

            s_count = conn.execute("SELECT COUNT(*) FROM servicios").fetchone()[0]
            if s_count == 0:
                conn.execute('''
                    INSERT INTO servicios (
                        folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin,
                        costo, gasto_quimicos, gasto_gasolina, gasto_nomina, gasto_equipo,
                        quimico_utilizado, ingrediente_activo, dosis_aplicada, equipo_utilizado, tiempo_reentrada,
                        actividades_realizadas, recomendaciones, estatus
                    ) VALUES 
                    ('3501', 1, 'MANEJO INTEGRAL DE CUCARACHAS', '2026-09-19', '08:41 PM', '09:41 PM',
                     1400.0, 180.0, 150.0, 350.0, 50.0,
                     'DEMAND DUO', 'LAMBDA CYHALOTRINA 9.7%', '4 ml / L de agua', 'Aspersora Manual Swissmex', '2 Horas',
                     'Aspersión perimetral focalizada y colocación de gel cucarachicida', 'No realizar aseo profundo en 24h', 'Terminado'),
                    ('3502', 2, 'CONTROL DE ROEDORES (MIP)', '2026-09-18', '04:52 PM', '06:18 PM',
                     1800.0, 220.0, 180.0, 400.0, 60.0,
                     'RODILON BLOQUE', 'DIFETIALONA 0.0025%', '1 Bloque / Cebadero', 'Cebaderos Perimetrales R-Lock', 'Inmediata',
                     'Revisión y reabastecimiento de 8 estaciones de cebado', 'Mantener pasillos libres de tarimas', 'Terminado')
                ''')
    except Exception as e:
        print(f"Error en init_db: {e}")

init_db()

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/panel')
@app.route('/admin')
def admin_redirect():
    return redirect(url_for('dashboard_financiero'))

@app.route('/dashboard')
@app.route('/dashboard_financiero')
def dashboard_financiero():
    try:
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

        return render_template('dashboard_financiero.html',
                               servicios=servicios,
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
def inventarios():
    try:
        with get_db() as conn:
            items = [dict(i) for i in conn.execute("SELECT * FROM inventario ORDER BY tipo DESC, nombre ASC").fetchall()]
        return render_template('inventarios.html', items=items)
    except Exception as e:
        return f"Error en Inventarios: {str(e)}", 500

@app.route('/prospectos')
def prospectos():
    try:
        with get_db() as conn:
            leads = [dict(f) for f in conn.execute("SELECT * FROM prospectos ORDER BY id DESC").fetchall()]
        return render_template('prospectos.html', leads=leads)
    except Exception as e:
        return f"Error en Prospectos: {str(e)}", 500

@app.route('/certificados')
def certificados():
    try:
        with get_db() as conn:
            filas = conn.execute('''
                SELECT s.*, coalesce(c.nombre_comercial, 'Cliente Comercial') as cliente_nombre 
                FROM servicios s 
                LEFT JOIN clientes c ON s.cliente_id = c.id 
                ORDER BY s.id DESC
            ''').fetchall()
            servicios = [dict(f) for f in filas]
        return render_template('certificados.html', servicios=servicios)
    except Exception as e:
        return f"Error en Certificados: {str(e)}", 500

@app.route('/tecnico')
def tecnico():
    return render_template('tecnico_home.html')

@app.route('/reporte_campo')
def reporte_campo():
    try:
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
            nombre = request.form.get('nombre', '').strip()
            telefono = request.form.get('telefono', '').strip()
            tipo_inmueble = request.form.get('tipo_inmueble', 'Comercial')
            plaga = request.form.get('plaga', 'Cucarachas')
            notas = request.form.get('notas', '')

            with get_db() as conn:
                conteo = conn.execute('SELECT COUNT(*) FROM prospectos').fetchone()[0]
                folio = f"COT-{901 + conteo}"
                fecha = datetime.now().strftime("%Y-%m-%d")

                conn.execute('''
                    INSERT INTO prospectos (folio, nombre, telefono, tipo_inmueble, plaga, fecha_solicitud, estatus, notas)
                    VALUES (?, ?, ?, ?, ?, ?, 'Pendiente', ?)
                ''', (folio, nombre, telefono, tipo_inmueble, plaga, fecha, notas))

            return redirect(url_for('cotizacion_exitosa', folio=folio))
        except Exception as e:
            return f"Error al procesar cotización: {str(e)}", 500

    return render_template('solicitar_cotizacion.html')

@app.route('/cotizacion_exitosa')
def cotizacion_exitosa():
    folio = request.args.get('folio', 'COT-901')
    return render_template('cotizacion_exitosa.html', folio=folio)

@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
def marcar_atendido(lead_id):
    try:
        with get_db() as conn:
            conn.execute("UPDATE prospectos SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
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
        pdf.drawRightString(572, 738, f"FECHA: {srv.get('fecha_servicio') or '2026-09-19'}")

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(35, 605, 542, 90, 6, fill=True, stroke=colors.HexColor("#cbd5e1"))
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

        pdf.setStrokeColor(colors.HexColor("#64748b"))
        pdf.line(60, 270, 230, 270)
        pdf.line(350, 270, 520, 270)
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(145, 258, "Jonathan Dávila")
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(145, 248, "Técnico Especialista COFEPRIS")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(435, 258, str(cliente.get('contacto'))[:30])
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(435, 248, "Firma de Conformidad del Cliente")

        pdf.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{folio_str}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error al generar Certificado: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
