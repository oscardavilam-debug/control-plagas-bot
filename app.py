import os
import io
import json
import base64
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "fumilab_control_pro_secret_key_2026"

def get_db():
    conn = sqlite3.connect('fumilab.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    
    # 1. Clientes
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

    # 2. Servicios / Certificados
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
            quimico_utilizado TEXT,
            ingrediente_activo TEXT,
            dosis_aplicada TEXT,
            tiempo_reentrada TEXT,
            actividades_realizadas TEXT,
            recomendaciones TEXT,
            firma_cliente TEXT,
            estatus TEXT DEFAULT 'Terminado'
        )
    ''')

    # 3. Prospectos / Cotizaciones web
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

    # 4. Fotos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio_id INTEGER,
            ruta_imagen TEXT
        )
    ''')

    # Migración defensiva
    columnas_servicios = [
        ("quimico_utilizado", "TEXT"),
        ("ingrediente_activo", "TEXT"),
        ("dosis_aplicada", "TEXT"),
        ("tiempo_reentrada", "TEXT"),
        ("actividades_realizadas", "TEXT"),
        ("recomendaciones", "TEXT"),
        ("firma_cliente", "TEXT")
    ]
    for col, tipo in columnas_servicios:
        try:
            conn.execute(f"ALTER TABLE servicios ADD COLUMN {col} {tipo}")
        except Exception:
            pass

    # Sembrado inicial de Clientes
    c_count = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    if c_count == 0:
        conn.execute('''
            INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion, tipo_inmueble) VALUES 
            ('Farmacia Similares 3509 Ecatepec', 'Nancy Claudia Padilla Garcia', '5541419369', 'Av. Jardines de Morelos Mz. 316 Lt 12', 'Comercial / Farmacia'),
            ('Purificadora Hidropura', 'Elizabeth Carbajal', '5534842783', 'Av. de los Valles Col. Atlante Cuautitlan Izcalli', 'Industrial / Purificadora'),
            ('Restaurante Aloha Mar y Tierra', 'Mauricio Garduño Mayer', '5632326172', 'Blvd. Valle San Felipe Mz 14 Lt 2', 'Alimentos y Bebidas')
        ''')

    # Sembrado inicial de Prospectos
    p_count = conn.execute("SELECT COUNT(*) FROM prospectos").fetchone()[0]
    if p_count == 0:
        conn.execute('''
            INSERT INTO prospectos (folio, nombre, telefono, tipo_inmueble, plaga, fecha_solicitud, estatus, notas) VALUES
            ('COT-901', 'Bodega Abarrotes Central', '5511223344', 'Bodega Industrial', 'Roedores y Cucaracha Germánica', '2026-09-19', 'Pendiente', 'Requiere visita técnica urgente'),
            ('COT-902', 'Panificadora La Espiga', '5598765432', 'Comercial / Alimentos', 'Cucaracha de Cocina', '2026-09-19', 'Atendido', 'Cotización enviada vía WhatsApp'),
            ('COT-903', 'Consultorio Médico San José', '5566778899', 'Sector Salud / Consultorio', 'Desinfección Ambiental', '2026-09-18', 'Atendido', 'Póliza bimestral acordada')
        ''')

    # Sembrado inicial de Servicios y Certificados
    s_count = conn.execute("SELECT COUNT(*) FROM servicios").fetchone()[0]
    if s_count == 0:
        conn.execute('''
            INSERT INTO servicios (
                folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin, costo,
                quimico_utilizado, ingrediente_activo, dosis_aplicada, tiempo_reentrada,
                actividades_realizadas, recomendaciones, estatus
            ) VALUES 
            ('3501', 1, 'MANEJO INTEGRAL DE PLAGAS URBANAS', '2026-09-19', '08:41 PM', '09:41 PM', 1400.0,
             'DEMAND DUO', 'LAMBDA CYHALOTRINA + TIAMETOXAM', '4 ml / Litro de agua', '2 Horas',
             'Aspersión perimetral focalizada y colocación de gel cucarachicida en grietas', 'No realizar aseo profundo en las áreas tratadas durante 24 horas', 'Terminado'),
            ('3502', 2, 'CONTROL INTEGRAL DE ROEDORES (MIP)', '2026-09-18', '04:52 PM', '06:18 PM', 1800.0,
             'RODILON BLOQUE', 'DIFETIALONA 0.0025%', '1 Bloque fijado por cebadero', 'Inmediata',
             'Revisión, limpieza y reabastecimiento de estaciones de cebado perimetrales', 'Mantener estaciones cerradas y libres de tarimas en periferia', 'Terminado'),
            ('3503', 3, 'DESINFECCION AMBIENTAL Y SANITIZACION', '2026-09-17', '10:00 AM', '11:30 AM', 2200.0,
             'BIOCIDAL PLUS', 'SALES DE AMONIO CUATERNARIO 5TA GEN', '5 ml / Litro de agua', '3 Horas',
             'Termonebulización en frío en salón comedor, cocina y cámaras frías', 'Ventilar 30 minutos antes del reingreso de personal', 'Terminado')
        ''')

    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    pass

# ================= RUTAS DE NAVEGACIÓN SaaS =================
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
        conn = get_db()
        filas = conn.execute("SELECT * FROM servicios ORDER BY id DESC").fetchall()
        servicios = [dict(f) for f in filas]
        
        ingresos_num = sum([float(s.get('costo') or 1400.0) for s in servicios if s.get('estatus') in ['Terminado', 'Atendido']])
        egresos_num = ingresos_num * 0.35
        balance_num = ingresos_num - egresos_num
        
        c_count = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        conn.close()
        
        return render_template('dashboard_financiero.html', 
                               servicios=servicios, 
                               total_ingresos=f"{ingresos_num:,.2f}", 
                               total_egresos=f"{egresos_num:,.2f}",
                               balance_neto=f"{balance_num:,.2f}",
                               total_servicios=len(servicios), 
                               clientes_activos=c_count)
    except Exception as e:
        return f"Error en Dashboard: {str(e)}", 500

@app.route('/prospectos')
def prospectos():
    try:
        conn = get_db()
        filas = conn.execute("SELECT * FROM prospectos ORDER BY id DESC").fetchall()
        leads = [dict(f) for f in filas]
        conn.close()
        return render_template('prospectos.html', leads=leads)
    except Exception as e:
        return f"Error en Prospectos: {str(e)}", 500

@app.route('/certificados')
def certificados():
    try:
        conn = get_db()
        filas = conn.execute('''
            SELECT s.*, c.nombre_comercial as cliente_nombre, c.direccion as cliente_direccion 
            FROM servicios s 
            LEFT JOIN clientes c ON s.cliente_id = c.id 
            ORDER BY s.id DESC
        ''').fetchall()
        servicios = [dict(f) for f in filas]
        conn.close()
        return render_template('certificados.html', servicios=servicios)
    except Exception as e:
        return f"Error en Certificados: {str(e)}", 500

@app.route('/tecnico')
def tecnico():
    return render_template('tecnico_home.html')

@app.route('/reporte_campo')
def reporte_campo():
    try:
        conn = get_db()
        clientes = [dict(c) for c in conn.execute("SELECT * FROM clientes").fetchall()]
        conn.close()
        return render_template('reporte_campo.html', clientes=clientes)
    except Exception as e:
        return f"Error en Reporte Campo: {str(e)}", 500

@app.route('/escaner_qr')
def escaner_qr():
    return render_template('escaner_qr.html')

# ================= COTIZACIONES WEB =================
@app.route('/solicitar_cotizacion', methods=['GET', 'POST'])
def solicitar_cotizacion():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        tipo_inmueble = request.form.get('tipo_inmueble', 'Comercial')
        plaga = request.form.get('plaga', 'Cucarachas')
        notas = request.form.get('notas', '')

        if nombre and telefono:
            conn = get_db()
            cur = conn.cursor()
            conteo = cur.execute('SELECT COUNT(*) FROM prospectos').fetchone()[0]
            folio = f"COT-{901 + conteo}"
            fecha = datetime.now().strftime("%Y-%m-%d")
            
            cur.execute('''
                INSERT INTO prospectos (folio, nombre, telefono, tipo_inmueble, plaga, fecha_solicitud, estatus, notas)
                VALUES (?, ?, ?, ?, ?, ?, 'Pendiente', ?)
            ''', (folio, nombre, telefono, tipo_inmueble, plaga, fecha, notas))
            conn.commit()
            conn.close()
            return redirect(url_for('cotizacion_exitosa', folio=folio))
    return render_template('solicitar_cotizacion.html')

@app.route('/cotizacion_exitosa')
def cotizacion_exitosa():
    folio = request.args.get('folio', 'COT-900')
    return render_template('cotizacion_exitosa.html', folio=folio)

# ================= APIS =================
@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
def marcar_atendido(lead_id):
    try:
        conn = get_db()
        conn.execute("UPDATE prospectos SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/guardar_reporte_servicio', methods=['POST'])
def guardar_reporte():
    try:
        data = request.get_json() or {}
        conn = get_db()
        cur = conn.cursor()
        c = cur.execute('SELECT COUNT(*) FROM servicios').fetchone()[0]
        folio = f"{3501 + c}"
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        cur.execute('''
            INSERT INTO servicios (
                folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin,
                costo, quimico_utilizado, ingrediente_activo, dosis_aplicada, tiempo_reentrada,
                actividades_realizadas, recomendaciones, firma_cliente, estatus
            ) VALUES (?, ?, ?, ?, ?, ?, 1400.0, ?, 'LAMBDA CYHALOTRINA', ?, '2 Horas', ?, 'No limpiar en 24h', ?, 'Terminado')
        ''', (
            folio,
            data.get('cliente_id', 1),
            data.get('tipo_visita', 'MIP'),
            fecha_hoy,
            data.get('hora_inicio', '08:00'),
            data.get('hora_fin', '09:00'),
            data.get('producto', 'DEMAND DUO'),
            data.get('dosis', '4 ml / L'),
            data.get('actividades', 'Aspersion focalizada'),
            data.get('firma', '')
        ))
        srv_id = cur.lastrowid
        for f in data.get('fotos', []):
            cur.execute('INSERT INTO servicio_fotos (servicio_id, ruta_imagen) VALUES (?, ?)', (srv_id, f))

        conn.commit()
        conn.close()
        return jsonify({'status': 'ok', 'servicio_id': srv_id, 'folio': folio})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ================= GENERADOR PDF OFICIAL COFEPRIS =================
@app.route('/descargar_reporte_pdf/<int:servicio_id>')
def descargar_reporte_pdf(servicio_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM servicios WHERE id = ?", (servicio_id,)).fetchone()
        if not row:
            conn.close()
            return "Servicio no encontrado", 404
        srv = dict(row)
        
        cliente_row = conn.execute("SELECT * FROM clientes WHERE id = ?", (srv.get('cliente_id', 1),)).fetchone()
        cliente = dict(cliente_row) if cliente_row else {
            'nombre_comercial': 'Establecimiento Comercial',
            'contacto': 'Responsable en Turno',
            'telefono': '55 8640 6475',
            'direccion': 'Ciudad de México y Área Metropolitana'
        }
        
        fotos = conn.execute("SELECT ruta_imagen FROM servicio_fotos WHERE servicio_id = ?", (servicio_id,)).fetchall()
        conn.close()

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(f"Certificado_Fumilab_{srv.get('folio')}")

        # --- PÁGINA 1: CERTIFICADO OFICIAL COFEPRIS ---
        pdf.setFillColor(colors.HexColor("#064e3b"))
        pdf.rect(0, 715, 612, 77, fill=True, stroke=False)
        pdf.setFillColor(colors.HexColor("#10b981"))
        pdf.rect(0, 710, 612, 5, fill=True, stroke=False)

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(40, 755, "FUMILAB CONTROL INTEGRAL")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(40, 738, "Servicios Profesionales de Desinfeccion y Manejo Integral de Plagas")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(40, 723, "LICENCIA SANITARIA COFEPRIS: 2009-15A013")

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(572, 755, f"CERTIFICADO: #{srv.get('folio')}")
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(572, 738, f"EMISIÓN: {srv.get('fecha_servicio')}")
        pdf.drawRightString(572, 723, "URGENCIAS: 55 8640 6475")

        # Tarjeta Datos Cliente
        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(35, 610, 542, 85, 6, fill=True, stroke=colors.HexColor("#cbd5e1"))
        
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 675, "Razón Social / Cliente:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(150, 675, str(cliente.get('nombre_comercial'))[:45])

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(380, 675, "Atención / Contacto:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(470, 675, str(cliente.get('contacto'))[:20])

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 655, "Dirección Inmueble:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(150, 655, str(cliente.get('direccion'))[:60])

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 635, "Servicio Ejecutado:")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#047857"))
        pdf.drawString(150, 635, str(srv.get('tipo_servicio')))

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(380, 635, "Horario de Operación:")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(470, 635, f"{srv.get('hora_inicio')} - {srv.get('hora_fin')}")

        # Tabla Técnica de Químicos COFEPRIS
        y_tbl = 565
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

        # Procedimientos y Recomendaciones
        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(35, 410, 542, 120, 6, fill=True, stroke=colors.HexColor("#cbd5e1"))

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 510, "ACTIVIDADES TÉCNICAS EJECUTADAS:")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(45, 495, str(srv.get('actividades_realizadas') or 'Aspersión focalizada en perímetro, zoclos, grietas y colocación de gel cucarachicida.'))

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(45, 470, "RECOMENDACIONES SANITARIAS Y DE REINGRESO:")
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(45, 455, str(srv.get('recomendaciones') or 'No realizar limpieza profunda húmeda en las primeras 24 horas para mantener la residualidad.'))
        pdf.drawString(45, 440, "Mantener ventilación natural cruzada al cumplir el tiempo de reingreso seguro indicado.")

        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.setFillColor(colors.HexColor("#047857"))
        pdf.drawString(45, 420, "VALIDEZ OFICIAL: Este documento certifica el tratamiento bajo la Norma Oficial Mexicana NOM-256-SSA1-2012.")

        # Sección de Firmas
        firma_data = srv.get('firma_cliente')
        if firma_data and ',' in firma_data:
            try:
                fb = base64.b64decode(firma_data.split(',')[1])
                pdf.drawImage(ImageReader(io.BytesIO(fb)), 360, 270, width=150, height=60, mask='auto')
            except Exception:
                pass

        pdf.setStrokeColor(colors.HexColor("#64748b"))
        pdf.setLineWidth(1)
        pdf.line(60, 270, 230, 270)
        pdf.line(350, 270, 520, 270)

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(145, 258, "Jonathan Dávila")
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(145, 248, "Técnico Especialista en Inocuidad")
        pdf.drawCentredString(145, 238, "Responsable Operativo Certificado")

        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(435, 258, str(cliente.get('contacto'))[:30])
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(435, 248, "Representante Legal / Encargado")
        pdf.drawCentredString(435, 238, "Firma de Aceptación y Conformidad")

        # Pie Legal
        pdf.setFillColor(colors.HexColor("#064e3b"))
        pdf.rect(35, 175, 542, 26, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawCentredString(306, 187, "FUMILAB CONTROL • MATRIZ: LAUREL LOTE 43 CASA 6, LOS REYES IZTACALA, TLALNEPANTLA, EDOMEX")
        pdf.setFont("Helvetica", 6.5)
        pdf.drawCentredString(306, 178, "Tel: 55 8640 6475 • Documento oficial protegido y validado en sistema central.")

        # --- PÁGINA 2: EVIDENCIA EN CAMPO ---
        if fotos:
            pdf.showPage()
            pdf.setFillColor(colors.HexColor("#064e3b"))
            pdf.rect(0, 735, 612, 57, fill=True, stroke=False)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(40, 755, "FUMILAB CONTROL | REPORTE GRÁFICO DE APLICACIÓN")
            pdf.drawRightString(572, 755, f"Folio: #{srv.get('folio')}")

            pos = [(45, 470), (315, 470), (45, 230), (315, 230)]
            for idx, f in enumerate(fotos[:4]):
                try:
                    raw = f['ruta_imagen']
                    if ',' in raw:
                        raw = raw.split(',')[1]
                    img = ImageReader(io.BytesIO(base64.b64decode(raw)))
                    x, y = pos[idx]
                    pdf.drawImage(img, x, y, width=250, height=195, preserveAspectRatio=True)
                except Exception:
                    pass

        pdf.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{srv.get('folio')}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error al generar Certificado: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
