import logging
import requests
import json
from typing import Dict, Any, List, Optional, Tuple

from app.extensions import db
from app.utils.config import Config

logger = logging.getLogger(__name__)

class AcestreamSearchService:
    """Service for searching Acestream channels via the engine API."""
    
    def __init__(self, engine_url: str = None):
        """Initialize search service with fixed engine URL."""
        # URL actualizada para la búsqueda en AceStream
        self.engine_url = "https://search.acestream.net"
        
        logger.debug(f"Acestream Search Service initialized with fixed engine URL: {self.engine_url}")
    
    def search(self, query: str = "", page: int = 1, page_size: int = 10, category: str = "") -> Dict[str, Any]:
        """
        Search for Acestream channels using the engine API.
        
        Args:
            query: The search query string (optional, defaults to empty string for all channels)
            page: Page number for pagination (1-based)
            page_size: Number of results per page
            category: Filter by category (optional)
            
        Returns:
            Dict containing search results, pagination info, and status
        """
        try:
            # Endpoint raíz con los parámetros solicitados
            search_url = self.engine_url
            api_page = page - 1
            
            params = {
                'method': 'search',
                'query': query,
                'api_version': 1,
                'api_key': 'test_api_key',
                'page': api_page,
                'page_size': page_size,
                'show_epg': 1
            }
            
            if category:
                params['category'] = category
            
            headers = {
                'User-Agent': 'AceStream/3.1'
            }
            
            # allow_redirects=True para manejar el 301 Moved Permanently hacia api.acestream.me
            response = requests.get(search_url, params=params, headers=headers, allow_redirects=True, timeout=10)
            logger.info(f"Search API response status code: {response.status_code}")
            
            if response.status_code == 200:
                raw_response = response.text
                try:
                    search_data = response.json()
                    # Adaptado al nuevo formato JSON plano de la API de AceStream
                    raw_results = search_data.get('results', [])
                    total_results = search_data.get('total', 0)
                    
                    processed_results = []
                    for result in raw_results:
                        if 'items' in result and isinstance(result['items'], list) and len(result['items']) > 0:
                            for item in result['items']:
                                infohash = item.get('infohash')
                                processed_item = {
                                    'name': result.get('name', 'Unnamed Channel'),
                                    'id': infohash,  # Se asigna directamente el infohash como id
                                    'categories': item.get('categories', []),
                                    'bitrate': item.get('bitrate', 0)
                                }
                                for key, value in item.items():
                                    if key not in processed_item:
                                        processed_item[key] = value
                                processed_results.append(processed_item)
                        else:
                            result_id = result.get('infohash', result.get('id', ''))
                            if result_id:
                                result['id'] = result_id
                                processed_results.append(result)
                    
                    result = {
                        'success': True,
                        'message': 'Search successful',
                        'results': processed_results,
                        'pagination': {
                            'page': page,
                            'page_size': page_size,
                            'total_results': total_results,
                            'total_pages': (total_results + page_size - 1) // page_size if total_results > 0 else 0
                        }
                    }
                    return result
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse JSON response: {json_err}")
                    return {
                        'success': False,
                        'message': f"Failed to parse API response: {json_err}",
                        'results': [],
                        'pagination': {'page': page, 'page_size': page_size, 'total_results': 0, 'total_pages': 0}
                    }
            else:
                error_msg = f"Acestream search failed with status code {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'results': [],
                    'pagination': {'page': page, 'page_size': page_size, 'total_results': 0, 'total_pages': 0}
                }
        except Exception as e:
            error_msg = f"Error searching Acestream: {str(e)}"
            logger.error(error_msg)
            logger.exception("Exception details:")
            return {
                'success': False,
                'message': error_msg,
                'results': [],
                'pagination': {'page': page, 'page_size': page_size, 'total_results': 0, 'total_pages': 0}
            }
    
    def search_all_pages(self, query: str = "", page_size: int = 100, category: str = "", max_pages: int = 10) -> Dict[str, Any]:
        all_processed_results = []
        seen_ids = set()
        current_page = 1
        total_pages = 1
        
        while current_page <= total_pages and current_page <= max_pages:
            try:
                search_url = self.engine_url
                api_page = current_page - 1
                
                params = {
                    'method': 'search',
                    'query': query,
                    'api_version': 1,
                    'api_key': 'test_api_key',
                    'page': api_page,
                    'page_size': page_size,
                    'show_epg': 1
                }
                if category:
                    params['category'] = category
                
                headers = {
                    'User-Agent': 'AceStream/3.1'
                }
                
                response = requests.get(search_url, params=params, headers=headers, allow_redirects=True, timeout=10)
                if response.status_code != 200:
                    break
                    
                search_data = response.json()
                raw_results = search_data.get('results', [])
                total_results = search_data.get('total', 0)
                
                if total_results > 0 and page_size > 0:
                    total_pages = (total_results + page_size - 1) // page_size

                for result in raw_results:
                    if 'items' in result and isinstance(result['items'], list) and len(result['items']) > 0:
                        for item in result['items']:
                            infohash = item.get('infohash')
                            if infohash and infohash not in seen_ids:
                                seen_ids.add(infohash)
                                processed_item = {
                                    'name': result.get('name', 'Unnamed Channel'),
                                    'id': infohash,  # Se asigna directamente el infohash como id
                                    'categories': item.get('categories', []),
                                    'bitrate': item.get('bitrate', 0)
                                }
                                for key, value in item.items():
                                    if key not in processed_item:
                                        processed_item[key] = value
                                all_processed_results.append(processed_item)
                    else:
                        result_id = result.get('infohash', result.get('id', ''))
                        if result_id:
                            if result_id not in seen_ids:
                                seen_ids.add(result_id)
                                result['id'] = result_id
                                all_processed_results.append(result)

                current_page += 1
            except Exception as e:
                logger.error(f"Error reading page {current_page}: {e}")
                break

        return {
            'success': True,
            'message': 'Deep search completed',
            'results': all_processed_results
        }
    
    def extract_acestream_id(self, url: str) -> Optional[str]:
        if url.startswith('acestream://'):
            return url.split('acestream://')[1]
        return None
    
    def get_content_id(self, infohash: str) -> Optional[str]:
        # Método adaptado para devolver directamente el infohash al no admitirlo el nuevo motor
        return infohash