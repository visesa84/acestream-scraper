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
        """Initialize search service with engine URL."""
        self.engine_url = "http://localhost:6879/search"
        
        logger.debug(f"Outpace Search Service initialized with engine URL: {self.engine_url}")
    
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
            search_url = self.engine_url
            
            params = {
                'query': query,
                'page': page - 1,
                'page_size': page_size
            }
            
            if category:
                params['category'] = category
            
            headers = {
                'User-Agent': 'AceStream/3.1'
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            logger.info(f"Search API response status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    search_data = response.json()
                    # Adaptado a la estructura {"error": null, "result": {"results": [...]}}
                    res_container = search_data.get('result', {})
                    raw_results = res_container.get('results', [])
                    total_results = len(raw_results)  # O ajustarlo si el motor devuelve un campo total global
                    
                    processed_results = []
                    for result in raw_results:
                        channel_name = result.get('name', 'Unnamed Channel')
                        items = result.get('items', [])
                        
                        if items and isinstance(items, list):
                            for item in items:
                                infohash = item.get('infohash')
                                if infohash:
                                    # Aseguramos que el ID lleve el prefijo ih: como se acordó en el proyecto
                                    formatted_id = f"ih:{infohash}" if not infohash.startswith('ih:') else infohash
                                    
                                    processed_item = {
                                        'name': item.get('name', channel_name),
                                        'id': formatted_id,
                                        'infohash': infohash,
                                        'bitrate': item.get('bitrate', 0),
                                        'categories': item.get('categories', []),
                                        'countries': item.get('countries', []),
                                        'languages': item.get('languages', []),
                                        'availability': item.get('availability', 0.0)
                                    }
                                    processed_results.append(processed_item)
                        else:
                            infohash = result.get('infohash')
                            if infohash:
                                formatted_id = f"ih:{infohash}" if not infohash.startswith('ih:') else infohash
                                result['id'] = formatted_id
                                processed_results.append(result)
                    
                    result_dict = {
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
                    return result_dict
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
        
        while current_page <= max_pages:
            try:
                params = {
                    'query': query,
                    'page': current_page - 1,
                    'page_size': page_size
                }
                if category:
                    params['category'] = category
                
                response = requests.get(self.engine_url, params=params, timeout=10)
                if response.status_code != 200:
                    break
                    
                search_data = response.json()
                res_container = search_data.get('result', {})
                raw_results = res_container.get('results', [])
                
                if not raw_results:
                    break

                for result in raw_results:
                    channel_name = result.get('name', 'Unnamed Channel')
                    items = result.get('items', [])
                    
                    if items and isinstance(items, list):
                        for item in items:
                            infohash = item.get('infohash')
                            if infohash and infohash not in seen_ids:
                                seen_ids.add(infohash)
                                formatted_id = f"ih:{infohash}" if not infohash.startswith('ih:') else infohash
                                processed_item = {
                                    'name': item.get('name', channel_name),
                                    'id': formatted_id,
                                    'infohash': infohash,
                                    'bitrate': item.get('bitrate', 0),
                                    'categories': item.get('categories', []),
                                    'availability': item.get('availability', 0.0)
                                }
                                all_processed_results.append(processed_item)

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
        return infohash if infohash.startswith('ih:') else f"ih:{infohash}"