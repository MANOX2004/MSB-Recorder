import flet as ft
from ui_components import (
    BG_COLOR, BORDER_COLOR, CARD_BG, TEXT_MUTED,
    create_title_bar, create_header, section_title,
    get_what_to_record, get_window_picker_ui, get_display_dropdown,
    get_include_options, get_quality_options,
    get_record_controls, get_footer
)
from logic import get_all_open_windows

def main(page: ft.Page):
    # Window Settings
    page.title = "ScreenForge"
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

    # Window Picker Dialog (ස්ථාවර Overlay ක්‍රමය)
    def open_window_picker_dialog(e):
        open_windows = get_all_open_windows()

        def select_window_and_close(win_name, dlg):
            nonlocal selected_window_title
            selected_window_title = win_name
            dlg.open = False
            page.update()
            update_ui()

        window_listView = ft.ListView(expand=1, spacing=6, padding=5)
        
        # තාවකාලික Dialog reference එකක් සඳහා variable එකක්
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
            create_header(),
            section_title("WHAT TO RECORD"),
            get_what_to_record(selected_mode=current_mode, on_select=on_mode_change),
        ]

        if current_mode == "Window":
            controls_list.append(get_window_picker_ui(selected_window_title, open_window_picker_dialog))

        controls_list.extend([
            get_display_dropdown(),
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