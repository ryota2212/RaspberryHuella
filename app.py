from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify, flash
from flask_mysqldb import MySQL
from PIL import Image
import io
import base64
import os
import sys
sys.path.append('/home/pc/raspberry/lcd/drivers')  # Ruta que contiene la carpeta 'drivers'
from drivers import Lcd
import MySQLdb.cursors
import bcrypt
import adafruit_fingerprint
import time
import serial
import math
import threading
import drivers
import RPi.GPIO as GPIO
from time import sleep
import threading
from datetime import datetime

# ===============================================
# Sección de Inicialización y Configuración General
# ===============================================

# Inicializa la comunicación serial y el sensor de huellas digitales
uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

# Inicializa el segundo sensor para salidas
uart2 = serial.Serial("/dev/ttyUSB1", baudrate=57600, timeout=1)
finger2 = adafruit_fingerprint.Adafruit_Fingerprint(uart2)

app = Flask(__name__)
app.secret_key = "HUELLA"

# Configuración de MySQL para el login (tabla usuarios y demás)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'pc'
app.config['MYSQL_PASSWORD'] = 'pc'
app.config['MYSQL_DB'] = 'sistema'

# Inicialización de MySQL
mysql = MySQL(app)

# ===============================================
# Rutas de la aplicación - Sección de Login
# ===============================================

@app.route('/')
def inicio():
    return render_template('admin/login.html')

@app.route('/admin', methods=['POST'])
def login():
    if request.method == 'POST':
        _usuario = request.form['txtUsuario']
        _password = request.form['txtPassword']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM usuarios WHERE usuario = %s', (_usuario,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and bcrypt.checkpw(_password.encode('utf-8'), user['password'].encode('utf-8')):
            session['login'] = True
            session['usuario'] = user['nombres']
            return redirect('/admin/index')
        else:
            return render_template('admin/login.html', mensaje="Acceso denegado")
    return render_template('admin/login.html')

@app.route("/admin/cerrar")
def sesion():
    session.clear()
    return redirect("/")

@app.route("/css/<archivocss>")
def css_link(archivocss):
    return send_from_directory(os.path.join('templates', 'sitio', 'css'), archivocss)

# ===============================================
# Rutas de la aplicación - Sección de Administración
# ===============================================

@app.route('/admin/index')
def index():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/index.html')

@app.route('/admin/registroshuella')
def registroshuella():
    if 'login' not in session:
        return redirect('/')
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombres, cedula, telefono, cargo FROM registro_huellas")
    usuarios = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/registroshuella.html', usuarios=usuarios)

@app.route('/admin/registrosingresos')
def registrosingresos():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/registrosingresos.html')

@app.route('/admin/salirsalon')
def salirsalon():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/salirsalon.html')


@app.route('/admin/editar/<int:_id>')
def editar_registros(_id):
    if not 'login' in session:
        return redirect('/')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM registro_huellas WHERE id=%s", (_id,))
    usuarios = cursor.fetchall()
    cursor.close()
    return render_template('admin/edit.html', usuarios=usuarios)

@app.route('/editar/registro')
def cambio_exitoso():
    return render_template("admin/edit.html", mensaje="Cambio Exitoso")

@app.route('/admin/registroshuella/borrar', methods=['POST'])
def registroshuella_borrar():
    if not 'login' in session:
        return redirect('/')
    
    _id = request.form['txtID']
    
    cursor = mysql.connection.cursor()
    
    try:
        # Primero eliminar los registros relacionados en registro_ingresos
        cursor.execute("DELETE FROM registro_ingresos WHERE id_persona=%s", (_id,))
        
        # Luego eliminar el registro en registro_huellas
        cursor.execute("DELETE FROM registro_huellas WHERE id=%s", (_id,))
        
        mysql.connection.commit()
        flash("Registro eliminado correctamente", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error al eliminar el registro: {str(e)}", "danger")
        print(f"Error al eliminar: {str(e)}")
    finally:
        cursor.close()
    
    return redirect('/admin/registroshuella')

@app.route('/store',methods=['POST'])
def storage():
    if not 'login' in session:
        return redirect('/')
    
    _id = request.form['txtID']
    _nombre = request.form['txtNombres']
    _cedula = request.form['txtCedula']
    _telefono = request.form['txtTelefono']
    _cargo = request.form['txtCargo']
   
    sql = "UPDATE registro_huellas SET nombres=%s, cedula=%s, telefono=%s, cargo=%s WHERE id=%s"
    datos = (_nombre, _cedula, _telefono, _cargo, _id)
    
    cursor = mysql.connection.cursor()
    cursor.execute(sql, datos)
    mysql.connection.commit()
    cursor.close()
    
    return redirect('admin/registroshuella')

@app.route('/admin/capturar/huella')
def capturar_huella():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/index.html')

# ===============================================
# Rutas de la aplicación - Registro de usuarios
# ===============================================

@app.route('/sitio/registrousuario')
def registro_usuario():
    return render_template('sitio/registrousuario.html')

@app.route('/sitio/registrousuario/guardar', methods=['POST'])
def sitio_registrousuario_guardar():
    _nombre = request.form['txtNombres']
    _apellido = request.form['txtApellidos']
    _usuario = request.form['txtUsuario']
    _contraseña = request.form['txtPassword']
    _cargo = request.form['txtCargo']
    
    hashed_password = bcrypt.hashpw(_contraseña.encode('utf-8'), bcrypt.gensalt())
    
    sql = "INSERT INTO usuarios (nombres, apellidos, usuario, password, cargo) VALUES (%s, %s, %s, %s, %s)"
    datos = (_nombre, _apellido, _usuario, hashed_password, _cargo)
    
    cursor = mysql.connection.cursor()
    cursor.execute(sql, datos)
    mysql.connection.commit()
    cursor.close()
    
    return redirect('/sitio/registrousuario/registro')

@app.route("/sitio/registrousuario/registro")
def registro_exitoso():
    return render_template("sitio/registrousuario.html", mensaje="Registro Exitoso")

# ===============================================
# Rutas de la aplicación - Registro de huellas
# ===============================================

@app.route('/sitio/registrohuellas/guardar', methods=['POST'])
def registrohuella_guardar():
    if 'login' not in session:
        return redirect('/')

    _nombres = request.form['txtNombres']
    _cedula = request.form['txtCedula']
    _telefono = request.form['txtTelefono']
    _cargo = request.form['txtCargo']
    _template_base64 = request.form['templateBase64']
    
    # Verificar que el template es válido
    try:
        template_decodificado = base64.b64decode(_template_base64)
        print(f"DEBUG - Template a guardar: longitud={len(template_decodificado)}")
        print(f"DEBUG - Primeros bytes: {template_decodificado[:10]}")
    except Exception as e:
        flash(f"Error: El template no es válido. {str(e)}", "danger")
        return redirect('/admin/index')

    cursor = mysql.connection.cursor()

    # Verificar si la cédula ya existe
    cursor.execute("SELECT COUNT(*) FROM registro_huellas WHERE cedula = %s", (_cedula,))
    existe = cursor.fetchone()[0]

    if existe > 0:
        cursor.close()
        flash("Error: La cédula ya está registrada.", "danger")
        return redirect('/admin/index')

    # Insertar template
    sql = """INSERT INTO registro_huellas 
            (nombres, cedula, telefono, cargo, template)
            VALUES (%s, %s, %s, %s, %s)"""
    datos = (_nombres, _cedula, _telefono, _cargo, _template_base64)

    try:
        cursor.execute(sql, datos)
        mysql.connection.commit()
        print(f"DEBUG - Template guardado correctamente para {_nombres}")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error en la base de datos: {str(e)}", "danger")
        return redirect('/admin/index')
    finally:
        cursor.close()

    return redirect('/sitio/registrohuellas/exito')

@app.route("/sitio/registrohuellas/exito")
def registrohuella_exitoso():
    return render_template("admin/index.html", mensaje="Registro Exitoso")

# ===============================================
# Funciones auxiliares para hardware
# ===============================================

def mostrar_en_lcd(mensaje):
    """
    Muestra un mensaje en la pantalla LCD.
    Se asume que existe un objeto 'lcd' configurado para ello.
    """
    # Implementación pendiente
    print(f"LCD: {mensaje}")

def abrir_cerradura():
    """
    Función para activar la cerradura electromagnética y permitir el ingreso.
    """
    # Implementación pendiente
    print("Cerradura activada. El salón se ha abierto.")

# ===============================================
# Algoritmo de comparación de huellas
# ===============================================

# Función para comparar templates


# ===============================================
# Clase para gestión de huellas digitales
# ===============================================




# ===============================================
# API para identificación de huellas
# ===============================================



# Nueva función para verificación de huella en index.html


# ===============================================
# API para captura y verificación de huellas
# ===============================================

# Variables globales para el estado de captura y verificación
captura_activa = False
verificacion_activa = False
template_capturado = None
huella_capturada = False
huella_verificada = False

@app.route('/api/iniciar-captura', methods=['POST'])
def api_iniciar_captura():
    global captura_activa, huella_capturada
    
    # Reiniciar estado
    captura_activa = True
    huella_capturada = False
    
    return jsonify({"status": "waiting", "message": "Esperando dedo"})

@app.route('/api/verificar-estado-captura', methods=['GET'])
def api_verificar_estado_captura():
    global captura_activa, huella_capturada
    
    if not captura_activa:
        # Reiniciamos la captura en lugar de devolver error
        captura_activa = True
        huella_capturada = False
        return jsonify({"status": "waiting", "message": "Esperando dedo"})
    
    # Verificar si hay un dedo en el sensor
    try:
        i = finger.get_image()
        
        if i == adafruit_fingerprint.OK:
            # Se detectó un dedo, procesar la imagen
            huella_capturada = True
            return jsonify({"status": "captured", "message": "Dedo detectado"})
        elif i == adafruit_fingerprint.NOFINGER:
            # No hay dedo, seguir esperando
            return jsonify({"status": "waiting", "message": "Esperando dedo"})
        else:
            # Cualquier otro error, seguimos esperando
            return jsonify({"status": "waiting", "message": "Esperando dedo"})
    except Exception as e:
        # Error crítico, pero seguimos esperando
        return jsonify({"status": "waiting", "message": "Esperando dedo"})

@app.route('/api/procesar-huella-capturada', methods=['POST'])
def api_procesar_huella_capturada():
    global captura_activa, template_capturado, huella_capturada
    
    if not huella_capturada:
        return jsonify({"success": False, "message": "No se ha capturado ninguna huella"})
    
    try:
        # Convertir imagen a plantilla
        i = finger.image_2_tz(1)
        if i != adafruit_fingerprint.OK:
            mensaje_error = "No se pudo crear la plantilla"
            if i == adafruit_fingerprint.IMAGEMESS:
                mensaje_error = "Imagen demasiado borrosa"
            elif i == adafruit_fingerprint.FEATUREFAIL:
                mensaje_error = "No se pudieron identificar características"
            elif i == adafruit_fingerprint.INVALIDIMAGE:
                mensaje_error = "Imagen inválida"
            
            captura_activa = False
            huella_capturada = False
            return jsonify({"success": False, "message": mensaje_error})
        
        # MODIFICACIÓN: Intentar guardar el template en el slot 1 del sensor
        try:
            # Guardar en slot 1
            i = finger.store_model(1)
            if i != adafruit_fingerprint.OK:
                print(f"ADVERTENCIA - No se pudo guardar el modelo en el sensor: {i}")
        except Exception as e:
            print(f"ADVERTENCIA - Error al guardar modelo en sensor: {str(e)}")
        
        # Obtener características y guardar en memoria
        caracteristicas = finger.get_fpdata("char", 1)
        if not caracteristicas:
            captura_activa = False
            huella_capturada = False
            return jsonify({"success": False, "message": "No se pudieron obtener las características"})
        
        # Información de depuración
        print(f"DEBUG - Tipo de características: {type(caracteristicas)}")
        print(f"DEBUG - Longitud de características: {len(caracteristicas) if hasattr(caracteristicas, '__len__') else 'N/A'}")
        
        # MODIFICACIÓN: Guardar características en formato raw
        if isinstance(caracteristicas, list):
            # Guardar directamente como bytes
            caracteristicas_bytes = bytes(caracteristicas)
        elif isinstance(caracteristicas, bytes):
            caracteristicas_bytes = caracteristicas
        else:
            # Si no es lista ni bytes, intentar convertir
            try:
                caracteristicas_bytes = bytes(caracteristicas)
            except:
                caracteristicas_bytes = str(caracteristicas).encode('utf-8')
        
        # Codificar en base64 para almacenamiento
        template_capturado = base64.b64encode(caracteristicas_bytes).decode('utf-8')
        
        # Verificar que el template se puede decodificar correctamente
        try:
            template_decodificado = base64.b64decode(template_capturado)
            print(f"DEBUG - Verificación de decodificación: OK, longitud={len(template_decodificado)}")
            print(f"DEBUG - Primeros bytes del template: {template_decodificado[:10]}")
            
            # MODIFICACIÓN: Verificar que podemos enviar el template de vuelta al sensor
            try:
                # Limpiar biblioteca
                finger.empty_library()
                
                # Enviar al slot 2 para prueba
                finger.send_fpdata(list(template_decodificado), "char", 2)
                
                # Intentar comparar con el original
                resultado = finger.create_model()
                if resultado == adafruit_fingerprint.OK:
                    confidence = finger.confidence
                    print(f"DEBUG - Verificación de template: similitud {confidence}%")
                    if confidence < 90:
                        print(f"ADVERTENCIA - Baja similitud en verificación de template: {confidence}%")
                else:
                    print(f"ADVERTENCIA - No se pudo comparar el template: {resultado}")
            except Exception as e:
                print(f"ADVERTENCIA - Error en verificación de template: {str(e)}")
        except Exception as e:
            print(f"ERROR - Fallo en verificación de decodificación: {str(e)}")
        
        captura_activa = False
        
        return jsonify({"success": True, "message": "Huella capturada correctamente"})
    except Exception as e:
        print(f"Error al procesar huella: {str(e)}")
        captura_activa = False
        huella_capturada = False
        return jsonify({"success": False, "message": f"Error al procesar la huella: {str(e)}"})

@app.route('/api/iniciar-verificacion', methods=['POST'])
def api_iniciar_verificacion():
    global verificacion_activa, huella_verificada
    
    if not template_capturado:
        return jsonify({"status": "error", "message": "No hay huella capturada previamente"})
    
    # Reiniciar estado
    verificacion_activa = True
    huella_verificada = False
    
    return jsonify({"status": "waiting", "message": "Esperando dedo para verificación"})

@app.route('/api/verificar-estado-verificacion', methods=['GET'])
def api_verificar_estado_verificacion():
    global verificacion_activa, huella_verificada
    
    if not verificacion_activa:
        # Reiniciamos la verificación en lugar de devolver error
        verificacion_activa = True
        huella_verificada = False
        return jsonify({"status": "waiting", "message": "Esperando dedo para verificación"})
    
    # Verificar si hay un dedo en el sensor
    try:
        i = finger.get_image()
        
        if i == adafruit_fingerprint.OK:
            # Se detectó un dedo, procesar la imagen
            huella_verificada = True
            return jsonify({"status": "captured", "message": "Dedo detectado para verificación"})
        elif i == adafruit_fingerprint.NOFINGER:
            # No hay dedo, seguir esperando
            return jsonify({"status": "waiting", "message": "Esperando dedo para verificación"})
        elif i == adafruit_fingerprint.IMAGEFAIL:
            # No cerrar la verificación, solo informar del error
            return jsonify({"status": "waiting", "message": "Error en imagen, intente de nuevo"})
        else:
            # No cerrar la verificación, solo informar del error
            return jsonify({"status": "waiting", "message": f"Error desconocido ({i}), intente de nuevo"})
    except Exception as e:
        # Error crítico, pero seguimos esperando
        return jsonify({"status": "waiting", "message": "Esperando dedo para verificación"})

@app.route('/api/procesar-verificacion', methods=['POST'])
def api_procesar_verificacion():
    global verificacion_activa, template_capturado, huella_verificada
    
    if not huella_verificada:
        return jsonify({"success": False, "message": "No se ha capturado ninguna huella para verificación"})
    
    # Convertir imagen a plantilla (slot 2)
    i = finger.image_2_tz(2)
    if i != adafruit_fingerprint.OK:
        mensaje_error = "No se pudo crear la plantilla para verificación"
        if i == adafruit_fingerprint.IMAGEMESS:
            mensaje_error = "Imagen demasiado borrosa"
        elif i == adafruit_fingerprint.FEATUREFAIL:
            mensaje_error = "No se pudieron identificar características"
        elif i == adafruit_fingerprint.INVALIDIMAGE:
            mensaje_error = "Imagen inválida"
        
        verificacion_activa = False
        return jsonify({"success": False, "message": mensaje_error})
    
    # Comparar las dos plantillas
    i = finger.create_model()
    if i != adafruit_fingerprint.OK:
        verificacion_activa = False
        if i == adafruit_fingerprint.ENROLLMISMATCH:
            return jsonify({"success": False, "message": "Las huellas no coinciden"})
        else:
            return jsonify({"success": False, "message": "Error al crear modelo de comparación"})
    
    # Si llegamos aquí, la verificación fue exitosa
    try:
        verificacion_activa = False
        return jsonify({
            "success": True, 
            "message": "Verificación exitosa", 
            "template": template_capturado
        })
    except Exception as e:
        verificacion_activa = False
        return jsonify({"success": False, "message": f"Error en la verificación: {str(e)}"})

@app.route('/api/verificar-cedula', methods=['GET'])
def api_verificar_cedula():
    cedula = request.args.get('cedula', '')
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM registro_huellas WHERE cedula = %s", (cedula,))
    existe = cursor.fetchone()[0] > 0
    cursor.close()
    
    return jsonify({"existe": existe})




# ===============================================
# API para identificación de huellas
# ===============================================

# ===============================================
# API para identificación de huellas
# ===============================================

# Almacenamiento de Templates en el Sensor



# Variables globales para identificación
identificacion_activa = False
huella_identificada = False
resultado_identificacion = None
esperando_nueva_verificacion = True  # Variable para controlar el ciclo de verificación
UMBRAL_CONFIANZA_MINIMO = 10  # Reducido de 30 a 10 para pruebas
UMBRAL_CONFIANZA_ALTO = 60    # Reducido de 80 a 60 para pruebas
TAMANO_LOTE = 10              # Tamaño del lote para procesamiento

# Función para cargar templates en el sensor
def cargar_templates_en_sensor(sensor=None):
    """
    Carga los templates de la base de datos en la memoria del sensor.
    Retorna un diccionario que mapea los IDs del sensor a los IDs de la base de datos.
    
    Args:
        sensor: Objeto del sensor a utilizar. Si es None, se usa el sensor principal (finger).
    """
    if sensor is None:
        sensor = finger
        
    try:
        # Limpiar biblioteca del sensor
        sensor.empty_library()
        print("Biblioteca del sensor limpiada")
        
        # Obtener templates de la base de datos
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT id, nombres, template FROM registro_huellas")
        registros = cursor.fetchall()
        cursor.close()
        
        print(f"Cargando {len(registros)} templates en el sensor...")
        
        # Mapeo de IDs del sensor a IDs de la base de datos
        id_mapping = {}
        
        # El sensor puede tener un límite de templates, así que cargamos hasta ese límite
        max_templates = min(len(registros), 200)  # Asumimos un máximo de 200 templates
        
        for i, registro in enumerate(registros[:max_templates]):
            if not registro['template']:
                continue
                
            try:
                # Decodificar template
                template_db = base64.b64decode(registro['template'])
                
                # Enviar al sensor (slot temporal)
                sensor.send_fpdata(list(template_db), "char", 1)
                
                # Guardar en la biblioteca del sensor con ID = i+1 (los IDs del sensor comienzan en 1)
                sensor_id = i + 1
                result = sensor.store_model(sensor_id)
                
                if result == adafruit_fingerprint.OK:
                    # Guardar mapeo de ID del sensor a ID de la base de datos
                    # Convertir explícitamente a enteros para evitar problemas de tipo
                    id_mapping[int(sensor_id)] = int(registro['id'])
                    print(f"Template de {registro['nombres']} cargado en el sensor (ID: {sensor_id}) -> DB ID: {registro['id']}")
                else:
                    print(f"Error al guardar template de {registro['nombres']} en el sensor: {result}")
            except Exception as e:
                print(f"Error al cargar template de {registro['nombres']}: {str(e)}")
        
        print(f"Se cargaron {len(id_mapping)} templates en el sensor")
        print(f"Mapeo de IDs: {id_mapping}")
        return id_mapping
    except Exception as e:
        print(f"Error al cargar templates en el sensor: {str(e)}")
        return {}

@app.route('/api/identificar_huella', methods=['POST'])
def api_identificar_huella():
    global identificacion_activa, huella_identificada, esperando_nueva_verificacion, resultado_identificacion
    
    # Reiniciar estado
    identificacion_activa = True
    huella_identificada = False
    esperando_nueva_verificacion = False  # Ya no estamos esperando, comenzamos a capturar
    resultado_identificacion = None
    
    # Cargar templates en el sensor
    id_mapping = cargar_templates_en_sensor()
    
    # Guardar el mapeo en la sesión para usarlo en la identificación
    # Convertir las claves a strings para que se puedan serializar en la sesión
    session['id_mapping'] = {str(k): v for k, v in id_mapping.items()}
    
    # Imprimir el mapeo para depuración
    print(f"DEBUG - Mapeo guardado en sesión: {session['id_mapping']}")
    
    return jsonify({"success": True, "message": "Esperando dedo...", "templates_cargados": len(id_mapping)})

@app.route('/api/resultado_identificacion', methods=['GET'])
def api_resultado_identificacion():
    global identificacion_activa, resultado_identificacion, esperando_nueva_verificacion
    
    if esperando_nueva_verificacion:
        if resultado_identificacion:
            return jsonify(resultado_identificacion)
        else:
            return jsonify({
                "encontrado": False, 
                "mensaje": "Presione el botón 'Verificar Huella' para iniciar una nueva verificación",
                "esperando_boton": True
            })
    
    try:
        # Capturar huella
        i = finger.get_image()
        if i == adafruit_fingerprint.NOFINGER:
            return jsonify({"encontrado": False, "mensaje": "Esperando dedo...", "esperando_boton": False})
        elif i != adafruit_fingerprint.OK:
            return jsonify({"encontrado": False, "mensaje": "Error al capturar huella", "esperando_boton": False})

        print("Huella capturada correctamente")
        
        # Convertir imagen a características
        i = finger.image_2_tz(1)
        if i != adafruit_fingerprint.OK:
            return jsonify({"encontrado": False, "mensaje": "Error al procesar la huella", "esperando_boton": False})

        print("Huella convertida a características correctamente")
        
        # Obtener el mapeo de IDs
        id_mapping_str = session.get('id_mapping', {})
        print(f"DEBUG - Mapeo recuperado de sesión: {id_mapping_str}")
        
        if not id_mapping_str:  # Changed from id_mapping to id_mapping_str
            esperando_nueva_verificacion = True
            resultado_identificacion = {
                "encontrado": False,
                "mensaje": "No hay templates cargados en el sensor",
                "esperando_boton": True
            }
            return jsonify(resultado_identificacion)
        
        # Buscar coincidencia en el sensor
        i = finger.finger_search()
        if i == adafruit_fingerprint.OK:
            # Encontró coincidencia
            finger_id = finger.finger_id
            confidence = finger.confidence
            
            print(f"Coincidencia encontrada en el sensor: ID={finger_id}, Confianza={confidence}")
            
            # Verificar si el ID del sensor está en nuestro mapeo (como string)
            finger_id_str = str(finger_id)
            print(f"DEBUG - Buscando ID {finger_id_str} en el mapeo")
            
            if finger_id_str in id_mapping_str:
                # Obtener el ID de la base de datos
                db_id = id_mapping_str[finger_id_str]
                print(f"DEBUG - ID encontrado en el mapeo. DB ID: {db_id}")
                
                # Obtener información de la persona
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("""
                    SELECT id, nombres, cedula, telefono, cargo, 
                           DATE_FORMAT(fecha_registro, '%%Y-%%m-%%d %%H:%%i:%%s') as fecha_registro 
                    FROM registro_huellas WHERE id = %s
                """, (db_id,))
                persona = cursor.fetchone()
                cursor.close()
                
                if persona:
                    # Registrar solo en la tabla de verificación de huella
                    if identificacion_activa:
                        cursor = mysql.connection.cursor()
                        cursor.execute(
                            "INSERT INTO registro_verificacion_huella (id_persona, fecha_hora, similitud) VALUES (%s, NOW(), %s)",
                            (persona['id'], confidence)
                        )
                        mysql.connection.commit()
                        cursor.close()
                    
                    esperando_nueva_verificacion = True
                    resultado_identificacion = {
                        "encontrado": True,
                        "mensaje": f"Huella identificada: {persona['nombres']}",
                        "persona": {
                            "nombres": persona['nombres'],
                            "cedula": persona['cedula'],
                            "telefono": persona.get('telefono', 'No disponible'),
                            "cargo": persona.get('cargo', 'No disponible'),
                            "fecha_registro": persona.get('fecha_registro', 'No disponible'),
                            "similitud": confidence
                        },
                        "esperando_boton": True
                    }
                    return jsonify(resultado_identificacion)
            
            # Si llegamos aquí, no pudimos encontrar la persona en la base de datos
            esperando_nueva_verificacion = True
            resultado_identificacion = {
                "encontrado": False,
                "mensaje": f"Error: Huella encontrada en el sensor (ID={finger_id}) pero no en el mapeo. Intente de nuevo.",
                "esperando_boton": True
            }
            return jsonify(resultado_identificacion)
        
        elif i == adafruit_fingerprint.NOTFOUND:
            # No encontró coincidencia
            esperando_nueva_verificacion = True
            resultado_identificacion = {
                "encontrado": False,
                "mensaje": "No se encontró coincidencia en la base de datos",
                "esperando_boton": True
            }
            return jsonify(resultado_identificacion)
        else:
            # Error en la búsqueda
            esperando_nueva_verificacion = True
            resultado_identificacion = {
                "encontrado": False,
                "mensaje": f"Error en la búsqueda de huella: {i}",
                "esperando_boton": True
            }
            return jsonify(resultado_identificacion)
    
    except Exception as e:
        print(f"Error en identificación: {str(e)}")
        esperando_nueva_verificacion = True
        resultado_identificacion = {
            "encontrado": False,
            "mensaje": f"Error en la identificación: {str(e)}",
            "esperando_boton": True
        }
        return jsonify(resultado_identificacion)










@app.route('/api/debug/id_mapping', methods=['GET'])
def api_debug_id_mapping():
    """
    Ruta de depuración para ver el mapeo actual de IDs.
    """
    id_mapping_str = session.get('id_mapping', {})
    
    # Obtener información adicional de la base de datos
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT id, nombres FROM registro_huellas")
    registros = {str(r['id']): r['nombres'] for r in cursor.fetchall()}
    cursor.close()
    
    # Crear un mapeo detallado para depuración
    mapeo_detallado = {}
    for sensor_id, db_id in id_mapping_str.items():
        mapeo_detallado[sensor_id] = {
            "db_id": db_id,
            "nombre": registros.get(str(db_id), "Desconocido")
        }
    
    return jsonify({
        "id_mapping": id_mapping_str,
        "mapeo_detallado": mapeo_detallado,
        "registros_totales": len(registros)
    })











# Setup for LCD
try:
    display = drivers.Lcd()
except Exception as e:
    print(f"Error initializing LCD: {str(e)}")
    display = None

# Setup for Solenoid
SOLENOID_PIN = 18
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(SOLENOID_PIN, GPIO.OUT)
GPIO.output(SOLENOID_PIN, 1)  # Ensure solenoid is off at start

# Function to display message on LCD
def mostrar_en_lcd(line1, line2=""):
    if display:
        try:
            display.lcd_clear()
            display.lcd_display_string(line1[:16], 1)  # Limit to 16 chars
            if line2:
                display.lcd_display_string(line2[:16], 2)
        except Exception as e:
            print(f"Error displaying on LCD: {str(e)}")

# Function to activate solenoid for a specific time
def activar_solenoid(seconds=3):
    try:
        GPIO.output(SOLENOID_PIN, 0)  # Activate solenoid
        sleep(seconds)
        GPIO.output(SOLENOID_PIN, 1)  # Deactivate solenoid
    except Exception as e:
        print(f"Error controlling solenoid: {str(e)}")
        # Ensure solenoid is deactivated in case of error
        GPIO.output(SOLENOID_PIN, 1)

@app.route('/admin/ingresosalon')
def ingresosalon():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/ingresosalon.html')

# Variables globales para control de ingreso al salón
ingreso_activo = False
huella_identificada = False
resultado_ingreso = None
esperando_nueva_verificacion = True

@app.route('/api/ingresar_salon', methods=['POST'])
def api_ingresar_salon():
    global ingreso_activo, huella_identificada, esperando_nueva_verificacion, resultado_ingreso
    
    # Reiniciar estado
    ingreso_activo = True
    huella_identificada = False
    esperando_nueva_verificacion = False
    resultado_ingreso = None
    
    # Mostrar mensaje en LCD
    mostrar_en_lcd("Ingreso al salon", "Coloque su dedo")
    
    # Cargar templates en el sensor (reutilizamos la función existente)
    id_mapping = cargar_templates_en_sensor()
    
    # Guardar el mapeo en la sesión para usarlo en la identificación
    session['id_mapping'] = {str(k): v for k, v in id_mapping.items()}
    
    return jsonify({"success": True, "message": "Esperando dedo...", "templates_cargados": len(id_mapping)})

@app.route('/api/resultado_ingreso_salon', methods=['GET'])
def api_resultado_ingreso_salon():
    global ingreso_activo, resultado_ingreso, esperando_nueva_verificacion
    
    if esperando_nueva_verificacion:
        if resultado_ingreso:
            return jsonify(resultado_ingreso)
        else:
            return jsonify({
                "encontrado": False, 
                "mensaje": "Presione el botón 'Ingresar al Salón' para iniciar una nueva verificación",
                "esperando_boton": True
            })
    
    try:
        # Capturar huella
        i = finger.get_image()
        if i == adafruit_fingerprint.NOFINGER:
            return jsonify({"encontrado": False, "mensaje": "Esperando dedo...", "esperando_boton": False})
        elif i != adafruit_fingerprint.OK:
            mostrar_en_lcd("Error", "Intente de nuevo")
            return jsonify({"encontrado": False, "mensaje": "Error al capturar huella", "esperando_boton": False})

        mostrar_en_lcd("Procesando", "huella...")
        
        # Convertir imagen a características
        i = finger.image_2_tz(1)
        if i != adafruit_fingerprint.OK:
            mostrar_en_lcd("Error", "Intente de nuevo")
            return jsonify({"encontrado": False, "mensaje": "Error al procesar la huella", "esperando_boton": False})
        
        # Obtener el mapeo de IDs
        id_mapping_str = session.get('id_mapping', {})
        
        if not id_mapping_str:
            esperando_nueva_verificacion = True
            mostrar_en_lcd("Error", "No hay registros")
            resultado_ingreso = {
                "encontrado": False,
                "mensaje": "No hay templates cargados en el sensor",
                "esperando_boton": True
            }
            return jsonify(resultado_ingreso)
        
        # Buscar coincidencia en el sensor
        i = finger.finger_search()
        if i == adafruit_fingerprint.OK:
            # Encontró coincidencia
            finger_id = finger.finger_id
            confidence = finger.confidence
            
            # Verificar si el ID del sensor está en nuestro mapeo
            finger_id_str = str(finger_id)
            
            if finger_id_str in id_mapping_str:
                # Obtener el ID de la base de datos
                db_id = id_mapping_str[finger_id_str]
                
                # Obtener información de la persona
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("""
                    SELECT id, nombres, cedula, telefono, cargo, 
                           DATE_FORMAT(fecha_registro, '%%Y-%%m-%%d %%H:%%i:%%s') as fecha_registro 
                    FROM registro_huellas WHERE id = %s
                """, (db_id,))
                persona = cursor.fetchone()
                cursor.close()
                
                if persona:
                    # Registrar entrada con la hora local del backend
                    ahora = datetime.now()
                    fecha_hora_local = ahora.strftime('%Y-%m-%d %H:%M:%S')
                    cursor = mysql.connection.cursor()
                    cursor.execute("""
                        INSERT INTO registro_ingresos 
                        (id_persona, fecha_hora_entrada) 
                        VALUES (%s, %s)
                    """, (persona['id'], fecha_hora_local))
                    mysql.connection.commit()
                    cursor.close()
                    
                    # Activar solenoid en un hilo separado
                    threading.Thread(target=activar_solenoid, args=(3,)).start()
                    
                    # Mostrar mensaje de bienvenida en LCD
                    nombre_corto = persona['nombres'].split()[0][:16]  # Primer nombre limitado a 16 caracteres
                    mostrar_en_lcd(f"Bienvenido", nombre_corto)
                    
                    esperando_nueva_verificacion = True
                    resultado_ingreso = {
                        "encontrado": True,
                        "mensaje": f"Acceso concedido: {persona['nombres']}",
                        "persona": {
                            "id": persona['id'],  # Añadir el ID para la sincronización
                            "nombres": persona['nombres'],
                            "cedula": persona['cedula'],
                            "telefono": persona.get('telefono', 'No disponible'),
                            "cargo": persona.get('cargo', 'No disponible'),
                            "fecha_registro": persona.get('fecha_registro', 'No disponible'),
                            "similitud": confidence
                        },
                        "esperando_boton": True
                    }
                    return jsonify(resultado_ingreso)
            
            # Si llegamos aquí, no pudimos encontrar la persona en la base de datos
            mostrar_en_lcd("Error", "Usuario no encontrado")
            esperando_nueva_verificacion = True
            resultado_ingreso = {
                "encontrado": False,
                "mensaje": f"Error: Huella encontrada en el sensor (ID={finger_id}) pero no en el mapeo. Intente de nuevo.",
                "esperando_boton": True
            }
            return jsonify(resultado_ingreso)
        
        elif i == adafruit_fingerprint.NOTFOUND:
            # No encontró coincidencia
            mostrar_en_lcd("Acceso denegado", "No registrado")
            esperando_nueva_verificacion = True
            resultado_ingreso = {
                "encontrado": False,
                "mensaje": "Acceso denegado: No se encontró coincidencia en la base de datos",
                "esperando_boton": True
            }
            return jsonify(resultado_ingreso)
        else:
            # Error en la búsqueda
            mostrar_en_lcd("Error", "Intente de nuevo")
            esperando_nueva_verificacion = True
            resultado_ingreso = {
                "encontrado": False,
                "mensaje": f"Error en la búsqueda de huella: {i}",
                "esperando_boton": True
            }
            return jsonify(resultado_ingreso)
    
    except Exception as e:
        print(f"Error en identificación: {str(e)}")
        mostrar_en_lcd("Error", "Sistema")
        esperando_nueva_verificacion = True
        resultado_ingreso = {
            "encontrado": False,
            "mensaje": f"Error en la identificación: {str(e)}",
            "esperando_boton": True
        }
        return jsonify(resultado_ingreso)


# ===============================================
# API para salida del salón
# ===============================================

# Variables globales para salida del salón
salida_activa = False
resultado_salida = None
esperando_nueva_verificacion_salida = True

@app.route('/api/sincronizar_hora_ingreso', methods=['POST'])
def api_sincronizar_hora_ingreso():
    if not request.is_json:
        return jsonify({"success": False, "message": "Se requiere JSON"}), 400
    
    data = request.get_json()
    id_persona = data.get('id_persona')
    hora_formateada = data.get('hora_formateada')
    
    if not id_persona or not hora_formateada:
        return jsonify({"success": False, "message": "Faltan datos requeridos"}), 400
    
    try:
        # Convertir la hora formateada a formato MySQL (YYYY-MM-DD HH:MM:SS)
        # Asumiendo que hora_formateada está en formato DD/MM/YYYY, HH:MM:SS
        partes = hora_formateada.replace(',', '').split()
        fecha_partes = partes[0].split('/')
        hora_partes = partes[1]
        
        # Reorganizar al formato MySQL
        fecha_mysql = f"{fecha_partes[2]}-{fecha_partes[1]}-{fecha_partes[0]} {hora_partes}"
        
        # Buscar el último registro de ingreso para esta persona y actualizarlo
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE registro_ingresos 
            SET fecha_hora_entrada = %s 
            WHERE id_persona = %s 
            ORDER BY id DESC 
            LIMIT 1
        """, (fecha_mysql, id_persona))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({"success": True, "message": "Hora sincronizada correctamente"})
    
    except Exception as e:
        print(f"Error al sincronizar hora: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/salir_salon', methods=['POST'])
def api_salir_salon():
    global salida_activa, resultado_salida, esperando_nueva_verificacion_salida
    
    # Reiniciar estado
    salida_activa = True
    resultado_salida = None
    esperando_nueva_verificacion_salida = False
    
    # Mostrar mensaje en LCD
    mostrar_en_lcd("Salida del salon", "Coloque su dedo")
    
    # Cargar templates en el segundo sensor
    id_mapping = cargar_templates_en_sensor(finger2)
    
    # Guardar el mapeo en la sesión
    session['id_mapping_salida'] = {str(k): v for k, v in id_mapping.items()}
    
    return jsonify({"success": True, "message": "Verificación de salida iniciada"})

@app.route('/api/resultado_salida_salon', methods=['GET'])
def api_resultado_salida_salon():
    global salida_activa, resultado_salida, esperando_nueva_verificacion_salida
    
    if esperando_nueva_verificacion_salida:
        if resultado_salida:
            return jsonify(resultado_salida)
        else:
            return jsonify({
                "encontrado": False, 
                "mensaje": "Presione el botón 'Salir del Salón' para iniciar una nueva verificación",
                "esperando_boton": True
            })
    
    try:
        # Capturar huella usando el segundo sensor (finger2)
        i = finger2.get_image()
        if i == adafruit_fingerprint.NOFINGER:
            return jsonify({"encontrado": False, "mensaje": "Esperando dedo para salida...", "esperando_boton": False})
        elif i != adafruit_fingerprint.OK:
            mostrar_en_lcd("Error", "Intente de nuevo")
            return jsonify({"encontrado": False, "mensaje": "Error al capturar huella para salida", "esperando_boton": False})

        mostrar_en_lcd("Procesando", "huella salida...")
        
        # Convertir imagen a características usando el segundo sensor
        i = finger2.image_2_tz(1)
        if i != adafruit_fingerprint.OK:
            mostrar_en_lcd("Error", "Intente de nuevo")
            return jsonify({"encontrado": False, "mensaje": "Error al procesar la huella para salida", "esperando_boton": False})
        
        # Obtener el mapeo de IDs
        id_mapping_str = session.get('id_mapping_salida', {})
        
        if not id_mapping_str:
            esperando_nueva_verificacion_salida = True
            mostrar_en_lcd("Error", "No hay registros")
            resultado_salida = {
                "encontrado": False,
                "mensaje": "No hay templates cargados en el sensor para salida",
                "esperando_boton": True
            }
            return jsonify(resultado_salida)
        
        # Buscar coincidencia en el segundo sensor
        i = finger2.finger_search()
        if i == adafruit_fingerprint.OK:
            # Encontró coincidencia
            finger_id = finger2.finger_id
            confidence = finger2.confidence
            
            # Verificar si el ID del sensor está en nuestro mapeo
            finger_id_str = str(finger_id)
            
            if finger_id_str in id_mapping_str:
                # Obtener el ID de la base de datos
                db_id = id_mapping_str[finger_id_str]
                
                # Obtener información de la persona
                cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cursor.execute("""
                    SELECT id, nombres, cedula, telefono, cargo, 
                           DATE_FORMAT(fecha_registro, '%%Y-%%m-%%d %%H:%%i:%%s') as fecha_registro 
                    FROM registro_huellas WHERE id = %s
                """, (db_id,))
                persona = cursor.fetchone()
                cursor.close()
                
                if persona:
                    # Buscar la entrada más reciente sin salida registrada
                    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                    cursor.execute("""
                        SELECT id, fecha_hora_entrada 
                        FROM registro_ingresos 
                        WHERE id_persona = %s AND fecha_hora_salida IS NULL 
                        ORDER BY fecha_hora_entrada DESC 
                        LIMIT 1
                    """, (persona['id'],))
                    entrada = cursor.fetchone()
                    
                    if entrada:
                        # Obtener la fecha y hora actual en formato local
                        ahora = datetime.now()
                        fecha_hora_local = ahora.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Actualizar el registro con la hora de salida local y calcular duración
                        cursor.execute("""
                            UPDATE registro_ingresos 
                            SET fecha_hora_salida = %s, 
                                duracion_minutos = TIMESTAMPDIFF(MINUTE, fecha_hora_entrada, %s) 
                            WHERE id = %s
                        """, (fecha_hora_local, fecha_hora_local, entrada['id']))
                        mysql.connection.commit()
                        
                        # También registrar en la tabla de salidas con hora local
                        cursor.execute("INSERT INTO registro_salidas (id_persona, fecha_hora) VALUES (%s, %s)", 
                                     (persona['id'], fecha_hora_local))
                        mysql.connection.commit()
                        cursor.close()
                        
                        # Activar solenoid en un hilo separado
                        threading.Thread(target=activar_solenoid, args=(3,)).start()
                        
                        # Mostrar mensaje de despedida en LCD
                        nombre_corto = persona['nombres'].split()[0][:16]  # Primer nombre limitado a 16 caracteres
                        mostrar_en_lcd(f"Hasta pronto", nombre_corto)
                        
                        esperando_nueva_verificacion_salida = True
                        resultado_salida = {
                            "encontrado": True,
                            "mensaje": f"Salida autorizada: {persona['nombres']}",
                            "persona": {
                                "nombres": persona['nombres'],
                                "cedula": persona['cedula'],
                                "telefono": persona.get('telefono', 'No disponible'),
                                "cargo": persona.get('cargo', 'No disponible'),
                                "fecha_registro": persona.get('fecha_registro', 'No disponible'),
                                "similitud": confidence
                            },
                            "esperando_boton": True
                        }
                        return jsonify(resultado_salida)
                    else:
                        # No hay entrada registrada para esta persona
                        mostrar_en_lcd("Error", "Sin entrada previa")
                        esperando_nueva_verificacion_salida = True
                        resultado_salida = {
                            "encontrado": False,
                            "mensaje": f"No hay registro de entrada previo para {persona['nombres']}",
                            "esperando_boton": True
                        }
                        return jsonify(resultado_salida)
            
            # Si llegamos aquí, no pudimos encontrar la persona en la base de datos
            mostrar_en_lcd("Error", "Usuario no encontrado")
            esperando_nueva_verificacion_salida = True
            resultado_salida = {
                "encontrado": False,
                "mensaje": f"Error: Huella encontrada en el sensor (ID={finger_id}) pero no en el mapeo. Intente de nuevo.",
                "esperando_boton": True
            }
            return jsonify(resultado_salida)
        
        elif i == adafruit_fingerprint.NOTFOUND:
            # No encontró coincidencia
            mostrar_en_lcd("Salida denegada", "No registrado")
            esperando_nueva_verificacion_salida = True
            resultado_salida = {
                "encontrado": False,
                "mensaje": "Salida denegada: No se encontró coincidencia en la base de datos",
                "esperando_boton": True
            }
            return jsonify(resultado_salida)
        else:
            # Error en la búsqueda
            mostrar_en_lcd("Error", "Intente de nuevo")
            esperando_nueva_verificacion_salida = True
            resultado_salida = {
                "encontrado": False,
                "mensaje": f"Error en la búsqueda de huella para salida: {i}",
                "esperando_boton": True
            }
            return jsonify(resultado_salida)
    
    except Exception as e:
        print(f"Error en identificación para salida: {str(e)}")
        mostrar_en_lcd("Error", "Sistema")
        esperando_nueva_verificacion_salida = True
        resultado_salida = {
            "encontrado": False,
            "mensaje": f"Error en la identificación para salida: {str(e)}",
            "esperando_boton": True
        }
        return jsonify(resultado_salida)

# ... existing code ...




#registro de ingresos 
# Agregar esta ruta después de las demás rutas de API

@app.route('/admin/registroingresos')
def registroingresos():
    if not 'login' in session:
        return redirect('/')
    return render_template('admin/registroingresos.html')

@app.route('/api/obtener_registros_ingresos', methods=['GET'])
def api_obtener_registros_ingresos():
    if 'login' not in session:
        return jsonify({"success": False, "mensaje": "No autorizado"})
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT ri.id, rh.nombres, rh.cedula, rh.cargo, 
                   DATE_FORMAT(ri.fecha_hora_entrada, '%Y-%m-%d %H:%i:%s') as fecha_hora_entrada,
                   CASE WHEN ri.fecha_hora_salida IS NOT NULL 
                        THEN DATE_FORMAT(ri.fecha_hora_salida, '%Y-%m-%d %H:%i:%s')
                        ELSE NULL END as fecha_hora_salida,
                   ri.duracion_minutos
            FROM registro_ingresos ri
            JOIN registro_huellas rh ON ri.id_persona = rh.id
            ORDER BY ri.fecha_hora_entrada DESC
        """)
        registros = cursor.fetchall()
        cursor.close()
        
        # Convertir a lista de diccionarios para serializar correctamente
        registros_lista = []
        for registro in registros:
            registro_dict = dict(registro)
            registros_lista.append(registro_dict)
        
        return jsonify({"success": True, "registros": registros_lista})
    except Exception as e:
        print(f"Error al obtener registros de ingresos: {str(e)}")
        return jsonify({"success": False, "mensaje": f"Error: {str(e)}"})


# ... existing code ...


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)




