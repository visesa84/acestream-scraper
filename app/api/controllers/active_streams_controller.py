from flask_restx import Namespace, Resource
from flask import current_app
import requests
from app.utils.config import Config

api = Namespace('active-streams', description='Active streams monitoring')

@api.route('')
class ActiveStreamsResource(Resource):
    @api.doc('get_active_streams')
    def get(self):
        """Get active streams and telemetry from AceStream/Outpace engine."""
        config = Config()
        ace_url = getattr(config, 'ace_engine_url', 'http://127.0.0.1:6878').rstrip('/')
        
        sessions = []
        try:
            # 1. Consultar los streams activos generales del motor
            resp = requests.get(f"{ace_url}/streams", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                streams_list = data.get('streams', [])
                
                for stream in streams_list:
                    stream_id = stream.get('id') or stream.get('infohash') or stream.get('content_id')
                    metadata = stream.get('metadata', {})
                    title = metadata.get('title', 'Unknown Channel')
                    
                    speed_down = 0.0
                    peers = 0
                    bitrate = 0
                    
                    if stream_id:
                        try:
                            # Limpiamos prefijos como 'ih:' o 'cid:' para obtener el hash puro
                            clean_id = str(stream_id).replace('ih:', '').replace('cid:', '').strip()
                            
                            # Determinamos si el stream usa infohash o content_id tradicional
                            is_infohash = str(stream_id).startswith('ih:') or len(clean_id) == 40
                            
                            params = {'format': 'json'}
                            if is_infohash:
                                params['infohash'] = clean_id
                            else:
                                params['content_id'] = clean_id
                            
                            getstream_resp = requests.get(
                                f"{ace_url}/ace/getstream",
                                params=params,
                                timeout=2
                            )
                            current_app.logger.info(f"Getstream response for {clean_id}: status {getstream_resp.status_code}")
                            
                            if getstream_resp.status_code == 200:
                                gs_data = getstream_resp.json()
                                gs_response = gs_data.get('response', {})
                                stat_url = gs_response.get('stat_url')
                                
                                current_app.logger.info(f"Stat URL found: {stat_url}")

                                if stat_url:
                                    stat_resp = requests.get(stat_url, timeout=2)
                                    if stat_resp.status_code == 200:
                                        stat_data = stat_resp.json()
                                        stat_res = stat_data.get('response', {})
                                        speed_down = stat_res.get('speed_down', 0.0)
                                        peers = stat_res.get('peers', 0)
                                        bitrate = stat_res.get('metadata', {}).get('bitrate', 0)
                        except Exception as inner_err:
                            current_app.logger.error(f"Error fetching telemetry for stream {stream_id}: {inner_err}")

                    sessions.append({
                        'channel_id': stream_id,
                        'title': title,
                        'speed_down': speed_down,
                        'peers': peers,
                        'bitrate': bitrate
                    })
                    
                return {
                    'total_streams': len(sessions),
                    'active_sessions': sessions
                }
        except Exception as e:
            current_app.logger.error(f"Error getting active streams from engine: {e}")
            
        return {'total_streams': 0, 'active_sessions': []}