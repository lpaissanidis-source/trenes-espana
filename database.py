import sqlite3
import datetime

DB_FILE = "precios.db"


def crear_tabla():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS precios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            operador     TEXT,
            ruta         TEXT,
            fecha_ida    TEXT,
            fecha_vuelta TEXT,
            precio_total REAL,
            hora_ida     TEXT,
            hora_vuelta  TEXT,
            timestamp    TEXT
        )
    """)
    conn.commit()
    conn.close()


def guardar_precio(operador, ruta, fecha_ida, fecha_vuelta,
                   precio_total, hora_ida="", hora_vuelta=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO precios
            (operador, ruta, fecha_ida, fecha_vuelta, precio_total, hora_ida, hora_vuelta, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        operador, ruta, fecha_ida, fecha_vuelta,
        precio_total, hora_ida, hora_vuelta,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()


def obtener_minimo_historico(operador, ruta, fecha_ida, fecha_vuelta):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT MIN(precio_total) FROM precios
        WHERE operador=? AND ruta=? AND fecha_ida=? AND fecha_vuelta=?
    """, (operador, ruta, fecha_ida, fecha_vuelta))
    resultado = c.fetchone()
    conn.close()
    if resultado and resultado[0] is not None:
        return resultado[0]
    return None
