import time
ti=time.time()
from flask import Flask, session, redirect, url_for, request
from flask_session import Session
import secrets
from routes.login import login_bp
from routes.dashboard import dashboard_bp
from routes.resultados import resultados_bp
from routes.carga import carga_bp
from routes.finanzas import finanzas_bp
from routes.insumos import insumos_bp
from routes.nuevo_servicio import nuevo_servicio_bp
from routes.administrar_servicio import administrar_servicio_bp
from routes.externo import externo_bp
from routes.cotizaciones import cotizaciones_bp
from models import db
from datetime import timedelta
tf=time.time()
print(f'Tiempo en importar modulos {tf-ti:.2f} segundos')



app = Flask(__name__)

# Configura la clave secreta para las sesiones
app.secret_key = secrets.token_hex(16)  # Usa una clave secreta generada aleatoriamente

# Configuración de Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # Usa 'filesystem' o 'redis' para almacenamiento
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = './flask_session/'  # Si usas 'filesystem', define el directorio
app.config['SESSION_PERMANENT'] = True

# Inicializar la extensión de sesión
Session(app)


# Conexión a la base
@app.before_request
def _db_connect():
    if db.db.is_closed():
        db.db.connect()

@app.teardown_request
def _db_close(exc):
    if not db.db.is_closed():
        db.db.close()


# ✅ Nueva función para proteger todas las rutas excepto las públicas
@app.before_request
def requerir_login():
    rutas_publicas = ['login.login', 'login.logout', None]  # None por si acaso en páginas estáticas
    
    # Permitir archivos estáticos sin sesión
    if request.endpoint and request.endpoint.startswith('static'):
        return

    if request.endpoint not in rutas_publicas and 'usuario' not in session:
        return redirect(url_for('login.login'))


# Registro de Blueprints
app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(resultados_bp)
app.register_blueprint(carga_bp)
app.register_blueprint(finanzas_bp)
app.register_blueprint(insumos_bp)
app.register_blueprint(nuevo_servicio_bp)
app.register_blueprint(administrar_servicio_bp)
app.register_blueprint(externo_bp)
app.register_blueprint(cotizaciones_bp)

# En las VMs es mejor usar debug=False porque sino queda muy lento
if __name__ == "__main__":
    app.run(debug=False)
