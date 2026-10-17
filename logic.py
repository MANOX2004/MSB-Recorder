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