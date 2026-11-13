from flask_restx import Namespace, Resource, fields
from flask import request
import os
import requests
from app.repositories import SettingsRepository
from app.utils.config import Config
from app.extensions import db
import logging
from app.models.acestream_channel import AcestreamChannel

logger = logging.getLogger(__name__)

api = Namespace('config', description='Configuration management')

base_url_model = api.model('BaseURL', {
    'base_url': fields.String(required=False, description='Base URL for acestream links')
})

stream_mode_model = api.model('StreamMode', {
    'stream_mode': fields.String(required=True, description='Stream playback mode (traditional or hls)')
})

rescrape_interval_model = api.model('RescrapeInterval', {
    'hours': fields.Integer(required=True, description='Hours between automatic rescans')
})

checkstatus_interval_model = api.model('CheckStatusInterval', {
    'hours': fields.Integer(required=True, description='Hours between automatic rescans'),
    'enabled': fields.Boolean(required=True, description='Whether automatic status check is enabled')
})

audio_normalize_model = api.model('AudioNormalize', {
    'audio_normalize': fields.Integer(required=True, description='1 to enable OUTPACE_LIVE_AUDIO_NORMALIZE, 0 to disable')
})

@api.route('/base_url')
class BaseURL(Resource):
    def get(self):
        """Get the current base URL."""
        config = Config()
        return {"base_url": config.base_url}, 200
        
    @api.doc('update_base_url')
    @api.expect(base_url_model)
    def put(self):
        """Update base URL for acestream links (now optional)."""
        data = request.json or {}
        base_url = data.get('base_url', '')
        
        try:
            config = Config()
            config.base_url = base_url.strip()
            return {"message": "Base URL updated successfully"}
        except Exception as e:
            api.abort(500, str(e))

@api.route('/stream_mode')
class StreamMode(Resource):
    def get(self):
        """Get the current stream mode."""
        config = Config()
        return {"stream_mode": config.stream_mode}, 200
        
    @api.doc('update_stream_mode')
    @api.expect(stream_mode_model)
    def put(self):
        """Update stream playback mode (traditional or hls)."""
        data = request.json or {}
        mode = data.get('stream_mode')
        
        if mode not in ('traditional', 'hls'):
            api.abort(400, "Invalid stream mode. Must be 'traditional' or 'hls'")
        
        try:
            config = Config()
            config.stream_mode = mode
            return {"message": "Stream mode updated successfully", "stream_mode": mode}
        except Exception as e:
            api.abort(500, str(e))

@api.route('/rescrape_interval')
class RescrapeInterval(Resource):
    @api.doc('get_rescrape_interval')
    def get(self):
        """Get current URL rescrape interval."""
        try:
            config = Config()
            return {"hours": config.rescrape_interval}
        except Exception as e:
            api.abort(500, str(e))
    
    @api.doc('update_rescrape_interval')
    @api.expect(rescrape_interval_model)
    def put(self):
        """Update URL rescrape interval."""
        data = request.json
        hours = data.get('hours')
        
        if not hours:
            api.abort(400, "hours is required")
        
        try:
            config = Config()
            config.rescrape_interval = int(hours)
            return {"message": "Rescrape interval updated successfully"}
        except Exception as e:
            api.abort(500, str(e))

@api.route('/checkstatus_interval')
class CheckStatusInterval(Resource):
    @api.doc('get_checkstatus_interval')
    def get(self):
        """Get current Streams check status interval and enabled status."""
        try:
            config = Config()
            return {
                "hours": config.checkstatus_interval,
                "enabled": config.checkstatus_enabled
            }
        except Exception as e:
            api.abort(500, str(e))
    
    @api.doc('update_checkstatus_interval')
    @api.expect(checkstatus_interval_model)
    def put(self):
        """Update Streams check status configuration."""
        data = request.json
        hours = data.get('hours')
        enabled = data.get('enabled')
        
        try:
            config = Config()
            if hours is not None:
                config.checkstatus_interval = int(hours)
            if enabled is not None:
                config.checkstatus_enabled = bool(enabled)
                
            return {"message": "Configuration updated successfully"}, 200
        except Exception as e:
            api.abort(500, str(e))

@api.route('/setup_completed')
class SetupCompleted(Resource):
    @api.doc('mark_setup_completed')
    @api.expect(api.model('SetupCompleted', {
        'completed': fields.Boolean(required=True, description='Setup completion status')
    }))
    @api.response(200, 'Setup status updated')
    def put(self):
        """Mark setup as completed."""
        try:
            data = request.json
            config = Config()
            
            if data.get('completed'):
                config.settings_repo.mark_setup_completed()
                logger.info("Setup marked as completed")
                return {'message': 'Setup completed successfully'}, 200
            
            return {'message': 'Invalid request'}, 400
            
        except Exception as e:
            logger.error(f"Error updating setup status: {e}")
            api.abort(500, str(e))

@api.route('/audio_normalize')
class AudioNormalize(Resource):
    def get(self):
        """Get current OUTPACE_LIVE_AUDIO_NORMALIZE status."""
        try:
            repo = SettingsRepository()
            val = repo.get('outpace_live_audio_normalize', '0')
            return {"audio_normalize": int(val)}, 200
        except Exception as e:
            api.abort(500, str(e))
    
    @api.doc('update_audio_normalize')
    @api.expect(audio_normalize_model)
    def put(self):
        """Update OUTPACE_LIVE_AUDIO_NORMALIZE and restart Outpace engine."""
        data = request.json or {}
        raw_val = data.get('audio_normalize', 0)
        
        val_str = '1' if (raw_val is True or raw_val == 1 or raw_val == '1' or raw_val == 'true') else '0'
        
        try:
            repo = SettingsRepository()
            success = repo.set('outpace_live_audio_normalize', val_str)
            if not success:
                api.abort(500, "Error al guardar la normalización de audio en la base de datos.")
            
            # Actualizamos la variable de entorno actual
            os.environ['OUTPACE_LIVE_AUDIO_NORMALIZE'] = val_str
            
            # Enviamos señal SIGUSR2 al proceso supervisor para reiniciar Outpace
            supervisor_pid = os.environ.get('OUTPACE_SUPERVISOR_PID')
            if supervisor_pid:
                import signal
                os.kill(int(supervisor_pid), signal.SIGUSR2)
                logger.info(f"Sent SIGUSR2 signal to supervisor to restart Outpace with setting: {val_str}")
            
            return {"message": "Audio normalization updated and Outpace restart triggered", "audio_normalize": int(val_str)}, 200
        except Exception as e:
            logger.error(f"Error updating audio normalization: {e}")
            api.abort(500, str(e))