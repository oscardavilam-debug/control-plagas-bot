import sqlite3

def get_db_connection():
    conn = sqlite3.connect('plagas.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla de servicios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            proxima_cita TEXT,
            cliente TEXT NOT NULL,
            direccion TEXT NOT NULL,
            tipo_plaga TEXT NOT NULL,
            producto_quimico TEXT NOT NULL,
            dosis TEXT NOT NULL,
            tecnico TEXT NOT NULL,
            observaciones TEXT
        )
    ''')

    # Tabla de inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            ingrediente_activo TEXT NOT NULL,
            stock REAL NOT NULL,
            unidad TEXT NOT NULL,
            registro_sanitario TEXT
        )
    ''')

    # Tabla de prospectos (Landing Page y WhatsApp Chatbot)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro TEXT NOT NULL,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            tipo_inmueble TEXT,
            plaga_problema TEXT,
            mensaje TEXT,
            origen TEXT NOT NULL,
            estatus TEXT DEFAULT 'Pendiente'
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Tablas actualizadas con éxito.")