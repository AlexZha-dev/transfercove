import webbrowser

import flet as ft

from app.controller.controller import AppController
from app.core.theme import (
    COLORS,
    button_style,
    eyebrow,
    icon_badge,
    panel,
    section_title,
)
from app.server.manager import ServerState


class HomePage:
    def __init__(self, controller: AppController, open_settings) -> None:
        self.controller = controller
        self.open_settings = open_settings

        self.status = ft.Text(size=11, weight=ft.FontWeight.W_600)
        self.status_dot = ft.Container(width=6, height=6, border_radius=3)
        self.headline = ft.Text(
            size=30, weight=ft.FontWeight.W_600, color=COLORS["text"]
        )
        self.description = ft.Text(size=13, color=COLORS["muted_bright"])
        self.url = ft.Text(
            size=14, color=COLORS["primary"], selectable=True, font_family="Consolas"
        )
        self.host_value = ft.Text(size=18, color=COLORS["text"], selectable=True)
        self.port_value = ft.Text(
            size=22, color=COLORS["text"], weight=ft.FontWeight.W_600
        )
        self.storage_value = ft.Text(
            size=13,
            color=COLORS["text"],
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
            selectable=True,
        )
        self.network_hint = ft.Text(size=12, color=COLORS["muted"])
        self.error = ft.Text(
            size=12, color=COLORS["danger"], visible=False, selectable=True
        )
        self.server_button = ft.Button(
            content="Start server",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self.toggle_server,
            style=button_style(primary=True),
            height=46,
        )
        self.open_upload_button = ft.Button(
            content="Open upload page",
            icon=ft.Icons.ARROW_OUTWARD_ROUNDED,
            on_click=self.open_upload_page,
            style=button_style(),
            height=46,
            disabled=True,
        )
        self.signal_icon = ft.Icon(
            ft.Icons.WIFI_ROUNDED, size=52, color=COLORS["primary"]
        )
        self.signal_caption = ft.Text(
            "WAITING TO CONNECT",
            size=9,
            color=COLORS["muted"],
            style=ft.TextStyle(letter_spacing=1.5),
        )

        server_card = panel(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            eyebrow("Transfer server"),
                            ft.Container(
                                content=ft.Row(
                                    [self.status_dot, self.status],
                                    spacing=7,
                                    tight=True,
                                ),
                                padding=ft.Padding.symmetric(horizontal=11, vertical=7),
                                bgcolor=COLORS["field"],
                                border_radius=30,
                                border=ft.Border.all(1, COLORS["border"]),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ResponsiveRow(
                        controls=[
                            ft.Column(
                                controls=[
                                    self.headline,
                                    self.description,
                                    ft.Container(height=4),
                                    ft.Container(
                                        content=ft.Row(
                                            [
                                                ft.Icon(
                                                    ft.Icons.LINK_ROUNDED,
                                                    size=18,
                                                    color=COLORS["muted"],
                                                ),
                                                ft.Container(self.url, expand=True),
                                            ],
                                            spacing=10,
                                        ),
                                        padding=16,
                                        bgcolor=COLORS["field"],
                                        border=ft.Border.all(1, COLORS["border"]),
                                        border_radius=12,
                                    ),
                                    ft.Row(
                                        [self.server_button, self.open_upload_button],
                                        spacing=10,
                                        run_spacing=10,
                                        wrap=True,
                                    ),
                                    self.error,
                                ],
                                col={"xs": 12, "md": 8},
                                spacing=14,
                            ),
                            ft.Container(
                                self.signal_art(),
                                col={"xs": 0, "md": 4},
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        spacing=24,
                        run_spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=24,
            ),
            padding=26,
        )
        server_card.gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#142D1E", "#0E1D15", "#10271A"],
        )

        self.root = ft.Column(
            controls=[
                ft.Column(
                    controls=[
                        eyebrow("Local file transfer"),
                        ft.Text(
                            spans=[
                                ft.TextSpan("Your files. "),
                                ft.TextSpan(
                                    "Your network.",
                                    style=ft.TextStyle(color=COLORS["primary"]),
                                ),
                            ],
                            size=38,
                            weight=ft.FontWeight.W_700,
                            color=COLORS["text"],
                            style=ft.TextStyle(letter_spacing=-1.4, height=1.15),
                        ),
                        ft.Text(
                            "A simple space to share files between your devices.",
                            size=14,
                            color=COLORS["muted"],
                        ),
                    ],
                    spacing=12,
                ),
                server_card,
                ft.Row(
                    controls=[
                        section_title("Connection details"),
                        ft.TextButton(
                            "Configure",
                            icon=ft.Icons.TUNE_ROUNDED,
                            on_click=open_settings,
                            style=ft.ButtonStyle(color=COLORS["primary"]),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ResponsiveRow(
                    controls=[
                        self.detail_card(
                            "Bind address",
                            self.host_value,
                            "Server network interface",
                            ft.Icons.LAN_ROUNDED,
                            {"xs": 12, "sm": 6, "md": 4},
                        ),
                        self.detail_card(
                            "Port",
                            self.port_value,
                            "Incoming file transfers",
                            ft.Icons.SETTINGS_ETHERNET_ROUNDED,
                            {"xs": 12, "sm": 6, "md": 3},
                        ),
                        self.detail_card(
                            "Save location",
                            self.storage_value,
                            "Files arrive here",
                            ft.Icons.FOLDER_OPEN_ROUNDED,
                            {"xs": 12, "md": 5},
                        ),
                    ],
                    spacing=14,
                    run_spacing=14,
                ),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "From one device to another",
                                "Three small steps. All on your network.",
                            ),
                            ft.ResponsiveRow(
                                controls=[
                                    self.step(
                                        "01",
                                        "Start your server",
                                        "Your computer becomes the receiver.",
                                    ),
                                    self.step(
                                        "02",
                                        "Open the upload page",
                                        "Use the receiver’s LAN address on the same Wi-Fi.",
                                    ),
                                    self.step(
                                        "03",
                                        "Drop your files",
                                        "Uploaded files go to your save location.",
                                    ),
                                ],
                                spacing=20,
                                run_spacing=18,
                            ),
                            ft.Divider(height=1, color=COLORS["border"]),
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.INFO_OUTLINE_ROUNDED,
                                        size=16,
                                        color=COLORS["muted"],
                                    ),
                                    ft.Container(self.network_hint, expand=True),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            ),
                        ],
                        spacing=22,
                    )
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.WIFI_ROUNDED, size=14, color=COLORS["primary"]
                            ),
                            ft.Text(
                                "WiFi Transmitter  /  A direct connection to your devices",
                                size=11,
                                color=COLORS["muted"],
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.only(bottom=8),
                ),
            ],
            spacing=24,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.refresh()

    def signal_art(self) -> ft.Column:
        signal = ft.Container(
            self.signal_icon,
            border_radius=1000,
            bgcolor="#183C27",
            border=ft.Border.all(1, "#386547"),
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=40, color="#186EF0A0"),
        )
        rings = ft.Container(
            ft.Container(
                signal,
                padding=25,
                border_radius=1000,
                border=ft.Border.all(1, "#294C34"),
            ),
            aspect_ratio=1,
            padding=25,
            border_radius=1000,
            border=ft.Border.all(1, "#1D3B28"),
        )
        return ft.Column(
            [ft.Container(rings, width=210), self.signal_caption],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )

    @staticmethod
    def detail_card(title, value, subtitle, icon, col) -> ft.Container:
        return panel(
            ft.Column(
                [
                    ft.Row(
                        [
                            icon_badge(icon, size=34),
                            ft.Text(
                                title,
                                size=12,
                                color=COLORS["muted_bright"],
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(value, height=42, alignment=ft.Alignment.CENTER_LEFT),
                    ft.Text(
                        subtitle, size=11, color=COLORS["muted"], height=30, max_lines=2
                    ),
                ],
                spacing=12,
            ),
            padding=20,
            col=col,
        )

    @staticmethod
    def step(number: str, title: str, description: str) -> ft.Row:
        return ft.Row(
            [
                ft.Container(
                    ft.Text(
                        number,
                        size=11,
                        color=COLORS["primary"],
                        weight=ft.FontWeight.W_600,
                    ),
                    width=30,
                    height=30,
                    border_radius=9,
                    bgcolor=COLORS["primary_dark"],
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(
                            title,
                            size=12,
                            color=COLORS["text"],
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(description, size=11, color=COLORS["muted"]),
                    ],
                    spacing=6,
                    expand=True,
                ),
            ],
            col={"xs": 12, "md": 4},
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    async def toggle_server(self, _):
        if not self.controller.initialized:
            return
        if self.controller.server_running:
            await self.controller.stop_server()
        else:
            started = await self.controller.start_server()
            if started and self.controller.settings.desktop.open_browser:
                webbrowser.open(self.controller.server_url)

    def open_upload_page(self, _):
        if self.controller.server_running:
            webbrowser.open(self.controller.server_url)

    def refresh(self) -> None:
        settings = self.controller.settings
        self.host_value.value = settings.uvicorn.host
        self.port_value.value = str(settings.uvicorn.port)
        self.storage_value.value = str(settings.transmitter.storage_dir)
        self.storage_value.tooltip = str(settings.transmitter.storage_dir)
        self.url.value = self.controller.server_url
        loopback = settings.uvicorn.host.lower() in {"127.0.0.1", "localhost", "::1"}
        self.network_hint.value = (
            "Currently available on this computer only. Change the bind host in Settings to accept files from other devices."
            if loopback
            else "On another device, open this computer’s LAN address and port in a browser on the same network."
        )

        state = self.controller.server_state
        label, headline, description, color = {
            ServerState.RUNNING: (
                "Online",
                "Ready to receive.",
                "Your server is running. Open the upload page to send files.",
                COLORS["primary"],
            ),
            ServerState.STARTING: (
                "Starting",
                "Making the connection.",
                "Your file transfer server will be ready in a moment.",
                COLORS["warning"],
            ),
            ServerState.STOPPING: (
                "Stopping",
                "Wrapping things up.",
                "Waiting for your server to finish shutting down.",
                COLORS["warning"],
            ),
            ServerState.ERROR: (
                "Needs attention",
                "Let’s try that again.",
                "The server could not start. Check the details below or review your settings.",
                COLORS["danger"],
            ),
            ServerState.STOPPED: (
                "Offline",
                "Ready when you are.",
                "Start your server and give your files a place to land.",
                COLORS["muted_bright"],
            ),
        }[state]
        if not self.controller.initialized:
            label, headline = "Loading", "Getting things ready."
            description, color = "Loading your saved settings.", COLORS["warning"]
        self.status.value, self.status.color = label, color
        self.status_dot.bgcolor = color
        self.headline.value, self.description.value = headline, description
        self.signal_icon.color = (
            COLORS["primary"] if state == ServerState.RUNNING else COLORS["muted"]
        )
        self.signal_caption.value = (
            "CONNECTED & READY" if state == ServerState.RUNNING else label.upper()
        )
        self.signal_caption.color = color
        self.error.value = self.controller.last_error or ""
        self.error.visible = state == ServerState.ERROR and bool(
            self.controller.last_error
        )
        busy = state in {ServerState.STARTING, ServerState.STOPPING}
        running = state == ServerState.RUNNING
        self.server_button.content = (
            f"{label}..." if busy else ("Stop server" if running else "Start server")
        )
        self.server_button.icon = (
            ft.Icons.HOURGLASS_TOP
            if busy
            else ft.Icons.STOP_ROUNDED
            if running
            else ft.Icons.PLAY_ARROW_ROUNDED
        )
        self.server_button.style = button_style(primary=not running, danger=running)
        self.server_button.disabled = not self.controller.initialized or busy
        self.open_upload_button.disabled = not running

    def dispose(self) -> None:
        """Release page-specific resources before switching views."""
