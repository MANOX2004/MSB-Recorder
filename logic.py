import os
import time
import threading
import datetime
import numpy as np
import cv2
import mss

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


def _record_screen_worker(save_dir, record_mode="Screen", window_title=None, fps=20.0):
    """පසුබිමෙන් (Thread) Screen එක හෝ නිශ්චිත Window එක පමණක් Capture කරන Function එක"""
    global _is_recording_flag

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(save_dir, f"MSB_REC_{timestamp}.mp4")

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        width, height = monitor["width"], monitor["height"]
        region = None

        # Window Mode නම් අදාළ Window එකේ Coordinates ලබා ගැනීම
        if record_mode == "Window" and window_title and window_title != "None":
            try:
                import win32gui
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd:
                    rect = win32gui.GetWindowRect(hwnd)
                    x, y, x2, y2 = rect
                    w = x2 - x
                    h = y2 - y
                    if w > 0 and h > 0:
                        region = {"left": x, "top": y, "width": w, "height": h}
                        width, height = w, h
            except Exception as e:
                print(f"Window capture error: {e}")

        # Region එකක් සොයා ගැනීමට නොහැකි වුවහොත් මුළු Screen එකම ලබා ගැනීම
        if not region:
            region = monitor

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

        while _is_recording_flag:
            start_time = time.time()

            # Window එක Minimize කර ඇත්නම් හෝ මකා දමා ඇත්නම් error එකක් ඒම වැළැක්වීම
            try:
                if record_mode == "Window" and window_title and window_title != "None":
                    import win32gui
                    hwnd = win32gui.FindWindow(None, window_title)
                    if hwnd:
                        rect = win32gui.GetWindowRect(hwnd)
                        x, y, x2, y2 = rect
                        w, h = x2 - x, y2 - y
                        if w > 0 and h > 0:
                            region = {"left": x, "top": y, "width": w, "height": h}
            except:
                pass

            # Screen/Window Capture
            img = np.array(sct.grab(region))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Window එකේ සයිස් එක වෙනස් වුවහොත් VideoWriter එකට ගැලපෙන සේ Resize කිරීම
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))

            out.write(frame)

            elapsed = time.time() - start_time
            delay = max(0, (1.0 / fps) - elapsed)
            time.sleep(delay)

        out.release()


def start_screen_recording(custom_save_path=None, record_mode="Screen", window_title=None):
    """Screen Recording එක ආරම්භ කිරීම"""
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
        args=(custom_save_path, record_mode, window_title), 
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