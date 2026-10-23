import os
import subprocess
import psutil
import re
import threading
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from app.extensions import db
from app.models import RecordingSchedule, EPGProgram, TVChannel, AcestreamChannel, Setting

# Pool de conversión limitado a 2 tareas simultáneas para no saturar la CPU/Disco
executor = ThreadPoolExecutor(max_workers=2)

# Conjunto y bloqueo para evitar conversiones simultáneas del mismo archivo
active_conversions = set()
conversion_lock = threading.Lock()

def fast_remux_to_mp4(input_ts, output_mp4):
    """
    Transcodifica de forma segura a H.264/AAC estándar para evitar 
    cualquier corrupción y errores de memoria en Firefox.
    """
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-fflags', '+genpts+discardcorrupt',
        '-i', input_ts,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'main',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        output_mp4
    ]
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0

def convert_part_task(app, input_path, output_path, rec_id):
    """Tarea ejecutada en la cola de trabajo con control de exclusión."""
    with app.app_context():
        try:
            app.logger.info(f"[CONVERTER] Starting safe transcode for {input_path}")
            
            success = fast_remux_to_mp4(input_path, output_path)
            
            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                if os.path.exists(input_path):
                    try: os.remove(input_path)
                    except Exception: pass
                app.logger.info(f"[CONVERTER] Part transcoded successfully: {output_path}")
            else:
                app.logger.error(f"[CONVERTER] Transcode failed for {input_path}")

            _actualizar_estado_global(app, rec_id)

        except Exception as e:
            app.logger.error(f"[CONVERTER] Error processing {input_path}: {e}")
        finally:
            with conversion_lock:
                active_conversions.discard(input_path)

def procesar_partes_inactivas(app, rec):
    """Identifica archivos .ts inactivos y evita duplicar tareas de conversión."""
    save_path = "/app/config/recordings"
    prog = rec.program
    clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')

    active_ts_files = set()
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmdline_args = proc.info.get('cmdline') or []
            cmdline_str = " ".join(cmdline_args)
            if f"prog_id:{prog.id}" in cmdline_str:
                for arg in cmdline_args:
                    if arg.endswith('.ts'):
                        active_ts_files.add(os.path.basename(arg))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    all_ts = [f for f in os.listdir(save_path) if f.startswith(f"{clean_title}_{prog.id}") and f.endswith('.ts')]

    for ts_file in all_ts:
        if ts_file not in active_ts_files:
            input_path = os.path.join(save_path, ts_file)
            output_path = input_path.replace('.ts', '.mp4')

            if not os.path.exists(output_path):
                with conversion_lock:
                    if input_path not in active_conversions:
                        active_conversions.add(input_path)
                        executor.submit(convert_part_task, app, input_path, output_path, rec.id)

def disparar_conversion(app, rec, *args, **kwargs):
    """Alias de compatibilidad para llamadas antiguas."""
    procesar_partes_inactivas(app, rec)
    return True

def _actualizar_estado_global(app, rec_id):
    """Marca la grabación en BD como 'completed' solo si no hay grabaciones ni conversiones pendientes."""
    with app.app_context():
        rec = db.session.get(RecordingSchedule, rec_id)
        if not rec: return

        save_path = "/app/config/recordings"
        prog = rec.program
        clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')

        remaining_ts = [f for f in os.listdir(save_path) if f.startswith(f"{clean_title}_{prog.id}") and f.endswith('.ts')]
        
        is_ffmpeg_active = any(f"prog_id:{prog.id}" in " ".join(p.info.get('cmdline') or []) 
                               for p in psutil.process_iter(['cmdline']))

        if not remaining_ts and not is_ffmpeg_active and rec.end_time <= datetime.now():
            rec.status = 'completed'
            db.session.commit()

def _kill_ffmpeg_for_program(program_id):
    """Detiene cualquier proceso FFmpeg activo para un programa."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            cmdline_str = " ".join(proc.info.get('cmdline') or [])
            if 'ffmpeg' in (proc.info.get('name') or '') and f"prog_id:{program_id}" in cmdline_str:
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def _get_random_online_channel(tv_channel_id):
    """Obtiene de forma aleatoria un canal de AceStream online disponible para evitar siempre el mismo enlace roto."""
    channels = AcestreamChannel.query.filter_by(tv_channel_id=tv_channel_id, status='active', is_online=True).all()
    if not channels:
        return None
    return random.choice(channels)

def process_recordings(app, single_program_id=None):
    """Motor principal de gestión de grabaciones."""
    with app.app_context():
        now = datetime.now()
        save_path = "/app/config/recordings"
        
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)

        setting_rec = Setting.query.filter_by(key='base_url').first()
        if setting_rec and setting_rec.value:
            base_url = setting_rec.value.rstrip('/') + "/ace/getstream?id="
        else:
            base_url = "http://127.0.0.1:6878/ace/getstream?id="

        # 1. PARAR GRABACIONES CUYO TIEMPO EXPIRÓ
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline_str = " ".join(proc.info.get('cmdline') or [])
                if 'ffmpeg' in (proc.info.get('name') or '') and "prog_id:" in cmdline_str:
                    match = re.search(r"prog_id:(\d+)", cmdline_str)
                    if match:
                        found_id = int(match.group(1))
                        rec_entry = RecordingSchedule.query.filter_by(program_id=found_id).first()
                        if not rec_entry or rec_entry.status not in ['recording', 'pending', 'retrying'] or rec_entry.end_time <= now:
                            app.logger.warning(f"[RECORDER] Stopping expired ffmpeg for program ID {found_id}")
                            proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 2. PROCESAR PARTES FINALIZADAS
        active_or_pending = RecordingSchedule.query.filter(
            RecordingSchedule.status.in_(['recording', 'pending', 'retrying'])
        ).all()

        for rec in active_or_pending:
            prog = rec.program
            clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            
            procesar_partes_inactivas(app, rec)

            if rec.end_time <= now:
                _kill_ffmpeg_for_program(prog.id)
                procesar_partes_inactivas(app, rec)
                continue

            is_alive = any(f"prog_id:{rec.program_id}" in " ".join(p.info.get('cmdline') or []) 
                           for p in psutil.process_iter(['cmdline']))

            if rec.status == 'recording' and not is_alive:
                app.logger.warning(f"[RECORDER] Connection lost for {prog.title}. Retrying...")
                rec.status = 'retrying'
                rec.retry_start = datetime.now()
                db.session.commit()
                continue

            if rec.status == 'retrying':
                elapsed = (datetime.now() - rec.retry_start).total_seconds()
                if elapsed >= 120:
                    rec.status = 'failed'
                    db.session.commit()
                    continue

                tv_chan = TVChannel.query.filter_by(epg_id=prog.epg_channel.channel_xml_id).first()
                if tv_chan:
                    ace_chan = _get_random_online_channel(tv_chan.id)
                    if ace_chan:
                        rec.status = 'pending'
                        db.session.commit()
                continue

        # 3. INICIAR PENDIENTES
        query = RecordingSchedule.query.filter(
            RecordingSchedule.status == 'pending',
            RecordingSchedule.start_time <= now,
            RecordingSchedule.end_time > now
        )

        to_start = query.filter(RecordingSchedule.program_id == single_program_id).all() if single_program_id else query.all()

        for rec in to_start:
            already_recording = any(f"prog_id:{rec.program_id}" in " ".join(p.info.get('cmdline') or []) 
                                    for p in psutil.process_iter(['cmdline']))
            if already_recording:
                rec.status = 'recording'
                db.session.commit()
                continue

            prog = rec.program
            tv_chan = TVChannel.query.filter_by(epg_id=prog.epg_channel.channel_xml_id).first()
            if not tv_chan: continue

            ace_chan = _get_random_online_channel(tv_chan.id)
            if not ace_chan: continue

            clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            existing_parts = [f for f in os.listdir(save_path) if f.startswith(f"{clean_title}_{prog.id}")]
            
            part_suffix = f"_part{len(existing_parts) + 1}" if existing_parts else "_part1"
            filename = os.path.join(save_path, f"{clean_title}_{prog.id}{part_suffix}.ts")
            
            duration = int((rec.end_time - now).total_seconds())
            if duration <= 0: continue

            stream_url = f"{base_url}{ace_chan.id}"

            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-fflags', '+genpts+discardcorrupt',
                '-reconnect', '1', '-reconnect_at_eof', '1', '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5', '-rw_timeout', '15000000',
                '-i', stream_url,
                '-c', 'copy',                    # Captura limpia y directa sin re-codificar en caliente
                '-user_agent', f'prog_id:{prog.id}', filename
            ]

            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                rec.status = 'recording'
                db.session.commit()
                app.logger.info(f"[RECORDER] Started: {prog.title} ID:{prog.id} ({part_suffix}) using ace_id: {ace_chan.id}")
            except Exception as e:
                app.logger.error(f"Error starting recording for {prog.id}: {e}")

def stop_recording_now(program_id):
    """Parada manual inmediata desde la UI."""
    from flask import current_app
    app = current_app._get_current_object()
    
    with app.app_context():
        rec = RecordingSchedule.query.filter_by(program_id=program_id).first()
        if rec:
            rec.end_time = datetime.now()
            db.session.commit()
            
            _kill_ffmpeg_for_program(program_id)
            procesar_partes_inactivas(app, rec)

def start_recording_now(app, program_id):
    """Inicio manual inmediato."""
    thread = threading.Thread(target=process_recordings, args=(app, program_id))
    thread.daemon = True
    thread.start()