import flet as ft
import asyncio
from datetime import datetime
import subprocess
from logic import (
    get_audio_capture_devices,
    get_video_capture_devices,
    capture_region_screenshot,
    capture_window_screenshot,
    AreaFrameOverlay,
    select_capture_region,
    start_screen_recording,
    stop_screen_recording,
    set_recording_paused,
)
from ui_components import (
    BG_COLOR, BORDER_COLOR, CARD_BG, TEXT_MUTED, card_border,
    create_title_bar, create_header, section_title,
    get_what_to_record, get_window_picker_ui, get_display_dropdown,
    get_include_options,
    get_record_controls, get_footer
)
from logic import get_all_open_windows, get_connected_displays
from pynput import keyboard
from settings_store import load_settings, save_settings as save_settings_file

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
    selected_area = None
    area_frame_overlay = None
    area_status_text = None
    is_paused = False
    hotkey_listener = None
    shortcut_capture_target = None
    shortcut_capture_fields = {}
    shortcut_capture_values = {}
    shortcut_capture_listener = None

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
        "Screenshot Format": "PNG",
        "Show Save Confirmation": True,
        "Hotkeys": {
            "Record": "<f9>",
            "Stop": "<f10>",
            "Pause": "<f11>",
            "Screenshot": "<f12>",
        },
        "Save Path": default_save_path,
        "Microphone": microphone_devices[0]["id"] if microphone_devices else None,
        "Audio Source": loopback_devices[0]["id"] if loopback_devices else None,
        "Webcam Source": webcam_devices[0] if webcam_devices else None,
        "Key Overlay Position": "Left",
        "Key Overlay Size": "Medium",
        "Key Overlay Color": "#6C5CE7",
        "Key Overlay Key Type": "All Keys",
        "Webcam Position": "Top Right",
    }
    settings_load_error = None
    try:
        loaded_settings, loaded_include_states = load_settings(
            advanced_settings,
            include_states,
        )
        advanced_settings.update(loaded_settings)
        include_states.update(loaded_include_states)
    except RuntimeError as error:
        settings_load_error = str(error)

    available_microphones = {device["id"] for device in microphone_devices}
    if advanced_settings["Microphone"] not in available_microphones:
        advanced_settings["Microphone"] = (
            microphone_devices[0]["id"] if microphone_devices else None
        )
    available_loopbacks = {device["id"] for device in loopback_devices}
    if advanced_settings["Audio Source"] not in available_loopbacks:
        advanced_settings["Audio Source"] = (
            loopback_devices[0]["id"] if loopback_devices else None
        )
    if advanced_settings["Webcam Source"] not in webcam_devices:
        advanced_settings["Webcam Source"] = (
            webcam_devices[0] if webcam_devices else None
        )

    invalid_hotkeys = False
    shortcut_signatures = set()
    for action, shortcut in advanced_settings["Hotkeys"].items():
        try:
            parsed_shortcut = keyboard.HotKey.parse(shortcut)
        except (TypeError, ValueError):
            invalid_hotkeys = True
            break
        signature = tuple(sorted(repr(key) for key in parsed_shortcut))
        if signature in shortcut_signatures:
            invalid_hotkeys = True
            break
        shortcut_signatures.add(signature)
    if invalid_hotkeys:
        advanced_settings["Hotkeys"] = {
            "Record": "<f9>",
            "Stop": "<f10>",
            "Pause": "<f11>",
            "Screenshot": "<f12>",
        }
        settings_load_error = (
            "Saved shortcuts were invalid or duplicated and have been reset "
            "to their defaults."
        )

    # මෙතැන expand=True සහ SPACE_BETWEEN මඟින් මුළු ඉඩ හරියටම බෙදා හරිනු ලැබේ
    content_column = ft.Column(
        spacing=8,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        expand=True
    )

    # Record button එක ක්ලික් කළ විට රෙකෝඩින් ආරම්භ වීම / නැවතීම
    def toggle_recording(e):
        nonlocal is_recording, is_paused
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
            if current_mode == "Area" and selected_area is None:
                error_message = "Select an area before starting the recording."
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
                    key_overlay_position=advanced_settings["Key Overlay Position"],
                    key_overlay_size=advanced_settings["Key Overlay Size"],
                    key_overlay_color=advanced_settings["Key Overlay Color"],
                    key_overlay_key_type=advanced_settings["Key Overlay Key Type"],
                    webcam_position=advanced_settings["Webcam Position"],
                    capture_region=(
                        dict(selected_area)
                        if current_mode == "Area" and selected_area
                        else None
                    ),
                )
                is_recording = True
                is_paused = False
                if current_mode == "Area" and area_frame_overlay:
                    area_frame_overlay.set_recording(True)
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
                is_paused = False
                if area_frame_overlay:
                    area_frame_overlay.set_recording(False)

        update_ui()
        if error_message:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Recording error"),
                content=ft.Text(error_message),
                bgcolor=BG_COLOR,
            ))
        elif saved_file and advanced_settings["Show Save Confirmation"]:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Recording saved"),
                content=ft.Text(f"Saved video to:\n{saved_file}"),
                bgcolor=BG_COLOR,
            ))

    def toggle_pause(e):
        nonlocal is_paused
        if not is_recording:
            return
        try:
            set_recording_paused(not is_paused)
            is_paused = not is_paused
        except RuntimeError as error:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Could not change pause state"),
                content=ft.Text(str(error)),
                bgcolor=BG_COLOR,
            ))
        update_ui()

    async def handle_hotkey(action):
        if shortcut_capture_target:
            return
        if action == "Record" and not is_recording:
            toggle_recording(None)
        elif action == "Stop" and is_recording:
            toggle_recording(None)
        elif action == "Pause" and is_recording:
            toggle_pause(None)
        elif action == "Screenshot":
            take_screenshot(None)

    def install_hotkeys(shortcuts):
        nonlocal hotkey_listener
        callbacks = {
            shortcut: (
                lambda action=action: page.run_task(handle_hotkey, action)
            )
            for action, shortcut in shortcuts.items()
        }
        listener = keyboard.GlobalHotKeys(callbacks)
        listener.start()
        previous_listener = hotkey_listener
        hotkey_listener = listener
        if previous_listener:
            previous_listener.stop()

    def format_hotkey(shortcut):
        key_names = {
            "esc": "Esc",
            "space": "Space",
            "enter": "Enter",
            "tab": "Tab",
            "backspace": "Backspace",
            "delete": "Delete",
            "insert": "Insert",
            "home": "Home",
            "end": "End",
            "page_up": "Page Up",
            "page_down": "Page Down",
            "left": "Left",
            "right": "Right",
            "up": "Up",
            "down": "Down",
        }
        modifier_names = {
            keyboard.Key.ctrl: "Ctrl",
            keyboard.Key.shift: "Shift",
            keyboard.Key.alt: "Alt",
            keyboard.Key.cmd: "Win",
        }
        virtual_key_names = {
            19: "Pause",
            20: "Caps Lock",
            44: "Print Screen",
            45: "Insert",
            46: "Delete",
            144: "Num Lock",
            145: "Scroll Lock",
            166: "Browser Back",
            167: "Browser Forward",
            168: "Browser Refresh",
            169: "Browser Stop",
            170: "Browser Search",
            171: "Browser Favorites",
            172: "Browser Home",
            173: "Mute",
            174: "Volume Down",
            175: "Volume Up",
            176: "Media Next",
            177: "Media Previous",
            178: "Media Stop",
            179: "Media Play/Pause",
        }
        parts = []
        for key in keyboard.HotKey.parse(shortcut):
            if key in modifier_names:
                parts.append(modifier_names[key])
            elif isinstance(key, keyboard.KeyCode):
                if key.char:
                    parts.append(key.char.upper())
                elif key.vk in range(112, 136):
                    parts.append(f"F{key.vk - 111}")
                else:
                    parts.append(virtual_key_names.get(key.vk, f"Key {key.vk}"))
            else:
                key_name = key.name.casefold()
                parts.append(
                    key_names.get(key_name, key_name.replace("_", " ").title())
                )
        return " + ".join(parts)

    def shortcut_signature(shortcut):
        return tuple(sorted(
            repr(key) for key in keyboard.HotKey.parse(shortcut)
        ))

    def find_shortcut_conflict(action, shortcut):
        signature = shortcut_signature(shortcut)
        return next(
            (
                assigned_action
                for assigned_action, assigned_shortcut
                in shortcut_capture_values.items()
                if assigned_action != action
                and shortcut_signature(assigned_shortcut) == signature
            ),
            None,
        )

    def begin_shortcut_capture(action):
        nonlocal hotkey_listener, shortcut_capture_listener
        nonlocal shortcut_capture_target
        if shortcut_capture_target:
            previous_field = shortcut_capture_fields[shortcut_capture_target]
            previous_field.content.value = format_hotkey(
                shortcut_capture_values[shortcut_capture_target]
            )
            previous_field.update()
        if shortcut_capture_listener:
            shortcut_capture_listener.stop()
            shortcut_capture_listener.join(timeout=1)
            shortcut_capture_listener = None
        shortcut_capture_target = action
        if hotkey_listener:
            hotkey_listener.stop()
            hotkey_listener.join(timeout=1)
            hotkey_listener = None

        field = shortcut_capture_fields[action]
        field.content.value = "Press a key..."
        field.update()

        modifier_names = {
            keyboard.Key.ctrl: "ctrl",
            keyboard.Key.ctrl_l: "ctrl",
            keyboard.Key.ctrl_r: "ctrl",
            keyboard.Key.shift: "shift",
            keyboard.Key.shift_l: "shift",
            keyboard.Key.shift_r: "shift",
            keyboard.Key.alt: "alt",
            keyboard.Key.alt_l: "alt",
            keyboard.Key.alt_r: "alt",
            keyboard.Key.cmd: "cmd",
            keyboard.Key.cmd_l: "cmd",
            keyboard.Key.cmd_r: "cmd",
        }
        special_names = {
            "esc": "esc",
            "space": "space",
            "enter": "enter",
            "tab": "tab",
            "backspace": "backspace",
            "delete": "delete",
            "insert": "insert",
            "home": "home",
            "end": "end",
            "page_up": "page_up",
            "page_down": "page_down",
            "left": "left",
            "right": "right",
            "up": "up",
            "down": "down",
        }
        held_modifiers = set()
        pressed_modifiers = set()
        modifier_used = False

        def on_capture_key(key):
            nonlocal modifier_used
            if shortcut_capture_target != action:
                return False
            modifier = modifier_names.get(key)
            if modifier:
                held_modifiers.add(modifier)
                pressed_modifiers.add(modifier)
                return

            if isinstance(key, keyboard.KeyCode):
                key_name = key.char.casefold() if key.char else None
                key_part = (
                    key_name
                    if key_name and len(key_name) == 1
                    else f"<{key.vk}>"
                    if key.vk is not None
                    else None
                )
            else:
                key_name = key.name.casefold()
                if key_name in special_names:
                    key_part = f"<{special_names[key_name]}>"
                else:
                    key_part = f"<{key_name}>"
            if not key_part:
                return

            modifier_used = True
            modifiers = [
                name for name in ("ctrl", "alt", "shift", "cmd")
                if name in held_modifiers
            ]
            shortcut = "+".join(
                [*(f"<{name}>" for name in modifiers), key_part]
            )
            try:
                keyboard.HotKey.parse(shortcut)
            except ValueError:
                return

            conflict = find_shortcut_conflict(action, shortcut)
            if conflict:
                settings_error = shortcut_capture_fields.get("error")
                if settings_error:
                    settings_error.value = (
                        f"{format_hotkey(shortcut)} is already assigned to {conflict}."
                    )
                    settings_error.visible = True
                    settings_error.update()
                return

            page.run_task(finish_shortcut_capture, action, shortcut)
            return False

        def on_capture_release(key):
            nonlocal modifier_used
            if shortcut_capture_target != action:
                return
            modifier = modifier_names.get(key)
            if not modifier:
                return
            held_modifiers.discard(modifier)
            if not held_modifiers and pressed_modifiers and not modifier_used:
                shortcut = "+".join(
                    f"<{name}>"
                    for name in ("ctrl", "alt", "shift", "cmd")
                    if name in pressed_modifiers
                )
                try:
                    keyboard.HotKey.parse(shortcut)
                except ValueError:
                    return
                conflict = find_shortcut_conflict(action, shortcut)
                if conflict:
                    settings_error = shortcut_capture_fields.get("error")
                    if settings_error:
                        settings_error.value = (
                            f"{format_hotkey(shortcut)} is already assigned to "
                            f"{conflict}."
                        )
                        settings_error.visible = True
                        settings_error.update()
                    return
                page.run_task(finish_shortcut_capture, action, shortcut)

        try:
            shortcut_capture_listener = keyboard.Listener(
                on_press=on_capture_key,
                on_release=on_capture_release,
            )
            shortcut_capture_listener.start()
        except (OSError, RuntimeError) as error:
            shortcut_capture_target = None
            field.content.value = format_hotkey(
                shortcut_capture_values[action]
            )
            field.update()
            settings_error = shortcut_capture_fields.get("error")
            if settings_error:
                settings_error.value = f"Could not capture shortcut: {error}"
                settings_error.visible = True
                settings_error.update()
            try:
                install_hotkeys(advanced_settings["Hotkeys"])
            except (OSError, RuntimeError, ValueError) as restore_error:
                if settings_error:
                    settings_error.value += (
                        f"\nCould not restore existing shortcuts: {restore_error}"
                    )
                    settings_error.update()

    async def finish_shortcut_capture(action, shortcut):
        nonlocal hotkey_listener, shortcut_capture_listener
        nonlocal shortcut_capture_target
        shortcut_capture_target = None
        if shortcut_capture_listener:
            shortcut_capture_listener.stop()
            shortcut_capture_listener.join(timeout=1)
            shortcut_capture_listener = None
        shortcut_capture_values[action] = shortcut
        field = shortcut_capture_fields[action]
        field.content.value = format_hotkey(shortcut)
        field.update()
        try:
            install_hotkeys(advanced_settings["Hotkeys"])
        except (OSError, RuntimeError, ValueError) as error:
            settings_error = shortcut_capture_fields.get("error")
            if settings_error:
                settings_error.value = f"Could not resume shortcuts: {error}"
                settings_error.visible = True
                settings_error.update()

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
        screenshot_format = advanced_settings["Screenshot Format"]
        file_extension = screenshot_format.lower()
        screenshot_path = os.path.join(
            save_path,
            f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{file_extension}",
        )
        try:
            os.makedirs(save_path, exist_ok=True)
            if current_mode == "Area":
                if selected_area is None:
                    raise ValueError("Select an area before taking an area screenshot.")
                screenshot = capture_region_screenshot(selected_area)
            elif current_mode == "Window":
                if not selected_window_title or selected_window_title == "None":
                    raise ValueError("Select a window before taking a window screenshot.")
                screenshot = capture_window_screenshot(selected_window_title)
            else:
                screenshot = pyautogui.screenshot()

            if screenshot_format == "JPEG":
                screenshot = screenshot.convert("RGB")
                screenshot.save(screenshot_path, format="JPEG", quality=100)
            else:
                screenshot.save(screenshot_path, format="PNG")
        except (
            OSError,
            RuntimeError,
            ValueError,
            pyautogui.PyAutoGUIException,
            pyscreeze.PyScreezeException,
        ) as error:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Could not take screenshot"),
                content=ft.Text(str(error)),
                bgcolor=BG_COLOR,
            ))
            return

        if advanced_settings["Show Save Confirmation"]:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Screenshot saved"),
                content=ft.Text(f"Saved screenshot to:\n{screenshot_path}"),
                bgcolor=BG_COLOR,
            ))

    def minimize_window(e):
        page.window.minimized = True
        page.update()

    async def close_window(e):
        if area_frame_overlay:
            area_frame_overlay.close()
        if hotkey_listener:
            hotkey_listener.stop()
        if shortcut_capture_listener:
            shortcut_capture_listener.stop()
            shortcut_capture_listener.join(timeout=1)
        await page.window.close()

    def on_mode_change(mode):
        nonlocal current_mode
        if mode == "Area":
            if selected_area and area_frame_overlay:
                current_mode = "Area"
                area_frame_overlay.set_visible(True)
                update_ui()
                return
            page.run_task(open_area_selector)
            return
        current_mode = mode
        if area_frame_overlay:
            area_frame_overlay.set_visible(False)
        update_ui()

    async def open_area_selector():
        nonlocal current_mode, selected_area, area_frame_overlay
        page.window.visible = False
        page.update()
        selection_error = None
        region = None
        try:
            await asyncio.sleep(0.2)
            region = select_capture_region()
        except (OSError, RuntimeError, ValueError) as error:
            selection_error = error
        finally:
            page.window.visible = True
            page.update()

        if selection_error:
            page.show_dialog(ft.AlertDialog(
                title=ft.Text("Could not select recording area"),
                content=ft.Text(str(selection_error)),
                bgcolor=BG_COLOR,
            ))
            return
        if region:
            try:
                def update_selected_area(updated_region):
                    nonlocal selected_area
                    selected_area = updated_region
                    if area_status_text:
                        area_status_text.value = (
                            f"Area: {selected_area['width']} x {selected_area['height']} "
                            "· Drag center to move; edges to resize"
                        )
                        page.run_task(refresh_area_status)

                def report_area_overlay_error(error):
                    async def show_error():
                        page.show_dialog(ft.AlertDialog(
                            title=ft.Text("Recording area frame error"),
                            content=ft.Text(str(error)),
                            bgcolor=BG_COLOR,
                        ))

                    page.run_task(show_error)

                def exit_area_mode():
                    async def switch_to_screen_mode():
                        if is_recording:
                            toggle_recording(None)
                        on_mode_change("Screen")

                    page.run_task(switch_to_screen_mode)

                area_frame_overlay = AreaFrameOverlay(
                    region,
                    update_selected_area,
                    exit_area_mode,
                    report_area_overlay_error,
                )
                selected_area = dict(region)
                current_mode = "Area"
                update_ui()
            except (OSError, RuntimeError, TimeoutError) as error:
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Could not show recording area"),
                    content=ft.Text(str(error)),
                    bgcolor=BG_COLOR,
                ))

    async def refresh_area_status():
        page.update()

    def open_settings_dialog(e):
        nonlocal shortcut_capture_fields, shortcut_capture_values
        nonlocal shortcut_capture_listener
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

        screenshot_format_dropdown = ft.Dropdown(
            value=advanced_settings["Screenshot Format"],
            options=[
                ft.dropdown.Option("PNG"),
                ft.dropdown.Option("JPEG"),
            ],
            bgcolor=CARD_BG, border_color=BORDER_COLOR, color="white", text_size=11, filled=True,
            border_radius=8, content_padding=8, focused_border_color="#6C5CE7", expand=True,
        )
        shortcut_capture_values = advanced_settings["Hotkeys"].copy()
        shortcut_inputs = {
            action: ft.FilledButton(
                content=ft.Text(format_hotkey(shortcut), size=11, color="white"),
                bgcolor="#222736",
                color="white",
                width=140,
                tooltip="Click, then press the shortcut key",
                on_click=lambda _event, name=action: begin_shortcut_capture(name),
            )
            for action, shortcut in advanced_settings["Hotkeys"].items()
        }
        shortcut_capture_fields = {
            **shortcut_inputs,
            "error": settings_error,
        }
        save_confirmation_switch = ft.Switch(
            value=advanced_settings["Show Save Confirmation"],
            active_color="#3B82F6",
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
        webcam_position_dropdown = ft.Dropdown(
            value=advanced_settings["Webcam Position"],
            options=[
                ft.dropdown.Option("Top Left"),
                ft.dropdown.Option("Top Right"),
                ft.dropdown.Option("Bottom Left"),
                ft.dropdown.Option("Bottom Right"),
            ],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=11,
            filled=True,
            border_radius=8,
            content_padding=8,
            focused_border_color="#6C5CE7",
            expand=True,
        )
        cursor_switch = include_switch("Cursor")
        clicks_switch = include_switch("Clicks")
        keys_switch = include_switch("Keys")
        key_overlay_position_dropdown = ft.Dropdown(
            value=advanced_settings["Key Overlay Position"],
            options=[
                ft.dropdown.Option("Left"),
                ft.dropdown.Option("Center"),
                ft.dropdown.Option("Right"),
            ],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=11,
            filled=True,
            border_radius=8,
            content_padding=8,
            focused_border_color="#6C5CE7",
            expand=True,
        )
        key_overlay_size_dropdown = ft.Dropdown(
            value=advanced_settings["Key Overlay Size"],
            options=[
                ft.dropdown.Option("Small"),
                ft.dropdown.Option("Medium"),
                ft.dropdown.Option("Large"),
            ],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=11,
            filled=True,
            border_radius=8,
            content_padding=8,
            focused_border_color="#6C5CE7",
            expand=True,
        )
        key_overlay_key_type_dropdown = ft.Dropdown(
            value=advanced_settings["Key Overlay Key Type"],
            options=[
                ft.dropdown.Option("All Keys"),
                ft.dropdown.Option("Special Keys"),
            ],
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=11,
            filled=True,
            border_radius=8,
            content_padding=8,
            focused_border_color="#6C5CE7",
            expand=True,
        )
        key_overlay_color = advanced_settings["Key Overlay Color"]
        key_overlay_color_preview = ft.Container(
            width=26,
            height=26,
            bgcolor=key_overlay_color,
            border=card_border("#FFFFFF"),
            border_radius=6,
        )

        def choose_key_overlay_color(_event):
            import tkinter as tk
            from tkinter import colorchooser

            root = None
            try:
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                _, selected_color = colorchooser.askcolor(
                    color=key_overlay_color_preview.bgcolor,
                    parent=root,
                    title="Choose Keys Overlay Color",
                )
                if selected_color:
                    key_overlay_color_preview.bgcolor = selected_color.upper()
                    key_overlay_color_preview.update()
            except tk.TclError as error:
                settings_error.value = f"Could not open the color picker: {error}"
                settings_error.visible = True
                settings_error.update()
            finally:
                if root is not None:
                    root.destroy()

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

        screenshot_card = build_card(
            ft.Icons.ADD_A_PHOTO_OUTLINED,
            "Screenshot Settings",
            "Choose the image format. JPEG uses maximum quality.",
            [
                ft.Column(
                    [
                        ft.Text("File type", size=10, color=TEXT_MUTED),
                        screenshot_format_dropdown,
                    ],
                    spacing=2,
                ),
                ft.Text(
                    "Screen mode captures the full screen; Window mode captures the selected window.",
                    size=10,
                    color=TEXT_MUTED,
                ),
            ],
        )

        # --- Section 2: Audio Settings Card ---
        audio_card = build_card(
            ft.Icons.VOLUME_UP_OUTLINED,
            "Audio Settings",
            "Selected microphone and system audio are mixed automatically.",
            [
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
                        ft.Text("Enable webcam overlay", size=11, color="white", expand=True),
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

        webcam_card = build_card(
            ft.Icons.VIDEOCAM_OUTLINED,
            "Webcam Overlay",
            "Choose the camera and one of the four inset corners.",
            [
                ft.Row(
                    controls=[
                        ft.Text("Camera", size=11, color="white", width=80),
                        webcam_dropdown,
                    ],
                    spacing=8,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Position", size=11, color="white", expand=True),
                        webcam_position_dropdown,
                    ],
                    spacing=8,
                ),
            ],
        )

        keys_overlay_card = build_card(
            ft.Icons.KEYBOARD_OUTLINED,
            "Keys Overlay",
            "Choose where key presses appear and customize their size and color.",
            [
                ft.Row(
                    controls=[
                        ft.Column(
                            [
                                ft.Text("Position", size=10, color=TEXT_MUTED),
                                key_overlay_position_dropdown,
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        ft.Column(
                            [
                                ft.Text("Size", size=10, color=TEXT_MUTED),
                                key_overlay_size_dropdown,
                            ],
                            expand=True,
                            spacing=2,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Column(
                    [
                        ft.Text("Key types", size=10, color=TEXT_MUTED),
                        key_overlay_key_type_dropdown,
                    ],
                    spacing=2,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Overlay color", size=11, color="white", expand=True),
                        key_overlay_color_preview,
                        ft.FilledButton(
                            "Choose color",
                            on_click=choose_key_overlay_color,
                            bgcolor="#222736",
                            color="white",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=8,
                ),
            ],
        )

        hotkeys_card = build_card(
            ft.Icons.KEYBOARD_OUTLINED,
            "Keyboard Shortcuts",
            "Click a button, then press any key or a modifier combination.",
            [
                ft.Row(
                    controls=[
                        ft.Text(label, size=11, color="white", expand=True),
                        shortcut_inputs[action],
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=8,
                )
                for action, label in (
                    ("Record", "Start recording"),
                    ("Stop", "Stop recording"),
                    ("Pause", "Pause / Resume"),
                    ("Screenshot", "Screenshot"),
                )
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
                ),
                ft.Row(
                    controls=[
                        ft.Text(
                            "Show saved-file popups",
                            size=11,
                            color="white",
                            expand=True,
                        ),
                        save_confirmation_switch,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    spacing=6,
                ),
            ]
        )

        def save_settings(evt):
            nonlocal shortcut_capture_target
            nonlocal shortcut_capture_listener
            selected_path = (save_path_input.value or "").strip()
            if not selected_path:
                settings_error.value = "Choose a folder where recordings can be saved."
                settings_error.visible = True
                settings_error.update()
                return

            shortcuts = {
                action: shortcut_capture_values[action]
                for action in shortcut_inputs
            }
            try:
                shortcut_signatures = {
                    action: shortcut_signature(shortcut)
                    for action, shortcut in shortcuts.items()
                }
            except ValueError:
                settings_error.value = (
                    "One of the captured shortcuts is invalid. Click its button "
                    "and press a supported key or key combination."
                )
                settings_error.visible = True
                settings_error.update()
                return
            if len(set(shortcut_signatures.values())) != len(shortcuts):
                settings_error.value = "Each action must use a different shortcut."
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

            try:
                shortcut_capture_target = None
                if shortcut_capture_listener:
                    shortcut_capture_listener.stop()
                    shortcut_capture_listener.join(timeout=1)
                    shortcut_capture_listener = None
                install_hotkeys(shortcuts)
            except (OSError, RuntimeError, ValueError) as error:
                settings_error.value = f"Could not register keyboard shortcuts: {error}"
                settings_error.visible = True
                settings_error.update()
                return

            updated_settings = {
                "Resolution": res_dropdown.value,
                "Frame Rate": fps_dropdown.value,
                "Quality": quality_dropdown.value,
                "Output Format": format_dropdown.value,
                "Screenshot Format": screenshot_format_dropdown.value,
                "Show Save Confirmation": save_confirmation_switch.value,
                "Hotkeys": shortcuts,
                "Save Path": selected_path,
                "Microphone": mic_dropdown.value,
                "Audio Source": sys_audio_dropdown.value,
                "Webcam Source": webcam_dropdown.value,
                "Key Overlay Position": key_overlay_position_dropdown.value,
                "Key Overlay Size": key_overlay_size_dropdown.value,
                "Key Overlay Color": key_overlay_color_preview.bgcolor,
                "Key Overlay Key Type": key_overlay_key_type_dropdown.value,
                "Webcam Position": webcam_position_dropdown.value,
            }
            try:
                save_settings_file(updated_settings, settings_include_states)
            except RuntimeError as error:
                try:
                    install_hotkeys(advanced_settings["Hotkeys"])
                except (OSError, RuntimeError, ValueError) as rollback_error:
                    error = RuntimeError(
                        f"{error}\nCould not restore the previous shortcuts: "
                        f"{rollback_error}"
                    )
                settings_error.value = str(error)
                settings_error.visible = True
                settings_error.update()
                return

            advanced_settings.update(updated_settings)
            include_states.update(settings_include_states)
            settings_error.visible = False
            main_container.content = content_column
            update_ui()

        def cancel_settings(evt):
            nonlocal shortcut_capture_target
            nonlocal shortcut_capture_listener
            if shortcut_capture_listener:
                shortcut_capture_listener.stop()
                shortcut_capture_listener.join(timeout=1)
                shortcut_capture_listener = None
            for action, field in shortcut_inputs.items():
                field.content.value = format_hotkey(
                    advanced_settings["Hotkeys"][action]
                )
                field.update()
            shortcut_capture_target = None
            if not hotkey_listener:
                try:
                    install_hotkeys(advanced_settings["Hotkeys"])
                except (OSError, RuntimeError, ValueError) as error:
                    settings_error.value = f"Could not resume shortcuts: {error}"
                    settings_error.visible = True
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
                        ft.TextButton(
                            "Back",
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            icon_color=TEXT_MUTED,
                            style=ft.ButtonStyle(color=TEXT_MUTED),
                            on_click=cancel_settings,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Column(
                    controls=[
                        video_card,
                        screenshot_card,
                        hotkeys_card,
                        audio_card,
                        include_card,
                        webcam_card,
                        keys_overlay_card,
                        other_card,
                        settings_error,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Cancel",
                            style=ft.ButtonStyle(
                                color="white",
                                bgcolor="#B42332",
                            ),
                            on_click=cancel_settings,
                        ),
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
        nonlocal area_status_text
        content_column.controls.clear()
        area_status_text = None

        def toggle_include_option(label):
            previous_value = include_states[label]
            include_states[label] = not previous_value
            try:
                save_settings_file(advanced_settings, include_states)
            except RuntimeError as error:
                include_states[label] = previous_value
                page.show_dialog(ft.AlertDialog(
                    title=ft.Text("Could not save settings"),
                    content=ft.Text(str(error)),
                    bgcolor=BG_COLOR,
                ))
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

        if current_mode == "Area" and selected_area:
            area_status_text = ft.Text(
                f"Area: {selected_area['width']} x {selected_area['height']} "
                "· Drag center to move; edges to resize",
                size=9,
                color=TEXT_MUTED,
            )
            controls_list.append(area_status_text)

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
                is_paused=is_paused,
                on_record_click=toggle_recording,
                on_pause_click=toggle_pause,
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
    try:
        install_hotkeys(advanced_settings["Hotkeys"])
    except (OSError, RuntimeError, ValueError) as error:
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Could not register keyboard shortcuts"),
            content=ft.Text(str(error)),
            bgcolor=BG_COLOR,
        ))
    if settings_load_error:
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Settings could not be fully loaded"),
            content=ft.Text(settings_load_error),
            bgcolor=BG_COLOR,
        ))
    page.run_task(center_window, page)

async def center_window(page):
    await page.window.center()

ft.run(main)