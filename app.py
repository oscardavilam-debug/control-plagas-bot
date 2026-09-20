import os
import io
import json
import base64
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, render_template_string, request, redirect, url_for, jsonify, send_file, session

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
        CREATE TABLE IF NOT EXISTS servicio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio_id INTEGER,
            ruta_imagen TEXT
        )
    ''')
    conn.commit()
    conn.close()

try:
    init_db()
except Exception:
    pass

@app.route('/')
def home():
    try:
        return render_template('landing.html')
    except Exception as e:
        return redirect('/dashboard')

@app.route('/panel')
@app.route('/admin')
def admin_redirect():
    return redirect(url_for('dashboard_financiero'))

@app.route('/dashboard')
@app.route('/dashboard_financiero')
def dashboard_financiero():
    try:
        init_db()
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
        init_db()
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
        init_db()
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
        init_db()
        conn = get_db()
        clientes = [dict(c) for c in conn.execute("SELECT * FROM clientes").fetchall()]
        conn.close()
        return render_template('reporte_campo.html', clientes=clientes)
    except Exception as e:
        return f"Error en Reporte: {str(e)}", 500

@app.route('/escaner_qr')
def escaner_qr():
    return render_template('escaner_qr.html')

@app.route('/solicitar_cotizacion', methods=['GET', 'POST'])
def solicitar_cotizacion():
    init_db()
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre', '').strip()
            telefono = request.form.get('telefono', '').strip()
            tipo_inmueble = request.form.get('tipo_inmueble', 'Comercial')
            plaga = request.form.get('plaga', 'Cucarachas')
            notas = request.form.get('notas', '')

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
        except Exception as e:
            return f"Error al procesar cotización: {str(e)}", 500

    try:
        return render_template('solicitar_cotizacion.html')
    except Exception:
        # Fallback embebido directo para que JAMÁS marque error 500
        return '''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8"><title>Solicitud de Cotización | FumilabControl</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        </head>
        <body class="bg-slate-900 text-white min-h-screen py-12 px-4 flex items-center justify-center">
            <div class="max-w-lg w-full bg-slate-800/90 border border-slate-700 rounded-3xl p-8 shadow-2xl">
                <div class="text-center mb-6">
                    <div class="w-12 h-12 bg-emerald-500 text-slate-950 rounded-2xl flex items-center justify-center text-xl font-black mx-auto mb-3">
                        <i class="fa-solid fa-shield-virus"></i>
                    </div>
                    <h1 class="text-2xl font-black">Solicitar Cotización Inmediata</h1>
                    <p class="text-xs text-slate-400 mt-1">Atención certificada COFEPRIS para empresas y hogares</p>
                </div>
                <form action="/solicitar_cotizacion" method="POST" class="space-y-4 text-xs font-bold">
                    <div>
                        <label class="block uppercase text-slate-400 mb-1">Nombre o Empresa</label>
                        <input type="text" name="nombre" required placeholder="Ej. Restaurante Roma" class="w-full p-3.5 bg-slate-900 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-emerald-500">
                    </div>
                    <div>
                        <label class="block uppercase text-slate-400 mb-1">Teléfono / WhatsApp</label>
                        <input type="tel" name="telefono" required placeholder="Ej. 5512345678" class="w-full p-3.5 bg-slate-900 border border-slate-700 rounded-xl text-white outline-none focus:ring-2 focus:ring-emerald-500">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block uppercase text-slate-400 mb-1">Inmueble</label>
                            <select name="tipo_inmueble" class="w-full p-3.5 bg-slate-900 border border-slate-700 rounded-xl text-white outline-none">
                                <option>Comercial / Alimentos</option>
                                <option>Industrial / Bodega</option>
                                <option>Sector Salud</option>
                                <option>Residencial</option>
                            </select>
                        </div>
                        <div>
                            <label class="block uppercase text-slate-400 mb-1">Plaga</label>
                            <select name="plaga" class="w-full p-3.5 bg-slate-900 border border-slate-700 rounded-xl text-white outline-none">
                                <option>Cucarachas</option>
                                <option>Roedores</option>
                                <option>Rastreros / Chinches</option>
                                <option>Sanitización</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" class="w-full py-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black rounded-xl text-sm transition">
                        Enviar Solicitud
                    </button>
                </form>
            </div>
        </body>
        </html>
        '''

@app.route('/cotizacion_exitosa')
def cotizacion_exitosa():
    folio = request.args.get('folio', 'COT-901')
    return f'''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8"><title>Cotización Registrada | Fumilab</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    </head>
    <body class="bg-slate-900 text-white min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full bg-slate-800 border border-slate-700 rounded-3xl p-8 text-center space-y-4">
            <div class="w-14 h-14 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center text-2xl mx-auto">
                <i class="fa-solid fa-check"></i>
            </div>
            <h1 class="text-xl font-black">¡Cotización Registrada!</h1>
            <p class="text-xs text-slate-300">Folio asignado: <strong class="text-emerald-400">{folio}</strong></p>
            <div class="pt-3 space-y-2 text-xs font-bold">
                <a href="/prospectos" class="block w-full py-3 bg-emerald-500 text-slate-950 rounded-xl">Ver en Bandeja de Prospectos</a>
                <a href="/dashboard" class="block w-full py-3 bg-slate-700 text-white rounded-xl">Ir al Dashboard</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/api/marcar-atendido/<int:lead_id>', methods=['POST'])
def marcar_atendido(lead_id):
    try:
        init_db()
        conn = get_db()
        conn.execute("UPDATE prospectos SET estatus = 'Atendido' WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/descargar_reporte_pdf/<int:servicio_id>')
def descargar_reporte_pdf(servicio_id):
    try:
        init_db()
        conn = get_db()
        row = conn.execute("SELECT * FROM servicios WHERE id = ?", (servicio_id,)).fetchone()
        if not row:
            conn.close()
            return "Servicio no encontrado", 404
        srv = dict(row)
        cliente_row = conn.execute("SELECT * FROM clientes WHERE id = ?", (srv.get('cliente_id', 1),)).fetchone()
        cliente = dict(cliente_row) if cliente_row else {'nombre_comercial': 'Establecimiento Comercial', 'contacto': 'Responsable en Turno', 'direccion': 'CDMX y EdoMex'}
        fotos = conn.execute("SELECT ruta_imagen FROM servicio_fotos WHERE servicio_id = ?", (servicio_id,)).fetchall()
        conn.close()

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setTitle(f"Certificado_Fumilab_{srv.get('folio')}")

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

        pdf.setFillColor(colors.HexColor("#f8fafc"))
        pdf.roundRect(35, 610, 542, 85, 6, fill=True, stroke=colors.HexColor("#cbd5e1"))
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
        pdf.drawString(45, 635, "Servicio Ejecutado:")
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColor(colors.HexColor("#047857"))
        pdf.drawString(150, 635, str(srv.get('tipo_servicio')))

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
        return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{srv.get('folio')}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error al generar PDF: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
