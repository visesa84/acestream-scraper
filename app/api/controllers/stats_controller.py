import io
import tarfile
import zipfile
import requests
import psutil
import os
import signal
import tempfile
from flask_restx import Namespace, Resource, fields
from app.models import AcestreamChannel, ScrapedURL
from app.utils.config import Config
from app.utils.platform_version import (
    check_kubo_github_updates,
    check_outpace_github_updates,
    get_kubo_update_arch,
    get_local_kubo_version
)

api = Namespace('stats', description='Application statistics')

url_stats_model = api.model('URLStats', {
    'id': fields.String(description='ID of the URL'),
    'url': fields.String(description='URL being scraped'),
    'url_type': fields.String(description='Type of URL (regular, zeronet, ipfs)'),
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
    'outpace_update_available': fields.Boolean(description='Update available flag'),
    'ipfs_enabled': fields.Boolean(description='Whether Kubo IPFS is enabled'),
    'ipfs_running': fields.Boolean(description='Whether the Kubo daemon is running'),
    'ipfs_version': fields.String(description='Installed Kubo version'),
    'ipfs_update_available': fields.Boolean(description='Whether a Kubo update is available')
})

def is_kubo_running():
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            process_info = process.info
        except psutil.Error:
            continue
        if (
            (process_info.get("name") or "").lower() == "ipfs"
            and "daemon" in (process_info.get("cmdline") or [])
        ):
            return True
    return False

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
            ipfs_enabled = os.environ.get("ENABLE_IPFS", "false").lower() == "true"
            ipfs_running = False
            ipfs_version = "N/A"
            ipfs_update_available = False
            if ipfs_enabled:
                ipfs_version = get_local_kubo_version()
                ipfs_running = is_kubo_running()
                ipfs_check = check_kubo_github_updates(ipfs_version)
                ipfs_update_available = ipfs_check.get("update_available", False)

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
                'outpace_update_available': update_available,
                'ipfs_enabled': ipfs_enabled,
                'ipfs_running': ipfs_running,
                'ipfs_version': ipfs_version,
                'ipfs_update_available': ipfs_update_available
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
        """Download and replace Outpace, then ask the entrypoint to restart both instances."""
        supervisor_pid = os.environ.get("OUTPACE_SUPERVISOR_PID")
        if not supervisor_pid:
            return {"error": "Outpace supervisor is not available"}, 503

        try:
            supervisor_pid = int(supervisor_pid)
            os.kill(supervisor_pid, 0)
        except (ValueError, ProcessLookupError, PermissionError):
            return {"error": "Outpace supervisor is not available"}, 503

        temporary_path = None
        try:
            gh_check = check_outpace_github_updates()
            download_url = gh_check.get("download_url")

            if not download_url:
                return {"error": "No suitable binary found for your platform"}, 400

            binary_response = requests.get(download_url, timeout=30)
            binary_response.raise_for_status()
            content = binary_response.content

            if download_url.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                    members = tar.getmembers()
                    executable_member = next(
                        (member for member in members if member.isfile() and member.name.endswith("outpace")),
                        next((member for member in members if member.isfile()), None)
                    )
                    if executable_member is None:
                        raise ValueError("Outpace archive contains no executable file")
                    binary = tar.extractfile(executable_member)
                    if binary is None:
                        raise ValueError("Could not read the Outpace binary")
                    with binary:
                        binary_data = binary.read()
            elif download_url.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    filenames = [name for name in z.namelist() if not name.endswith('/')]
                    filename = next(
                        (name for name in filenames if "outpace" in name.lower()),
                        next(iter(filenames), None)
                    )
                    if filename is None:
                        raise ValueError("Outpace archive contains no executable file")
                    binary_data = z.read(filename)
            else:
                binary_data = content

            target_path = "/usr/local/bin/outpace"
            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(target_path),
                prefix=".outpace-update-",
                delete=False
            ) as temporary_binary:
                temporary_path = temporary_binary.name
                temporary_binary.write(binary_data)

            os.chmod(temporary_path, 0o755)
            os.replace(temporary_path, target_path)
            temporary_path = None
            os.kill(supervisor_pid, signal.SIGUSR2)
            return {
                "success": True,
                "message": "Outpace updated; both engine instances are restarting."
            }
        except Exception as e:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
            api.abort(500, f"Error updating Outpace engine: {str(e)}")

@api.route('/ipfs/update')
class KuboUpdate(Resource):
    @api.doc('update_kubo_ipfs')
    def post(self):
        """Download the latest supported Kubo binary and restart the managed daemon."""
        if os.environ.get("ENABLE_IPFS", "false").lower() != "true":
            return {"error": "Kubo IPFS is not enabled"}, 409
        if get_kubo_update_arch() is None:
            return {"error": "Kubo updates are not supported on this architecture"}, 400

        supervisor_pid = os.environ.get("IPFS_SUPERVISOR_PID")
        if not supervisor_pid:
            return {"error": "Kubo supervisor is not available"}, 503

        try:
            os.kill(int(supervisor_pid), 0)
        except (ValueError, ProcessLookupError, PermissionError):
            return {"error": "Kubo supervisor is not available"}, 503

        try:
            local_version = get_local_kubo_version()
            update = check_kubo_github_updates(local_version)
            download_url = update.get("download_url")
            if not update.get("update_available") or not download_url:
                return {"error": "No Kubo update is available"}, 409

            target_path = "/usr/local/bin/ipfs"
            temporary_path = None
            with requests.get(download_url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with tempfile.TemporaryFile() as archive_file:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            archive_file.write(chunk)
                    archive_file.seek(0)

                    with tarfile.open(fileobj=archive_file, mode="r:gz") as archive:
                        member = archive.getmember("kubo/ipfs")
                        if not member.isfile():
                            raise ValueError("Kubo release archive has no regular ipfs binary")
                        binary = archive.extractfile(member)
                        if binary is None:
                            raise ValueError("Could not read the Kubo binary")

                        with tempfile.NamedTemporaryFile(
                            dir=os.path.dirname(target_path),
                            prefix=".ipfs-update-",
                            delete=False
                        ) as temporary_binary:
                            temporary_path = temporary_binary.name
                            with binary:
                                while chunk := binary.read(65536):
                                    temporary_binary.write(chunk)

            os.chmod(temporary_path, 0o755)
            os.replace(temporary_path, target_path)
            os.kill(int(supervisor_pid), signal.SIGUSR1)
            return {
                "success": True,
                "message": f"Kubo {update['latest_version']} installed; daemon restart requested."
            }
        except Exception as e:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)
            api.abort(500, f"Error updating Kubo IPFS: {str(e)}")