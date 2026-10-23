from flask import request, Response, redirect, jsonify
from app.models import User
import logging

logger = logging.getLogger(__name__)

# Función auxiliar para detectar si la petición proviene de la red local o entorno Docker de casa
def is_local_network(req):
    host = req.host.split(':')[0] if req.host else ''
    if (host in ('localhost', '127.0.0.1', '::1') or 
        host.startswith('192.168.') or 
        host.startswith('10.') or 
        host.startswith('172.')):
        return True

    ip = req.headers.get('X-Forwarded-For', req.remote_addr)
    if ip:
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        if ip.startswith('::ffff:'):
            ip = ip[7:]
            
        if (ip == '127.0.0.1' or 
            ip == '::1' or 
            ip.startswith('192.168.') or 
            ip.startswith('10.') or 
            ip.startswith('172.') or 
            ip.startswith('169.254.')):
            return True

    return False

def check_db_auth(username, password):
    """Verifica el usuario y la contraseña consultando la base de datos."""
    try:
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            return user
    except Exception as e:
        logger.error(f"Error verifying authentication in the database: {e}")
    return None

def authenticate_response():
    """Retorna la cabecera 401 para solicitar autenticación HTTP Basic."""
    return Response(
        'Unauthorized access. Authentication required.\n', 401,
        {'WWW-Authenticate': 'Basic realm="Acestream Scraper Secure Area"'}
    )

def init_global_db_auth(app):
    """Registra el middleware global de autenticación y el inyector de contexto para las plantillas."""
    
    @app.context_processor
    def inject_user_context():
        """Inyecta is_admin y current_user globalmente en todas las vistas y plantillas."""
        is_admin_val = False
        current_user_val = None

        # Si estamos en la red local, otorgamos privilegios de administrador automáticamente
        if is_local_network(request):
            is_admin_val = True
            try:
                current_user_val = User.query.filter_by(is_admin=True).first()
            except Exception:
                pass
            
            if not current_user_val:
                class MockUser:
                    username = "LocalAdmin"
                    is_admin = True
                    is_authenticated = True
                current_user_val = MockUser()
        else:
            # Si requiere autenticación HTTP Basic, validamos las credenciales
            auth = request.authorization
            if auth:
                user = check_db_auth(auth.username, auth.password)
                if user:
                    current_user_val = user
                    is_admin_val = user.is_admin

        return {
            'is_admin': is_admin_val,
            'current_user': current_user_val
        }

    @app.before_request
    def global_auth_middleware():
        if request.method == 'OPTIONS':
            return None

        if request.path.startswith('/static/'):
            return None

        # Si la petición viene de la red local, permitimos el acceso total
        if is_local_network(request):
            return None

        try:
            user_count = User.query.count()
            if user_count == 0:
                allowed_paths = [
                    '/setup', '/api/users/', '/api/config/base_url', 
                    '/api/config/stream_mode', '/api/config/rescrape_interval', 
                    '/api/config/checkstatus_interval', '/api/config/setup_completed', '/api/urls/'
                ]
                if request.path not in allowed_paths and not request.path.startswith('/api/urls'):
                    return redirect('/setup')
                return None
        except Exception as e:
            logger.warning(f"The user table is not yet available: {e}")
            return None

        if request.path == '/logout':
            return None

        auth = request.authorization
        if not auth:
            return authenticate_response()
            
        user = check_db_auth(auth.username, auth.password)
        if not user:
            return authenticate_response()

        if not user.is_admin:
            if request.method in ['POST', 'PUT', 'DELETE']:
                return jsonify({'error': 'Forbidden: Administrator privileges required for modifications.'}), 403

            is_root = request.path == '/'
            is_tv_channels_page = request.path == '/tv-channels'
            is_playlist_file = request.path.endswith('.m3u') or request.path.endswith('.m3u8')
            is_stream_route = '/streams/' in request.path or '/ace/getstream' in request.path or '/api/playlists/' in request.path
            is_allowed_api_get = request.path.startswith('/api/') and request.method == 'GET'

            if not (is_root or is_tv_channels_page or is_playlist_file or is_stream_route or is_allowed_api_get):
                return Response('Forbidden: Standard users can only access TV channels page.', 403)

        return None