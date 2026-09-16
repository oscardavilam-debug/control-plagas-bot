import io
import csv
import json
import urllib.request
import urllib.error
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, send_file, Response, jsonify
from database import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)

# --- CONFIGURACIÓN META WHATSAPP CLOUD API ---
PHONE_NUMBER_ID = "1281507521716481"
WHATSAPP_TOKEN = "EAAj3VdqPd8MBSawNdZBPxv8OtpLBek1IpceFK7tPMlAwhen2COHhiiyDI5AmJ19EQS5FBCR58bpZAI3weYEAin8cQod83fqKpO87zV1ZCqzNVOclx38SiFobnhygLT0iBxW7ylPe3Yy7IoKfQNxN0iuVv7JEZCWXKuEP6yTfaxEHUSvUa6gb3gP4QnKmw3IRlOPrXh97z75aLvrWCaVY9REbZCJSTX7VZAvyU14cDjI0O3QekSHqB39mqaVZBPQmxZB6f3SaRZAZABBLZBLZCZAPyPEKQLgZDZD"
WHATSAPP_VERIFY_TOKEN = "mi_token_secreto_plagas_2026"

def enviar_mensaje_whatsapp(destinatario, texto):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destinatario,
        "type": "text",
        "text": {"body": texto}
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[ERROR DETALLADO WHATSAPP]: {error_body}")
        return None
    except Exception as e:
        print(f"[ERROR ENVÍO WHATSAPP]: {e}")
        return None

# --- RUTA PÚBLICA: LANDING PAGE ---
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/solicitar-cotizacion', methods=['POST'])
def solicitar_cotizacion():
    nombre = request.form.get('nombre', '').strip()
    telefono = request.form.get('telefono', '').strip()
    tipo_inmueble = request.form.get('tipo_inmueble', '')
    plaga = request.form.get('plaga', '')
    mensaje = request.form.get('mensaje', '')
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO prospectos (fecha_registro, nombre, telefono, tipo_inmueble, plaga_problema, mensaje, origen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha_hoy, nombre, telefono, tipo_inmueble, plaga, mensaje, 'Landing Page'))
    conn.commit()
    conn.close()

    return render_template('gracias.html', nombre=nombre)

# --- PANEL ADMINISTRATIVO DE SERVICIOS ---
@app.route('/admin')
def index():
    busqueda = request.args.get('q', '').strip()
    conn = get_db_connection()

    if busqueda:
        query = '''
            SELECT * FROM servicios 
            WHERE cliente LIKE ? OR tipo_plaga LIKE ? OR tecnico LIKE ?
            ORDER BY id DESC
        '''
        servicios_raw = conn.execute(query, (f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%')).fetchall()
    else:
        servicios_raw = conn.execute('SELECT * FROM servicios ORDER BY id DESC').fetchall()

    hoy = date.today()
    servicios = []
    vencidas_count = 0
    proximas_count = 0

    for s in servicios_raw:
        item = dict(s)
        estado_cita = "normal"
        if item.get('proxima_cita'):
            try:
                fecha_cita = datetime.strptime(item['proxima_cita'], '%Y-%m-%d').date()
                dias_restantes = (fecha_cita - hoy).days
                if dias_restantes < 0:
                    estado_cita = "vencida"
                    vencidas_count += 1
                elif dias_restantes <= 7:
                    estado_cita = "proxima"
                    proximas_count += 1
                else:
                    estado_cita = "vigente"
            except ValueError:
                estado_cita = "normal"
        item['estado_cita'] = estado_cita
        servicios.append(item)

    total_servicios = conn.execute('SELECT COUNT(*) FROM servicios').fetchone()[0]
    total_clientes = conn.execute('SELECT COUNT(DISTINCT cliente) FROM servicios').fetchone()[0]
    total_prospectos = conn.execute('SELECT COUNT(*) FROM prospectos WHERE estatus = "Pendiente"').fetchone()[0]
    conn.close()

    metricas = {
        'total': total_servicios,
        'clientes': total_clientes,
        'vencidas': vencidas_count,
        'proximas': proximas_count,
        'prospectos_pendientes': total_prospectos
    }

    return render_template('index.html', servicios=servicios, busqueda=busqueda, metricas=metricas)

@app.route('/prospectos')
def ver_prospectos():
    conn = get_db_connection()
    prospectos = conn.execute('SELECT * FROM prospectos ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('prospectos.html', prospectos=prospectos)

@app.route('/prospectos/atender/<int:prospecto_id>', methods=['POST'])
def atender_prospecto(prospecto_id):
    conn = get_db_connection()
    conn.execute("UPDATE prospectos SET estatus = 'Atendido' WHERE id = ?", (prospecto_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('ver_prospectos'))

# --- MÓDULO SERVICIOS (CRUD) ---
@app.route('/nuevo', methods=('GET', 'POST'))
def nuevo_servicio():
    conn = get_db_connection()
    if request.method == 'POST':
        fecha = request.form['fecha']
        proxima_cita = request.form.get('proxima_cita', '')
        cliente = request.form['cliente']
        direccion = request.form['direccion']
        tipo_plaga = request.form['tipo_plaga']
        producto_quimico = request.form['producto_quimico']
        dosis = request.form['dosis']
        tecnico = request.form['tecnico']
        observaciones = request.form.get('observaciones', '')

        conn.execute('''
            INSERT INTO servicios 
            (fecha, proxima_cita, cliente, direccion, tipo_plaga, producto_quimico, dosis, tecnico, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fecha, proxima_cita, cliente, direccion, tipo_plaga, producto_quimico, dosis, tecnico, observaciones))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('nuevo_servicio.html')

@app.route('/editar/<int:servicio_id>', methods=('GET', 'POST'))
def editar_servicio(servicio_id):
    conn = get_db_connection()
    servicio = conn.execute('SELECT * FROM servicios WHERE id = ?', (servicio_id,)).fetchone()
    if not servicio:
        conn.close()
        return "Servicio no encontrado", 404

    if request.method == 'POST':
        conn.execute('''
            UPDATE servicios 
            SET fecha = ?, proxima_cita = ?, cliente = ?, direccion = ?, 
                tipo_plaga = ?, producto_quimico = ?, dosis = ?, tecnico = ?, observaciones = ?
            WHERE id = ?
        ''', (
            request.form['fecha'], request.form.get('proxima_cita', ''), request.form['cliente'],
            request.form['direccion'], request.form['tipo_plaga'], request.form['producto_quimico'],
            request.form['dosis'], request.form['tecnico'], request.form.get('observaciones', ''), servicio_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('editar_servicio.html', servicio=servicio)

@app.route('/eliminar/<int:servicio_id>', methods=('POST',))
def eliminar_servicio(servicio_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM servicios WHERE id = ?', (servicio_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/cliente/<string:nombre_cliente>')
def historial_cliente(nombre_cliente):
    conn = get_db_connection()
    servicios = conn.execute('SELECT * FROM servicios WHERE cliente = ? ORDER BY fecha DESC', (nombre_cliente,)).fetchall()
    conn.close()
    return render_template('cliente_historial.html', cliente=nombre_cliente, servicios=servicios)

# --- INVENTARIO ---
@app.route('/inventario', methods=('GET', 'POST'))
def inventario():
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('''
            INSERT INTO inventario (producto, ingrediente_activo, stock, unidad, registro_sanitario)
            VALUES (?, ?, ?, ?, ?)
        ''', (request.form['producto'], request.form['ingrediente_activo'], float(request.form['stock']), request.form['unidad'], request.form.get('registro_sanitario', '')))
        conn.commit()
        return redirect(url_for('inventario'))

    productos = conn.execute('SELECT * FROM inventario ORDER BY producto ASC').fetchall()
    conn.close()
    return render_template('inventario.html', productos=productos)

@app.route('/inventario/eliminar/<int:item_id>', methods=('POST',))
def eliminar_inventario(item_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM inventario WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventario'))

# --- EXPORTAR Y PDF ---
@app.route('/exportar-csv')
def exportar_csv():
    conn = get_db_connection()
    servicios = conn.execute('SELECT * FROM servicios ORDER BY id DESC').fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fecha', 'Próxima Cita', 'Cliente', 'Dirección', 'Plaga', 'Producto', 'Dosis', 'Técnico', 'Observaciones'])
    for s in servicios:
        writer.writerow([s['id'], s['fecha'], s['proxima_cita'] or '', s['cliente'], s['direccion'], s['tipo_plaga'], s['producto_quimico'], s['dosis'], s['tecnico'], s['observaciones'] or ''])
    
    output.seek(0)
    return Response(output.getvalue().encode('utf-8-sig'), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=servicios_plagas.csv"})

@app.route('/pdf/<int:servicio_id>')
def generar_pdf(servicio_id):
    conn = get_db_connection()
    servicio = conn.execute('SELECT * FROM servicios WHERE id = ?', (servicio_id,)).fetchone()
    conn.close()
    if not servicio:
        return "Servicio no encontrado", 404

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFillColor(colors.HexColor("#1b4d3e"))
    p.rect(0, height - 75, width, 75, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 17)
    p.drawString(40, height - 42, "CERTIFICADO DE CONTROL Y MANEJO INTEGRAL DE PLAGAS")
    p.setFont("Helvetica", 10)
    p.drawString(40, height - 60, f"Folio Oficial: #{servicio['id']:05d}  |  Emisión: {date.today().strftime('%d/%m/%Y')}")

    y = height - 115
    p.setFillColor(colors.HexColor("#222222"))
    campos = [
        ("Fecha de Aplicación:", servicio['fecha']),
        ("Próxima Cita / Refuerzo:", servicio['proxima_cita'] or "No programada"),
        ("Cliente / Razón Social:", servicio['cliente']),
        ("Dirección / Instalación:", servicio['direccion']),
        ("Plaga Identificada / Tratada:", servicio['tipo_plaga']),
        ("Producto Químico / Registro:", servicio['producto_quimico']),
        ("Dosis y Método Aplicado:", servicio['dosis']),
        ("Técnico Especialista:", servicio['tecnico']),
        ("Observaciones y Recomendaciones:", servicio['observaciones'] or "Ninguna")
    ]

    for label, valor in campos:
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, y, label)
        p.setFont("Helvetica", 10)
        p.drawString(245, y, str(valor))
        p.setStrokeColor(colors.HexColor("#E2E8F0"))
        p.setLineWidth(0.6)
        p.line(50, y - 5, width - 50, y - 5)
        y -= 28

    y -= 20
    p.setFillColor(colors.HexColor("#f8fafc"))
    p.rect(50, y - 35, width - 100, 45, fill=1, stroke=0)
    p.setFillColor(colors.HexColor("#475569"))
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(60, y - 5, "Nota sanitaria: Servicio ejecutado conforme a lineamientos de bioseguridad y manejo seguro de plaguicidas.")
    p.drawString(60, y - 18, "Se sugiere mantener las áreas ventiladas y respetar el tiempo de reingreso indicado.")

    y -= 70
    p.setStrokeColor(colors.HexColor("#334155"))
    p.setLineWidth(1)
    p.line(width / 2 - 110, y, width / 2 + 110, y)
    p.setFillColor(colors.HexColor("#1e293b"))
    p.setFont("Helvetica-Bold", 9)
    p.drawCentredString(width / 2, y - 14, str(servicio['tecnico']))
    p.setFont("Helvetica", 8)
    p.drawCentredString(width / 2, y - 26, "Firma del Responsable Técnico")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"certificado_servicio_{servicio['id']}.pdf", mimetype='application/pdf')

# --- CHATBOT WEBHOOK (WHATSAPP CLOUD API) ---
@app.route('/webhook/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
            return challenge, 200
        return 'Verificación fallida', 403

    if request.method == 'POST':
        data = request.get_json()
        try:
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            
            if 'messages' in value:
                mensaje_obj = value['messages'][0]
                remitente = str(mensaje_obj['from']).strip()
                texto = mensaje_obj.get('text', {}).get('body', '').lower().strip()
                nombre_contacto = value.get('contacts', [{}])[0].get('profile', {}).get('name', 'Usuario WhatsApp')

                # Normalización de número para México (de 521XXXXXXXXXX a 52XXXXXXXXXX)
                if remitente.startswith("521") and len(remitente) == 13:
                    remitente = "52" + remitente[3:]

                conn = get_db_connection()
                conn.execute('''
                    INSERT INTO prospectos (fecha_registro, nombre, telefono, tipo_inmueble, plaga_problema, mensaje, origen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (datetime.now().strftime("%Y-%m-%d %H:%M"), nombre_contacto, remitente, 'Por definir', 'Consulta WhatsApp', texto, 'WhatsApp Chatbot'))
                conn.commit()
                conn.close()

                if any(saludo in texto for saludo in ['hola', 'buen', 'buenas', 'inicio', 'menu']):
                    respuesta = (
                        f"👋 ¡Hola {nombre_contacto}! Bienvenido a *Fumilab Biocontrol* 🌿.\n\n"
                        "¿En qué podemos apoyarte hoy?\n"
                        "1️⃣ Cotizar un servicio de fumigación\n"
                        "2️⃣ Plagas comunes que atendemos\n"
                        "3️⃣ Consultar vigencia de mi certificado\n"
                        "4️⃣ Hablar con un especialista técnico\n\n"
                        "👉 Responde con el número de la opción deseada."
                    )
                elif texto == '1':
                    respuesta = "📋 Excelente. Indícanos por favor si tu inmueble es *Residencial*, *Comercial* o *Industrial*, y qué tipo de plaga has detectado para preparar tu presupuesto."
                elif texto == '2':
                    respuesta = "🐜 Controlamos activamente cucaracha alemana y americana, chinches de cama, roedores, termitas, hormigas y fauna nociva con productos seguros y certificados."
                elif texto == '3':
                    respuesta = "📄 Para validar tu certificado o póliza, por favor compártenos el nombre de tu establecimiento o el folio de tu último servicio."
                elif texto == '4':
                    respuesta = "👨‍🔬 Un técnico especialista tomará tu conversación en breve. También puedes llamarnos o agendar inspección directamente."
                else:
                    respuesta = (
                        "Hemos recibido tu mensaje correctamente ✅. "
                        "Uno de nuestros asesores técnicos te atenderá enseguida, o escribe *HOLA* para volver a ver las opciones."
                    )

                enviar_mensaje_whatsapp(remitente, respuesta)
                print(f"[BOT ENVIADO] Respuesta enviada a {remitente}")

        except Exception as e:
            print(f"[ERROR WEBHOOK]: {e}")

        return jsonify({'status': 'recibido'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)