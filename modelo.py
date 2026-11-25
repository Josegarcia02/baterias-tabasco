# modelo.py - Solo se encarga de la base de datos
import calendar
import sqlite3
from datetime import date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

def crear_usuario(nombre, password, rol):
    conn = sqlite3.connect('baterias_tabasco.db')
    conn.execute('INSERT OR IGNORE INTO usuarios (nombre, password_hash, rol) VALUES (?,?,?)',
                 (nombre, generate_password_hash(password), rol))
    conn.commit()
    conn.close()

def obtener_usuario_por_nombre(nombre):
    conn = sqlite3.connect('baterias_tabasco.db')
    v = conn.execute('SELECT id, nombre, password_hash, rol FROM usuarios WHERE nombre = ?', (nombre,)).fetchone()
    conn.close()
    if v is None:
        return None
    return {'id': v[0], 'nombre': v[1], 'password_hash': v[2], 'rol': v[3]}

def verificar_password(usuario, password):
    return usuario is not None and check_password_hash(usuario['password_hash'], password)

def sumar_meses(fecha_obj, meses):
    mes = fecha_obj.month - 1 + meses
    año = fecha_obj.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha_obj.day, calendar.monthrange(año, mes)[1])
    return date(año, mes, dia)

def init_db():
    conn = sqlite3.connect('baterias_tabasco.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS ventas
                 (id INTEGER PRIMARY KEY, cliente TEXT, telefono TEXT,
                  bateria TEXT, precio REAL, fecha TEXT, garantia_meses INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, password_hash TEXT, rol TEXT)''')
    # Migración: ventas viejas no tienen cantidad; se agrega con valor 1
    try:
        conn.execute('ALTER TABLE ventas ADD COLUMN cantidad INTEGER DEFAULT 1')
    except Exception:
        pass
    conn.execute('''CREATE TABLE IF NOT EXISTS venta_items
                 (id INTEGER PRIMARY KEY, venta_id INTEGER, bateria TEXT, precio REAL)''')
    # Migración: cada venta vieja (una batería) pasa a ser un renglón en venta_items
    try:
        viejas = conn.execute('SELECT id, bateria, precio FROM ventas').fetchall()
        for vid, bat, pre in viejas:
            existe = conn.execute('SELECT COUNT(*) FROM venta_items WHERE venta_id = ?', (vid,)).fetchone()[0]
            if not existe:
                conn.execute('INSERT INTO venta_items (venta_id, bateria, precio) VALUES (?,?,?)', (vid, bat, pre))
    except Exception:
        pass
    conn.commit()
    conn.close()
    # Usuarios iniciales: CAMBIA estas contraseñas en tu PC
    crear_usuario('admin', 'admin123', 'admin')
    crear_usuario('vendedor', 'vendedor123', 'vendedor')

def guardar_venta(cliente, telefono, items, garantia):
    # items: lista de (bateria, precio). Todo se guarda en MAYÚSCULAS.
    cliente = (cliente or '').strip().upper()
    telefono = (telefono or '').strip()
    items = [(str(b).strip().upper(), float(p)) for b, p in items if b and p not in (None, '')]
    if not items:
        return None
    total = sum(p for _, p in items)
    conn = sqlite3.connect('baterias_tabasco.db')
    cur = conn.execute('INSERT INTO ventas (cliente, telefono, bateria, precio, fecha, garantia_meses, cantidad) VALUES (?,?,?,?,?,?,?)',
                 (cliente, telefono, items[0][0], total, str(date.today()), garantia, len(items)))
    venta_id = cur.lastrowid
    for bat, pre in items:
        conn.execute('INSERT INTO venta_items (venta_id, bateria, precio) VALUES (?,?,?)', (venta_id, bat, pre))
    conn.commit()
    conn.close()
    return venta_id

def _items_de_venta(conn, venta_id):
    rows = conn.execute('SELECT bateria, precio FROM venta_items WHERE venta_id = ? ORDER BY id', (venta_id,)).fetchall()
    return [{'bateria': r[0], 'precio': r[1]} for r in rows]

def _venta_a_dict(v, items):
    hoy = date.today()
    vence = sumar_meses(date.fromisoformat(v[5]), v[6])
    estado = 'VIGENTE' if vence >= hoy else 'VENCIDA'
    total = sum(i['precio'] for i in items) if items else float(v[4])
    return {'id': v[0], 'cliente': v[1], 'telefono': v[2], 'bateria': items[0]['bateria'] if items else v[3],
            'precio': total, 'fecha': v[5], 'garantia': v[6], 'garantia_meses': v[6],
            'vence': str(vence), 'estado': estado, 'cantidad': len(items) if items else 1,
            'total': total, 'items': items}

def obtener_ventas():
    conn = sqlite3.connect('baterias_tabasco.db')
    ventas = conn.execute('SELECT * FROM ventas ORDER BY id DESC').fetchall()
    lista = [_venta_a_dict(v, _items_de_venta(conn, v[0])) for v in ventas]
    conn.close()
    return lista

def buscar_ventas_por_telefono(telefono):
    conn = sqlite3.connect('baterias_tabasco.db')
    ventas = conn.execute('SELECT * FROM ventas WHERE telefono LIKE ? ORDER BY  id DESC', (f"%{telefono}%",)).fetchall()
    lista = [_venta_a_dict(v, _items_de_venta(conn, v[0])) for v in ventas]
    conn.close()
    return lista

def eliminar_venta(id):
    conn = sqlite3.connect('baterias_tabasco.db')
    conn.execute('DELETE FROM venta_items WHERE venta_id = ?', (id,))
    conn.execute('DELETE FROM ventas WHERE id = ?', (id,))
    conn.commit()
    conn.close()

def obtener_venta_por_id(id):
    conn = sqlite3.connect('baterias_tabasco.db')
    v = conn.execute('SELECT * FROM ventas WHERE id = ?', (id,)).fetchone()
    if v is None:
        conn.close()
        return None
    d = _venta_a_dict(v, _items_de_venta(conn, v[0]))
    conn.close()
    return d

def actualizar_venta(id, cliente, telefono, items, garantia):
    # items: lista de (bateria, precio). Todo en MAYÚSCULAS.
    cliente = (cliente or '').strip().upper()
    telefono = (telefono or '').strip()
    items = [(str(b).strip().upper(), float(p)) for b, p in items if b and p not in (None, '')]
    if not items:
        return
    total = sum(p for _, p in items)
    conn = sqlite3.connect('baterias_tabasco.db')
    conn.execute('UPDATE ventas SET cliente=?, telefono=?, bateria=?, precio=?, garantia_meses=?, cantidad=? WHERE id=?',
                 (cliente, telefono, items[0][0], total, garantia, len(items), id))
    conn.execute('DELETE FROM venta_items WHERE venta_id = ?', (id,))
    for bat, pre in items:
        conn.execute('INSERT INTO venta_items (venta_id, bateria, precio) VALUES (?,?,?)', (id, bat, pre))
    conn.commit()
    conn.close()
