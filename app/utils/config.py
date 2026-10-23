import os
import json
import logging
from pathlib import Path
from app.repositories import SettingsRepository
from flask import has_app_context, current_app

logger = logging.getLogger(__name__)

class Config:
    """Configuration management class."""
    DEFAULT_BASE_URL = ''
    DEFAULT_RESCRAPE_INTERVAL = 24
    DEFAULT_CHECKSTATUS_INTERVAL = 24
    DEFAULT_CHECKSTATUS_ENABLED = True
    DEFAULT_EPG_REFRESH_INTERVAL = 24
    DEFAULT_STREAM_MODE = 'traditional'
    
    _instance = None
    config_path = None
    database_path = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
            
        self.logger = logging.getLogger(__name__)
        self.settings_repo = None
        self._needs_init = True
        
        if os.environ.get('DOCKER_ENV'):
            base_config_dir = Path('/app/config')
        else:
            project_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            base_config_dir = project_root / 'config'
        
        base_config_dir.mkdir(parents=True, exist_ok=True)
        
        if Config.config_path is None:
            Config.config_path = base_config_dir / 'config.json'
        
        if Config.database_path is None:
            Config.database_path = base_config_dir / 'acestream.db'
        
        self._config = {}
        self._load_config()
        
        try:
            self.settings_repo = SettingsRepository()
        except Exception as e:
            self.logger.warning(f"Could not initialize settings repository: {e}")
        
        self._initialized = True

    def _ensure_app_context(self):
        """Ensure we're in an app context and initialize if needed."""
        if not has_app_context():
            return False
            
        if self._needs_init and self.settings_repo:
            self._needs_init = False
            self._ensure_required_settings()
            if hasattr(self.settings_repo, 'commit_cache_to_db'):
                self.settings_repo.commit_cache_to_db()
            
        return True

    def _ensure_required_settings(self):
        """Ensure all required settings exist with default values."""
        if not self.settings_repo or os.environ.get('TESTING'):
            return
        
        required_settings = {
            'base_url': self.DEFAULT_BASE_URL,
            'rescrape_interval': self.DEFAULT_RESCRAPE_INTERVAL,
            'checkstatus_interval': self.DEFAULT_CHECKSTATUS_INTERVAL,
            'checkstatus_enabled': self.DEFAULT_CHECKSTATUS_ENABLED,
            'epg_refresh_interval': self.DEFAULT_EPG_REFRESH_INTERVAL,
            'stream_mode': self.DEFAULT_STREAM_MODE
        }
        
        for key, default_value in required_settings.items():
            try:
                if not self.settings_repo.get_setting(key):
                    self.logger.info(f"Setting default value for {key}: {default_value}")
                    self.settings_repo.set_setting(key, default_value)
            except Exception as e:
                self.logger.error(f"Error ensuring required setting {key}: {e}")

    def set_settings_repository(self, settings_repo):
        self.settings_repo = settings_repo
        self._needs_init = False

    def _load_config(self):
        try:
            if Config.config_path and Config.config_path.exists():
                with open(Config.config_path, 'r') as f:
                    self._config = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config file: {e}")
            self._config = {}
    
    def get(self, key, default=None):
        """Get a configuration value with database fallback."""
        if self._needs_init:
            self._ensure_app_context()
        
        try:
            if self.settings_repo:
                value = self.settings_repo.get_setting(key)
                if value is not None:
                    return value
            
            if key in self._config:
                return self._config[key]
                
            default_attr = f'DEFAULT_{key.upper()}'
            if hasattr(self, default_attr):
                return getattr(self, default_attr)
                
            return default
        except Exception as e:
            self.logger.error(f"Error getting config value for {key}: {e}")
            return default
    
    def set(self, key, value):
        """Set a configuration value in the database."""
        if self._needs_init:
            self._ensure_app_context()
        
        try:
            if self.settings_repo:
                self.settings_repo.set_setting(key, value)
            self._config[key] = value
        except Exception as e:
            self.logger.error(f"Error setting config value for {key}: {e}")
    
    @property
    def database_uri(self) -> str:
        if os.environ.get('TESTING'):
            return 'sqlite:///:memory:'
        return f'sqlite:///{Config.database_path}'

    # --- PROPIEDADES (GETTERS / SETTERS) ---

    @property
    def base_url(self):
        return self.get('base_url', self.DEFAULT_BASE_URL)
    
    @base_url.setter
    def base_url(self, value):
        self.set('base_url', value)

    @property
    def rescrape_interval(self):
        val = self.get('rescrape_interval', self.DEFAULT_RESCRAPE_INTERVAL)
        return int(val) if val is not None else self.DEFAULT_RESCRAPE_INTERVAL
    
    @rescrape_interval.setter
    def rescrape_interval(self, value):
        self.set('rescrape_interval', str(value))
    
    @property
    def checkstatus_interval(self):
        if self._needs_init: return self.DEFAULT_CHECKSTATUS_INTERVAL
        val = self.get('checkstatus_interval', self.DEFAULT_CHECKSTATUS_INTERVAL)
        return int(val) if val is not None else self.DEFAULT_CHECKSTATUS_INTERVAL
    
    @checkstatus_interval.setter
    def checkstatus_interval(self, value):
        self.set('checkstatus_interval', str(value))

    @property
    def checkstatus_enabled(self):
        if self._needs_init: return self.DEFAULT_CHECKSTATUS_ENABLED
        env_val = os.environ.get('CHECKSTATUS_ENABLED')
        if env_val is not None:
            return env_val.lower() in ('true', 'yes', '1', 'on')
        val = self.get('checkstatus_enabled', self.DEFAULT_CHECKSTATUS_ENABLED)
        if isinstance(val, str):
            return val.lower() in ('true', 'yes', '1', 'on')
        return bool(val)

    @checkstatus_enabled.setter
    def checkstatus_enabled(self, value):
        normalized_value = str(value).lower() in ['true', '1', 'on', 'yes']
        str_to_save = 'true' if normalized_value else 'false'
        self.set('checkstatus_enabled', str_to_save)
        
    @property
    def epg_refresh_interval(self):
        val = self.get('epg_refresh_interval', self.DEFAULT_EPG_REFRESH_INTERVAL)
        return int(val) if val is not None else self.DEFAULT_EPG_REFRESH_INTERVAL
    
    @epg_refresh_interval.setter
    def epg_refresh_interval(self, value):
        self.set('epg_refresh_interval', str(value))

    @property
    def stream_mode(self):
        val = self.get('stream_mode', self.DEFAULT_STREAM_MODE)
        return val if val in ('traditional', 'hls') else self.DEFAULT_STREAM_MODE
    
    @stream_mode.setter
    def stream_mode(self, value):
        if value in ('traditional', 'hls'):
            self.set('stream_mode', value)
        
    def is_initialized(self):
        self._ensure_app_context()
        try:
            if self.settings_repo:
                setup_completed = self.settings_repo.get_setting('setup_completed')
                return setup_completed and setup_completed.lower() == 'true'
            return False
        except Exception:
            return False