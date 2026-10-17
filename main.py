import flet as ft
from ui_components import (
    BG_COLOR, BORDER_COLOR, CARD_BG, TEXT_MUTED,
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
    content_column = ft.Column(spacing=8)

    def minimize_window(e):
        page.window.minimized = True
        page.update()

    async def close_window(e):
        await page.window.close()

    def on_mode_change(mode):
        nonlocal current_mode
        current_mode = mode
        update_ui()

    # 1. Night Mode / Light Mode Toggle Function
    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        page.update()

    # 2. Settings Dialog Window Function
    # 2. Settings Dialog Window Function
    # 2. Settings Dialog Window Function (Display Dropdown එක සමඟ)
    def open_settings_dialog(e):
        from logic import get_connected_displays
        
        displays = get_connected_displays()
        dropdown_options = [
            ft.dropdown.Option(text=disp) for disp in displays
        ]

        display_dropdown = ft.Dropdown(
            value=displays[0] if displays else None,
            options=dropdown_options,
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            color="white",
            text_size=12,
            border_radius=8,
            filled=True,
            content_padding=10,
            focused_border_color="#6C5CE7",
        )

        settings_dialog = ft.AlertDialog(
            title=ft.Text("Settings & Displays", size=14, color="white", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Select Target Display", size=11, color=TEXT_MUTED),
                    display_dropdown,
                    ft.Divider(height=10, color=BORDER_COLOR),
                    ft.Text("Recorder Preferences", size=11, color=TEXT_MUTED),
                    ft.Row([
                        ft.Text("Save logs automatically", color="white", size=12),
                        ft.Switch(value=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([
                        ft.Text("Hardware Acceleration", color="white", size=12),
                        ft.Switch(value=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], tight=True, spacing=10),
                width=320,
                height=240,
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
                    border=ft.Border(
                        top=ft.BorderSide(1, BORDER_COLOR),
                        bottom=ft.BorderSide(1, BORDER_COLOR),
                        left=ft.BorderSide(1, BORDER_COLOR),
                        right=ft.BorderSide(1, BORDER_COLOR),
                    ),
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
        inc1, inc2 = get_include_options()

        controls_list = [
            create_title_bar(page, minimize_window, close_window),
            create_header(on_theme_toggle=toggle_theme, on_settings_click=open_settings_dialog),
            section_title("WHAT TO RECORD"),
            get_what_to_record(selected_mode=current_mode, on_select=on_mode_change),
        ]

        if current_mode == "Window":
            controls_list.append(get_window_picker_ui(selected_window_title, open_window_picker_dialog))

        # මෙහි තිබූ get_display_dropdown() ඉවත් කර ඇත (දැන් එය settings window එක ඇතුළේ ඇත)
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
        border=ft.Border(
            top=ft.BorderSide(1, BORDER_COLOR),
            bottom=ft.BorderSide(1, BORDER_COLOR),
            left=ft.BorderSide(1, BORDER_COLOR),
            right=ft.BorderSide(1, BORDER_COLOR),
        ),
        padding=16,
        expand=True,
    )

    page.add(main_container)
    update_ui()

ft.run(main)