import streamlit as st
import sqlite3
import pandas as pd
import datetime

st.set_page_config(page_title="SIGA - AgroRepuestos del Valle", layout="wide")


@st.cache_resource
def obtener_conexion():
    conn = sqlite3.connect("mi_sistema.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
    tabla_existe = cur.fetchone()

    if not tabla_existe:
        cur.executescript("""
        CREATE TABLE proveedores (
            id_proveedor    INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            telefono        TEXT
        );
        CREATE TABLE clientes (
            id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            telefono        TEXT
        );
        CREATE TABLE productos (
            id_producto     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            categoria       TEXT NOT NULL,
            precio_unitario REAL NOT NULL,
            stock_minimo    INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE movimientos (
            id_movimiento   INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto     INTEGER NOT NULL,
            tipo            TEXT NOT NULL CHECK (tipo IN ('entrada', 'salida')),
            cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
            fecha           TEXT NOT NULL,
            id_proveedor    INTEGER,
            id_cliente      INTEGER,
            FOREIGN KEY (id_producto)  REFERENCES productos(id_producto),
            FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor),
            FOREIGN KEY (id_cliente)   REFERENCES clientes(id_cliente)
        );
        """)

        cur.executemany(
            "INSERT INTO proveedores (nombre, telefono) VALUES (?, ?)",
            [
                ("Todo filtros", "3115243395"),
                ("Baterías Mac", "3205514879"),
                ("Mangueras industriales Ltda", "3158250341"),
                ("Polybandas", "3134080854"),
            ],
        )

        cur.executemany(
            "INSERT INTO clientes (nombre, telefono) VALUES (?, ?)",
            [
                ("Manuelita S.A.", "6022756000"),
                ("Riopaila Castilla S.A.", "6022116000"),
                ("Ingenio Mayagüez S.A.", "6022608000"),
                ("Ingenio Providencia S.A.", "6022858000"),
            ],
        )

        cur.executemany(
            """INSERT INTO productos (nombre, categoria, precio_unitario, stock_minimo)
               VALUES (?, ?, ?, ?)""",
            [
                ("Exterior CASE IH", "Filtros de Aire", 150000, 5),
                ("Filtro Interno Caterpillar", "Filtros de Aire", 95000, 5),
                ("Filtro Primario Donaldson", "Filtros de Aire", 120000, 5),
                ("Caltric AGM John Deere D", "Batería", 267000, 5),
                ("Batería Bosch Alta Capacidad", "Batería", 310000, 5),
                ("Batería Willard Titanio", "Batería", 245000, 5),
                ("Case IH / New Holland", "Manguera Hidráulica", 301000, 5),
                ("Manguera Alta Presión Gates", "Manguera Hidráulica", 180000, 5),
                ("Manguera Flexible Parker", "Manguera Hidráulica", 145000, 5),
                ("Trapezoidal John Deere", "Correa", 84000, 5),
                ("Correa Dentada Gates", "Correa", 62000, 5),
                ("Correa en V Continental", "Correa", 55000, 5),
            ],
        )

        cur.executemany(
            """INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_proveedor)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (1, "entrada", 20, "2026-09-15", 1),
                (4, "entrada", 14, "2026-09-03", 2),
                (7, "entrada", 11, "2026-08-26", 3),
                (10, "entrada", 18, "2026-08-19", 4),
            ],
        )

        cur.executemany(
            """INSERT INTO movimientos (id_producto, tipo, cantidad, fecha, id_cliente)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (1, "salida", 4, "2026-09-20", 1),
                (4, "salida", 5, "2026-09-16", 2),
                (7, "salida", 4, "2026-08-30", 3),
                (10, "salida", 2, "2026-08-22", 4),
            ],
        )

        cur.execute("""
        CREATE VIEW IF NOT EXISTS vw_inventario AS
        SELECT
            p.id_producto,
            p.nombre,
            p.categoria,
            p.precio_unitario,
            p.stock_minimo,
            COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad
                              WHEN m.tipo = 'salida' THEN -m.cantidad
                              ELSE 0 END), 0) AS stock_actual
        FROM productos p
        LEFT JOIN movimientos m ON p.id_producto = m.id_producto
        GROUP BY p.id_producto, p.nombre, p.categoria, p.precio_unitario, p.stock_minimo
        """)

        conn.commit()

    return conn


conexion = obtener_conexion()
cursor = conexion.cursor()


def existe_producto(id_producto):
    cursor.execute("SELECT 1 FROM productos WHERE id_producto = ?", (id_producto,))
    return cursor.fetchone() is not None


def registrar_entrada(id_producto, cantidad, fecha=None):
    if fecha is None:
        fecha = datetime.date.today().strftime("%Y-%m-%d")

    if cantidad <= 0:
        return False, "Error: La cantidad debe ser mayor a cero."

    try:
        cursor.execute("SELECT nombre FROM productos WHERE id_producto = ?", (id_producto,))
        producto = cursor.fetchone()
        if not producto:
            return False, f"Error: El producto con ID {id_producto} no existe."

        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (?, 'entrada', ?, ?)",
            (id_producto, cantidad, fecha)
        )

        conexion.commit()
        return True, f"Éxito: Se registraron {cantidad} unidades de '{producto[0]}' como entrada."

    except Exception as e:
        conexion.rollback()
        return False, f"Error al guardar: {str(e)}"


def registrar_salida(id_producto, cantidad, fecha=None):
    if fecha is None:
        fecha = datetime.date.today().strftime("%Y-%m-%d")

    if cantidad <= 0:
        return False, "Error: La cantidad a retirar debe ser mayor a cero."

    try:
        cursor.execute("SELECT nombre, stock_actual FROM vw_inventario WHERE id_producto = ?", (id_producto,))
        resultado = cursor.fetchone()

        if not resultado:
            return False, f"Error: El producto con ID {id_producto} no existe."

        nombre_prod, stock_actual = resultado

        if stock_actual < cantidad:
            return False, f"Error: Stock insuficiente para '{nombre_prod}'. Disponible: {stock_actual}, Solicitado: {cantidad}."

        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (?, 'salida', ?, ?)",
            (id_producto, cantidad, fecha)
        )

        conexion.commit()
        return True, f"Éxito: Se registraron {cantidad} unidades de '{nombre_prod}' como salida."

    except Exception as e:
        conexion.rollback()
        return False, f"Error al guardar: {str(e)}"


def consultar_inventario(categoria=None):
    try:
        if categoria:
            sql = "SELECT * FROM vw_inventario WHERE categoria = ?"
            df = pd.read_sql_query(sql, conexion, params=(categoria,))
        else:
            sql = "SELECT * FROM vw_inventario"
            df = pd.read_sql_query(sql, conexion)
        return df
    except Exception as e:
        st.error(f"Error al consultar el inventario: {e}")
        return pd.DataFrame()


def alertas_stock_bajo(minimo_limite=None):
    try:
        if minimo_limite is not None:
            sql = "SELECT * FROM vw_inventario WHERE stock_actual < ?"
            df = pd.read_sql_query(sql, conexion, params=(minimo_limite,))
        else:
            sql = "SELECT * FROM vw_inventario WHERE stock_actual <= stock_minimo"
            df = pd.read_sql_query(sql, conexion)
        return df
    except Exception as e:
        st.error(f"Error al consultar alertas: {e}")
        return pd.DataFrame()


def consultar_movimientos_proveedor(id_proveedor):
    sql = """
    SELECT m.id_movimiento, p.nombre AS producto, m.tipo, m.cantidad, m.fecha
    FROM movimientos m
    JOIN productos p ON m.id_producto = p.id_producto
    WHERE m.id_proveedor = ?
    """
    return pd.read_sql_query(sql, conexion, params=(id_proveedor,))


def registro_lote_entradas(lista_entradas):
    try:
        for id_prod, cant in lista_entradas:
            if cant <= 0:
                raise ValueError(f"Cantidad inválida ({cant}) para el producto ID {id_prod}")

            cursor.execute("SELECT nombre FROM productos WHERE id_producto = ?", (id_prod,))
            if not cursor.fetchone():
                raise ValueError(f"El producto con ID {id_prod} no existe")

            cursor.execute(
                "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (?, 'entrada', ?, ?)",
                (id_prod, cant, datetime.date.today().strftime("%Y-%m-%d"))
            )

        conexion.commit()
        return True, "Éxito: El lote completo de movimientos fue guardado."
    except Exception as e:
        conexion.rollback()
        return False, f"Transacción cancelada (Rollback ejecutado): {str(e)}"


def main():
    df_inventario = consultar_inventario()
    df_alertas_base = alertas_stock_bajo()

    tab_inicio, tab_movimiento, tab_inventario, tab_alertas = st.tabs([
        "Inicio",
        "Registrar movimiento",
        "Inventario",
        "Alertas"
    ])

    with tab_inicio:
        st.title("SIGA - Sistema de Gestión de Inventario")
        st.subheader("AGROREPUESTOS DEL VALLE")
        st.write(
