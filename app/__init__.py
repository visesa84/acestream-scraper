import os
import asyncio
import threading
import logging
import fasteners
import tempfile
from flask import Flask, redirect, url_for, request
from werkzeug.middleware.proxy_fix import ProxyFix
from app.extensions import db, migrate
from app.models import User

task_manager = None

def is_local_network(req):
    """
    Determina si la petición proviene de la red local basándose exclusivamente 
    en la IP remota real (gestionada de forma segura por ProxyFix), 
    eliminando el uso inseguro del encabezado Host.
    """
    ip = req.remote_addr or ''
    if ip.startswith('::ffff:'):
        ip = ip[7:]
        
    return (
        ip in ('127.0.0.1', '::1') or
        ip.startswith('192.168.') or
        ip.startswith('10.') or
        ip.startswith('172.') or
        ip.startswith('169.254.')
    )

def create_app(test_config=None):
    from app.utils.config import Config
    from app.tasks.manager import TaskManager
    from app.repositories import SettingsRepository

    global task_manager
    if not task_manager:
        task_manager = TaskManager()

    app = Flask(__name__)

    # ProxyFix configurado para confiar en las cabeceras del proxy (NPM)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)
    app.config['PREFERRED_URL_SCHEME'] = 'http'

    logging_level = logging.DEBUG if os.environ.get('FLASK_ENV') == 'development' else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'

    try:
        config = Config()
        if config.database_path:
            config.database_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Config directory verified: {config.database_path.parent}")
    
        app.config['SQLALCHEMY_DATABASE_URI'] = config.database_uri
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "connect_args": {
                "timeout": 30,
                "check_same_thread": False 
            },
            "pool_pre_ping": True
        }
    except Exception as e:
        logger.error(f"Error initializing Config: {e}")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api import bp as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    from app.views.main import bp as main_blueprint
    import app.views.main as main_module
    
    main_module.task_manager = task_manager
    app.register_blueprint(main_blueprint)
    
    is_testing = test_config == 'testing' or os.environ.get('TESTING') == '1'
    app.config['TESTING'] = is_testing

    with app.app_context():
        try:
            try:
                logger.info("Initializing database tables...")
                db.create_all()
            except Exception as e:
                logger.info("Tables already exist.")
            
            settings_repo = SettingsRepository()
            config.set_settings_repository(settings_repo)

            if not is_testing:
                task_manager.init_app(app)

                def run_background_loop():
                    from app.tasks.recorder import process_recordings 
                    
                    tmpdir = tempfile.gettempdir()
                    lockfile = os.path.join(tmpdir, 'task_manager.lock')
                    lock = fasteners.InterProcessLock(lockfile)
                    got_lock = lock.acquire(blocking=False)
                    
                    if not got_lock:
                        logger.info("[Worker] TaskManager/Recorder is already active. Skipping.")
                        return

                    logger.info("[MANAGER] Lock acquired! Starting background loops.")
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def combined_tasks():
                        asyncio.create_task(task_manager.start())
                        
                        while True:
                            try:
                                await loop.run_in_executor(None, process_recordings, app)
                            except Exception as e:
                                logger.error(f"Error in recording worker: {e}")
                            
                            await asyncio.sleep(60)

                    try:
                        loop.run_until_complete(combined_tasks())
                    except Exception as e:
                        logger.error(f"Background loop crashed: {e}")
                    finally:
                        if lock.exists():
                            lock.release()
                        loop.close()
                
                thread = threading.Thread(
                    target=run_background_loop, 
                    name="TaskManagerThread", 
                    daemon=True
                )
                thread.start()

        except Exception as e:
            logger.error(f"Fatal error during app startup: {e}", exc_info=True)

    @app.context_processor
    def inject_config():
        is_admin_user = False
        current_user_obj = None
        
        try:
            # Validación robusta basada en IP limpia mediante ProxyFix
            if is_local_network(request):
                admin_user = User.query.filter_by(is_admin=True).first()
                if admin_user:
                    current_user_obj = admin_user
                    is_admin_user = True
            else:
                # Dominio externo exige HTTP Basic Auth
                auth = request.authorization
                if auth:
                    user = User.query.filter_by(username=auth.username).first()
                    if user and user.check_password(auth.password):
                        current_user_obj = user
                        is_admin_user = user.is_admin
        except Exception as e:
            logger.error(f"Error in inject_config auth: {e}")

        return {
            'enable_acestream_search': os.environ.get('ENABLE_ACESTREAM_SEARCH', 'true').lower() == 'true',
            'enable_warp': os.environ.get('ENABLE_WARP', 'false').lower() == 'true',
            'current_user': current_user_obj,
            'is_admin': is_admin_user
        }

    @app.route('/')
    def index():
        """Gestiona la entrada a la raíz evitando bucles de redirección según el rol."""
        try:
            if not is_local_network(request):
                auth = request.authorization
                if auth:
                    user = User.query.filter_by(username=auth.username).first()
                    if user and user.check_password(auth.password):
                        if not user.is_admin:
                            return redirect(url_for('main.tv_channels'))
        except Exception:
            pass
        
        from app.views.main import dashboard
        return dashboard()

    return app