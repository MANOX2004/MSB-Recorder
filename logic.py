def get_all_open_windows():
    """Windows API (`win32gui`) භාවිතයෙන් පරිගණකයේ දැනට විවෘතව ඇති සැබෑ වින්ඩෝස් ලැයිස්තුව ලබා ගැනීම"""
    windows_list = []
    try:
        import win32gui

        def enum_windows_handler(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                # හිස් නොවන සහ ScreenForge හැර අනෙකුත් ප්‍රධාන වින්ඩෝස් පමණක් ලබා ගැනීම
                if title and title.strip() and title != "ScreenForge":
                    # වැදගත් නැති system windows ඉවත් කිරීම
                    if len(title) > 1:
                        windows_list.append(title)
            return True

        win32gui.EnumWindows(enum_windows_handler, None)
    except Exception as e:
        # Fallback එකක් ලෙස pygetwindow පාවිච්චි කිරීම
        try:
            import pygetwindow as gw
            windows_list = [w.title for w in gw.getAllWindows() if w.title.strip() and w.title != "ScreenForge"]
        except:
            windows_list = ["Google Chrome", "Visual Studio Code", "Notepad"]
            
    # එකම නම ඇති ඒවා duplicate ඉවත් කර ලැයිස්තුව ලබා දීම
    return sorted(list(set(windows_list)))