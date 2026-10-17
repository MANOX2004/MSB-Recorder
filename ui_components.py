import flet as ft
from logic import get_connected_displays

# Color Constants
BG_COLOR = "#12131C"
CARD_BG = "#1A1B26"
BORDER_COLOR = "#2A2B3D"
TEXT_MUTED = "#8A8B9D"
ACCENT_RED = "#FF4B4B"

def card_border(color=BORDER_COLOR):
    return ft.Border(
        top=ft.BorderSide(1, color),
        bottom=ft.BorderSide(1, color),
        left=ft.BorderSide(1, color),
        right=ft.BorderSide(1, color),
    )

def create_title_bar(page, on_minimize, on_close):
    return ft.WindowDragArea(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.VIDEOCAM_ROUNDED, color="white", size=13),
                                bgcolor="#6C5CE7",
                                padding=5,
                                border_radius=6,
                            ),
                            ft.Text("MSB Recorder", size=13, weight=ft.FontWeight.BOLD, color="white"),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.REMOVE_ROUNDED,
                                icon_size=13,
                                icon_color=TEXT_MUTED,
                                on_click=on_minimize,
                                tooltip="Minimize",
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_size=13,
                                icon_color=TEXT_MUTED,
                                on_click=on_close,
                                tooltip="Close",
                            ),
                        ],
                        spacing=0,
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            height=30,
        )
    )

def create_header():
    return ft.Row(
        controls=[
            ft.Text("MSB Recorder Studio", size=16, weight=ft.FontWeight.BOLD, color="white"),
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.NIGHTLIGHT_ROUNDED,
                        icon_size=16,
                        icon_color="white",
                        bgcolor=CARD_BG,
                        style=ft.ButtonStyle(shape=ft.CircleBorder()),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.SETTINGS_OUTLINED,
                        icon_size=16,
                        icon_color="white",
                        bgcolor=CARD_BG,
                        style=ft.ButtonStyle(shape=ft.CircleBorder()),
                    ),
                ],
                spacing=6,
            )
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

def section_title(text):
    return ft.Text(text, size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED)

def get_what_to_record(selected_mode="Screen", on_select=None):
    def record_option(icon, label):
        is_selected = (label == selected_mode)
        b_color = "#6C5CE7" if is_selected else BORDER_COLOR
        
        def on_click_action(e):
            if on_select:
                on_select(label)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, color="white", size=20),
                    ft.Text(label, color="white", size=12, weight=ft.FontWeight.W_500),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=3,
            ),
            bgcolor="#222332" if is_selected else CARD_BG,
            border=card_border(b_color),
            border_radius=8,
            padding=8,
            expand=True,
            height=65,
            on_click=on_click_action,
        )

    return ft.Row(
        controls=[
            record_option(ft.Icons.MONITOR, "Screen"),
            record_option(ft.Icons.CROP_PORTRAIT, "Window"),
            record_option(ft.Icons.CROP, "Area"),
        ],
        spacing=8,
    )

def get_window_picker_ui(selected_window_title, on_pick_click):
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Selected Window", size=10, color=TEXT_MUTED),
                        ft.Text(
                            selected_window_title if selected_window_title else "No window selected",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color="white",
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MY_LOCATION, color="white", size=14),
                            ft.Text("Pick Window", color="white", size=12, weight=ft.FontWeight.W_500),
                        ],
                        spacing=5,
                        tight=True,
                    ),
                    bgcolor="#6C5CE7",
                    padding=10,
                    border_radius=6,
                    on_click=on_pick_click,
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=CARD_BG,
        border=card_border(BORDER_COLOR),
        border_radius=8,
        padding=12,
    )

def get_display_dropdown():
    """ಸම්බන්ධ කර ඇති සැබෑ ඩිස්ප්ලේස් පෙන්වන Flet Dropdown මෙනුව"""
    displays = get_connected_displays()
    
    dropdown_options = [
        ft.dropdown.Option(text=disp) for disp in displays
    ]

    return ft.Dropdown(
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

def get_include_options():
    def chip_option(icon, label, is_selected=False):
        b_color = "#6C5CE7" if is_selected else BORDER_COLOR
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color="white", size=14),
                    ft.Text(label, color="white", size=11, weight=ft.FontWeight.W_500),
                ],
                tight=True,
                spacing=5,
            ),
            bgcolor=CARD_BG,
            border=card_border(b_color),
            border_radius=16,
            padding=8,
        )
    
    row1 = ft.Row(
        controls=[
            chip_option(ft.Icons.VOLUME_UP_ROUNDED, "System audio", True),
            chip_option(ft.Icons.MIC_ROUNDED, "Mic"),
            chip_option(ft.Icons.CAMERA_ALT_ROUNDED, "Webcam"),
        ],
        spacing=6,
    )
    row2 = ft.Row(
        controls=[
            chip_option(ft.Icons.MOUSE_ROUNDED, "Cursor"),
            chip_option(ft.Icons.AUTO_AWESOME_ROUNDED, "Clicks"),
            chip_option(ft.Icons.KEYBOARD_ROUNDED, "Keys"),
        ],
        spacing=6,
    )
    return row1, row2

def get_quality_options():
    def quality_option(title, sub1, sub2="", is_selected=False):
        b_color = "#6C5CE7" if is_selected else BORDER_COLOR
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, color="white", size=12, weight=ft.FontWeight.BOLD),
                    ft.Text(sub1, color="white", size=11),
                    ft.Text(sub2, color="white", size=11) if sub2 else ft.Container(),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=1,
            ),
            bgcolor=CARD_BG,
            border=card_border(b_color),
            border_radius=8,
            padding=6,
            expand=True,
            height=70,
        )
    return ft.Row(
        controls=[
            quality_option("Light", "720p", "30"),
            quality_option("Standard", "1080p 30", is_selected=True),
            quality_option("Smooth", "1080p", "60"),
            quality_option("Ultra", "4K 60"),
        ],
        spacing=6,
    )

def get_record_controls():
    record_button = ft.Container(
        content=ft.Container(
            width=18,
            height=18,
            border=card_border("white"),
            border_radius=9,
        ),
        width=60,
        height=60,
        shape=ft.BoxShape.CIRCLE,
        bgcolor=ACCENT_RED,
        alignment=ft.alignment.Alignment(0, 0),
        shadow=ft.BoxShadow(spread_radius=1, blur_radius=10, color="#FF4B4B44"),
    )
    small_btn_left = ft.IconButton(
        icon=ft.Icons.ADD_A_PHOTO_OUTLINED,
        icon_color="white",
        icon_size=16,
        bgcolor=CARD_BG,
        style=ft.ButtonStyle(shape=ft.CircleBorder()),
        width=38,
        height=38,
    )
    small_btn_right = ft.IconButton(
        icon=ft.Icons.PAUSE_ROUNDED,
        icon_color="white",
        icon_size=16,
        bgcolor=CARD_BG,
        style=ft.ButtonStyle(shape=ft.CircleBorder()),
        width=38,
        height=38,
    )
    return ft.Column(
        controls=[
            ft.Row(
                controls=[small_btn_left, record_button, small_btn_right],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            ),
            ft.Text("Press F9 to start", color=TEXT_MUTED, size=11),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6,
    )

def get_footer():
    return ft.Row(
        controls=[
            ft.Text("Ready", color=TEXT_MUTED, size=11),
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=TEXT_MUTED, size=13),
                    ft.Text("Open recordings", color=TEXT_MUTED, size=11),
                ],
                spacing=4,
            )
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )