import json
import os
import io
import urllib.request
import urllib.error
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from database import get_db_connection
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = Flask(__name__)

# --- CONFIGURACIÓN META WHATSAPP CLOUD API ---
PHONE_NUMBER_ID = "1281507521716481"
WHATSAPP_TOKEN = "EAAj3VdqPd8MBSTGRcsgAo6brXJcJMZCtRcsJYTdn29KZBhh3zzv3ZBZBuSm5KKeFDCTaHLsg9J5sIZC86cOHmKVvlFzxSAaL9iOMHzjiygIHXHhlsKfokxzhnJZB3hRw5PnVtOHdNhhkqYYTs9o687XZCgIxnZCGQVmwGG94Xdb7wpvZAD2NEPuTVwBNV7kVcrc9A8XYmSl56HrBm6Y4tMfDgM9WwBuatFTixJTqB1UrdF0Fo4v1ES46qFtXB0xe8Px0vXeEAkemdOcZCXzYwRE8P1oQZDZD"
WHATSAPP_VERIFY_TOKEN = "mi_token_secreto_plagas_2026"

USER_SESSIONS = {}

def enviar_mensaje_whatsapp(destinatario, texto):
    destinatario_str = str(destinatario)
    
    # Corrección automática para México: quita el '1' inicial si viene como 521...
    if destinatario_str.startswith('521') and len(destinatario_str) == 13:
        destinatario_str = '52' + destinatario_str[3:]

    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destinatario_str,
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
            res_data = json.loads(response.read().decode('utf-8'))
            print(f"[BOT ENVIADO] Mensaje enviado a {destinatario_str}")
            return res_data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"[ERROR DETALLADO WHATSAPP]: {error_body}")
        return None
    except Exception as e:
        print(f"[ERROR ENVÍO WHATSAPP]: {e}")
        return None


# --- RUTAS WEB ---
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/solicitar_cotizacion', methods=['GET', 'POST'])
def solicitar_cotizacion():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '')
        telefono = request.form.get('telefono', '')
        plaga = request.form.get('plaga', 'General')
        inmueble = request.form.get('inmueble', 'Casa')
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO prospectos (telefono, plaga, inmueble, fecha_registro)
                VALUES (?, ?, ?, ?)
            ''', (f"{nombre} - {telefono}", plaga, inmueble, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB ERROR COTIZACION]: {e}")
        return render_template('gracias.html')
    return redirect(url_for('landing'))

@app.route('/panel')
def index():
    conn = get_db_connection()
    servicios = conn.execute('SELECT * FROM servicios ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', servicios=servicios)

@app.route('/prospectos')
def ver_prospectos():
    conn = get_db_connection()
    prospectos = conn.execute('SELECT * FROM prospectos ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('prospectos.html', prospectos=prospectos)

@app.route('/inventario')
def inventario():
    conn = get_db_connection()
    productos = conn.execute('SELECT * FROM productos ORDER BY nombre ASC').fetchall()
    conn.close()
    return render_template('inventario.html', productos=productos)

@app.route('/nuevo_servicio', methods=['GET', 'POST'])
def nuevo_servicio():
    if request.method == 'POST':
        cliente = request.form['cliente']
        telefono = request.form['telefono']
        tipo_plaga = request.form['tipo_plaga']
        fecha = request.form['fecha']
        costo = request.form['costo']
        notas = request.form.get('notas', '')

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO servicios (cliente, telefono, tipo_plaga, fecha, costo, notas)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cliente, telefono, tipo_plaga, fecha, costo, notas))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('nuevo_servicio.html')

@app.route('/editar_servicio/<int:id>', methods=['GET', 'POST'])
def editar_servicio(id):
    conn = get_db_connection()
    if request.method == 'POST':
        cliente = request.form['cliente']
        telefono = request.form['telefono']
        tipo_plaga = request.form['tipo_plaga']
        fecha = request.form['fecha']
        costo = request.form['costo']
        notas = request.form.get('notas', '')

        conn.execute('''
            UPDATE servicios SET cliente=?, telefono=?, tipo_plaga=?, fecha=?, costo=?, notas=?
            WHERE id=?
        ''', (cliente, telefono, tipo_plaga, fecha, costo, notas, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    servicio = conn.execute('SELECT * FROM servicios WHERE id=?', (id,)).fetchone()
    conn.close()
    return render_template('editar_servicio.html', servicio=servicio)

@app.route('/reporte_pdf/<int:id>')
def reporte_pdf(id):
    conn = get_db_connection()
    servicio = conn.execute('SELECT * FROM servicios WHERE id=?', (id,)).fetchone()
    conn.close()

    if not servicio:
        return "Servicio no encontrado", 404

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setTitle(f"Certificado_Servicio_{id}")

    p.setFillColor(colors.HexColor("#1b4332"))
    p.rect(0, 720, 612, 80, fill=True, stroke=False)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, 755, "FUMILAB - CONTROL INTEGRAL DE PLAGAS")
    p.setFont("Helvetica", 11)
    p.drawString(50, 735, "Certificado de Fumigación y Control Sanitario")

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 680, f"Folio del Servicio: #{servicio['id']}")
    p.setFont("Helvetica", 11)
    p.drawString(50, 650, f"Cliente: {servicio['cliente']}")
    p.drawString(50, 630, f"Teléfono: {servicio['telefono']}")
    p.drawString(50, 610, f"Tipo de Plaga Tratada: {servicio['tipo_plaga']}")
    p.drawString(50, 590, f"Fecha de Aplicación: {servicio['fecha']}")
    p.drawString(50, 570, f"Costo: ${servicio['costo']}")
    p.drawString(50, 540, "Observaciones y Recomendaciones:")
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(60, 520, str(servicio['notas']) if servicio['notas'] else "Sin observaciones adicionales.")

    p.setStrokeColor(colors.HexColor("#1b4332"))
    p.setLineWidth(1)
    p.line(50, 480, 550, 480)
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.gray)
    p.drawString(50, 460, "Este documento avala la aplicación de productos autorizados por COFEPRIS.")
    p.drawString(50, 445, "Garantía de servicio sujeta a las condiciones preventivas indicadas por el técnico.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Certificado_Fumilab_{id}.pdf", mimetype='application/pdf')


# --- RUTA DEL WEBHOOK DE WHATSAPP ---
@app.route('/webhook/whatsapp', methods=['GET', 'POST'])
def webhook_whatsapp():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
            print("[WEBHOOK VERIFICADO EXITOSAMENTE]")
            return challenge, 200
        print("[ERROR TOKEN VERIFICACIÓN]")
        return 'Token no válido', 403

    data = request.get_json()
    try:
        entry = data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])

        if messages:
            msg = messages[0]
            remitente = msg.get('from')
            tipo_msg = msg.get('type')

            texto = ""
            if tipo_msg == 'text':
                texto = msg.get('text', {}).get('body', '').strip().lower()
            elif tipo_msg == 'interactive':
                interactivo = msg.get('interactive', {})
                if 'button_reply' in interactivo:
                    texto = interactivo['button_reply']['id'].lower()
                elif 'list_reply' in interactivo:
                    texto = interactivo['list_reply']['id'].lower()

            print(f"[REMITENTE]: {remitente} | [TEXTO]: {texto}")

            estado = USER_SESSIONS.get(remitente, 'INICIO')

            saludos = ['hola', 'buen dia', 'buenas', 'inicio', 'menu', 'empezar', 'ayuda', 'start']
            if any(s in texto for s in saludos) or estado == 'INICIO':
                USER_SESSIONS[remitente] = 'MENU'
                menu_msg = (
                    "👋 ¡Hola! Bienvenido al sistema automatizado de *Fumilab / Biocontrol Pro*.\n\n"
                    "Por favor selecciona una opción respondiendo con el número correspondiente:\n\n"
                    "1️⃣ *Cotizar servicio de fumigación*\n"
                    "2️⃣ *Ver plagas y tratamientos*\n"
                    "3️⃣ *Consultar garantía de servicio*\n"
                    "4️⃣ *Hablar con un técnico especialista*"
                )
                enviar_mensaje_whatsapp(remitente, menu_msg)

            elif estado == 'MENU':
                if texto == '1':
                    USER_SESSIONS[remitente] = 'ESPERANDO_PLAGA'
                    enviar_mensaje_whatsapp(
                        remitente,
                        "📋 *Cotización Inmediata*\n\n¿Qué tipo de problema o plaga necesitas controlar?\n\n"
                        "A) Cucarachas / Chinches\n"
                        "B) Roedores (Ratas / Ratones)\n"
                        "C) Termitas / Polilla\n"
                        "D) Sanitización y desinfección preventiva\n\n"
                        "Responde con la letra de tu opción (A, B, C o D)."
                    )
                elif texto == '2':
                    enviar_mensaje_whatsapp(
                        remitente,
                        "🛡️ *Nuestros Tratamientos:*\n\n"
                        "• *Residencial:* Termonebulización y aplicación de gel sin olor, 100% seguro para niños y mascotas.\n"
                        "• *Comercial / Restaurantes:* Tratamientos con certificado oficial para inspecciones sanitarias.\n"
                        "• *Industrial:* Control perimetral de roedores y monitoreo constante.\n\n"
                        "Escribe *1* si deseas cotizar tu servicio o *menu* para volver."
                    )
                elif texto == '3':
                    enviar_mensaje_whatsapp(
                        remitente,
                        "📄 *Póliza de Garantía:*\nTodos nuestros servicios cuentan con póliza de garantía por escrito de 30 a 90 días con refuerzo sin costo adicional si persiste la plaga.\n\nEscribe *menu* para regresar."
                    )
                elif texto == '4':
                    USER_SESSIONS[remitente] = 'INICIO'
                    enviar_mensaje_whatsapp(
                        remitente,
                        "👨‍🔧 Un asesor técnico se comunicará contigo por este mismo chat en breve.\nSi es una urgencia, déjanos tu dirección y horario de contacto."
                    )
                else:
                    enviar_mensaje_whatsapp(remitente, "Por favor responde con un número del *1 al 4* o escribe *menu* para reiniciar.")

            elif estado == 'ESPERANDO_PLAGA':
                opciones_plaga = {
                    'a': 'Cucarachas / Chinches',
                    'b': 'Roedores',
                    'c': 'Termitas',
                    'd': 'Sanitización'
                }
                plaga_elegida = opciones_plaga.get(texto, 'General')
                USER_SESSIONS[f"{remitente}_plaga"] = plaga_elegida
                USER_SESSIONS[remitente] = 'ESPERANDO_UBICACION'
                enviar_mensaje_whatsapp(
                    remitente,
                    f"Entendido, tratamiento para *{plaga_elegida}*.\n\n"
                    "¿Para qué tipo de inmueble es el servicio?\n"
                    "1. Casa / Departamento\n"
                    "2. Negocio / Restaurante\n"
                    "3. Bodega / Empresa"
                )

            elif estado == 'ESPERANDO_UBICACION':
                plaga = USER_SESSIONS.get(f"{remitente}_plaga", "General")
                try:
                    conn = get_db_connection()
                    conn.execute('''
                        INSERT INTO prospectos (telefono, plaga, inmueble, fecha_registro)
                        VALUES (?, ?, ?, ?)
                    ''', (remitente, plaga, texto, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                except Exception as err_db:
                    print(f"[DB ERROR]: {err_db}")

                USER_SESSIONS[remitente] = 'INICIO'
                enviar_mensaje_whatsapp(
                    remitente,
                    "✅ *¡Cotización registrada con éxito!*\n\n"
                    f"Plaga seleccionada: *{plaga}*\n"
                    "Un técnico revisará los detalles y te mandará el presupuesto estimado en unos minutos.\n\n"
                    "¡Gracias por contactar a Fumilab!"
                )

    except Exception as e:
        print(f"[ERROR WEBHOOK]: {e}")

    return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)