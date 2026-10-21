import flet as ft
from datetime import datetime
import subprocess
from logic import (
    get_audio_capture_devices,
    get_video_capture_devices,
    start_screen_recording,
    stop_screen_recording,
)
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
    is_recording = False
    selected_area = {"x": 0, "y": 0, "w": 0, "h": 0} # Area coordinates

    import os
    videos_dir = os.path.join(os.path.expanduser("~"), "Videos")
    default_save_path = os.path.join(videos_dir, "MSB Recordings")

    # Include Options State (Main screen buttons සඳහා)
    try:
        audio_capture_devices = get_audio_capture_devices()
    except Exception as error:
        audio_capture_devices = []
        audio_device_error = str(error)
    else:
        audio_device_error = None

    microphone_devices = [
        device for device in audio_capture_devices if not device["is_loopback"]
    ]
    loopback_devices = [
        device for device in audio_capture_devices if device["is_loopback"]
    ]
    try:
        webcam_devices = get_video_capture_devices()
    except (OSError, subprocess.SubprocessError) as error:
        webcam_devices = []
        webcam_device_error = str(error)
    else:
        webcam_device_error = None

    include_states = {
        "System audio": bool(loopback_devices),
        "Mic": False,
        "Webcam": False,
        "Cursor": False,
        "Clicks": False,
        "Keys": False
    }

    # Settings වල Advanced Dropdown States
    advanced_settings = {
        "Resolution": "1920 x 1080 (Full HD)",
        "Frame Rate": "60 FPS",
        "Quality": "High",
        "Output Format": "MP4 (Recommended)",
        "Save Path": default_save_path,
        "Microphone": microphone_devices[0]["id"] if microphone_devices else None,
        "Audio Source": loopback_devices[0]["id"] if loopback_devices else None,
        "Webcam Source": webcam_devices[0] if webcam_devices else None,
    }

    # මෙතැන expand=True සහ SPACE_BETWEEN මඟින් මුළු ඉඩ හරියටම බෙදා හරිනු ලැබේ
    content_column = ft.Column(
        spacing=8,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        expand=True
    )

    # Record button එක ක්ලික් කළ විට රෙකෝඩින් ආරම්භ වීම / නැවතීම
    def toggle_recording(e):
        nonlocal is_recording
        error_message = None
        saved_file = None
        if not is_recording:
            save_loc = advanced_settings.get("Save Path", default_save_path)
            resolution = {
                "1920 x 1080 (Full HD)": (1920, 1080),
                "1280 x 720 (HD)": (1280, 720),
                "3840 x 2160 (4K)": (3840, 2160),
            }[advanced_settings["Resolution"]]
            frame_rate = int(advanced_settings["Frame Rate"].split()[0])
            output_format = advanced_settings["Output Format"].split()[0].lower()
            audio_inputs = {}
            if include_states["Mic"]:
                microphone_id = advanced_settings.get("Microphone")
                if not microphone_id:
                    error_message = "No microphone is available. Connect a microphone and reopen Settings."
                else:
                    audio_inputs["mic"] = microphone_id
            if include_states["System audio"]:
                loopback_id = advanced_settings.get("Audio Source")
                if not loopback_id:
                    error_message = "No system-audio loopback device is available on this computer."
                else:
                    audio_inputs["system_audio"] = loopback_id
            webcam_device = None
            if include_states["Webcam"]:
                webcam_device = advanced_settings.get("Webcam Source")
                if not webcam_device:
                    error_message = "No webcam is available. Connect a webcam and reopen Settings."
            try:
                if error_message:
                    raise ValueError(error_message)
                start_screen_recording(
                    custom_save_path=save_loc,
                    record_mode=current_mode,
                    window_title=selected_window_title,
                    resolution=resolution,
                    frame_rate=frame_rate,
                    quality=advanced_settings["Quality"],
                    output_format=output_format,
                    audio_inputs=audio_inputs,
                    mix_audio=True,
                    webcam_device=webcam_device,
                    include_cursor=include_states["Cursor"],
                    include_clicks=include_states["Clicks"],
                    include_keys=include_states["Keys"],
                )
                is_recording = True
            except (OSError, RuntimeError, ValueError) as error:
                is_recording = False
                error_message = str(error)
        else:
            try:
                saved_file = stop_screen_recording()
            except (OSError, RuntimeError) as error:
                error_message = str(error)
            finally:
                is_recording = False

        update_ui()
        if error_message:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Recording error"),
                content=ft.Text(error_message),
                bgcolor=BG_COLOR,
            ))
        elif saved_file:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Recording saved"),
                content=ft.Text(f"Saved video to:\n{saved_file}"),
                bgcolor=BG_COLOR,
            ))

    def open_recordings(e):
        import os

        save_path = advanced_settings.get("Save Path", default_save_path)
        try:
            os.makedirs(save_path, exist_ok=True)
            os.startfile(save_path)
        except OSError as error:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Could not open recordings folder"),
                content=ft.Text(str(error)),
                bgcolor=BG_COLOR,
            ))

    def take_screenshot(e):
        import pyautogui
        import pyscreeze

        save_path = advanced_settings.get("Save Path", default_save_path)
        screenshot_path = os.path.join(
            save_path,
            f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png",
        )
        try:
            os.makedirs(save_path, exist_ok=True)
            pyautogui.screenshot().save(screenshot_path)
        except (OSError, pyautogui.PyAutoGUIException, pyscreeze.PyScreezeException) as error:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Could not take screenshot"),
                content=ft.Text(str(error)),
                bgcolor=BG_COLOR,
            ))
            return

        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Screenshot saved"),
            content=ft.Text(f"Saved screenshot to:\n{screenshot_path}"),
            bgcolor=BG_COLOR,
        ))

    def minimize_window(e):
        page.window.minimized = True
        page.update()

    async def close_window(e):
        await page.window.close()

    def on_mode_change(mode):
        nonlocal current_mode
        if mode == "Area":
            open_coming_soon_dialog(None)
            return
        current_mode = mode
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
            page.pop_dialog()

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
        page.show_dialog(coming_soon_dialog)

    def open_settings_dialog(e):
        settings_include_states = include_states.copy()
        settings_error = ft.Text(
            value="\n".join(
                error
                for error in (audio_device_error, webcam_device_error)
                if error
            ),
            color="#FF6B6B",
            size=11,
            visible=bool(audio_device_error or webcam_device_error),
        )

        def include_switch(label):
            return ft.Switch(
                value=settings_include_states[label],
                active_color="#3B82F6",
                on_change=lambda event: settings_include_states.__setitem__(
                    label, event.control.value
                ),
            )

        # ---------------- Video Settings Controls ----------------
        res_dropdown = ft.Dropdown(
            value=advanced_settings.get("Resolution", "1920 x 1080 (Full HD)"),
            options=[
                ft.dropdown.Option("1920 x 1080 (Full HD)"),
                ft.dropdown.Option("1280 x 720 (HD)"),
                ft.dropdown.Option("3840 x 2160 (4K)"),
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", expand=True
        )

        fps_dropdown = ft.Dropdown(
            value=advanced_settings.get("Frame Rate", "60 FPS"),
            options=[
                ft.dropdown.Option("60 FPS"),
                ft.dropdown.Option("30 FPS"),
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", width=95
        )

        quality_dropdown = ft.Dropdown(
            value=advanced_settings.get("Quality", "High"),
            options=[
                ft.dropdown.Option("High"),
                ft.dropdown.Option("Ultra Lossless"),
                ft.dropdown.Option("Medium"),
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", width=95
        )

        format_dropdown = ft.Dropdown(
            value=advanced_settings.get("Output Format", "MP4 (Recommended)"),
            options=[
                ft.dropdown.Option("MP4 (Recommended)"),
                ft.dropdown.Option("MKV"),
                ft.dropdown.Option("AVI"),
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", expand=True
        )

        # ---------------- Audio Settings Controls ----------------
        mic_options = [
            ft.dropdown.Option(key=device["id"], text=device["name"])
            for device in microphone_devices
        ]
        mic_dropdown = ft.Dropdown(
            value=advanced_settings.get("Microphone"),
            options=mic_options,
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", expand=True,
            disabled=not microphone_devices
        )
        mic_switch = include_switch("Mic")

        loopback_options = [
            ft.dropdown.Option(key=device["id"], text=device["name"])
            for device in loopback_devices
        ]
        sys_audio_dropdown = ft.Dropdown(
            value=advanced_settings.get("Audio Source"),
            options=loopback_options,
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", expand=True,
            disabled=not loopback_devices
        )
        sys_audio_switch = include_switch("System audio")

        def on_audio_switch_change(label, event):
            settings_include_states[label] = event.control.value
            page.update()

        mic_switch.on_change = lambda event: on_audio_switch_change("Mic", event)
        sys_audio_switch.on_change = lambda event: on_audio_switch_change(
            "System audio", event
        )

        webcam_dropdown = ft.Dropdown(
            value=advanced_settings.get("Webcam Source"),
            options=[ft.dropdown.Option(device) for device in webcam_devices],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=11,
            filled=True,
            border_radius=8,
            content_padding=8,
            focused_border_color="#6C5CE7",
            expand=True,
            disabled=not webcam_devices,
        )
        webcam_switch = include_switch("Webcam")
        cursor_switch = include_switch("Cursor")
        clicks_switch = include_switch("Clicks")
        keys_switch = include_switch("Keys")

        # ---------------- Other Settings Controls (Tkinter Folder Picker) ----------------
        save_path_input = ft.TextField(
            value=advanced_settings.get("Save Path", default_save_path),
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11,
            border_radius=8, content_padding=10, focused_border_color="#6C5CE7", expand=True, read_only=True
        )
        def browse_folder(e):
            import tkinter as tk
            from tkinter import filedialog
            root = None
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                initial_dir = save_path_input.value or videos_dir
                if not os.path.isdir(initial_dir):
                    initial_dir = os.path.dirname(initial_dir)
                if not os.path.isdir(initial_dir):
                    initial_dir = os.path.expanduser("~")
                chosen_dir = filedialog.askdirectory(
                    initialdir=initial_dir
                )
                if chosen_dir:
                    save_path_input.value = chosen_dir
                    save_path_input.update()
            except tk.TclError as error:
                settings_error.value = f"Could not open the folder picker: {error}"
                settings_error.visible = True
                settings_error.update()
            finally:
                if root is not None:
                    root.destroy()

        # Card Container Generator Function
        def build_card(icon, title, subtitle, content_controls):
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(icon, color="#3B82F6", size=18),
                                ft.Column(
                                    controls=[
                                        ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="white"),
                                        ft.Text(subtitle, size=10, color=TEXT_MUTED),
                                    ],
                                    spacing=1
                                )
                            ],
                            spacing=8
                        ),
                        ft.Container(height=2),
                        *content_controls
                    ],
                    spacing=8
                ),
                bgcolor="#161922",
                border=card_border(BORDER_COLOR),
                border_radius=10,
                padding=12
            )

        # --- Section 1: Video Settings Card ---
        video_card = build_card(
            ft.Icons.VIDEOCAM_OUTLINED,
            "Video Settings",
            "Set the video quality and format.",
            [
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Resolution", size=10, color=TEXT_MUTED), res_dropdown], expand=True, spacing=2),
                    ],
                    spacing=6
                ),
                ft.Row(
                    controls=[
                        ft.Column([ft.Text("Frame Rate", size=10, color=TEXT_MUTED), fps_dropdown], spacing=2),
                        ft.Column([ft.Text("Quality", size=10, color=TEXT_MUTED), quality_dropdown], spacing=2),
                    ],
                    spacing=6
                ),
                ft.Column([
                    ft.Text("Output Format", size=10, color=TEXT_MUTED),
                    format_dropdown
                ], spacing=2)
            ]
        )

        # --- Section 2: Audio Settings Card ---
        audio_card = build_card(
            ft.Icons.VOLUME_UP_OUTLINED,
            "Audio Settings",
            "Selected microphone and system audio are mixed automatically.",
            [
                ft.Text(
                    "Select both sources to enable mixing; Mix locks these switches while active.",
                    size=10,
                    color=TEXT_MUTED,
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MIC_OUTLINED, color=TEXT_MUTED, size=16),
                        ft.Text("Microphone", size=11, color="white", width=80),
                        mic_dropdown,
                        mic_switch
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.VOLUME_UP_ROUNDED, color=TEXT_MUTED, size=16),
                        ft.Text("System Audio", size=11, color="white", width=80),
                        sys_audio_dropdown,
                        sys_audio_switch
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6
                ),
            ]
        )

        include_card = build_card(
            ft.Icons.TUNE,
            "Capture Options",
            "These switches stay in sync with the main-screen shortcuts.",
            [
                ft.Row(
                    controls=[
                        ft.Text("Webcam", size=11, color="white", expand=True),
                        webcam_dropdown,
                        webcam_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Show cursor", size=11, color="white", expand=True),
                        cursor_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Highlight clicks", size=11, color="white", expand=True),
                        clicks_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Show key presses", size=11, color="white", expand=True),
                        keys_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6,
                ),
            ],
        )

        # --- Section 3: Other Settings Card ---
        other_card = build_card(
            ft.Icons.SETTINGS_OUTLINED,
            "Other Settings",
            "Additional options for a better experience.",
            [
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.FOLDER_OUTLINED, color=TEXT_MUTED, size=16),
                        ft.Text("Save location", size=11, color="white", width=80),
                        save_path_input,
                        ft.Container(
                            content=ft.Text("Browse", size=11, color="white", weight=ft.FontWeight.W_500),
                            bgcolor="#222736",
                            padding=10,
                            border_radius=6,
                            on_click=browse_folder
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6
                )
            ]
        )

        def save_settings(evt):
            selected_path = (save_path_input.value or "").strip()
            if not selected_path:
                settings_error.value = "Choose a folder where recordings can be saved."
                settings_error.visible = True
                settings_error.update()
                return

            try:
                os.makedirs(selected_path, exist_ok=True)
            except OSError as error:
                settings_error.value = f"Could not use this save folder: {error}"
                settings_error.visible = True
                settings_error.update()
                return

            advanced_settings.update({
                "Resolution": res_dropdown.value,
                "Frame Rate": fps_dropdown.value,
                "Quality": quality_dropdown.value,
                "Output Format": format_dropdown.value,
                "Save Path": selected_path,
                "Microphone": mic_dropdown.value,
                "Audio Source": sys_audio_dropdown.value,
                "Webcam Source": webcam_dropdown.value,
            })
            include_states.update(settings_include_states)
            settings_error.visible = False
            main_container.content = content_column
            update_ui()

        def cancel_settings(evt):
            main_container.content = content_column
            page.update()

        settings_view = ft.Column(
            controls=[
                create_title_bar(page, minimize_window, close_window),
                ft.Row(
                    controls=[
                        ft.Text(
                            "Capture Settings",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color="white",
                            expand=True,
                        ),
                        ft.TextButton("Back", on_click=cancel_settings),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Column(
                    controls=[
                        video_card,
                        audio_card,
                        include_card,
                        other_card,
                        settings_error,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                ft.Row(
                    controls=[
                        ft.TextButton("Cancel", on_click=cancel_settings),
                        ft.FilledButton(
                            "Save Changes",
                            on_click=save_settings,
                            bgcolor="#3B82F6",
                            color="white",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=10,
                ),
            ],
            spacing=8,
            expand=True,
        )
        main_container.content = settings_view
        page.update()

    # Window Picker Dialog
    def open_window_picker_dialog(e):
        open_windows = get_all_open_windows()

        def select_window_and_close(win_name):
            nonlocal selected_window_title
            selected_window_title = win_name
            page.pop_dialog()
            page.update()
            update_ui()

        window_listView = ft.ListView(expand=1, spacing=6, padding=5)

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
                    on_click=lambda _, w=win: select_window_and_close(w),
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
        
        page.show_dialog(dialog)

    def update_ui():
        content_column.controls.clear()

        def toggle_include_option(label):
            include_states[label] = not include_states[label]
            update_ui()

        inc1, inc2 = get_include_options(
            include_states, on_toggle=toggle_include_option
        )

        controls_list = [
            create_title_bar(page, minimize_window, close_window),
            create_header(on_settings_click=open_settings_dialog),
            section_title("WHAT TO RECORD"),
            get_what_to_record(selected_mode=current_mode, on_select=on_mode_change),
        ]

        if current_mode == "Window":
            controls_list.append(get_window_picker_ui(selected_window_title, open_window_picker_dialog))

        controls_list.extend([
            section_title("INCLUDE"),
            ft.Text(
                "Quick switches here stay synchronized with Settings.",
                size=10,
                color=TEXT_MUTED,
            ),
            inc1,
            inc2,
            ft.Container(expand=True),  
            get_record_controls(
                is_recording=is_recording,
                on_record_click=toggle_recording,
                on_screenshot_click=take_screenshot,
            ),
            ft.Divider(height=1, color=BORDER_COLOR),
            get_footer(on_open_recordings=open_recordings),
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
    page.run_task(center_window, page)

async def center_window(page):
    await page.window.center()

ft.run(main)