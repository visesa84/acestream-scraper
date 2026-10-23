from flask_restx import Namespace, Resource, fields
import requests
from requests.exceptions import RequestException
from app.utils.config import Config
import logging

logger = logging.getLogger(__name__)

api = Namespace('health', description='Health check endpoints')

health_model = api.model('HealthStatus', {
    'status': fields.String(required=True, description='System health status'),
    'app': fields.Boolean(required=True, description='Application status'),
    'database': fields.Boolean(required=True, description='Database status'),
    'acestream': fields.Boolean(description='Acestream/Outpace Engine status'),
    'task_manager': fields.Boolean(description='Task manager status'),
    'details': fields.Raw(description='Additional status details')
})

@api.route('/')
class HealthCheck(Resource):
    @api.doc('health_check')
    @api.marshal_with(health_model)
    def get(self):
        """Get system health status"""
        health_data = {
            'status': 'healthy',
            'app': True,
            'database': True,
            'acestream': True,
            'task_manager': False,
            'details': {}
        }
        
        try:
            # 1. Check database
            try:
                from app.extensions import db
                from sqlalchemy import text
                db.session.execute(text('SELECT 1'))
            except Exception as e:
                logger.error(f"Database check failed: {str(e)}")
                health_data['database'] = False
                health_data['status'] = 'degraded'
                health_data['details']['database_error'] = str(e)
            
            # 2. Check Acestream / Outpace Engine
            try:
                config = Config()
                ace_url = getattr(config, 'ace_engine_url', 'http://127.0.0.1:6878').rstrip('/')
                
                session = requests.Session()
                session.verify = False  # Desactivar verificación SSL para llamadas locales
                
                response = session.get(
                    f"{ace_url}/webui/api/service",
                    timeout=2,
                    headers={'Accept': 'application/json'}
                )
                health_data['acestream'] = response.status_code == 200
                if not health_data['acestream']:
                    health_data['status'] = 'degraded'
                    health_data['details']['acestream_error'] = f'Service returned {response.status_code}'
            except RequestException as e:
                logger.error(f"Acestream check failed: {str(e)}")
                health_data['acestream'] = False
                health_data['status'] = 'degraded'
                health_data['details']['acestream_error'] = str(e)
            
            # 3. Check Task Manager
            try:
                from app.views.main import task_manager
                if task_manager:
                    health_data['task_manager'] = task_manager.running
                    if not health_data['task_manager']:
                        health_data['status'] = 'degraded'
                        health_data['details']['task_manager_error'] = 'Not running'
                else:
                    health_data['details']['task_manager_error'] = 'Task manager not initialized'
            except Exception as e:
                logger.error(f"Task manager check failed: {str(e)}")
                health_data['task_manager'] = False
                health_data['status'] = 'degraded'
                health_data['details']['task_manager_error'] = str(e)

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            health_data['status'] = 'error'
            health_data['app'] = False
            health_data['details']['error'] = str(e)
        
        return health_data