import sqlite3

def get_db_connection():
    conn = sqlite3.connect('fumilab.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # 1. Catálogo de Clientes y Sucursales
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_comercial TEXT NOT NULL,
            contacto TEXT,
            telefono TEXT,
            correo TEXT,
            direccion TEXT,
            coordenadas TEXT
        )
    ''')

    # 2. Catálogo de Químicos e Insumos (con registro sanitario)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quimicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            laboratorio TEXT,
            ingrediente_activo TEXT,
            dosis_sugerida TEXT,
            registro_cofepris TEXT,
            tipo_aplicacion TEXT
        )
    ''')

    # 3. Técnicos Operativos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tecnicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT,
            activo INTEGER DEFAULT 1
        )
    ''')

    # 4. Servicios / Órdenes de Trabajo en Campo
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE,
            cliente_id INTEGER,
            tecnico_id INTEGER,
            tipo_servicio TEXT,
            fecha_servicio TEXT,
            hora_inicio TEXT,
            hora_fin TEXT,
            areas_cubiertas TEXT,
            actividades_realizadas TEXT,
            plagas_controladas TEXT,
            recomendaciones TEXT,
            tiempo_reentrada TEXT,
            costo REAL DEFAULT 0,
            metodo_pago TEXT,
            quimico_utilizado TEXT,
            dosis_aplicada TEXT,
            firma_cliente TEXT,
            firma_tecnico TEXT,
            estatus TEXT DEFAULT 'Pendiente',
            FOREIGN KEY (cliente_id) REFERENCES clientes (id),
            FOREIGN KEY (tecnico_id) REFERENCES tecnicos (id)
        )
    ''')

    # 5. Evidencias Fotográficas por Servicio
    conn.execute('''
        CREATE TABLE IF NOT EXISTS servicio_fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio_id INTEGER,
            ruta_imagen TEXT,
            FOREIGN KEY (servicio_id) REFERENCES servicios (id)
        )
    ''')

    # 6. Monitoreo QR de Estaciones / Trampas de Cebado
    conn.execute('''
        CREATE TABLE IF NOT EXISTS estaciones_monitoreo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_qr TEXT UNIQUE,
            cliente_id INTEGER,
            area TEXT,
            perimetro TEXT,
            numero_estacion TEXT,
            ultimo_consumo TEXT,
            fecha_revision TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')

    # Precargar datos base si está vacío
    c = conn.execute("SELECT COUNT(*) as total FROM quimicos").fetchone()['total']
    if c == 0:
        conn.execute('''
            INSERT INTO quimicos (producto, laboratorio, ingrediente_activo, dosis_sugerida, registro_cofepris, tipo_aplicacion)
            VALUES 
            ('DEMAND DUO', 'SYNGENTA', 'LAMBDA CYHALOTRINA + TIAMETOXAM', '4 ml por litro de agua', 'RSCO-URB-MEZQ-1101C-329-009-015', 'Aspersión focalizada'),
            ('MAXFORCE FORTE', 'BAYER', 'FIPRONIL 0.05%', '1 gota por m2', 'RSCO-URB-INAC-111-383-009-0.05', 'Puntos de gel cebo'),
            ('VALENT', 'VALENT', 'CLOTIANIDIN Y PIRIPROXIFEN', '6 grs por cada 5 m2', 'RSCO-MEZQ-INAC-0104K-383-009-1.00', 'Puntos de gel')
        ''')

    t = conn.execute("SELECT COUNT(*) as total FROM tecnicos").fetchone()['total']
    if t == 0:
        conn.execute("INSERT INTO tecnicos (nombre, telefono) VALUES ('Jonathan Davila', '5514806293')")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Base de datos fumilab.db inicializada con éxito.")