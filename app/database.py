import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_NAME = BASE_DIR / "agenda.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            texto_original TEXT,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            detalle TEXT NOT NULL,
            monto REAL,
            cantidad REAL,
            unidad TEXT,
            respuesta TEXT,
            productividad TEXT,
            duracion_minutos INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contexto_diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo_dia TEXT,
            eventos TEXT,
            es_exigente INTEGER DEFAULT 0,
            fuente TEXT DEFAULT 'manual'
        )
    """)

    cursor.execute("PRAGMA table_info(registros)")
    columnas = [col[1] for col in cursor.fetchall()]

    if "respuesta" not in columnas:
        cursor.execute("ALTER TABLE registros ADD COLUMN respuesta TEXT")

    if "productividad" not in columnas:
        cursor.execute("ALTER TABLE registros ADD COLUMN productividad TEXT")

    if "duracion_minutos" not in columnas:
        cursor.execute("ALTER TABLE registros ADD COLUMN duracion_minutos INTEGER")

    conn.commit()
    conn.close()