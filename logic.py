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
import queue
import re
import wave

# Global Recording Control Flags
_is_recording_flag = False
_is_paused_flag = False
_recording_thread = None
_recording_error = None
_recording_started = None
_recording_file_path = None
_audio_capture_threads = []
_audio_temp_dir = None
_key_listener = None


def _fit_frame_to_resolution(frame, width, height):
    """Scale a frame proportionally and pad it to the selected output size."""
    source_height, source_width = frame.shape[:2]
    scale = min(width / source_width, height / source_height)
    fitted_width = max(1, min(width, round(source_width * scale)))
    fitted_height = max(1, min(height, round(source_height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(
        frame, (fitted_width, fitted_height), interpolation=interpolation
    )
    output = np.zeros((height, width, 3), dtype=frame.dtype)
    left = (width - fitted_width) // 2
    top = (height - fitted_height) // 2
    output[top:top + fitted_height, left:left + fitted_width] = resized
    return output


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


def capture_window_screenshot(window_title):
    import ctypes
    import win32gui
    import win32ui
    from PIL import Image

    window_handle = win32gui.FindWindow(None, window_title)
    if not window_handle:
        raise RuntimeError(f"The selected window is no longer open: {window_title}")

    left, top, right, bottom = win32gui.GetWindowRect(window_handle)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError("The selected window has no capturable area.")

    window_dc = win32gui.GetWindowDC(window_handle)
    if not window_dc:
        raise RuntimeError("Windows could not access the selected window.")

    memory_dc = None
    capture_dc = None
    bitmap = None
    try:
        memory_dc = win32ui.CreateDCFromHandle(window_dc)
        capture_dc = memory_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(memory_dc, width, height)
        capture_dc.SelectObject(bitmap)
        if not ctypes.windll.user32.PrintWindow(
            window_handle, capture_dc.GetSafeHdc(), 2
        ):
            raise RuntimeError("Windows could not capture the selected window.")

        pixels = np.frombuffer(
            bitmap.GetBitmapBits(True), dtype=np.uint8
        ).reshape((height, width, 4))
        return Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGRA2RGB))
    finally:
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if capture_dc is not None:
            capture_dc.DeleteDC()
        if memory_dc is not None:
            memory_dc.DeleteDC()
        win32gui.ReleaseDC(window_handle, window_dc)


def capture_region_screenshot(region):
    from PIL import Image
    from mss.exception import ScreenShotError

    try:
        with mss.mss() as screen_capture:
            screenshot = screen_capture.grab(region)
            return Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    except ScreenShotError as error:
        raise RuntimeError(f"Could not capture the selected area: {error}") from error


def select_capture_region():
    import ctypes
    from ctypes import wintypes
    import tkinter as tk
    from PIL import Image, ImageEnhance, ImageTk
    from mss.exception import ScreenShotError

    try:
        with mss.mss() as screen_capture:
            monitor = dict(screen_capture.monitors[0])
            screenshot = Image.frombytes(
                "RGB",
                (monitor["width"], monitor["height"]),
                screen_capture.grab(monitor).rgb,
            )
    except ScreenShotError as error:
        raise RuntimeError(f"Could not capture the screen for area selection: {error}") from error

    root = None
    selection = None
    try:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.geometry(f"{monitor['width']}x{monitor['height']}+0+0")
        root.update_idletasks()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        set_window_position = user32.SetWindowPos
        set_window_position.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        set_window_position.restype = wintypes.BOOL
        ctypes.set_last_error(0)
        if not set_window_position(
            wintypes.HWND(int(root.wm_frame(), 0)),
            wintypes.HWND(-1),
            monitor["left"],
            monitor["top"],
            monitor["width"],
            monitor["height"],
            0x0040,
        ):
            raise OSError(ctypes.get_last_error(), "Could not position the area selector.")

        screenshot = ImageTk.PhotoImage(
            ImageEnhance.Brightness(screenshot).enhance(0.55), master=root
        )
        canvas = tk.Canvas(
            root,
            width=monitor["width"],
            height=monitor["height"],
            highlightthickness=0,
            cursor="crosshair",
        )
        canvas.pack(fill="both", expand=True)
        canvas.create_image(0, 0, image=screenshot, anchor="nw")
        canvas.create_text(
            20,
            20,
            anchor="nw",
            text="Drag to select an area  |  Esc to cancel",
            fill="white",
            font=("Segoe UI", 14, "bold"),
        )
        selection_rectangle = None
        start = {}

        def begin_selection(event):
            nonlocal selection_rectangle
            start["x"] = canvas.canvasx(event.x)
            start["y"] = canvas.canvasy(event.y)
            selection_rectangle = canvas.create_rectangle(
                start["x"],
                start["y"],
                start["x"],
                start["y"],
                outline="#8B7CFF",
                width=2,
                fill="#6C5CE7",
                stipple="gray50",
            )

        def update_selection(event):
            if selection_rectangle is not None:
                canvas.coords(
                    selection_rectangle,
                    start["x"],
                    start["y"],
                    canvas.canvasx(event.x),
                    canvas.canvasy(event.y),
                )

        def finish_selection(event):
            nonlocal selection
            end_x = canvas.canvasx(event.x)
            end_y = canvas.canvasy(event.y)
            left = int(min(start["x"], end_x))
            top = int(min(start["y"], end_y))
            width = int(abs(end_x - start["x"]))
            height = int(abs(end_y - start["y"]))
            if width >= 2 and height >= 2:
                selection = {
                    "left": monitor["left"] + left,
                    "top": monitor["top"] + top,
                    "width": width,
                    "height": height,
                }
            root.quit()

        canvas.bind("<ButtonPress-1>", begin_selection)
        canvas.bind("<B1-Motion>", update_selection)
        canvas.bind("<ButtonRelease-1>", finish_selection)
        root.bind("<Escape>", lambda _: root.quit())
        root.bind_all("<Escape>", lambda _: root.quit())
        root.protocol("WM_DELETE_WINDOW", root.quit)
        root.focus_force()
        root.update()
        root.mainloop()
    except tk.TclError as error:
        raise RuntimeError(f"Could not open the area selector: {error}") from error
    finally:
        if root is not None:
            root.destroy()

    return selection


class AreaFrameOverlay:
    def __init__(self, region, on_region_change, on_exit, on_error):
        self._commands = queue.Queue()
        self._ready = threading.Event()
        self._error = None
        self._on_region_change = on_region_change
        self._on_exit = on_exit
        self._on_error = on_error
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            self.close()
            raise TimeoutError("Timed out while showing the selected area frame.")
        if self._error:
            raise RuntimeError(f"Could not show the selected area frame: {self._error}")
        self.update_region(region)

    def update_region(self, region):
        self._commands.put(("region", dict(region)))

    def set_recording(self, is_recording):
        self._commands.put(("recording", is_recording))

    def set_visible(self, visible):
        self._commands.put(("visible", visible))

    def close(self):
        self._commands.put(("close", None))

    def _run(self):
        import ctypes
        import tkinter as tk
        from ctypes import wintypes

        root = None
        escape_listener = None
        try:
            from pynput import keyboard

            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            transparent_color = "#ff00ff"
            root.configure(bg=transparent_color)
            root.attributes("-transparentcolor", transparent_color)
            canvas = tk.Canvas(
                root,
                bg=transparent_color,
                highlightthickness=0,
                bd=0,
            )
            canvas.pack(fill="both", expand=True)

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            set_window_position = user32.SetWindowPos
            set_window_position.argtypes = (
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            )
            set_window_position.restype = wintypes.BOOL
            set_window_display_affinity = user32.SetWindowDisplayAffinity
            set_window_display_affinity.argtypes = (
                wintypes.HWND,
                wintypes.DWORD,
            )
            set_window_display_affinity.restype = wintypes.BOOL
            root.update_idletasks()
            window_handle = wintypes.HWND(int(root.wm_frame(), 0))
            ctypes.set_last_error(0)
            if not set_window_display_affinity(window_handle, 0x00000011):
                raise OSError(
                    ctypes.get_last_error(),
                    "Could not exclude the recording-area frame from screen capture.",
                )

            region = {}
            recording = False
            visible = True
            drag = None
            exit_requested = False
            margin = 12
            min_size = 2
            with mss.mss() as capture:
                virtual_screen = dict(capture.monitors[0])

            def position_overlay():
                if not region:
                    return
                root.geometry(
                    f"{region['width'] + margin * 2}x"
                    f"{region['height'] + margin * 2}+0+0"
                )
                root.update_idletasks()
                ctypes.set_last_error(0)
                if not set_window_position(
                    window_handle,
                    wintypes.HWND(-1),
                    region["left"] - margin,
                    region["top"] - margin,
                    region["width"] + margin * 2,
                    region["height"] + margin * 2,
                    0x0040,
                ):
                    raise OSError(
                        ctypes.get_last_error(),
                        "Could not position the selected area frame.",
                    )
                canvas.configure(
                    width=region["width"] + margin * 2,
                    height=region["height"] + margin * 2,
                )

            def draw_frame():
                canvas.delete("all")
                if not region:
                    return
                color = "#ff3b30" if recording else "#34c759"
                left = margin
                top = margin
                right = margin + region["width"]
                bottom = margin + region["height"]
                canvas.create_rectangle(
                    left,
                    top,
                    right,
                    bottom,
                    outline=color,
                    width=3,
                )
                handle_size = 8
                for x, y in (
                    (left, top),
                    (right, top),
                    (left, bottom),
                    (right, bottom),
                ):
                    canvas.create_rectangle(
                        x - handle_size / 2,
                        y - handle_size / 2,
                        x + handle_size / 2,
                        y + handle_size / 2,
                        fill=color,
                        outline=color,
                    )
                close_left = right - 30
                close_top = top + 6
                canvas.create_rectangle(
                    close_left,
                    close_top,
                    close_left + 24,
                    close_top + 24,
                    fill="#202020",
                    outline=color,
                    width=2,
                )
                canvas.create_line(
                    close_left + 7,
                    close_top + 7,
                    close_left + 17,
                    close_top + 17,
                    fill=color,
                    width=2,
                )
                canvas.create_line(
                    close_left + 17,
                    close_top + 7,
                    close_left + 7,
                    close_top + 17,
                    fill=color,
                    width=2,
                )
                center_x = (left + right) / 2
                center_y = (top + bottom) / 2
                canvas.create_line(
                    center_x - 6,
                    center_y,
                    center_x + 6,
                    center_y,
                    fill=color,
                    width=3,
                )
                canvas.create_line(
                    center_x,
                    center_y - 6,
                    center_x,
                    center_y + 6,
                    fill=color,
                    width=3,
                )

            def close_handle_hit(x, y):
                close_left = margin + region["width"] - 30
                close_top = margin + 6
                return (
                    close_left <= x <= close_left + 24
                    and close_top <= y <= close_top + 24
                )

            def move_handle_hit(x, y):
                center_x = margin + region["width"] / 2
                center_y = margin + region["height"] / 2
                return (x - center_x) ** 2 + (y - center_y) ** 2 <= 14 ** 2

            def resize_zone(x, y):
                left = margin
                top = margin
                right = margin + region["width"]
                bottom = margin + region["height"]
                tolerance = margin
                near_left = abs(x - left) <= tolerance
                near_right = abs(x - right) <= tolerance
                near_top = abs(y - top) <= tolerance
                near_bottom = abs(y - bottom) <= tolerance
                on_horizontal_edge = top - tolerance <= y <= bottom + tolerance
                on_vertical_edge = left - tolerance <= x <= right + tolerance

                if near_left and near_top:
                    return "nw"
                if near_right and near_top:
                    return "ne"
                if near_left and near_bottom:
                    return "sw"
                if near_right and near_bottom:
                    return "se"
                if near_left and on_horizontal_edge:
                    return "w"
                if near_right and on_horizontal_edge:
                    return "e"
                if near_top and on_vertical_edge:
                    return "n"
                if near_bottom and on_vertical_edge:
                    return "s"
                return None

            cursors = {
                "n": "sb_v_double_arrow",
                "s": "sb_v_double_arrow",
                "e": "sb_h_double_arrow",
                "w": "sb_h_double_arrow",
                "nw": "size_nw_se",
                "se": "size_nw_se",
                "ne": "size_ne_sw",
                "sw": "size_ne_sw",
                "move": "fleur",
                "close": "hand2",
            }

            def on_motion(event):
                zone = None
                if region:
                    zone = (
                        "close"
                        if close_handle_hit(event.x, event.y)
                        else (
                            "move"
                            if move_handle_hit(event.x, event.y)
                            else resize_zone(event.x, event.y)
                        )
                    )
                canvas.configure(cursor=cursors.get(zone, ""))

            def request_exit():
                nonlocal exit_requested
                if visible and not exit_requested:
                    exit_requested = True
                    self._commands.put(("exit", None))

            def on_resize_start(event):
                nonlocal drag
                if recording or not region:
                    return
                zone = (
                    "close"
                    if close_handle_hit(event.x, event.y)
                    else (
                        "move"
                        if move_handle_hit(event.x, event.y)
                        else resize_zone(event.x, event.y)
                    )
                )
                if zone:
                    drag = {
                        "zone": zone,
                        "x": event.x_root,
                        "y": event.y_root,
                        "region": dict(region),
                    }

            def on_resize(event):
                if not drag or recording or drag["zone"] == "close":
                    return
                original = drag["region"]
                delta_x = event.x_root - drag["x"]
                delta_y = event.y_root - drag["y"]
                left = original["left"]
                top = original["top"]
                right = left + original["width"]
                bottom = top + original["height"]
                zone = drag["zone"]

                if zone == "move":
                    left = min(
                        max(
                            left + delta_x,
                            virtual_screen["left"],
                        ),
                        virtual_screen["left"] + virtual_screen["width"] - original["width"],
                    )
                    top = min(
                        max(top + delta_y, virtual_screen["top"]),
                        virtual_screen["top"] + virtual_screen["height"] - original["height"],
                    )
                    right = left + original["width"]
                    bottom = top + original["height"]
                else:
                    if "w" in zone:
                        left = min(
                            max(left + delta_x, virtual_screen["left"]),
                            right - min_size,
                        )
                    if "e" in zone:
                        right = max(
                            min(
                                right + delta_x,
                                virtual_screen["left"] + virtual_screen["width"],
                            ),
                            left + min_size,
                        )
                    if "n" in zone:
                        top = min(
                            max(top + delta_y, virtual_screen["top"]),
                            bottom - min_size,
                        )
                    if "s" in zone:
                        bottom = max(
                            min(
                                bottom + delta_y,
                                virtual_screen["top"] + virtual_screen["height"],
                            ),
                            top + min_size,
                        )

                region.update(
                    left=int(left),
                    top=int(top),
                    width=int(right - left),
                    height=int(bottom - top),
                )
                position_overlay()
                draw_frame()

            def on_resize_end(_event):
                nonlocal drag
                if drag:
                    zone = drag["zone"]
                    drag = None
                    if zone == "close":
                        request_exit()
                    else:
                        self._on_region_change(dict(region))

            escape_listener = keyboard.Listener(
                on_press=lambda key: request_exit()
                if key == keyboard.Key.esc
                else None
            )
            escape_listener.start()
            root.bind("<Escape>", lambda _event: request_exit())
            canvas.bind("<Motion>", on_motion)
            canvas.bind("<ButtonPress-1>", on_resize_start)
            canvas.bind("<B1-Motion>", on_resize)
            canvas.bind("<ButtonRelease-1>", on_resize_end)

            def process_commands():
                nonlocal recording, visible, exit_requested
                while True:
                    try:
                        command, value = self._commands.get_nowait()
                    except queue.Empty:
                        break
                    if command == "close":
                        root.destroy()
                        if escape_listener:
                            escape_listener.stop()
                        return
                    if command == "exit":
                        self._on_exit()
                    if command == "region":
                        region.clear()
                        region.update(value)
                        position_overlay()
                        draw_frame()
                    elif command == "recording":
                        recording = value
                        draw_frame()
                    elif command == "visible":
                        visible = value
                        if visible:
                            exit_requested = False
                            root.deiconify()
                            root.attributes("-topmost", True)
                        else:
                            root.withdraw()
                if root.winfo_exists():
                    root.after(16, process_commands)

            root.after(0, process_commands)
            self._ready.set()
            root.mainloop()
        except Exception as error:
            was_ready = self._ready.is_set()
            self._error = error
            self._ready.set()
            if was_ready:
                self._on_error(error)
        finally:
            if escape_listener and escape_listener.is_alive():
                escape_listener.stop()
            if root is not None:
                try:
                    if root.winfo_exists():
                        root.destroy()
                except tk.TclError:
                    pass


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
    capture_region=None,
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
                        if _is_paused_flag:
                            time.sleep(0.05)
                            continue
                        samples = recorder.record(numframes=4800)
                        if _is_paused_flag:
                            continue
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
                if _is_paused_flag:
                    time.sleep(0.05)
                else:
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

    if record_mode in {"Screen", "Area"} or not window_title or window_title == "None":
        with mss.mss() as sct:
            if record_mode == "Area":
                if not capture_region:
                    raise ValueError("Select an area before starting the recording.")
                monitor = {
                    key: int(capture_region[key])
                    for key in ("left", "top", "width", "height")
                }
                if monitor["width"] < 2 or monitor["height"] < 2:
                    raise ValueError("The selected area is too small to record.")
            else:
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
                    if record_mode == "Area":
                        if include_cursor or include_clicks:
                            draw_pointer(
                                frame,
                                monitor.get("left", 0),
                                monitor.get("top", 0),
                                monitor["width"],
                                monitor["height"],
                            )
                        frame = _fit_frame_to_resolution(frame, width, height)
                    elif frame.shape[1] != width or frame.shape[0] != height:
                        frame = cv2.resize(
                            frame, (width, height), interpolation=cv2.INTER_CUBIC
                        )
                    if record_mode != "Area" and (
                        include_cursor or include_clicks
                    ):
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
    global _is_recording_flag, _is_paused_flag
    global _recording_error, _key_listener, _audio_temp_dir
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
        _is_paused_flag = False
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
    capture_region=None,
):
    global _is_recording_flag, _is_paused_flag, _recording_thread, _recording_error
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
    _is_paused_flag = False
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
            capture_region,
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


def set_recording_paused(is_paused):
    global _is_paused_flag
    if is_paused and not _is_recording_flag:
        raise RuntimeError("There is no active recording to pause.")
    _is_paused_flag = bool(is_paused)


def stop_screen_recording():
    """Screen Recording එක නතර කිරීම"""
    global _is_recording_flag, _is_paused_flag, _recording_thread
    _is_recording_flag = False
    _is_paused_flag = False
    if _recording_thread:
        _recording_thread.join(timeout=15.0)
        if _recording_thread.is_alive():
            raise TimeoutError("The video encoder is still finalizing the recording.")
        _recording_thread = None
    if _recording_error:
        raise RuntimeError(_recording_error) from None
    return _recording_file_path