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
            direccion TEXT
        )
    ''')

    # 2. Servicios
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT,
            cliente_id INTEGER,
            tipo_servicio TEXT,
            fecha_servicio TEXT,
            hora_inicio TEXT,
            hora_fin TEXT,
            costo REAL DEFAULT 1400.0,
            quimico_utilizado TEXT,
            dosis_aplicada TEXT,
            tiempo_reentrada TEXT,
            actividades_realizadas TEXT,
            recomendaciones TEXT,
            firma_cliente TEXT,
            estatus TEXT DEFAULT 'Terminado'
        )
    ''')

    # Migraciones no destructivas
    columnas = [
        ("quimico_utilizado", "TEXT"),
        ("dosis_aplicada", "TEXT"),
        ("tiempo_reentrada", "TEXT"),
        ("actividades_realizadas", "TEXT"),
        ("recomendaciones", "TEXT"),
        ("firma_cliente", "TEXT")
    ]
    for col, tipo in columnas:
        try:
            conn.execute(f"ALTER TABLE servicios ADD COLUMN {col} {tipo}")
        except Exception:
            pass

    # 3. Fotos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio_id INTEGER,
            ruta_imagen TEXT
        )
    ''')

    # Sembrado inicial seguro si la base está vacía
    try:
        c = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        if c == 0:
            conn.execute("INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion) VALUES ('Farmacia Similares 3509 Ecatepec', 'Nancy Padilla', '5541419369', 'Av. Jardines de Morelos Mz. 316')")
            conn.execute("INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion) VALUES ('Purificadora Hidropura', 'Elizabeth Carbajal', '5534842783', 'Cuautitlan Izcalli')")
            conn.execute("INSERT INTO clientes (nombre_comercial, contacto, telefono, direccion) VALUES ('Restaurante Aloha Mar y Tierra', 'Mauricio Garduño', '5632326172', 'Blvd. Valle San Felipe')")
    except Exception:
        pass

    try:
        s = conn.execute("SELECT COUNT(*) FROM servicios").fetchone()[0]
        if s == 0:
            conn.execute('''
                INSERT INTO servicios (folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin, costo, quimico_utilizado, dosis_aplicada, tiempo_reentrada, estatus)
                VALUES ('3501', 1, 'MANEJO INTEGRAL DE CUCARACHAS', '2026-09-19', '08:41 PM', '09:41 PM', 1400.0, 'DEMAND DUO', '4 ml / L de agua', '2 Horas', 'Terminado')
            ''')
            conn.execute('''
                INSERT INTO servicios (folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin, costo, quimico_utilizado, dosis_aplicada, tiempo_reentrada, estatus)
                VALUES ('3502', 2, 'CONTROL DE ROEDORES (CEBADEROS)', '2026-09-18', '04:52 PM', '06:18 PM', 1800.0, 'RODILON BLOQUE', '1 Bloque / Cebadero', 'Inmediata', 'Terminado')
            ''')
            conn.execute('''
                INSERT INTO servicios (folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin, costo, quimico_utilizado, dosis_aplicada, tiempo_reentrada, estatus)
                VALUES ('3503', 3, 'DESINFECCION & SANITIZACION AMBIENTAL', '2026-09-17', '10:00 AM', '11:30 AM', 2200.0, 'TERMICIDA PREMISE', '2 ml / L de agua', '4 Horas', 'Pendiente')
            ''')
    except Exception:
        pass

    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    pass

# ================= RUTAS PRINCIPALES =================
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
        
        # Cálculos Financieros
        ingresos_num = sum([float(s.get('costo') or 1400.0) for s in servicios if s.get('estatus') in ['Terminado', 'Atendido']])
        egresos_num = ingresos_num * 0.35  # 35% de costo operativo real
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
        filas = conn.execute("SELECT * FROM servicios ORDER BY id DESC").fetchall()
        leads = [dict(f) for f in filas]
        conn.close()
        return render_template('prospectos.html', leads=leads)
    except Exception as e:
        return f"Error en Prospectos: {str(e)}", 500

@app.route('/certificados')
def certificados():
    try:
        conn = get_db()
        filas = conn.execute("SELECT * FROM servicios ORDER BY id DESC").fetchall()
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

# ================= APIS =================
@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
def marcar_atendido(lead_id):
    try:
        conn = get_db()
        conn.execute("UPDATE servicios SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
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
            INSERT INTO servicios (folio, cliente_id, tipo_servicio, fecha_servicio, hora_inicio, hora_fin, costo, quimico_utilizado, dosis_aplicada, tiempo_reentrada, actividades_realizadas, firma_cliente, estatus)
            VALUES (?, ?, ?, ?, ?, ?, 1400.0, ?, ?, ?, ?, ?, 'Terminado')
        ''', (
            folio, data.get('cliente_id', 1), data.get('tipo_visita', 'MIP'),
            fecha_hoy, data.get('hora_inicio', '08:00'), data.get('hora_fin', '09:00'),
            data.get('producto', 'DEMAND DUO'), data.get('dosis', '4 ml / L'),
            data.get('reentrada', '2 Horas'), data.get('actividades', 'Aspersion'),
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

@app.route('/descargar_reporte_pdf/<int:servicio_id>')
def descargar_reporte_pdf(servicio_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM servicios WHERE id = ?", (servicio_id,)).fetchone()
        if not row:
            conn.close()
            return "Servicio no encontrado", 404
        srv = dict(row)
        fotos = conn.execute("SELECT ruta_imagen FROM servicio_fotos WHERE servicio_id = ?", (servicio_id,)).fetchall()
        conn.close()

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(f"Reporte_{srv.get('folio')}")

        # PÁGINA 1: CERTIFICADO OFICIAL
        pdf.setFillColor(colors.HexColor("#107c41"))
        pdf.rect(0, 720, 612, 72, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, 760, "FUMILABCONTROL")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(40, 742, "Reporte de Servicio & Certificado Oficial de Fumigacion")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawRightString(572, 760, f"Folio: #{srv.get('folio')}")
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(572, 742, "Licencia Sanitaria: 2009-15A013 (COFEPRIS)")

        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(45, 680, f"Servicio: {srv.get('tipo_servicio')}")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(45, 660, f"Fecha: {srv.get('fecha_servicio')} | Horario: {srv.get('hora_inicio')} a {srv.get('hora_fin')}")
        pdf.drawString(45, 640, f"Producto: {srv.get('quimico_utilizado')} | Dosis: {srv.get('dosis_aplicada')}")
        pdf.drawString(45, 620, f"Tiempo Reentrada Seguro: {srv.get('tiempo_reentrada')}")

        # Firma Cliente
        firma_data = srv.get('firma_cliente')
        if firma_data and ',' in firma_data:
            try:
                fb = base64.b64decode(firma_data.split(',')[1])
                pdf.drawImage(ImageReader(io.BytesIO(fb)), 350, 480, width=150, height=60, mask='auto')
            except Exception:
                pass

        pdf.line(50, 480, 220, 480)
        pdf.line(340, 480, 510, 480)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(80, 465, "Tecnico Aplicador Certificado")
        pdf.drawString(380, 465, "Firma de Conformidad del Cliente")

        # PÁGINA 2: EVIDENCIA EN CAMPO
        if fotos:
            pdf.showPage()
            pdf.setFillColor(colors.HexColor("#107c41"))
            pdf.rect(0, 740, 612, 52, fill=True, stroke=False)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(40, 760, "FUMILABCONTROL | EVIDENCIA FOTOGRAFICA EN SITIO")
            pdf.drawRightString(572, 760, f"Folio: #{srv.get('folio')}")
            pos = [(50, 480), (320, 480), (50, 240), (320, 240)]
            for idx, f in enumerate(fotos[:4]):
                try:
                    raw = f['ruta_imagen']
                    if ',' in raw:
                        raw = raw.split(',')[1]
                    img = ImageReader(io.BytesIO(base64.b64decode(raw)))
                    x, y = pos[idx]
                    pdf.drawImage(img, x, y, width=240, height=190, preserveAspectRatio=True)
                except Exception:
                    pass

        pdf.save()
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{srv.get('folio')}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error al generar PDF: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
