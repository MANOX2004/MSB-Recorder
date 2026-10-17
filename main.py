import flet as ft
from ui_components import (
    BG_COLOR, BORDER_COLOR, CARD_BG, TEXT_MUTED, card_border,
    create_title_bar, create_header, section_title,
    get_what_to_record, get_window_picker_ui, get_display_dropdown,
    get_include_options,
    get_record_controls, get_footer
)
from logic import get_all_open_windows, get_connected_displays

def main(page: ft.Page):
    # Window Settings
    page.title = "MSB Recorder"
    page.window.width = 380
    page.window.height = 510
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

    # Settings වල Advanced Dropdown States
    advanced_settings = {
        "Audio Source": "Default System Audio",
        "Microphone": "None",
        "Webcam Source": "HD Camera",
        "Cursor Highlight": "Enabled"
    }

    # මෙතැන expand=True සහ SPACE_BETWEEN මඟින් මුළු ඉඩ හරියටම බෙදා හරිනු ලැබේ
    content_column = ft.Column(
        spacing=8,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        expand=True
    )

    def minimize_window(e):
        page.window.minimized = True
        page.update()

    async def close_window(e):
        await page.window.close()

    def on_mode_change(mode):
        nonlocal current_mode
        current_mode = mode
        if mode == "Area":
            open_coming_soon_dialog(None)
        update_ui()

    # Snipping Tool වැනි Area Selector එක (Ultimate Stable Version)
    def open_area_selector(e):
        import os
        import pyautogui
        
        screenshot_path = "temp_screenshot.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)

        coords = {"start_x": 0, "start_y": 0}

        rect_container = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.3, "#6C5CE7"),
            border=ft.Border(
                top=ft.BorderSide(2, "#6C5CE7"),
                bottom=ft.BorderSide(2, "#6C5CE7"),
                left=ft.BorderSide(2, "#6C5CE7"),
                right=ft.BorderSide(2, "#6C5CE7"),
            ),
            left=0,
            top=0,
            width=0,
            height=0,
            visible=False
        )

        def on_pan_start(evt: ft.DragStartEvent):
            coords["start_x"] = getattr(evt, 'local_x', getattr(evt, 'x', 100))
            coords["start_y"] = getattr(evt, 'local_y', getattr(evt, 'y', 100))
            
            rect_container.left = coords["start_x"]
            rect_container.top = coords["start_y"]
            rect_container.width = 0
            rect_container.height = 0
            rect_container.visible = True
            rect_container.update()

        def on_pan_update(evt: ft.DragUpdateEvent):
            dx = getattr(evt, 'delta_x', getattr(evt, 'dx', 0))
            dy = getattr(evt, 'delta_y', getattr(evt, 'dy', 0))
            if dx is None: dx = 5
            if dy is None: dy = 5

            new_w = (rect_container.width or 0) + dx
            new_h = (rect_container.height or 0) + dy

            if new_w >= 0:
                rect_container.width = new_w
            if new_h >= 0:
                rect_container.height = new_h

            rect_container.update()

        def on_pan_end(evt: ft.DragEndEvent):
            nonlocal selected_area
            selected_area = {
                "x": int(rect_container.left or 0),
                "y": int(rect_container.top or 0),
                "w": int(rect_container.width or 100),
                "h": int(rect_container.height or 100)
            }
            if area_overlay in page.views:
                page.views.remove(area_overlay)
            page.update()
            
            if os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                except:
                    pass

        gesture_detector = ft.GestureDetector(
            content=ft.Stack([
                ft.Image(src=screenshot_path, fit="fill", expand=True),
                ft.Container(bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.BLACK), expand=True),
                rect_container
            ], expand=True),
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

    # Coming Soon Dialog එක විවෘත කිරීම
    def open_coming_soon_dialog(e):
        def close_dlg(evt):
            coming_soon_dialog.open = False
            page.update()

        coming_soon_dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color="#6C5CE7", size=20),
                    ft.Text("Coming Soon!", size=14, color="white", weight=ft.FontWeight.BOLD)
                ],
                spacing=8
            ),
            content=ft.Text(
                "Area recording feature is under development and will be available soon!",
                size=12,
                color=TEXT_MUTED
            ),
            actions=[
                ft.TextButton("OK", on_click=close_dlg)
            ],
            bgcolor=BG_COLOR,
        )
        page.overlay.append(coming_soon_dialog)
        coming_soon_dialog.open = True
        page.update()

    # Settings Dialog Window Function
    def open_settings_dialog(e):
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

        quality_dropdown = ft.Dropdown(
            value=advanced_settings.get("Quality", "1080p 60FPS"),
            options=[
                ft.dropdown.Option("1080p 60FPS"),
                ft.dropdown.Option("1080p 30FPS"),
                ft.dropdown.Option("720p 60FPS"),
                ft.dropdown.Option("4K 60FPS")
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=12, filled=True,
        )

        def save_settings(evt):
            advanced_settings["Audio Source"] = audio_dropdown.value
            advanced_settings["Microphone"] = mic_dropdown.value
            advanced_settings["Webcam Source"] = webcam_dropdown.value
            advanced_settings["Quality"] = quality_dropdown.value
            settings_dialog.open = False
            page.update()

        settings_dialog = ft.AlertDialog(
            title=ft.Text("Advanced Settings", color="white", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Column(
                controls=[
                    ft.Text("Audio Source", color=TEXT_MUTED, size=11),
                    audio_dropdown,
                    ft.Container(height=5),
                    ft.Text("Microphone", color=TEXT_MUTED, size=11),
                    mic_dropdown,
                    ft.Container(height=5),
                    ft.Text("Webcam Source", color=TEXT_MUTED, size=11),
                    webcam_dropdown,
                    ft.Container(height=5),
                    ft.Text("Recording Quality", color=TEXT_MUTED, size=11),
                    quality_dropdown,
                ],
                tight=True,
                spacing=8,
                width=300,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: setattr(settings_dialog, 'open', False) or page.update()),
                ft.FilledButton("Save", on_click=save_settings, bgcolor="#6C5CE7", color="white"),
            ],
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

        def toggle_include_option(label):
            include_states[label] = not include_states[label]
            update_ui()

        inc1, inc2 = get_include_options(include_states, toggle_include_option)

        controls_list = [
            create_title_bar(page, minimize_window, close_window),
            create_header(on_settings_click=open_settings_dialog),
            section_title("WHAT TO RECORD"),
            get_what_to_record(selected_mode=current_mode, on_select=on_mode_change),
        ]

        if current_mode == "Window":
            controls_list.append(get_window_picker_ui(selected_window_title, open_window_picker_dialog))

        # Include බටන් සහ පහළ කොටස (Record controls & footer) හරියටම පහළටම තල්ලු කිරීමට ft.Container(expand=True) යොදා ඇත
        controls_list.extend([
            section_title("INCLUDE"),
            inc1,
            inc2,
            ft.Container(expand=True),  
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
        border=card_border("#6C5CE7"),
        padding=16,
        expand=True,
    )

    page.add(main_container)
    update_ui()

ft.run(main)