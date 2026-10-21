import os
import time
import threading
import datetime
import numpy as np
import cv2
import mss
import subprocess
import imageio_ffmpeg
import tempfile
import re
import wave

# Global Recording Control Flags
_is_recording_flag = False
_recording_thread = None
_recording_error = None
_recording_started = None
_recording_file_path = None
_audio_capture_threads = []
_audio_temp_dir = None
_key_listener = None


def get_audio_capture_devices():
    import soundcard

    return [
        {
            "id": microphone.id,
            "name": microphone.name,
            "is_loopback": microphone.isloopback,
        }
        for microphone in soundcard.all_microphones(include_loopback=True)
    ]


def get_video_capture_devices():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    return re.findall(r'\] "(.+)" \(video\)', result.stderr)


def get_connected_displays():
    """පරිගණකයට සම්බන්ධ කර ඇති සියලුම ඩිස්ප්ලේස් (Monitors) ලැයිස්තුව ලබා ගැනීම"""
    displays_list = []
    try:
        from screeninfo import get_monitors
        for i, m in enumerate(get_monitors()):
            display_name = f"Display {i+1} · {m.width} x {m.height}"
            displays_list.append(display_name)
    except Exception as e:
        displays_list = ["Display 1 · 1920 x 1080"]
        
    return displays_list


def get_all_open_windows():
    """Windows API (`win32gui`) භාවිතයෙන් පරිගණකයේ දැනට විවෘතව ඇති සැබෑ වින්ඩෝස් ලැයිස්තුව ලබා ගැනීම"""
    windows_list = []
    try:
        import win32gui

        def enum_windows_handler(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title.strip() and title != "MSB Recorder":
                    if len(title) > 1:
                        windows_list.append(title)
            return True

        win32gui.EnumWindows(enum_windows_handler, None)
    except Exception as e:
        try:
            import pygetwindow as gw
            windows_list = [w.title for w in gw.getAllWindows() if w.title.strip() and w.title != "MSB Recorder"]
        except:
            windows_list = ["Google Chrome", "Visual Studio Code", "Notepad"]
            
    return sorted(list(set(windows_list)))


def _record_screen_worker(
    save_dir,
    record_mode="Screen",
    window_title=None,
    resolution=(1920, 1080),
    frame_rate=60,
    quality="High",
    output_format="mp4",
    audio_inputs=None,
    mix_audio=True,
    webcam_device=None,
    include_cursor=False,
    include_clicks=False,
    include_keys=False,
):
    """Capture the screen or a window and encode it with the selected settings."""
    global _is_recording_flag

    os.makedirs(save_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join(save_dir, f"MSB_REC_{timestamp}.{output_format}")
    width, height = resolution
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError("Video resolution must use positive even dimensions.")
    if frame_rate <= 0:
        raise ValueError("Frame rate must be greater than zero.")
    quality_crf = {"High": 18, "Ultra Lossless": 0, "Medium": 28}.get(quality)
    if quality_crf is None:
        raise ValueError(f"Unsupported video quality: {quality}")
    if output_format not in {"mp4", "mkv", "avi"}:
        raise ValueError(f"Unsupported output format: {output_format}")
    global _recording_file_path, _audio_temp_dir
    _recording_file_path = file_path

    audio_inputs = audio_inputs or {}
    audio_temp_dir = tempfile.TemporaryDirectory(dir=save_dir) if audio_inputs else None
    _audio_temp_dir = audio_temp_dir
    audio_sessions = []
    audio_errors = []
    key_overlay = {"label": "", "timestamp": 0.0}

    if include_keys:
        from pynput import keyboard

        def on_key_press(key):
            try:
                key_overlay["label"] = key.char or key.name
            except AttributeError:
                key_overlay["label"] = str(key).replace("Key.", "")
            key_overlay["timestamp"] = time.time()

        global _key_listener
        _key_listener = keyboard.Listener(on_press=on_key_press)
        _key_listener.start()
    if audio_temp_dir:
        global _audio_capture_threads
        _audio_capture_threads = []

    def capture_audio(device_id, wav_path, ready):
        global _is_recording_flag
        try:
            import soundcard

            microphone = soundcard.get_microphone(device_id, include_loopback=True)
            channels = max(1, min(2, microphone.channels))
            with wave.open(wav_path, "wb") as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(48000)
                with microphone.recorder(
                    samplerate=48000, channels=channels
                ) as recorder:
                    while _is_recording_flag:
                        samples = recorder.record(numframes=4800)
                        if samples.ndim == 1:
                            samples = samples.reshape(-1, 1)
                        pcm = (
                            np.clip(samples, -1.0, 1.0) * 32767
                        ).astype("<i2")
                        wav_file.writeframesraw(pcm.tobytes())
                        ready.set()
        except Exception as error:
            audio_errors.append(f"Audio capture failed: {error}")
            _is_recording_flag = False
        finally:
            ready.set()

    if audio_inputs:
        for source_name, device_id in audio_inputs.items():
            wav_path = os.path.join(audio_temp_dir.name, f"{source_name}.wav")
            ready = threading.Event()
            thread = threading.Thread(
                target=capture_audio,
                args=(device_id, wav_path, ready),
                daemon=True,
            )
            audio_sessions.append((thread, ready, wav_path))
            _audio_capture_threads.append(thread)
            thread.start()
        for _, ready, _ in audio_sessions:
            if not ready.wait(timeout=10):
                _is_recording_flag = False
                raise RuntimeError("Timed out while starting audio capture.")
        if audio_errors:
            _is_recording_flag = False
            for thread, _, _ in audio_sessions:
                thread.join(timeout=2)
            raise RuntimeError("\n".join(audio_errors))

    video_file_path = (
        os.path.join(audio_temp_dir.name, "recording.mp4")
        if audio_inputs
        else file_path
    )

    def add_video_inputs(command):
        if webcam_device:
            command.extend([
                "-f", "dshow",
                "-framerate", str(frame_rate),
                "-i", f"video={webcam_device}",
                "-filter_complex",
                "[1:v]scale=320:-1[webcam];"
                "[0:v][webcam]overlay=main_w-overlay_w-20:20[vout]",
                "-map", "[vout]",
            ])

    def draw_pointer(frame, screen_x, screen_y, capture_width, capture_height):
        if not include_cursor and not include_clicks:
            return
        import ctypes
        from ctypes import wintypes

        point = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return
        x = int((point.x - screen_x) * frame.shape[1] / capture_width)
        y = int((point.y - screen_y) * frame.shape[0] / capture_height)
        if not (0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]):
            return
        clicked = include_clicks and any(
            ctypes.windll.user32.GetAsyncKeyState(button) & 0x8000
            for button in (1, 2)
        )
        if clicked:
            cv2.circle(frame, (x, y), 22, (0, 0, 255), 3)
        if include_cursor:
            cv2.circle(frame, (x, y), 6, (255, 255, 255), -1)
            cv2.circle(frame, (x, y), 6, (0, 0, 0), 1)

    def draw_key_overlay(frame):
        if include_keys and key_overlay["label"] and time.time() - key_overlay["timestamp"] < 2:
            cv2.putText(
                frame,
                key_overlay["label"],
                (20, frame.shape[0] - 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

    def record_frames(pipe, stderr_file, frame_supplier):
        global _recording_started
        failure = None
        try:
            frame_supplier(pipe)
            _recording_started.set()
            while _is_recording_flag:
                frame_supplier(pipe)
        except Exception as error:
            failure = error
        finally:
            if pipe.stdin and not pipe.stdin.closed:
                try:
                    pipe.stdin.close()
                except OSError as error:
                    if failure is None:
                        failure = error

        return_code = pipe.wait()
        if return_code:
            stderr_file.seek(0)
            details = stderr_file.read().decode("utf-8", errors="replace").strip()
            message = f"FFmpeg exited with code {return_code}: {details[-2000:]}"
            if failure:
                raise RuntimeError(f"{failure}\n{message}") from failure
            raise RuntimeError(message)
        if failure:
            raise failure

    if record_mode == "Screen" or not window_title or window_title == "None":
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', f'{width}x{height}',
                '-pix_fmt', 'bgr24',
                '-r', str(frame_rate),
                '-i', '-',
                '-c:v', 'libx264',
                '-crf', str(quality_crf),
                '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p',
            ]
            add_video_inputs(cmd)
            cmd.append(video_file_path)
            with tempfile.TemporaryFile() as stderr_file:
                pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=stderr_file)

                def write_screen_frame(process):
                    start_time = time.time()
                    img = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    if frame.shape[1] != width or frame.shape[0] != height:
                        frame = cv2.resize(
                            frame, (width, height), interpolation=cv2.INTER_CUBIC
                        )
                    if include_cursor or include_clicks:
                        draw_pointer(
                            frame,
                            monitor.get("left", 0),
                            monitor.get("top", 0),
                            monitor["width"],
                            monitor["height"],
                        )
                    draw_key_overlay(frame)
                    process.stdin.write(frame.tobytes())
                    time.sleep(max(0, (1.0 / frame_rate) - (time.time() - start_time)))

                record_frames(pipe, stderr_file, write_screen_frame)

    else:
        import win32gui
        import win32ui
        import ctypes

        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            raise RuntimeError(f"The selected window is no longer open: {window_title}")

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', 'bgr24',
            '-r', str(frame_rate),
            '-i', '-',
            '-c:v', 'libx264',
            '-crf', str(quality_crf),
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
        ]
        add_video_inputs(cmd)
        cmd.append(video_file_path)
        with tempfile.TemporaryFile() as stderr_file:
            pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=stderr_file)

            def write_window_frame(process):
                start_time = time.time()
                current_hwnd = win32gui.FindWindow(None, window_title)
                if not current_hwnd or not win32gui.IsWindow(current_hwnd):
                    raise RuntimeError(f"The selected window is no longer open: {window_title}")

                rect = win32gui.GetWindowRect(current_hwnd)
                capture_width = rect[2] - rect[0]
                capture_height = rect[3] - rect[1]
                if capture_width <= 0 or capture_height <= 0:
                    raise RuntimeError("The selected window has no capturable area.")

                hwnd_dc = win32gui.GetWindowDC(current_hwnd)
                memory_dc = None
                save_dc = None
                bitmap = None
                try:
                    memory_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                    save_dc = memory_dc.CreateCompatibleDC()
                    bitmap = win32ui.CreateBitmap()
                    bitmap.CreateCompatibleBitmap(memory_dc, capture_width, capture_height)
                    save_dc.SelectObject(bitmap)
                    if not ctypes.windll.user32.PrintWindow(
                        current_hwnd, save_dc.GetSafeHdc(), 2
                    ):
                        raise RuntimeError("Windows could not capture the selected window.")
                    image = np.frombuffer(
                        bitmap.GetBitmapBits(True), dtype=np.uint8
                    ).reshape((capture_height, capture_width, 4))
                    frame = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
                    if capture_width != width or capture_height != height:
                        frame = cv2.resize(
                            frame, (width, height), interpolation=cv2.INTER_CUBIC
                        )
                    if include_cursor or include_clicks:
                        draw_pointer(
                            frame, rect[0], rect[1], capture_width, capture_height
                        )
                    draw_key_overlay(frame)
                    process.stdin.write(frame.tobytes())
                finally:
                    if bitmap is not None:
                        win32gui.DeleteObject(bitmap.GetHandle())
                    if save_dc is not None:
                        save_dc.DeleteDC()
                    if memory_dc is not None:
                        memory_dc.DeleteDC()
                    win32gui.ReleaseDC(current_hwnd, hwnd_dc)

                time.sleep(max(0, (1.0 / frame_rate) - (time.time() - start_time)))

            record_frames(pipe, stderr_file, write_window_frame)

    if audio_sessions:
        _is_recording_flag = False
        for thread, _, _ in audio_sessions:
            thread.join(timeout=10)
            if thread.is_alive():
                raise TimeoutError("Audio capture did not stop cleanly.")
        if audio_errors:
            raise RuntimeError("\n".join(audio_errors))

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        muxed_file_path = os.path.join(
            audio_temp_dir.name, f"muxed_recording.{output_format}"
        )
        mux_cmd = [ffmpeg_exe, "-y", "-i", video_file_path]
        for _, _, wav_path in audio_sessions:
            mux_cmd.extend(["-i", wav_path])

        if len(audio_sessions) > 1 and mix_audio:
            audio_inputs_filter = "".join(
                f"[{index}:a:0]" for index in range(1, len(audio_sessions) + 1)
            )
            mux_cmd.extend([
                "-filter_complex",
                f"{audio_inputs_filter}amix=inputs={len(audio_sessions)}:"
                "duration=longest[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
            ])
        else:
            mux_cmd.extend(["-map", "0:v:0"])
            for index in range(1, len(audio_sessions) + 1):
                mux_cmd.extend(["-map", f"{index}:a:0"])

        audio_codec = "libmp3lame" if output_format == "avi" else "aac"
        mux_cmd.extend(["-c:v", "copy", "-c:a", audio_codec, "-shortest", muxed_file_path])
        with tempfile.TemporaryFile() as stderr_file:
            result = subprocess.run(
                mux_cmd,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                check=False,
            )
            if result.returncode:
                stderr_file.seek(0)
                details = stderr_file.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"Could not combine the recording's audio and video: {details[-2000:]}"
                )
        os.replace(muxed_file_path, file_path)
        audio_temp_dir.cleanup()

    if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
        raise RuntimeError("FFmpeg finished without creating a video file.")


def _run_recording_worker(*args):
    global _is_recording_flag, _recording_error, _key_listener, _audio_temp_dir
    try:
        _record_screen_worker(*args)
    except Exception as error:
        _recording_error = str(error)
        if _recording_file_path and os.path.exists(_recording_file_path):
            try:
                os.remove(_recording_file_path)
            except OSError as cleanup_error:
                _recording_error += f"\nCould not remove the incomplete video: {cleanup_error}"
    finally:
        _is_recording_flag = False
        for thread in _audio_capture_threads:
            thread.join(timeout=10)
        if _audio_temp_dir:
            _audio_temp_dir.cleanup()
            _audio_temp_dir = None
        if _key_listener:
            _key_listener.stop()
            _key_listener = None
        _recording_started.set()


def start_screen_recording(
    custom_save_path=None,
    record_mode="Screen",
    window_title=None,
    resolution=(1920, 1080),
    frame_rate=60,
    quality="High",
    output_format="mp4",
    audio_inputs=None,
    mix_audio=True,
    webcam_device=None,
    include_cursor=False,
    include_clicks=False,
    include_keys=False,
):
    global _is_recording_flag, _recording_thread, _recording_error
    global _recording_started, _recording_file_path

    if _is_recording_flag or (
        _recording_thread is not None and _recording_thread.is_alive()
    ):
        raise RuntimeError("A recording is already in progress.")

    if not custom_save_path:
        videos_folder = os.path.join(os.path.expanduser("~"), "Videos")
        custom_save_path = os.path.join(videos_folder, "MSB Recordings")

    _recording_error = None
    _recording_started = threading.Event()
    _recording_file_path = None
    _is_recording_flag = True
    _recording_thread = threading.Thread(
        target=_run_recording_worker,
        args=(
            custom_save_path,
            record_mode,
            window_title,
            resolution,
            frame_rate,
            quality,
            output_format,
            audio_inputs,
            mix_audio,
            webcam_device,
            include_cursor,
            include_clicks,
            include_keys,
        ),
        daemon=True
    )
    _recording_thread.start()
    if not _recording_started.wait(timeout=10):
        _is_recording_flag = False
        _recording_thread.join(timeout=1)
        raise RuntimeError("Timed out while starting the video encoder.")
    if _recording_error:
        _recording_thread.join(timeout=1)
        raise RuntimeError(_recording_error) from None


def stop_screen_recording():
    """Screen Recording එක නතර කිරීම"""
    global _is_recording_flag, _recording_thread
    _is_recording_flag = False
    if _recording_thread:
        _recording_thread.join(timeout=15.0)
        if _recording_thread.is_alive():
            raise TimeoutError("The video encoder is still finalizing the recording.")
        _recording_thread = None
    if _recording_error:
        raise RuntimeError(_recording_error) from None
    return _recording_file_path