import os
import base64
import time
import html
from datetime import datetime
from flask import request
from urllib.parse import urlparse, quote
from typing import List, Dict, Optional
from ..repositories import ChannelRepository
from app.utils.config import Config
from app.repositories.tv_channel_repository import TVChannelRepository
from app.services.tv_channel_service import TVChannelService
from app.models.acestream_channel import AcestreamChannel

class PlaylistService:
    def __init__(self):
        self.channel_repository = ChannelRepository()
        self.config = Config()
        self.tv_channel_repository = TVChannelRepository()
        self.tv_channel_service = TVChannelService()
    
    def get_basic_auth_credentials(self):
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Basic "):
            return None, None

        encoded = auth.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        user, password = decoded.split(":", 1)
        return user, password

    def _format_stream_url(self, channel_id: str, local_id: int, base_url: str = None) -> str:
        def is_ip_address(h):
            parts = h.split(".")
            return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

        def is_local_host(h):
            return h in ('localhost', '127.0.0.1') or h.startswith('192.168.') or h.startswith('10.') or h.startswith('172.')

        if base_url:
            base_url = base_url.strip().rstrip("/")
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                if is_ip_address(base_url) or is_local_host(base_url):
                    base_url = "http://" + base_url
                else:
                    base_url = "https://" + base_url
        else:
            base_url = request.host_url.rstrip('/')

        parsed = urlparse(base_url)

        scheme = parsed.scheme
        if is_local_host(parsed.hostname or ''):
            scheme = 'http'

        rp_user, rp_pass = self.get_basic_auth_credentials()
        auth_str = ""
        if rp_user and rp_pass:
            safe_user = quote(rp_user, safe='')
            safe_pass = quote(rp_pass, safe='')
            auth_str = f"{safe_user}:{safe_pass}@"

        host = f"{scheme}://{auth_str}{parsed.netloc}"

        stream_mode = getattr(self.config, 'stream_mode', 'traditional')

        if stream_mode == 'hls':
            return f"{host}/streams/ace/cid:{channel_id}.m3u8"
        else:
            return f"{host}/ace/getstream?id={channel_id}"

    def _get_channels(self, search_term: str = None):
        """Retrieve active and online channels from the repository with optional search term."""
        query = self.channel_repository.model.query.filter(
            (self.channel_repository.model.status == 'active') &
            (self.channel_repository.model.is_online.is_(True))
        )
        if search_term:
            query = query.filter(self.channel_repository.model.name.ilike(f'%{search_term}%'))
        return query.all()

    def generate_playlist(self, search_term=None, base_url=None):
        """Generate M3U playlist with online channels."""
        playlist_lines = ['#EXTM3U']
        
        channels = self._get_channels(search_term)
        channels = sorted(channels, key=lambda c: (c.name or "").lower())
        
        name_counts = {}
        
        for local_id, channel in enumerate(channels, start=0):
            stream_url = self._format_stream_url(channel.id, local_id, base_url=base_url)
            
            base_name = (channel.name or "").strip()
            if base_name in name_counts:
                name_counts[base_name] += 1
                display_name = f"{base_name} #{name_counts[base_name]}"
            else:
                name_counts[base_name] = 1
                display_name = base_name
            
            metadata = []
            if channel.tvg_name:
                metadata.append(f'tvg-name="{channel.tvg_name}"')
            if channel.tvg_id:
                metadata.append(f'tvg-id="{channel.tvg_id}"')
            if channel.logo:
                metadata.append(f'tvg-logo="{channel.logo}"')
            if channel.group:
                metadata.append(f'group-title="{channel.group}"')
            
            extinf = '#EXTINF:-1'
            if metadata:
                extinf += f' {" ".join(metadata)}'
            extinf += f',{display_name}'
            
            playlist_lines.append(extinf)
            playlist_lines.append(stream_url)
            
        return '\n'.join(playlist_lines)
    
    def generate_tv_channels_playlist(self, search_term=None, favorites_only=False, base_url=None):
        """Generate M3U playlist with TV channels using only online acestreams."""
        playlist_lines = ['#EXTM3U']
        
        channels, total, _ = self.tv_channel_repository.filter_channels(
            search_term=search_term,
            favorites_only=favorites_only,
            per_page=1000
        )
        
        sorted_channels = sorted(
            channels, 
            key=lambda c: (c.channel_number is None, c.channel_number or 0, c.name.lower())
        )
        
        local_id = 0
        
        for tv_channel in sorted_channels:
            acestreams = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == tv_channel.id,
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            ).all()
            
            if not acestreams:
                continue
                
            def score_acestream(acestream):
                score = 0
                if acestream.is_online:
                    score += 10
                if acestream.logo:
                    score += 3
                if acestream.tvg_id:
                    score += 2
                if acestream.tvg_name:
                    score += 1
                return score
                
            sorted_acestreams = sorted(acestreams, key=score_acestream, reverse=True)
            
            for stream_index, acestream in enumerate(sorted_acestreams):
                stream_url = self._format_stream_url(acestream.id, local_id, base_url=base_url)
                local_id += 1
                
                display_name = tv_channel.name
                epg_id = tv_channel.epg_id if tv_channel.epg_id else acestream.tvg_id
                
                metadata = []
                
                if tv_channel.channel_number is not None:
                    metadata.append(f'tvg-chno="{tv_channel.channel_number}"')
                
                if epg_id:
                    metadata.append(f'tvg-id="{epg_id}"')
                    
                metadata.append(f'tvg-name="{display_name}"')
                
                if tv_channel.logo_url:
                    metadata.append(f'tvg-logo="{tv_channel.logo_url}"')
                elif acestream.logo:
                    metadata.append(f'tvg-logo="{acestream.logo}"')
                    
                if tv_channel.category:
                    metadata.append(f'group-title="{tv_channel.category}"')
                
                extinf = '#EXTINF:-1'
                if metadata:
                    extinf += f' {" ".join(metadata)}'
                extinf += f',{display_name}'
                
                playlist_lines.append(extinf)
                playlist_lines.append(stream_url)
            
        return '\n'.join(playlist_lines)

    def generate_epg_xml(self, search_term=None, favorites_only=False, base_url=None):
        """Generate XML EPG guide for channels with online associated acestreams."""
        from datetime import datetime, timedelta
        from app.repositories.epg_channel_repository import EPGChannelRepository
        from app.repositories.epg_program_repository import EPGProgramRepository
        import html
        
        xml_lines = [
            '<?xml version="1.0" encoding="utf-8" ?>',
            '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
            '<tv generator-info-name="Acestream Scraper Outpace Generator" generator-info-url="https://github.com/visesa84/acestream-scraper-outpace">'
        ]
        
        channels, _, _ = self.tv_channel_repository.filter_channels(
            search_term=search_term,
            favorites_only=favorites_only,
            is_active=True,
            per_page=1000
        )
        
        sorted_channels = sorted(
            channels, 
            key=lambda c: (c.channel_number is None, c.channel_number or 0, c.name.lower())
        )
        
        epg_channel_repo = EPGChannelRepository()
        epg_program_repo = EPGProgramRepository()
        
        channel_epg_mappings = []
        name_counts = {}
        
        for tv_channel in sorted_channels:
            online_count = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == tv_channel.id,
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            ).count()

            if not tv_channel.epg_id or online_count == 0:
                continue
                
            acestreams = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == tv_channel.id,
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            ).all()
            if not acestreams:
                continue
                
            def score_acestream(acestream):
                score = 0
                if acestream.is_online:
                    score += 10
                if acestream.logo:
                    score += 3
                if acestream.tvg_id:
                    score += 2
                if acestream.tvg_name:
                    score += 1
                return score
                
            sorted_acestreams = sorted(acestreams, key=score_acestream, reverse=True)
            epg_channels = epg_channel_repo.get_by_channel_xml_id(tv_channel.epg_id)
            epg_channel = epg_channels[0] if epg_channels else None
            
            base_name = tv_channel.name
            
            for stream_index, acestream in enumerate(sorted_acestreams):
                if len(sorted_acestreams) > 1:
                    display_name = f"{tv_channel.name} #{stream_index + 1}"
                    epg_id = tv_channel.epg_id
                else:
                    if base_name in name_counts:
                        name_counts[base_name] += 1
                        display_name = f"{base_name} #{name_counts[base_name]}"
                        epg_id = tv_channel.epg_id
                    else:
                        name_counts[base_name] = 1
                        display_name = base_name
                        epg_id = tv_channel.epg_id
                
                channel_epg_mappings.append({
                    'epg_id': epg_id,
                    'display_name': display_name,
                    'tv_channel': tv_channel,
                    'epg_channel': epg_channel,
                    'stream_index': stream_index,
                    'original_epg_id': tv_channel.epg_id
                })
        
        for mapping in channel_epg_mappings:
            epg_id = mapping['epg_id']
            display_name = mapping['display_name']
            tv_channel = mapping['tv_channel']
            xml_lines.append(f'  <channel id="{html.escape(epg_id)}">')
            xml_lines.append(f'    <display-name>{html.escape(display_name)}</display-name>')
            
            if tv_channel.logo_url:
                xml_lines.append(f'    <icon src="{html.escape(tv_channel.logo_url)}" />')
                
            if tv_channel.website:
                xml_lines.append(f'    <url>{html.escape(tv_channel.website)}</url>')
                
            xml_lines.append('  </channel>')
        
        xml_lines.append('')
        
        processed_epg_ids = set()
        
        for mapping in channel_epg_mappings:
            epg_id = mapping['epg_id']
            epg_channel = mapping['epg_channel']
            
            if not epg_channel or epg_id in processed_epg_ids:
                continue
            
            processed_epg_ids.add(epg_id)
            
            now = datetime.now()
            start_time = now - timedelta(hours=12)
            end_time = now + timedelta(days=7)
            
            programs = epg_program_repo.get_programs_for_channel(epg_channel.id, start_time, end_time)
            
            is_dst = time.localtime().tm_isdst
            offset_seconds = -(time.altzone if is_dst else time.timezone)
            
            h, m = divmod(abs(offset_seconds) // 60, 60)
            sign = '+' if offset_seconds >= 0 else '-'
            local_offset = f"{sign}{h:02d}{m:02d}"

            for program in programs:
                start_dt = datetime.fromisoformat(program['start_time'])
                end_dt = datetime.fromisoformat(program['end_time'])
                
                start_time_str = f"{start_dt.strftime('%Y%m%d%H%M%S')} {local_offset}"
                stop_time_str = f"{end_dt.strftime('%Y%m%d%H%M%S')} {local_offset}"
                
                xml_lines.append(f'  <programme start="{start_time_str}" stop="{stop_time_str}" channel="{html.escape(epg_id)}">')
                
                title = program.get('title', 'Untitled')
                xml_lines.append(f'    <title>{html.escape(str(title))}</title>')
                
                desc = program.get('description')
                if desc:
                    xml_lines.append(f'    <desc>{html.escape(str(desc))}</desc>')
                
                cat = program.get('category')
                if cat:
                    xml_lines.append(f'    <category>{html.escape(str(cat))}</category>')
                
                xml_lines.append('  </programme>')

        xml_lines.append('</tv>')
        return '\n'.join(xml_lines)
    
    def generate_all_streams_playlist(self, search_term=None, include_unassigned=True, base_url=None):
        """Generate M3U playlist with all online acestreams."""
        playlist_lines = ['#EXTM3U']
        local_id = 0
        name_counts = {}
        
        channels, _, _ = self.tv_channel_repository.filter_channels(
            search_term=search_term,
            per_page=1000
        )
        
        sorted_channels = sorted(
            channels, 
            key=lambda c: (c.channel_number is None, c.channel_number or 0, c.name.lower())
        )
        
        processed_acestreams = set()
        
        for tv_channel in sorted_channels:
            acestreams = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == tv_channel.id,
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            ).all()
            if not acestreams:
                continue
                
            def score_acestream(acestream):
                score = 0
                if acestream.is_online:
                    score += 10
                if acestream.logo:
                    score += 3
                if acestream.tvg_id:
                    score += 2
                if acestream.tvg_name:
                    score += 1
                return score
                
            sorted_acestreams = sorted(acestreams, key=score_acestream, reverse=True)
            
            for stream_index, acestream in enumerate(sorted_acestreams):
                processed_acestreams.add(acestream.id)
                
                stream_url = self._format_stream_url(acestream.id, local_id, base_url=base_url)
                local_id += 1
                
                base_name = tv_channel.name
                if len(sorted_acestreams) > 1:
                    display_name = f"{base_name} ({stream_index + 1})"
                else:
                    if base_name in name_counts:
                        name_counts[base_name] += 1
                        display_name = f"{base_name} #{name_counts[base_name]}"
                    else:
                        name_counts[base_name] = 1
                        display_name = base_name
                
                metadata = []
                
                if tv_channel.channel_number is not None:
                    if len(sorted_acestreams) > 1:
                        channel_number = f"{tv_channel.channel_number}.{stream_index + 1}"
                    else:
                        channel_number = str(tv_channel.channel_number)
                    metadata.append(f'tvg-chno="{channel_number}"')
                
                if tv_channel.epg_id:
                    metadata.append(f'tvg-id="{tv_channel.epg_id}"')
                elif acestream.tvg_id:
                    metadata.append(f'tvg-id="{acestream.tvg_id}"')
                    
                metadata.append(f'tvg-name="{display_name}"')
                
                if tv_channel.logo_url:
                    metadata.append(f'tvg-logo="{tv_channel.logo_url}"')
                elif acestream.logo:
                    metadata.append(f'tvg-logo="{acestream.logo}"')
                    
                if tv_channel.category:
                    metadata.append(f'group-title="{tv_channel.category}"')
                
                extinf = '#EXTINF:-1'
                if metadata:
                    extinf += f' {" ".join(metadata)}'
                extinf += f',{display_name}'
                
                playlist_lines.append(extinf)
                playlist_lines.append(stream_url)
        
        if include_unassigned:
            unassigned_query = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == None,
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            )
            if search_term:
                unassigned_query = unassigned_query.filter(
                    AcestreamChannel.name.ilike(f'%{search_term}%')
                )
                
            unassigned_acestreams = unassigned_query.all()
            
            next_channel_number = 1
            if sorted_channels:
                max_channel_number = max((c.channel_number or 0) for c in sorted_channels)
                next_channel_number = max(next_channel_number, max_channel_number + 1)
            
            for acestream in unassigned_acestreams:
                if acestream.id in processed_acestreams:
                    continue
                    
                stream_url = self._format_stream_url(acestream.id, local_id, base_url=base_url)
                local_id += 1
                
                display_name = acestream.name or f"Stream {acestream.id[:8]}"
                
                if display_name in name_counts:
                    name_counts[display_name] += 1
                    display_name = f"{display_name} #{name_counts[display_name]}"
                else:
                    name_counts[display_name] = 1
                
                metadata = []
                metadata.append(f'tvg-chno="{next_channel_number}"')
                next_channel_number += 1
                
                if acestream.tvg_id:
                    metadata.append(f'tvg-id="{acestream.tvg_id}"')
                    
                metadata.append(f'tvg-name="{display_name}"')
                
                if acestream.logo:
                    metadata.append(f'tvg-logo="{acestream.logo}"')
                    
                if acestream.group:
                    metadata.append(f'group-title="{acestream.group}"')
                else:
                    metadata.append(f'group-title="Unassigned Streams"')
                
                extinf = '#EXTINF:-1'
                if metadata:
                    extinf += f' {" ".join(metadata)}'
                extinf += f',{display_name}'
                
                playlist_lines.append(extinf)
                playlist_lines.append(stream_url)
            
        return '\n'.join(playlist_lines)
        
    def generate_online_only_playlist(self, search_term=None, base_url=None):
        """Generate M3U playlist with ONLY active and online acestreams."""
        playlist_lines = ['#EXTM3U']
        
        query = AcestreamChannel.query.filter(
            AcestreamChannel.status == 'active',
            AcestreamChannel.is_online.is_(True)
        )

        if search_term:
            query = query.filter(AcestreamChannel.name.ilike(f'%{search_term}%'))

        online_acestreams = query.all()
        online_acestreams = sorted(online_acestreams, key=lambda x: (x.name or "").lower())
        
        name_counts = {}
        local_id = 0
        
        for acestream in online_acestreams:
            stream_url = self._format_stream_url(acestream.id, local_id, base_url=base_url)
            local_id += 1

            base_name = (acestream.name or "").strip()
            
            if base_name in name_counts:
                name_counts[base_name] += 1
                display_name = f"{base_name} #{name_counts[base_name]}"
            else:
                name_counts[base_name] = 1
                display_name = base_name
            
            metadata = []            
            if acestream.tvg_name:
                metadata.append(f'tvg-name="{acestream.tvg_name}"')
            if acestream.tvg_id:
                metadata.append(f'tvg-id="{acestream.tvg_id}"')
            if acestream.logo:
                metadata.append(f'tvg-logo="{acestream.logo}"')
            if acestream.group:
                metadata.append(f'group-title="{acestream.group}"')
            
            metadata_str = f" {' '.join(metadata)}" if metadata else ""
            extinf = f'#EXTINF:-1{metadata_str},{display_name}'
            
            playlist_lines.append(extinf)
            playlist_lines.append(stream_url)
                    
        return '\n'.join(playlist_lines)
        
    def generate_m3u_with_epg(self, base_url=None, search_term=None, favorites_only=False):
        """Generate M3U playlist with EPG linking only online acestreams."""
        user, password = self.get_basic_auth_credentials()

        if user and password and base_url:
            parsed = urlparse(base_url)
            epg_url = f"{parsed.scheme}://{user}:{password}@{parsed.netloc}/api/playlists/epg.xml"
        else:
            epg_url = f"{base_url}/api/playlists/epg.xml" if base_url else ""

        m3u_lines = [f'#EXTM3U x-tvg-url="{epg_url}"']

        channels, _, _ = self.tv_channel_repository.filter_channels(
            search_term=search_term, 
            favorites_only=favorites_only, 
            is_active=True, 
            per_page=1000
        )
        
        name_counts = {}
        local_id = 0
        
        sorted_channels = sorted(channels, key=lambda c: (c.channel_number is None, c.channel_number or 0, c.name.lower()))

        for tv_channel in sorted_channels:
            acestreams = AcestreamChannel.query.filter(
                AcestreamChannel.tv_channel_id == tv_channel.id, 
                AcestreamChannel.status == 'active',
                AcestreamChannel.is_online.is_(True)
            ).all()
            
            if not acestreams: continue

            for i, stream in enumerate(acestreams):
                stream_url = self._format_stream_url(stream.id, local_id, base_url=base_url)
                local_id += 1

                if len(acestreams) > 1:
                    display_name = f"{tv_channel.name} #{i + 1}"
                elif tv_channel.name in name_counts:
                    name_counts[tv_channel.name] += 1
                    display_name = f"{tv_channel.name} #{name_counts[tv_channel.name]}"
                else:
                    name_counts[tv_channel.name] = 1
                    display_name = tv_channel.name

                tvg_id = tv_channel.epg_id or ""
                logo = tv_channel.logo_url or ""
                group = tv_channel.category or "General"
                
                m3u_lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{display_name}')
                m3u_lines.append(stream_url)

        return "\n".join(m3u_lines)