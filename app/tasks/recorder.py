import os
import json
import subprocess
import psutil
import re
import threading
import random
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from app.extensions import db
from app.models import RecordingSchedule, EPGProgram, TVChannel, AcestreamChannel, Setting

# Pool de conversión limitado a 1 tareas simultáneas para no saturar la CPU/Disco
executor = ThreadPoolExecutor(max_workers=1)

# Conjunto y bloqueo para evitar conversiones simultáneas del mismo archivo
active_conversions = set()
conversion_lock = threading.Lock()

BAD_STREAM_PATTERNS = (
    "corrupt",
    "reference count",
    "illegal reordering_of_pic_nums_idc",
    "error while decoding",
    "concealing",
    "invalid data found",
)

stream_watchers = {}
watchers_lock = threading.Lock()


class StreamHealthWatcher:
    """Vigila stderr de ffmpeg y corta si hay avalancha sostenida de errores graves."""

    def __init__(self, log_path, grace_seconds=20, window_seconds=15, max_errors=50):
        self.log_path = log_path
        self.grace_seconds = grace_seconds
        self.window_seconds = window_seconds
        self.max_errors = max_errors
        self.start_time = time.monotonic()
        self._file_pos = 0
        self._error_times = deque()

    def should_abort_stream(self):
        now = time.monotonic()
        if now - self.start_time < self.grace_seconds:
            return False

        if not os.path.exists(self.log_path):
            return False

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self._file_pos)
                new_lines = f.readlines()
                self._file_pos = f.tell()
        except OSError:
            return False

        for line in new_lines:
            low = line.lower()
            if any(pat in low for pat in BAD_STREAM_PATTERNS):
                self._error_times.append(now)

        cutoff = now - self.window_seconds
        while self._error_times and self._error_times[0] < cutoff:
            self._error_times.popleft()

        return len(self._error_times) >= self.max_errors


def _cleanup_stream_watcher(program_id):
    with watchers_lock:
        watcher = stream_watchers.pop(program_id, None)
    if watcher and watcher.log_path and os.path.exists(watcher.log_path):
        try:
            os.remove(watcher.log_path)
        except OSError:
            pass


def _get_vaapi_device():
    dri_dir = "/dev/dri"
    if os.path.isdir(dri_dir):
        render_nodes = sorted(
            f for f in os.listdir(dri_dir)
            if f.startswith("renderD") and os.path.exists(os.path.join(dri_dir, f))
        )
        if render_nodes:
            return os.path.join(dri_dir, render_nodes[0])
    return None


def _get_v4l2_device():
    if os.path.isdir("/dev"):
        video_nodes = sorted(
            f for f in os.listdir("/dev")
            if f.startswith("video") and f[5:].isdigit() and os.path.exists(os.path.join("/dev", f))
        )
        if video_nodes:
            return os.path.join("/dev", video_nodes[0])
    return None


def _has_nvidia_device():
    if os.path.isdir("/dev"):
        return any(
            f.startswith("nvidia") and f[6:].isdigit() and os.path.exists(os.path.join("/dev", f))
            for f in os.listdir("/dev")
        )
    return False


def _resolve_hwaccel_mode():
    mode = os.getenv("FFMPEG_HWACCEL", "auto").strip().lower()
    if mode in ("vaapi", "rpi", "nvenc", "cpu"):
        return mode
    if _get_vaapi_device():
        return "vaapi"
    if _get_v4l2_device():
        return "rpi"
    if _has_nvidia_device():
        return "nvenc"
    return "cpu"


def _build_ffmpeg_cmd(input_ts, output_mp4, mode="cpu"):
    base_in = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-fflags", "+genpts+discardcorrupt",
    ]
    base_out = [
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_mp4,
    ]

    if mode == "vaapi":
        vaapi_dev = _get_vaapi_device()
        if not vaapi_dev:
            return None
        return [
            *base_in,
            "-hwaccel", "vaapi",
            "-hwaccel_device", vaapi_dev,
            "-hwaccel_output_format", "vaapi",
            "-i", input_ts,
            "-vf", "scale_vaapi=format=nv12",
            "-c:v", "h264_vaapi", "-qp", "23",
            *base_out,
        ]

    if mode == "rpi":
        return [
            *base_in,
            "-hwaccel", "drm",
            "-i", input_ts,
            "-c:v", "h264_v4l2m2m", "-b:v", "4M", "-pix_fmt", "yuv420p",
            *base_out,
        ]

    if mode == "nvenc":
        return [
            *base_in,
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",
            "-i", input_ts,
            "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-pix_fmt", "yuv420p",
            *base_out,
        ]

    return [
        *base_in,
        "-i", input_ts,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-profile:v", "main",
        *base_out,
    ]


def _probe_media_streams(input_ts):
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_streams",
        input_ts,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        if res.returncode != 0 or not res.stdout:
            return None
        data = json.loads(res.stdout)
        streams = data.get("streams") or []

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        video_ok = bool(
            video_stream
            and video_stream.get("codec_name") == "h264"
            and video_stream.get("pix_fmt") == "yuv420p"
        )
        audio_ok = bool(
            audio_stream
            and audio_stream.get("codec_name") in ("aac", "mp3")
        )
        return {
            "video_ok": video_ok,
            "audio_ok": audio_ok,
            "has_audio": audio_stream is not None,
        }
    except Exception:
        return None


def _try_smart_remux(input_ts, output_mp4, probe_info):
    if not probe_info or not probe_info.get("video_ok"):
        return False

    video_args = ["-c:v", "copy"]
    if not probe_info.get("has_audio"):
        audio_args = []
    elif probe_info.get("audio_ok"):
        audio_args = ["-c:a", "copy"]
    else:
        audio_args = ["-c:a", "aac", "-b:a", "192k"]

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-fflags", "+genpts+discardcorrupt",
        "-i", input_ts,
        *video_args,
        *audio_args,
        "-movflags", "+faststart",
        output_mp4,
    ]
    res = subprocess.run(cmd, check=False)
    return (
        res.returncode == 0
        and os.path.exists(output_mp4)
        and os.path.getsize(output_mp4) > 0
    )


def fast_remux_to_mp4(input_ts, output_mp4):
    probe_info = _probe_media_streams(input_ts)
    if _try_smart_remux(input_ts, output_mp4, probe_info):
        return True

    if os.path.exists(output_mp4):
        try:
            os.remove(output_mp4)
        except Exception:
            pass

    mode = _resolve_hwaccel_mode()
    cmd = _build_ffmpeg_cmd(input_ts, output_mp4, mode=mode)

    if cmd is not None:
        res = subprocess.run(cmd, check=False)
        if res.returncode == 0 and os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 0:
            return True

    if mode != "cpu":
        cmd_cpu = _build_ffmpeg_cmd(input_ts, output_mp4, mode="cpu")
        res_cpu = subprocess.run(cmd_cpu, check=False)
        return res_cpu.returncode == 0 and os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 0

    return False


def convert_part_task(app, input_path, output_path, rec_id):
    """Tarea ejecutada en la cola de trabajo con control de exclusión."""
    with app.app_context():
        try:
            app.logger.info(f"[CONVERTER] Starting safe transcode for {input_path}")

            success = fast_remux_to_mp4(input_path, output_path)

            if success and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                if os.path.exists(input_path):
                    try:
                        os.remove(input_path)
                    except Exception:
                        pass
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
        if not rec:
            return

        save_path = "/app/config/recordings"
        prog = rec.program
        clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')

        remaining_ts = [f for f in os.listdir(save_path) if f.startswith(f"{clean_title}_{prog.id}") and f.endswith('.ts')]

        is_ffmpeg_active = any(
            f"prog_id:{prog.id}" in " ".join(p.info.get('cmdline') or [])
            for p in psutil.process_iter(['cmdline'])
        )

        if not remaining_ts and not is_ffmpeg_active and rec.end_time <= datetime.now():
            _cleanup_stream_watcher(prog.id)
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
            base_url = setting_rec.value.rstrip('/') + "/ace/getstream"
        else:
            base_url = "http://127.0.0.1:6878/ace/getstream"

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
                            _cleanup_stream_watcher(found_id)
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
                _cleanup_stream_watcher(prog.id)
                procesar_partes_inactivas(app, rec)
                continue

            is_alive = any(
                f"prog_id:{rec.program_id}" in " ".join(p.info.get('cmdline') or [])
                for p in psutil.process_iter(['cmdline'])
            )

            if rec.status == 'recording' and not is_alive:
                app.logger.warning(f"[RECORDER] Connection lost for {prog.title}. Retrying...")
                _cleanup_stream_watcher(prog.id)
                rec.status = 'retrying'
                rec.retry_start = datetime.now()
                db.session.commit()
                continue

            if rec.status == 'recording' and is_alive:
                with watchers_lock:
                    watcher = stream_watchers.get(prog.id)
                if watcher and watcher.should_abort_stream():
                    app.logger.warning(
                        f"[RECORDER] Severe stream errors detected for {prog.title} (ID:{prog.id}). Cutting stream to retry..."
                    )
                    _kill_ffmpeg_for_program(prog.id)
                    _cleanup_stream_watcher(prog.id)
                    rec.status = 'retrying'
                    rec.retry_start = datetime.now()
                    db.session.commit()
                    continue

            if rec.status == 'retrying':
                elapsed = (datetime.now() - rec.retry_start).total_seconds()

                # Buscamos si hay algún canal online disponible en este momento
                tv_chan = TVChannel.query.filter_by(epg_id=prog.epg_channel.channel_xml_id).first()
                ace_chan = _get_random_online_channel(tv_chan.id) if tv_chan else None

                if ace_chan:
                    # Si encuentra un canal online, pasa a pendiente para arrancar la grabación de inmediato
                    rec.status = 'pending'
                    db.session.commit()
                    app.logger.info(f"[RECORDER] Stream recovered for {prog.title}. Resuming recording...")
                elif elapsed >= 120:
                    # SI PASAN LOS 120 SEGUNDOS Y NO HAY STREAM:
                    if rec.end_time > now:
                        rec.retry_start = datetime.now()
                        db.session.commit()
                        app.logger.warning(f"[RECORDER] Still no streams for {prog.title}. Keeping retry alive...")
                    else:
                        _cleanup_stream_watcher(prog.id)
                        rec.status = 'failed'
                        db.session.commit()
                        app.logger.error(f"[RECORDER] Program {prog.title} ended while retrying. Marked as failed.")
                continue

        # 3. INICIAR PENDIENTES
        query = RecordingSchedule.query.filter(
            RecordingSchedule.status == 'pending',
            RecordingSchedule.start_time <= now,
            RecordingSchedule.end_time > now
        )

        to_start = query.filter(RecordingSchedule.program_id == single_program_id).all() if single_program_id else query.all()

        for rec in to_start:
            prog = rec.program

            if rec.end_time <= now:
                _cleanup_stream_watcher(prog.id)
                rec.status = 'failed'
                db.session.commit()
                app.logger.warning(f"[RECORDER] Program {prog.title} expired while pending. Marked as failed.")
                continue

            already_recording = any(
                f"prog_id:{rec.program_id}" in " ".join(p.info.get('cmdline') or [])
                for p in psutil.process_iter(['cmdline'])
            )
            if already_recording:
                rec.status = 'recording'
                db.session.commit()
                continue

            tv_chan = TVChannel.query.filter_by(epg_id=prog.epg_channel.channel_xml_id).first()
            if not tv_chan:
                _cleanup_stream_watcher(prog.id)
                rec.status = 'failed'
                db.session.commit()
                continue

            ace_chan = _get_random_online_channel(tv_chan.id)
            if not ace_chan:
                continue

            clean_title = "".join([c for c in prog.title if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            existing_parts = [f for f in os.listdir(save_path) if f.startswith(f"{clean_title}_{prog.id}")]

            part_suffix = f"_part{len(existing_parts) + 1}" if existing_parts else "_part1"
            filename = os.path.join(save_path, f"{clean_title}_{prog.id}{part_suffix}.ts")

            duration = int((rec.end_time - now).total_seconds())
            if duration <= 0:
                continue

            # Soporte inteligente para infohash (ih:) o Content ID tradicional
            if ace_chan.id.startswith('ih:'):
                clean_infohash = ace_chan.id.replace('ih:', '')
                stream_url = f"{base_url}?infohash={clean_infohash}"
            else:
                stream_url = f"{base_url}?id={ace_chan.id}"

            _cleanup_stream_watcher(prog.id)
            stderr_log_path = f"/tmp/ffmpeg_rec_{prog.id}_{part_suffix.lstrip('_')}.log"

            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'warning',
                '-fflags', '+genpts+discardcorrupt',
                '-reconnect', '1', '-reconnect_at_eof', '1', '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5', '-rw_timeout', '15000000',
                '-i', stream_url,
                '-c', 'copy',
                '-user_agent', f'prog_id:{prog.id}', filename
            ]

            try:
                with open(stderr_log_path, "w", encoding="utf-8") as stderr_file:
                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=stderr_file,
                        start_new_session=True,
                    )
                with watchers_lock:
                    stream_watchers[prog.id] = StreamHealthWatcher(stderr_log_path)
                rec.status = 'recording'
                db.session.commit()
                app.logger.info(f"[RECORDER] Started: {prog.title} ID:{prog.id} ({part_suffix}) using ace_id: {ace_chan.id}")
            except Exception as e:
                _cleanup_stream_watcher(prog.id)
                app.logger.error(f"Error starting recording for {prog.id}: {e}")


def stop_recording_now(program_id):
    """Parada manual inmediata desde la UI."""
    from flask import current_app
    app = current_app._get_current_object()

    with app.app_context():
        rec = RecordingSchedule.query.filter_by(program_id=program_id).first()
        if rec:
            rec.end_time = datetime.now()
            rec.status = 'completed'
            db.session.commit()

            _kill_ffmpeg_for_program(program_id)
            _cleanup_stream_watcher(program_id)
            procesar_partes_inactivas(app, rec)


def start_recording_now(app, program_id):
    """Inicio manual inmediato."""
    thread = threading.Thread(target=process_recordings, args=(app, program_id))
    thread.daemon = True
    thread.start()