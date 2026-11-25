# app.py - Controlador, solo conecta Modelo con Vista
from flask import Flask, render_template, request, redirect, send_file, session, url_for
from functools import wraps
import modelo
from modelo import guardar_venta, obtener_ventas, init_db, buscar_ventas_por_telefono, eliminar_venta, obtener_venta_por_id, actualizar_venta
import hashlib
import os
import qrcode
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
import os
app.secret_key = os.environ.get('SECRET_KEY', 'baterias-tabasco-secreto-cambialo-en-tu-pc')
modelo.init_db()

def login_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorada

def solo_admin(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('rol') != 'admin':
            return "Solo el admin puede hacer esto", 403
        return f(*args, **kwargs)
    return decorada

# --- FUNCIONES PARA NOTA SEGURA ---
def generar_codigo_unico(venta):
    # venta es tupla: (id, nombre, telefono, bateria, precio, garantia)
    if isinstance(venta, dict): 
        venta = (venta.get('id'), venta.get('cliente'), venta.get('telefono'), venta.get('bateria'), venta.get('precio'), venta.get('garantia_meses'))
    id_venta, nombre, telefono, bateria, precio, garantia, *_ = venta
    try:
        folio = 6160 + int(id_venta)
    except:
        folio = 6160 + 1
    
    

    # Código único con hash, imposible de adivinar
    texto = f"{id_venta}-{nombre}-{precio}-{folio}-BATERIAS-TABASCO"
    hash_corto = hashlib.sha256(texto.encode()).hexdigest()[:4].upper()
    codigo = f"BT-{folio}-{hash_corto}"
    return folio, codigo

def generar_pdf_nota(venta):
    fecha = venta.get('fecha', '') if isinstance(venta, dict) else ''
    vence = venta.get('vence', '') if isinstance(venta, dict) else ''
    estado = venta.get('estado', '') if isinstance(venta, dict) else ''
    cantidad = venta.get('cantidad', 1) if isinstance(venta, dict) else 1
    cantidad = cantidad or 1
    items_pdf = venta.get('items') if isinstance(venta, dict) else None
    if isinstance(venta, dict):
        venta = (venta.get('id'), venta.get('cliente'), venta.get('telefono'), venta.get('bateria'), venta.get('precio'), venta.get('garantia_meses')or 0)
    id_venta, nombre, telefono, bateria, precio, garantia, *_ = venta
    folio, codigo = generar_codigo_unico(venta)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    ancho, alto = letter

    # --- LOGO ---
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(logo_path):
        c.drawImage(ImageReader(logo_path), 40, alto-100, width=60, height=60, mask='auto')

    # --- ENCABEZADO ---
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(ancho/2, alto-60, "BATERIAS TABASCO")
    c.setFont("Helvetica", 10)
    c.drawCentredString(ancho/2, alto-78, "RFC: GAHC791002MJ2  |  VILLAHERMOSA, TABASCO")
    c.drawCentredString(ancho/2, alto-92, "Tel: 9932-331080    |  Andador Verdon 409")
    c.line(40, alto-105, ancho-40, alto-105)

    # --- FOLIO Y FECHA ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, alto-145, f"FOLIO: {folio}")
    c.drawString(40, alto-165, f"CODIGO UNICO: {codigo}")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, alto-120, f"FECHA: {fecha}")
    c.setFont("Helvetica", 10)
    c.drawString(ancho-180, alto-130, "NOTA DE VENTA")

    # --- CLIENTE ---
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, alto-185, "CLIENTE:")
    c.setFont("Helvetica", 12)
    c.drawString(110, alto-185, nombre)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, alto-205, "TELEFONO:")
    c.setFont("Helvetica", 12)
    c.drawString(130, alto-205, str(telefono))

    # --- TABLA ---
    y = alto-250
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "CANT.")
    c.drawString(90, y, "DESCRIPCION")
    c.drawString(ancho-120, y, "PRECIO")
    c.line(40, y-5, ancho-40, y-5)
    c.setFont("Helvetica", 11)
    items = items_pdf
    if not items:
        items = [{'bateria': bateria, 'precio': precio}]
    total = sum(float(i['precio']) for i in items)
    fila_y = y - 25
    for i in items:
        c.drawString(40, fila_y, "1")
        c.drawString(90, fila_y, str(i['bateria']))
        c.drawString(ancho-120, fila_y, f"${float(i['precio']):,.2f}")
        fila_y -= 25

    # --- TOTAL ---
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(ancho-40, fila_y - 10, f"TOTAL: ${total:,.2f}")
    c.setFont("Helvetica", 10)
    c.setFont("Helvetica", 10)
    c.drawCentredString(ancho/2, 175, f"GARANTIA: {garantia} MESES EN PARTICULAR")
    c.drawCentredString(ancho/2, 155, f"VENCE: {vence}")
    if estado == 'VIGENTE':
        c.setFillColorRGB(0, 0.5, 0)
    else:
        c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho/2, 135, f"ESTADO DE GARANTIA: {estado}")
    c.setFillColorRGB(0, 0, 0)

    # --- SELLO PAGADO ---
    c.setStrokeColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(ancho/2, y-120, "PAGADO")
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)

    # --- QR DE VERIFICACION ---
    qr_texto = f"VERIFICAR NOTA BATERIAS TABASCO\nFolio: {folio}\nCodigo: {codigo}\nCliente: {nombre}\nBaterias: {", ".join(str(i["bateria"]) for i in items)}\nTotal: ${total}\nSi este codigo no coincide, la nota fue alterada."
    qr_img = qrcode.make(qr_texto)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    c.drawImage(ImageReader(qr_buffer), 40, 80, width=110, height=110)
    c.setFont("Helvetica", 8)
    c.drawString(40, 65, "ESCANEA PARA VERIFICAR")
    c.drawString(40, 55, f"Codigo: {codigo}")

    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho/2, 40, "GRACIAS POR SU COMPRA - BATERIAS TABASCO - GARANTIA VALIDA SOLO CON ESTA NOTA")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer, folio

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = modelo.obtener_usuario_por_nombre(request.form['nombre'])
        if modelo.verificar_password(usuario, request.form['password']):
            session['usuario'] = usuario['nombre']
            session['rol'] = usuario['rol']
            return redirect(url_for('index'))
        return render_template('login.html', error='Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def items_del_formulario(form):
    cantidad = int(form.get('cantidad', 1))
    items = []
    for k in range(1, cantidad + 1):
        bateria = form.get(f'bateria_{k}') or form.get('bateria')
        precio = form.get(f'precio_{k}') or form.get('precio')
        if bateria and precio not in (None, ''):
            items.append((bateria, precio))
    return items

# PESTAÑA 1: Solo el formulario
@app.route('/')
@login_requerido
def index():
    return render_template('index.html', active='registrar')

# Guardar venta
@app.route('/vender', methods=['POST'])
@login_requerido
def vender():
    modelo.guardar_venta(
        request.form['nombre'],
        request.form['telefono'],
        items_del_formulario(request.form),
        request.form['garantia']
    )
    return redirect('/ventas')

# PESTAÑA 2: Solo la lista
@app.route('/ventas')
@login_requerido
def ventas():
    buscar_telefono = request.args.get('buscar_telefono', '')
    if buscar_telefono:
        ventas = modelo.buscar_ventas_por_telefono(buscar_telefono)
    else:
        ventas = modelo.obtener_ventas()
    return render_template('ventas.html', ventas=ventas, buscar_telefono=buscar_telefono, active='ventas')

@app.route('/eliminar/<int:id>')
@solo_admin
def eliminar(id):
    modelo.eliminar_venta(id)
    return redirect('/ventas')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar(id):
    if request.method == 'POST':
        modelo.actualizar_venta(id, request.form['nombre'], request.form['telefono'], items_del_formulario(request.form), request.form['garantia'])
        return redirect('/ventas')
    venta = modelo.obtener_venta_por_id(id)
    if not venta:
        return "Venta no encontrada", 404
    return render_template('editar.html', venta=venta, active='venta')

# NUEVO: IMPRIMIR NOTA CON QR
@app.route('/nota/<int:id>')
@login_requerido
def nota(id):
    venta = modelo.obtener_venta_por_id(id)
    if not venta:
        return "Venta no encontrada", 404
    pdf_buffer, folio = generar_pdf_nota(venta)
    return send_file(pdf_buffer, as_attachment=False, download_name=f"Nota_{folio}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)