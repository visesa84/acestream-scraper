import sys
import subprocess
import os
from app import create_app
from whitenoise import WhiteNoise
import logging
from app.utils.auth import init_global_db_auth

# 1. Migraciones (opcional): ejecutar sólo si la variable de entorno AUTO_MIGRATE=1
if os.environ.get('AUTO_MIGRATE', '0') == '1':
    try:
        subprocess.run([sys.executable, "manage.py", "upgrade"], check=True)
    except Exception as e:
        print(f"Migration error: {e}")

# 2. Crear App Flask
flask_app = create_app()

# --- AUTENTICACIÓN GLOBAL BASADA EN BASE DE DATOS Y SETUP ---
init_global_db_auth(flask_app)
# -----------------------------------------------------------

# 3. Envolver con WhiteNoise ANTES de WsgiToAsgi
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static')
flask_app.wsgi_app = WhiteNoise(
    flask_app.wsgi_app, 
    root=static_dir,
    prefix='static/',
    max_age=31536000 
)

app = flask_app