import os
import time
import threading
import datetime
import numpy as np
import cv2
import mss
import subprocess
import imageio_ffmpeg

# Global Recording Control Flags
_is_recording_flag = False
_recording_thread = None

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


def _record_screen_worker(save_dir, record_mode="Screen", window_title=None, quality="1080p 60FPS"):
    """FFmpeg සහ CRF මඟින් උපරිම ගුණාත්මකභාවයෙන් (Ultra High Quality) Screen හෝ Window එක කැප්චර් කිරීම"""
    global _is_recording_flag

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(save_dir, f"MSB_REC_{timestamp}.mp4")

    fps = 60.0
    if "30FPS" in quality:
        fps = 30.0

    # 1. Screen Mode සඳහා Width සහ Height ලබා ගැනීම
    if record_mode == "Screen" or not window_title or window_title == "None":
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            width, height = monitor["width"], monitor["height"]
            
            # FFmpeg Command එක සැකසීම (CRF 12 යනු ඉතාම පැහැදිලි උසස් තත්ත්වයකි)
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-s', f'{width}x{height}',
                '-pix_fmt', 'bgr24',
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-crf', '12',          # අකුරු සහ රූප ඉතාම තියුණු ලෙස තබා ගැනීමට (0 = Lossless, 12 = Ultra High)
                '-preset', 'ultrafast', # රෙකෝඩ් වන විට ලැග් වීම (Lag) වැළැක්වීමට
                '-pix_fmt', 'yuv420p',
                file_path
            ]
            
            pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

            while _is_recording_flag:
                start_time = time.time()
                img = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # FFmpeg වෙත Frame එක යැවීම
                pipe.stdin.write(frame.tobytes())

                elapsed = time.time() - start_time
                delay = max(0, (1.0 / fps) - elapsed)
                time.sleep(delay)
                
            pipe.stdin.close()
            pipe.wait()

    # 2. Window Mode සඳහා (PrintWindow හරහා පසුබිමින් කැප්චර් කිරීම)
    else:
        import win32gui
        import win32ui
        import ctypes

        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            return

        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        if width <= 0 or height <= 0:
            width, height = 800, 600

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', 'bgr24',
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-crf', '12',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            file_path
        ]
        
        pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        while _is_recording_flag:
            start_time = time.time()
            try:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd and win32gui.IsWindow(hwnd):
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]

                    if w > 0 and h > 0:
                        hwndDC = win32gui.GetWindowDC(hwnd)
                        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                        saveDC = mfcDC.CreateCompatibleDC()

                        saveBitMap = win32ui.CreateBitmap()
                        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
                        saveDC.SelectObject(saveBitMap)

                        ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 2)

                        bmpstr = saveBitMap.GetBitmapBits(True)
                        img = np.frombuffer(bmpstr, dtype=np.uint8)
                        img.shape = (h, w, 4)

                        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                        if w != width or h != height:
                            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_CUBIC)

                        # FFmpeg වෙත Frame එක යැවීම
                        pipe.stdin.write(frame.tobytes())

                        win32gui.DeleteObject(saveBitMap.GetHandle())
                        saveDC.DeleteDC()
                        mfcDC.DeleteDC()
                        win32gui.ReleaseDC(hwnd, hwndDC)
            except Exception as e:
                print(f"PrintWindow Error: {e}")

            elapsed = time.time() - start_time
            delay = max(0, (1.0 / fps) - elapsed)
            time.sleep(delay)

        pipe.stdin.close()
        pipe.wait()


def start_screen_recording(custom_save_path=None, record_mode="Screen", window_title=None, quality="1080p 60FPS"):
    global _is_recording_flag, _recording_thread

    if _is_recording_flag:
        return

    if not custom_save_path:
        videos_folder = os.path.join(os.path.expanduser("~"), "Videos")
        custom_save_path = os.path.join(videos_folder, "MSB Recordings")
    elif not custom_save_path.endswith("MSB Recordings"):
        custom_save_path = os.path.join(custom_save_path, "MSB Recordings")

    _is_recording_flag = True
    _recording_thread = threading.Thread(
        target=_record_screen_worker, 
        args=(custom_save_path, record_mode, window_title, quality), 
        daemon=True
    )
    _recording_thread.start()

def stop_screen_recording():
    """Screen Recording එක නතර කිරීම"""
    global _is_recording_flag, _recording_thread
    _is_recording_flag = False
    if _recording_thread:
        _recording_thread.join(timeout=2.0)
        _recording_thread = None