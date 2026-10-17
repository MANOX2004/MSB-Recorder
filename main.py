import flet as ft
from ui_components import (
    BG_COLOR, BORDER_COLOR, CARD_BG, TEXT_MUTED, card_border,
    create_title_bar, create_header, section_title,
    get_what_to_record, get_window_picker_ui, get_display_dropdown,
    get_include_options, get_quality_options,
    get_record_controls, get_footer
)
from logic import get_all_open_windows, get_connected_displays

def main(page: ft.Page):
    # Window Settings
    page.title = "MSB Recorder"
    page.window.width = 410
    page.window.height = 680
    page.window.resizable = False
    page.window.frameless = True
    page.window.bgcolor = ft.Colors.TRANSPARENT
    page.bgcolor = ft.Colors.TRANSPARENT
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK

    # State Variables
    current_mode = "Screen"
    selected_window_title = "None"
    selected_area = {"x": 0, "y": 0, "w": 0, "h": 0} # Area coordinates
    
    # Include Options State (Main screen buttons සඳහා)
    include_states = {
        "System audio": True,
        "Mic": False,
        "Webcam": False,
        "Cursor": True,
        "Clicks": False,
        "Keys": False
    }

    # Settings වල Advanced Dropdown States (උදාහරණ සඳහා Audio Source / Webcam Source වැනි ඒවා)
    advanced_settings = {
        "Audio Source": "Default System Audio",
        "Microphone": "None",
        "Webcam Source": "HD Camera",
        "Cursor Highlight": "Enabled"
    }

    content_column = ft.Column(spacing=8)

    def minimize_window(e):
        page.window.minimized = True
        page.update()

    async def close_window(e):
        await page.window.close()

    def on_mode_change(mode):
        nonlocal current_mode
        current_mode = mode
        if mode == "Area":
            open_area_selector(None)
        update_ui()

    # Night Mode / Light Mode Toggle Function
    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        page.update()

    # Snipping Tool වැනි Area Selector එක විවෘත කිරීම
    def open_area_selector(e):
        import os
        import pyautogui
        
        # 1. Screen එකේ තාවකාලික screenshot එකක් ගැනීම
        screenshot_path = "temp_screenshot.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)

        # Selected area values
        start_x, start_y = 0, 0
        rect_container = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.3, "#6C5CE7"),
            border=ft.Border(
                top=ft.BorderSide(2, "#6C5CE7"),
                bottom=ft.BorderSide(2, "#6C5CE7"),
                left=ft.BorderSide(2, "#6C5CE7"),
                right=ft.BorderSide(2, "#6C5CE7"),
            ),
            visible=False
        )

        def on_pan_start(evt: ft.DragStartEvent):
            nonlocal start_x, start_y
            start_x, start_y = evt.local_x, evt.local_y
            rect_container.left = start_x
            rect_container.top = start_y
            rect_container.width = 0
            rect_container.height = 0
            rect_container.visible = True
            rect_container.update()

        def on_pan_update(evt: ft.DragUpdateEvent):
            current_x, current_y = evt.local_x, evt.local_y
            
            # Width සහ Height ගණනය කිරීම (Negative values හැසිරවීම)
            w = current_x - start_x
            h = current_y - start_y
            
            if w < 0:
                rect_container.left = start_x + w
                rect_container.width = abs(w)
            else:
                rect_container.width = w

            if h < 0:
                rect_container.top = start_y + h
                rect_container.height = abs(h)
            else:
                rect_container.height = h
                
            rect_container.update()

        def on_pan_end(evt: ft.DragEndEvent):
            nonlocal selected_area
            selected_area = {
                "x": int(rect_container.left or 0),
                "y": int(rect_container.top or 0),
                "w": int(rect_container.width or 100),
                "h": int(rect_container.height or 100)
            }
            # Area select වූ පසු overlay එක ඉවත් කිරීම
            if area_overlay in page.overlay:
                page.overlay.remove(area_overlay)
            page.update()
            
            # Temporary file ඉවත් කිරීම
            if os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                except:
                    pass

        # Mouse drag අල්ලා ගැනීමට GestureDetector භාවිතය
        gesture_detector = ft.GestureDetector(
            content=ft.Stack([
                ft.Image(src=screenshot_path, fit=ft.ImageFit.FILL, expand=True),
                ft.Container(bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.BLACK), expand=True), # Dim effect එක සඳහා
                rect_container
            ]),
            expand=True,
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
        )

        area_overlay = ft.View(
            route="/snipping",
            controls=[gesture_detector],
            padding=0,
            bgcolor=ft.Colors.TRANSPARENT
        )

        page.views.append(area_overlay)
        page.update()

    # Settings Dialog Window Function (Advanced Dropdowns සමඟ)
    def open_settings_dialog(e):
        displays = get_connected_displays()
        
        display_dropdown = ft.Dropdown(
            value=displays[0] if displays else None,
            options=[ft.dropdown.Option(text=disp) for disp in displays],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=12,
            border_radius=8,
            filled=True,
            content_padding=10,
            focused_border_color="#6C5CE7",
        )

        # Advanced Dropdowns for Include features
        # Advanced Dropdowns for Include features (on_change ඉවත් කර ඇත)
        audio_dropdown = ft.Dropdown(
            value=advanced_settings["Audio Source"],
            options=[
                ft.dropdown.Option("Default System Audio"), 
                ft.dropdown.Option("Speakers Only"), 
                ft.dropdown.Option("Mute All")
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=12, filled=True,
        )

        mic_dropdown = ft.Dropdown(
            value=advanced_settings["Microphone"],
            options=[
                ft.dropdown.Option("None"), 
                ft.dropdown.Option("Default Microphone"), 
                ft.dropdown.Option("External Mic")
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=12, filled=True,
        )

        webcam_dropdown = ft.Dropdown(
            value=advanced_settings["Webcam Source"],
            options=[
                ft.dropdown.Option("HD Camera"), 
                ft.dropdown.Option("OBS Virtual Camera"), 
                ft.dropdown.Option("Disabled")
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=12, filled=True,
        )

        settings_dialog = ft.AlertDialog(
            title=ft.Text("Advanced Settings", size=14, color="white", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Select Target Display", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                    display_dropdown,
                    ft.Divider(height=10, color=BORDER_COLOR),
                    ft.Text("Advanced Audio Source", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                    audio_dropdown,
                    ft.Text("Microphone Device", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                    mic_dropdown,
                    ft.Text("Webcam Device", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                    webcam_dropdown,
                ], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
                width=340,
                height=350,
            ),
            bgcolor=BG_COLOR,
        )
        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    # Window Picker Dialog
    def open_window_picker_dialog(e):
        open_windows = get_all_open_windows()

        def select_window_and_close(win_name, dlg):
            nonlocal selected_window_title
            selected_window_title = win_name
            dlg.open = False
            page.update()
            update_ui()

        window_listView = ft.ListView(expand=1, spacing=6, padding=5)
        dialog_ref = [None]

        for win in open_windows:
            window_listView.controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WINDOW, color="#6C5CE7", size=16),
                            ft.Text(win, color="white", size=12, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ],
                    ),
                    bgcolor=CARD_BG,
                    padding=10,
                    border_radius=6,
                    border=card_border(BORDER_COLOR),
                    on_click=lambda _, w=win: select_window_and_close(w, dialog_ref[0]),
                )
            )

        dialog = ft.AlertDialog(
            title=ft.Text("Select a Window to Record", size=14, color="white", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=window_listView,
                width=320,
                height=300,
            ),
            bgcolor=BG_COLOR,
        )
        
        dialog_ref[0] = dialog
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    def update_ui():
        content_column.controls.clear()

        # Main screen එකේ Include buttons සඳහා action එක සකස් කිරීම
        def toggle_include_option(label):
            include_states[label] = not include_states[label]
            update_ui()

        inc1, inc2 = get_include_options(include_states, toggle_include_option)

        controls_list = [
            create_title_bar(page, minimize_window, close_window),
            create_header(on_theme_toggle=toggle_theme, on_settings_click=open_settings_dialog),
            section_title("WHAT TO RECORD"),
            get_what_to_record(selected_mode=current_mode, on_select=on_mode_change),
        ]

        if current_mode == "Window":
            controls_list.append(get_window_picker_ui(selected_window_title, open_window_picker_dialog))

        # ප්‍රධාන තිරයේ පරණ පරිදිම Include buttons පෙන්වීම
        controls_list.extend([
            section_title("INCLUDE"),
            inc1,
            inc2,
            section_title("QUALITY"),
            get_quality_options(),
            get_record_controls(),
            ft.Divider(height=1, color=BORDER_COLOR),
            get_footer(),
        ])

        content_column.controls.extend(controls_list)
        page.update()

    main_container = ft.Container(
        content=content_column,
        bgcolor=BG_COLOR,
        border_radius=16,
        border=card_border(BORDER_COLOR),
        padding=16,
        expand=True,
    )

    page.add(main_container)
    update_ui()

ft.run(main)