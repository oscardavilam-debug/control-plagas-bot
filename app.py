import os
import io
import json
import base64
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session
from database import get_db_connection, init_db

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "fumilab_control_pro_secret_key_2026"

init_db()

PHONE_NUMBER_ID = "1281507521716481"
WHATSAPP_TOKEN = "EAAj3VdqPd8MBSTjsNLBoKZAuqtKImsqTnivGVhcE3UTl2r5YTT52Fnbm4O6TczQVRbWU4hkqUQbvao3bIDMFWkna0wo7QyA2s5ZAqKi9wX26xTnFZCZCNMeyx"
WHATSAPP_VERIFY_TOKEN = "mi_token_secreto_dental_2026"
ADMIN_PHONE = "525586406475"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================= RUTAS PÚBLICAS Y DE CAMPO =================
@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/tecnico')
def tecnico_home():
    return render_template('tecnico_home.html')

@app.route('/reporte_campo')
def reporte_campo():
    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes ORDER BY nombre_comercial ASC').fetchall()
    quimicos = conn.execute('SELECT * FROM quimicos ORDER BY producto ASC').fetchall()
    conn.close()
    return render_template('reporte_campo.html', clientes=clientes, quimicos=quimicos)

@app.route('/escaner_qr')
def escaner_qr():
    return render_template('escaner_qr.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'admin' and password in ['admin123', 'fumilab2026']:
            session['logged_in'] = True
            session['user'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Credenciales no autorizadas.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= API DE GUARDADO =================
@app.route('/api/guardar_reporte_servicio', methods=['POST'])
def guardar_reporte():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Sin datos'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        conteo = cur.execute('SELECT COUNT(*) FROM servicios').fetchone()[0]
        folio = f"{3501 + conteo}"
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        cur.execute('''
            INSERT INTO servicios (
                folio, cliente_id, tecnico_id, tipo_servicio, fecha_servicio,
                hora_inicio, hora_fin, areas_cubiertas, actividades_realizadas,
                plagas_controladas, recomendaciones, tiempo_reentrada, costo,
                metodo_pago, quimico_utilizado, dosis_aplicada, firma_cliente, estatus
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Terminado')
        ''', (
            folio,
            data.get('cliente_id', 1),
            data.get('tecnico_id', 1),
            data.get('tipo_visita', 'MANEJO INTEGRAL DE PLAGAS'),
            fecha_hoy,
            data.get('hora_inicio', ''),
            data.get('hora_fin', ''),
            data.get('areas_cubiertas', 'Instalaciones Generales'),
            data.get('actividades', 'Aspersion y cebo en gel'),
            data.get('plagas', 'Cucaracha / Rastreros'),
            data.get('recomendaciones', 'No limpiar antes de 24h'),
            data.get('reentrada', '2 Horas'),
            data.get('costo', 1400.00),
            data.get('metodo_pago', 'Efectivo'),
            data.get('producto', 'DEMAND DUO'),
            data.get('dosis', '4 ml / litro de agua'),
            data.get('firma', '')
        ))

        servicio_id = cur.lastrowid
        for f in data.get('fotos', []):
            cur.execute('INSERT INTO servicio_fotos (servicio_id, ruta_imagen) VALUES (?, ?)', (servicio_id, f))

        conn.commit()
        conn.close()
        return jsonify({'status': 'ok', 'servicio_id': servicio_id, 'folio': folio})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/descargar_reporte_pdf/<int:servicio_id>')
def descargar_reporte_pdf(servicio_id):
    conn = get_db_connection()
    srv = conn.execute('SELECT * FROM servicios WHERE id = ?', (servicio_id,)).fetchone()
    if not srv:
        conn.close()
        return "Servicio no encontrado", 404

    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (srv['cliente_id'],)).fetchone()
    fotos = conn.execute('SELECT ruta_imagen FROM servicio_fotos WHERE servicio_id = ?', (servicio_id,)).fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"Reporte_Fumilab_{srv['folio']}")

    pdf.setFillColor(colors.HexColor("#107c41"))
    pdf.rect(0, 720, 612, 72, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, 760, "FUMILABCONTROL")
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(40, 742, "Reporte de Servicio & Certificado de Fumigacion")
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(572, 760, f"Folio: {srv['folio']}")
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(572, 744, "EMERGENCIAS: 55 1480 6293")
    pdf.drawRightString(572, 732, "Licencia Sanitaria: 2009-15A013 (COFEPRIS)")

    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.roundRect(35, 620, 542, 90, 6, fill=True, stroke=colors.HexColor("#cbd5e1"))
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(45, 694, "Cliente:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(100, 694, cliente['nombre_comercial'] if cliente else "Cliente General")
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(290, 694, "Contacto:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(340, 694, cliente['contacto'] if cliente else "General")
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(450, 694, "Telefono:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(500, 694, cliente['telefono'] if cliente else "N/A")

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(45, 678, "Direccion:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(100, 678, (cliente['direccion'] if cliente else "Local")[:60])

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(45, 662, "Fecha Servicio:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(115, 662, str(srv['fecha_servicio']))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(200, 662, "Hora Inicio:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(255, 662, str(srv['hora_inicio']))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(330, 662, "Hora Termino:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(395, 662, str(srv['hora_fin']))

    y_tbl = 585
    pdf.setFillColor(colors.HexColor("#e2e8f0"))
    pdf.rect(35, y_tbl, 542, 18, fill=True, stroke=False)
    pdf.setFillColor(colors.HexColor("#1e293b"))
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(40, y_tbl + 5, "PRODUCTO")
    pdf.drawString(185, y_tbl + 5, "INGREDIENTE ACTIVO")
    pdf.drawString(350, y_tbl + 5, "DOSIS")
    pdf.drawString(470, y_tbl + 5, "APLICACION")

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawString(40, y_tbl - 16, str(srv['quimico_utilizado']))
    pdf.drawString(185, y_tbl - 16, "LAMBDA CYHALOTRINA / FIPRONIL")
    pdf.drawString(350, y_tbl - 16, str(srv['dosis_aplicada']))
    pdf.drawString(470, y_tbl - 16, "Aspersion / Gel")

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(35, y_tbl - 55, "ACTIVIDADES REALIZADAS:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(35, y_tbl - 68, str(srv['actividades_realizadas']))

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(35, y_tbl - 85, "RECOMENDACIONES:")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(35, y_tbl - 98, str(srv['recomendaciones']))

    if srv['firma_cliente'] and ',' in srv['firma_cliente']:
        try:
            f_bytes = base64.b64decode(srv['firma_cliente'].split(',')[1])
            pdf.drawImage(ImageReader(io.BytesIO(f_bytes)), 360, 260, width=150, height=60, mask='auto')
        except Exception:
            pass

    pdf.setStrokeColor(colors.HexColor("#64748b"))
    pdf.setLineWidth(1)
    pdf.line(60, 260, 240, 260)
    pdf.line(350, 260, 530, 260)

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(150, 248, "Jonathan Davila")
    pdf.setFont("Helvetica", 7.5)
    pdf.drawCentredString(150, 238, "Tecnico Aplicador Certificado")

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(440, 248, "Firma del Cliente")
    pdf.setFont("Helvetica", 7.5)
    pdf.drawCentredString(440, 238, "Recibi de Conformidad")

    pdf.setFillColor(colors.HexColor("#991b1b"))
    pdf.rect(35, 175, 542, 22, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawCentredString(306, 183, "LAUREL LOTE 43 CASA 6 COL. LOS REYES IZTACALA TLALNEPANTLA - TEL: 56114806293")

    if fotos:
        pdf.showPage()
        pdf.setFillColor(colors.HexColor("#107c41"))
        pdf.rect(0, 740, 612, 52, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, 760, "FUMILABCONTROL | EVIDENCIA FOTOGRAFICA EN SITIO")
        pdf.drawRightString(572, 760, f"Folio: {srv['folio']}")

        posiciones = [(45, 480), (315, 480), (45, 260), (315, 260), (45, 40), (315, 40)]
        for i, foto in enumerate(fotos[:6]):
            try:
                fdata = foto['ruta_imagen'].split(',')[1] if ',' in foto['ruta_imagen'] else foto['ruta_imagen']
                img = ImageReader(io.BytesIO(base64.b64decode(fdata)))
                x, y = posiciones[i]
                pdf.drawImage(img, x, y, width=250, height=195, preserveAspectRatio=True)
            except Exception:
                pass

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Reporte_Fumilab_{srv['folio']}.pdf", mimetype='application/pdf')

@app.route('/admin')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    leads = conn.execute('SELECT * FROM servicios ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin.html', leads=leads)

@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
@login_required
def marcar_atendido(lead_id):
    try:
        conn = get_db_connection()
        conn.execute("UPDATE servicios SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == WHATSAPP_VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Token invalido', 403
    return 'EVENT_RECEIVED', 200

# ================= ARRANQUE DEL SERVIDOR =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
