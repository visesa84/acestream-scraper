import io
import tarfile
import zipfile
import subprocess
import requests
import psutil
import os
import time
from flask_restx import Namespace, Resource, fields
from app.models import AcestreamChannel, ScrapedURL
from app.utils.config import Config
from app.utils.platform_version import check_outpace_github_updates

api = Namespace('stats', description='Application statistics')

url_stats_model = api.model('URLStats', {
    'id': fields.String(description='ID of the URL'),
    'url': fields.String(description='URL being scraped'),
    'url_type': fields.String(description='Type of URL (regular, zeronet)'),
    'status': fields.String(description='Current status of the URL'),
    'last_processed': fields.DateTime(description='When the URL was last processed'),
    'channel_count': fields.Integer(description='Number of channels from this URL'),
    'enabled': fields.Boolean(description='Whether this URL is enabled'),
    'error_count': fields.Integer(description='Number of consecutive errors'),
    'last_error': fields.String(description='Last error message, if any')
})

stats_model = api.model('Stats', {
    'urls': fields.List(fields.Nested(url_stats_model), description='List of all tracked URLs'),
    'total_channels': fields.Integer(description='Total number of channels'),
    'channels_checked': fields.Integer(description='Number of channels with status checked'),
    'channels_online': fields.Integer(description='Number of online channels'),
    'channels_offline': fields.Integer(description='Number of offline channels'),
    'base_url': fields.String(description='Base URL for playlist generation'),
    'stream_mode': fields.String(description='Active stream mode'),
    'rescrape_interval': fields.Integer(description='Hours between automatic rescans'),
    'checkstatus_interval': fields.Integer(description='Hours between automatic check status'),
    'checkstatus_enabled': fields.Boolean(description='Whether automatic status check is enabled'),
    'task_manager_status': fields.String(description='Status of the background task manager'),
    'outpace_version': fields.String(description='Outpace engine version'),
    'outpace_update_available': fields.Boolean(description='Update available flag')
})

@api.route('/')
class Stats(Resource):
    @api.doc('get_stats')
    @api.marshal_with(stats_model)
    def get(self):
        """Get application statistics including URL and channel information."""
        try:
            urls = ScrapedURL.query.all()
            channels = AcestreamChannel.query.all()
            config = Config()
            
            total_channels = len(channels)
            channels_checked = sum(1 for ch in channels if ch.last_checked is not None)
            channels_online = sum(1 for ch in channels if ch.last_checked is not None and ch.is_online and ch.status == "active")
            channels_offline = sum(1 for ch in channels if ch.last_checked is not None and (not ch.is_online or ch.status == "disabled"))
            
            # --- Comprobación dinámica de versión y GitHub ---
            gh_check = check_outpace_github_updates()
            outpace_version = gh_check.get("version", "Unknown")
            update_available = gh_check.get("update_available", False)
            # ------------------------------------------------

            url_stats = []
            for url in urls:
                channel_count = AcestreamChannel.query.filter_by(source_url=url.url).count()
                
                url_stats.append({
                    'id': url.id,
                    'url': url.url,
                    'url_type': url.url_type,
                    'status': url.status,
                    'last_processed': url.last_processed, 
                    'channel_count': channel_count,
                    'enabled': url.status != 'disabled',
                    'error_count': url.error_count or 0,
                    'last_error': url.last_error
                })
            
            try:
                from app import task_manager
                task_status = "running" if task_manager and task_manager.running else "stopped"
            except ImportError:
                task_status = "unknown"
            
            return {
                'urls': url_stats,
                'total_channels': total_channels,
                'channels_checked': channels_checked, 
                'channels_online': channels_online,
                'channels_offline': channels_offline,
                'base_url': config.base_url,
                'stream_mode': config.stream_mode,
                'rescrape_interval': config.rescrape_interval,
                'checkstatus_interval': config.checkstatus_interval,
                'checkstatus_enabled': config.checkstatus_enabled,
                'task_manager_status': task_status,
                'outpace_version': outpace_version,
                'outpace_update_available': update_available
            }
        except Exception as e:
            api.abort(500, f"Error retrieving statistics: {str(e)}")

@api.route('/tv-channels/')
class TVChannelStats(Resource):
    @api.doc('get_tv_channel_stats')
    def get(self):
        """Get statistics about TV channels"""
        try:
            from app.models.tv_channel import TVChannel
            from sqlalchemy import func
            
            total_count = TVChannel.query.count()
            active_count = TVChannel.query.filter_by(is_active=True).count()
            with_epg_count = TVChannel.query.filter(TVChannel.epg_id.isnot(None)).count()
            acestreams_count = AcestreamChannel.query.filter(AcestreamChannel.tv_channel_id.isnot(None)).count()
            
            return {
                'total': total_count,
                'active': active_count,
                'with_epg': with_epg_count,
                'acestreams': acestreams_count
            }
        except Exception as e:
            api.abort(500, f"Error retrieving TV channel statistics: {str(e)}")

@api.route('/update')
class OutpaceUpdate(Resource):
    @api.doc('update_outpace_engine')
    def post(self):
        """Download, extract, replace the Outpace binary, and restart both engine instances automatically."""
        try:
            gh_check = check_outpace_github_updates()
            download_url = gh_check.get("download_url")
            
            if not download_url:
                return {"error": "No suitable binary found for your platform"}, 400
                
            binary_response = requests.get(download_url, timeout=30)
            if binary_response.status_code != 200:
                return {"error": "Failed to download binary from GitHub"}, 500
                
            target_path = "/usr/local/bin/outpace"
            content = binary_response.content
            
            # 1. Gestionar extracción si el asset descargado es un archivo comprimido
            binary_data = None
            if download_url.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                    executable_member = None
                    for member in tar.getmembers():
                        if member.name.endswith('outpace') or member.name == 'outpace':
                            executable_member = member
                            break
                    if not executable_member:
                        # Seleccionar el primer archivo regular si no coincide el nombre exacto
                        executable_member = next(m for m in tar.getmembers() if m.isfile())
                    binary_data = tar.extractfile(executable_member).read()
                    
            elif download_url.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    filename = next((name for name in z.namelist() if 'outpace' in name and not name.endswith('/')), z.namelist()[0])
                    binary_data = z.read(filename)
            else:
                # Si ya es un binario plano descargado directamente
                binary_data = content
                
            # 2. Guardar el binario extraído
            with open(target_path, "wb") as f:
                f.write(binary_data)
                
            # 3. Otorgar permisos de ejecución
            os.chmod(target_path, 0o755)
            
            # 4. Matar los procesos actuales de outpace
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'] == 'outpace' or (proc.info['exe'] and 'outpace' in proc.info['exe']):
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # 5. Relanzar ambas instancias con la configuración original
            log_dir = "/app/logs"
            os.makedirs(log_dir, exist_ok=True)
            
            # --- Instancia 1: Motor Principal (Puerto 6878) ---
            env_main = os.environ.copy()
            env_main.update({
                "OUTPACE_BIND": "0.0.0.0:6878",
                "OUTPACE_RTMP_BIND": "0.0.0.0:1935",
                "OUTPACE_PEER_LISTEN": "0.0.0.0:8621",
                "OUTPACE_DATA_DIR": "/root/.local/share/outpace",
                "OUTPACE_EXPERIMENTAL_ACE_COMPAT": "1",
                "OUTPACE_MAX_ACTIVE_UPSTREAMS": "6",
                "OUTPACE_MAX_PARALLEL_CONNECT": "16",
                "OUTPACE_REQUEST_TIMEOUT_MS": "3500",
                "OUTPACE_CONNECT_TIMEOUT_MS": "5000",
                "OUTPACE_READ_TIMEOUT_MS": "10000",
                "OUTPACE_CACHE_SIZE_MB": "128",
                "OUTPACE_MAX_CONNECTIONS_PER_STREAM": "35"
            })
            log_main = open(f"{log_dir}/outpace.log", "a")
            subprocess.Popen(["outpace", "serve"], env=env_main, stdout=log_main, stderr=subprocess.STDOUT)
            
            # Pausa de 3 segundos
            time.sleep(3)

            # --- Instancia 2: Motor de Comprobación de Streams (Puerto 6879) ---
            env_check = os.environ.copy()
            env_check.update({
                "OUTPACE_BIND": "0.0.0.0:6879",
                "OUTPACE_PEER_LISTEN": "0.0.0.0:8622",
                "OUTPACE_DATA_DIR": "/root/.local/share/outpace_check",
                "OUTPACE_EXPERIMENTAL_ACE_COMPAT": "1",
                "OUTPACE_MAX_ACTIVE_UPSTREAMS": "4",
                "OUTPACE_MAX_PARALLEL_CONNECT": "8",
                "OUTPACE_REQUEST_TIMEOUT_MS": "3500",
                "OUTPACE_CONNECT_TIMEOUT_MS": "5000",
                "OUTPACE_READ_TIMEOUT_MS": "10000",
                "OUTPACE_CACHE_SIZE_MB": "32"
            })
            env_check.pop("OUTPACE_RTMP_BIND", None)
            
            log_check = open(f"{log_dir}/outpace_check_stream.log", "a")
            subprocess.Popen(["outpace", "serve"], env=env_check, stdout=log_check, stderr=subprocess.STDOUT)

            return {
                "success": True, 
                "message": "Outpace updated and successfully extracted/restarted in the background."
            }
        except Exception as e:
            api.abort(500, f"Error updating Outpace engine: {str(e)}")