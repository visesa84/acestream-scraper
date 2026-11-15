from app.models import Setting
from app.extensions import db
import logging
from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
class SettingsRepository:
    """Repository for application settings."""
    
   # Add constants for settings keys
    BASE_URL = 'base_url'
    ACE_ENGINE_URL = 'ace_engine_url'
    RESCRAPE_INTERVAL = 'rescrape_interval'
    SETUP_COMPLETED = 'setup_completed'
    
    # Forzar valores fijos internos para que no puedan ser sobreescritos por la BD
    OUTPACE_BIND = '0.0.0.0:6878'
    OUTPACE_RTMP_BIND = '0.0.0.0:1935'
    OUTPACE_PEER_LISTEN = '0.0.0.0:8621'
    OUTPACE_DATA_DIR = '/root/.local/share/outpace'
    OUTPACE_CACHE_DIR = '/root/.local/share/outpace/cache'
    
    # Outpace core configurable constants keys
    OUTPACE_ACE_COMPAT_KEY = 'OUTPACE_ACE_COMPAT'
    OUTPACE_MAX_ACTIVE_UPSTREAMS_KEY = 'OUTPACE_MAX_ACTIVE_UPSTREAMS'
    OUTPACE_MAX_PARALLEL_CONNECT_KEY = 'OUTPACE_MAX_PARALLEL_CONNECT'
    OUTPACE_REQUEST_TIMEOUT_MS_KEY = 'OUTPACE_REQUEST_TIMEOUT_MS'
    OUTPACE_CONNECT_TIMEOUT_MS_KEY = 'OUTPACE_CONNECT_TIMEOUT_MS'
    OUTPACE_READ_TIMEOUT_MS_KEY = 'OUTPACE_READ_TIMEOUT_MS'
    OUTPACE_CACHE_SIZE_MB_KEY = 'OUTPACE_CACHE_SIZE_MB'
    OUTPACE_MAX_CONNECTIONS_PER_STREAM_KEY = 'OUTPACE_MAX_CONNECTIONS_PER_STREAM'
    OUTPACE_ENABLE_INBOUND_KEY = 'OUTPACE_ENABLE_INBOUND'
    OUTPACE_ENABLE_SEEDING_KEY = 'OUTPACE_ENABLE_SEEDING'
    OUTPACE_CACHE_TYPE_KEY = 'OUTPACE_CACHE_TYPE'
    OUTPACE_SEED_STORE_BYTES_KEY = 'OUTPACE_SEED_STORE_BYTES'
    AUDIO_NORMALIZE = 'outpace_live_audio_normalize'

    # Add constants for default values
    DEFAULT_BASE_URL = ''
    DEFAULT_ACE_ENGINE_URL = 'http://localhost:6878'
    DEFAULT_RESCRAPE_INTERVAL = '24'
    
    # Outpace default values
    DEFAULT_OUTPACE_ACE_COMPAT = '1'
    DEFAULT_OUTPACE_MAX_ACTIVE_UPSTREAMS = '6'
    DEFAULT_OUTPACE_MAX_PARALLEL_CONNECT = '16'
    DEFAULT_OUTPACE_REQUEST_TIMEOUT_MS = '3500'
    DEFAULT_OUTPACE_CONNECT_TIMEOUT_MS = '5000'
    DEFAULT_OUTPACE_READ_TIMEOUT_MS = '10000'
    DEFAULT_OUTPACE_CACHE_SIZE_MB = '128'
    DEFAULT_OUTPACE_MAX_CONNECTIONS_PER_STREAM = '35'
    DEFAULT_OUTPACE_ENABLE_INBOUND = '1'
    DEFAULT_OUTPACE_ENABLE_SEEDING = '1'
    DEFAULT_OUTPACE_CACHE_TYPE = 'memory'
    DEFAULT_OUTPACE_SEED_STORE_BYTES = '134217728'
    DEFAULT_AUDIO_NORMALIZE = '0'
    
    # Cache for values to use when no app context is available
    _cache = {}
    
    def get_setting(self, key, default=None):
        """Get a setting value by key."""
        if not has_app_context():
            logger.debug(f"No app context when getting {key}, using cache or default")
            return self._cache.get(key, self._get_class_default(key, default))
            
        try:
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                # Update cache
                self._cache[key] = setting.value
                return setting.value
                
            # Use class default if available
            return self._get_class_default(key, default)
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return self._get_class_default(key, default)
    
    def _get_class_default(self, key, custom_default=None):
        """Get default value from class constants or custom default."""
        default_attr = f'DEFAULT_{key.upper()}'
        if hasattr(self, default_attr):
            return getattr(self, default_attr)
        return custom_default

    def set_setting(self, key, value):
        """Set or update a setting value."""
        # Always update cache regardless of app context
        self._cache[key] = value
        
        if not has_app_context():
            logger.debug(f"No app context when setting {key}, updated cache only")
            return True
            
        try:
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                setting = Setting(key=key, value=value)
                db.session.add(setting)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database error setting {key}: {e}")
            db.session.rollback()
            return False
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False
        
    def get(self, key, default=None):
        """Alias for get_setting."""
        return self.get_setting(key, default)
        
    def set(self, key, value):
        """Alias for set_setting."""
        return self.set_setting(key, value)
        
    def get_all_settings(self):
        """Get all settings as a dictionary."""
        if not has_app_context():
            logger.debug("No app context when getting all settings, returning cache")
            return self._cache.copy()
            
        try:
            settings = {setting.key: setting.value for setting in Setting.query.all()}
            # Update cache
            self._cache.update(settings)
            return settings
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return self._cache.copy()
        
    def is_setup_completed(self):
        """Check if setup has been completed."""
        try:
            return self.get_setting(self.SETUP_COMPLETED, 'false').lower() == 'true'
        except Exception as e:
            logger.error(f"Error checking setup completion: {e}")
            return False
        
    def mark_setup_completed(self):
        """Mark setup as completed."""
        return self.set_setting(self.SETUP_COMPLETED, 'true')
        
    def setup_defaults(self):
        """Set up default settings if they don't exist."""
        default_settings = {
            self.BASE_URL: self.DEFAULT_BASE_URL,
            self.ACE_ENGINE_URL: self.DEFAULT_ACE_ENGINE_URL,
            self.RESCRAPE_INTERVAL: self.DEFAULT_RESCRAPE_INTERVAL,
            self.AUDIO_NORMALIZE: self.DEFAULT_AUDIO_NORMALIZE,
            self.OUTPACE_ACE_COMPAT_KEY: self.DEFAULT_OUTPACE_ACE_COMPAT,
            self.OUTPACE_MAX_ACTIVE_UPSTREAMS_KEY: self.DEFAULT_OUTPACE_MAX_ACTIVE_UPSTREAMS,
            self.OUTPACE_MAX_PARALLEL_CONNECT_KEY: self.DEFAULT_OUTPACE_MAX_PARALLEL_CONNECT,
            self.OUTPACE_REQUEST_TIMEOUT_MS_KEY: self.DEFAULT_OUTPACE_REQUEST_TIMEOUT_MS,
            self.OUTPACE_CONNECT_TIMEOUT_MS_KEY: self.DEFAULT_OUTPACE_CONNECT_TIMEOUT_MS,
            self.OUTPACE_READ_TIMEOUT_MS_KEY: self.DEFAULT_OUTPACE_READ_TIMEOUT_MS,
            self.OUTPACE_CACHE_SIZE_MB_KEY: self.DEFAULT_OUTPACE_CACHE_SIZE_MB,
            self.OUTPACE_MAX_CONNECTIONS_PER_STREAM_KEY: self.DEFAULT_OUTPACE_MAX_CONNECTIONS_PER_STREAM,
            self.OUTPACE_ENABLE_INBOUND_KEY: self.DEFAULT_OUTPACE_ENABLE_INBOUND,
            self.OUTPACE_ENABLE_SEEDING_KEY: self.DEFAULT_OUTPACE_ENABLE_SEEDING,
            self.OUTPACE_CACHE_TYPE_KEY: self.DEFAULT_OUTPACE_CACHE_TYPE,
            self.OUTPACE_SEED_STORE_BYTES_KEY: self.DEFAULT_OUTPACE_SEED_STORE_BYTES
        }
        
        for key, value in default_settings.items():
            if Setting.query.filter_by(key=key).first() is None:
                self.set_setting(key, value)
                
    def import_from_json_config(self, config_data):
        """Import settings from a JSON configuration dictionary."""
        for key, value in config_data.items():
            self.set_setting(key, value)
        self.mark_setup_completed()
        
    def commit_cache_to_db(self):
        """Commit cached settings to the database if app context is available."""
        if not has_app_context() or not self._cache:
            return False
            
        try:
            for key, value in self._cache.items():
                setting = Setting.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                else:
                    setting = Setting(key=key, value=value)
                    db.session.add(setting)
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error committing cached settings: {e}")
            db.session.rollback()
            return False