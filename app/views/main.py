from flask import Blueprint, render_template, request, Response, current_app, redirect, url_for, stream_with_context
from datetime import datetime, timezone
from functools import wraps
import requests
import logging

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# Referencia global para el manager
task_manager = None

def get_authenticated_user():
    """Función centralizada para autenticar al usuario (Red local o HTTP Basic Externo)."""
    from app.models import User
    
    # 1. Comprobar si es red local
    has_proxy = request.headers.get('X-Forwarded-For') is not None
    is_local = False

    if not has_proxy:
        host = request.host.split(':')[0] if request.host else ''
        ip = request.remote_addr or ''
        is_local = (
            host in ('localhost', '127.0.0.1', '::1') or 
            host.startswith(('192.168.', '10.')) or
            ip in ('127.0.0.1', '::1') or
            ip.startswith(('192.168.', '10.', '169.254.'))
        )

    if is_local:
        admin_user = User.query.filter_by(is_admin=True).first()
        if admin_user:
            admin_user.is_authenticated = True
        local_obj = admin_user or type('Obj', (object,), {'username': 'LocalAdmin', 'is_admin': True, 'is_authenticated': True})
        return local_obj, True, True  # (user, is_admin, is_local)

    # 2. Validación mediante HTTP Basic Auth para accesos externos
    try:
        auth = request.authorization
        if auth:
            user = User.query.filter_by(username=auth.username).first()
            if user and user.check_password(auth.password):
                user.is_authenticated = True
                return user, user.is_admin, False
    except Exception as e:
        logger.error(f"Error evaluating authentication: {e}")

    return None, False, False

def admin_required(f):
    """Decorador para restringir rutas exclusivamente a administradores."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from ..utils.config import Config
        config = Config()
        if not config.settings_repo or not config.settings_repo.is_setup_completed():
            return redirect(url_for('main.setup'))
            
        user, is_admin, is_local = get_authenticated_user()
        
        # Si no hay usuario autenticado externamente, forzar 401 para pedir credenciales
        if not user and not is_local:
            return Response(
                "Authentication required", 
                401, 
                {'WWW-Authenticate': 'Basic realm="Acestream Scraper Secure Area"'}
            )
            
        if not is_admin:
            return redirect(url_for('main.tv_channels'))
            
        return f(*args, **kwargs)
    return decorated_function

# --- PROCESADOR DE CONTEXTO GLOBAL PARA LAS VISTAS ---
@bp.app_context_processor
def inject_template_user_context():
    """Inyecta automáticamente is_admin, current_user e is_local en todas las plantillas HTML."""
    user, is_admin, is_local = get_authenticated_user()
    return {
        'is_admin': is_admin,
        'current_user': user,
        'is_local': is_local
    }

@bp.route('/logout')
def logout():
    """Fuerza al navegador a olvidar las credenciales de HTTP Basic mediante un código 401."""
    return Response(
        '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Logged Out</title>
            <script>
                setTimeout(function() {
                    window.location.href = "/";
                }, 500);
            </script>
        </head>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h3>Logged out successfully. Redirecting to login...</h3>
            <p><a href="/">Click here if you are not redirected</a></p>
        </body>
        </html>
        ''', 
        401, 
        {'WWW-Authenticate': 'Basic realm="Acestream Scraper Secure Area"'}
    )

@bp.route('/')
@admin_required
def index():
    from ..utils.config import Config
    config = Config()
    if config.settings_repo and config.settings_repo.is_setup_completed():
        return render_template('dashboard.html')
    return redirect(url_for('main.setup'))

@bp.route('/dashboard')
@admin_required
def dashboard():
    return index()

@bp.route('/setup')
def setup():
    from ..utils.config import Config
    config = Config()
    if config.is_initialized():
        return redirect(url_for('main.index'))
    return render_template('setup.html')

@bp.route('/playlist.m3u')
def get_playlist():
    from ..utils.config import Config
    from ..services import PlaylistService
    from ..repositories import URLRepository
    
    config = Config()
    if not config.is_initialized() and not current_app.testing:
        return redirect(url_for('main.setup'))
        
    refresh = request.args.get('refresh', 'false').lower() == 'true'
    search = request.args.get('search', None)
    base_url_param = request.args.get('base_url', None)
    
    if refresh and task_manager:
        url_repository = URLRepository()
        urls = url_repository.get_enabled()
        for url in urls:
            task_manager.add_task(url.url) 
    
    playlist_service = PlaylistService()
    # Pasamos el base_url directamente como argumento
    playlist = playlist_service.generate_playlist(search_term=search, base_url=base_url_param)
    
    return Response(playlist, mimetype="audio/x-mpegurl")

@bp.route('/search')
@admin_required
def search():
    from ..utils.config import Config
    config = Config()
    if not config.settings_repo or not config.settings_repo.is_setup_completed():
        return redirect(url_for('main.setup'))
    return render_template('search.html')

@bp.route('/config')
@admin_required
def config():
    return render_template('config.html')

@bp.route('/tv-channels')
def tv_channels():
    from ..utils.config import Config
    config = Config()
    if not config.settings_repo or not config.settings_repo.is_setup_completed():
        return redirect(url_for('main.setup'))
    return render_template('tv_channels.html')

@bp.route('/tv-channels/<int:tv_channel_id>')
def tv_channel_detail(tv_channel_id):
    from ..utils.config import Config
    config = Config()
    if not config.settings_repo or not config.settings_repo.is_setup_completed():
        return redirect(url_for('main.setup'))
    return render_template('tv_channel_detail.html', tv_channel_id=tv_channel_id)

@bp.route('/streams')
@admin_required
def streams():
    from ..utils.config import Config
    config = Config()
    if not config.settings_repo or not config.settings_repo.is_setup_completed():
        return redirect(url_for('main.setup'))
    return render_template('streams.html')

@bp.route('/epg')
@admin_required
def epg_management():
    from ..utils.config import Config
    config = Config()
    if not config.settings_repo or not config.settings_repo.is_setup_completed():
        return redirect(url_for('main.setup'))
    return render_template('epg.html')
    
@bp.route('/recordings')
@admin_required
def recordings_page():
    return render_template('recordings.html')

@bp.route('/ace/getstream')
def proxy_acestream():
    from ..utils.config import Config
    config = Config()
    stream_id = request.args.get('id')
    
    ace_url = getattr(config, 'ace_engine_url', 'http://127.0.0.1:6878').rstrip('/')
    target_url = f"{ace_url}/ace/getstream?id={stream_id}"
    
    try:
        req = requests.get(target_url, stream=True, timeout=15)
        return Response(
            stream_with_context(req.iter_content(chunk_size=1024*64)),
            status=req.status_code,
            content_type=req.headers.get('content-type', 'video/mp2t')
        )
    except Exception as e:
        logger.error(f"Error en proxy acestream: {e}")
        return f"Error connecting to engine: {e}", 502

@bp.route('/streams/ace/cid:<path:cid_path>')
def proxy_outpace_hls(cid_path):
    from ..utils.config import Config
    config = Config()
    
    ace_url = getattr(config, 'ace_engine_url', 'http://127.0.0.1:6878').rstrip('/')
    target_url = f"{ace_url}/streams/ace/cid:{cid_path}"
    
    try:
        req = requests.get(target_url, stream=True, timeout=60)
        return Response(
            stream_with_context(req.iter_content(chunk_size=1024*64)),
            status=req.status_code,
            content_type=req.headers.get('content-type', 'application/vnd.apple.mpegurl')
        )
    except Exception as e:
        logger.error(f"Error en proxy HLS outpace: {e}")
        return f"Error connecting to HLS engine: {e}", 502