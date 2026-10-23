import platform
import requests
import time

# --- Caché en memoria para evitar superar el límite de peticiones de GitHub ---
_github_cache = {
    "data": None,
    "timestamp": 0
}
CACHE_TTL = 3600  # 2 horas en segundos

def get_local_outpace_version():
    """Consulta la API local de Outpace para obtener la versión instalada de forma dinámica."""
    try:
        response = requests.get("http://127.0.0.1:6878/server/api?method=get_version", timeout=2)
        if response.status_code == 200:
            v_data = response.json()
            res_obj = v_data.get('result')
            if isinstance(res_obj, dict):
                return res_obj.get('version', 'Unknown')
            elif isinstance(res_obj, str):
                return res_obj
    except Exception:
        pass
    return "Unknown"

def compare_versions(latest_tag, local_version):
    """Compara de forma segura dos versiones semánticas."""
    def parse_v(v_str):
        return tuple(int(x) for x in v_str.split(".") if x.isdigit())
    if not latest_tag:
        return False
    try:
        return parse_v(latest_tag) > parse_v(local_version)
    except ValueError:
        return latest_tag != local_version

def check_outpace_github_updates():
    """Obtiene la versión local y contrasta con la última release de GitHub utilizando caché temporal."""
    global _github_cache
    current_time = time.time()
    
    local_version = get_local_outpace_version()
    
    if local_version == "Unknown":
        return {
            "version": "Unknown",
            "latest_version": "Unknown",
            "update_available": False,
            "download_url": None,
            "detected_platform": "unknown"
        }

    # Si la caché sigue vigente, la reutilizamos actualizando únicamente la versión local actual
    if _github_cache["data"] and (current_time - _github_cache["timestamp"]) < CACHE_TTL:
        cached_res = _github_cache["data"].copy()
        cached_res["version"] = local_version
        latest_tag = cached_res.get("latest_version", local_version)
        cached_res["update_available"] = compare_versions(latest_tag, local_version)
        return cached_res

    try:
        # 1. Consultar la API oficial de GitHub Releases
        api_url = "https://api.github.com/repos/jamezrin/outpace/releases/latest"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Acestream-Scraper-Client"
        }
        response = requests.get(api_url, headers=headers, timeout=3)
        
        if response.status_code != 200:
            # Si GitHub limita o falla temporalmente, usamos la caché anterior si existe
            if _github_cache["data"]:
                cached_res = _github_cache["data"].copy()
                cached_res["version"] = local_version
                return cached_res
            return {"version": local_version, "update_available": False, "latest_version": local_version}
            
        release_data = response.json()
        latest_tag = release_data.get("tag_name", "").lstrip("v")
        assets = release_data.get("assets", [])
        
        # 2. Detectar la arquitectura y sistema operativo actual
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if machine in ["x86_64", "amd64"]:
            arch_keywords = ["amd64", "x86_64", "x64"]
        elif machine in ["aarch64", "armv8"]:
            arch_keywords = ["arm64", "aarch64"]
        elif machine in ["arm", "hf", "armv7l"]:
            arch_keywords = ["armv7"]
        else:
            arch_keywords = [machine]
            
        # 3. Buscar el archivo binario correspondiente
        download_url = None
        for asset in assets:
            name = asset.get("name", "").lower()
            matches_system = system in name or "linux" in name
            matches_arch = any(ak in name for ak in arch_keywords)
            
            if matches_system and matches_arch:
                download_url = asset.get("browser_download_url")
                break
                
        if not download_url and len(assets) == 1:
            download_url = assets[0].get("browser_download_url")
                
        # 4. Comparar versiones
        update_available = compare_versions(latest_tag, local_version)

        result = {
            "version": local_version,
            "latest_version": latest_tag or local_version,
            "update_available": update_available,
            "download_url": download_url,
            "detected_platform": f"{system}-{machine}"
        }

        # Guardar en caché el resultado obtenido
        _github_cache["data"] = result
        _github_cache["timestamp"] = current_time

        return result
    except Exception as e:
        if _github_cache["data"]:
            cached_res = _github_cache["data"].copy()
            cached_res["version"] = local_version
            return cached_res
        return {"version": local_version, "update_available": False, "latest_version": local_version}
