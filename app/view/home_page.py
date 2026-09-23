import flet as ft

from app.controller.controller import AppController
from app.core.theme import COLORS, panel, section_title


class HomePage:
    def __init__(self, controller: AppController, open_settings) -> None:
        self.controller = controller
        self.open_settings = open_settings

        self.status = ft.Text()
        self.url = ft.Text()
        self.host_value = ft.Text()
        self.storage_value = ft.Text()
        self.server_button = ft.Button(
            content="Start server",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self.toggle_server,
        )

        self.root = ft.Column(
            controls=[
                ft.Text(
                    "Dashboard",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                ),
                ft.Text(
                    "Control your local file transfer server",
                    color=COLORS["muted"],
                ),
                ft.Divider(color=COLORS["border"]),
                ft.Row(
                    controls=[
                        panel(
                            ft.Column(
                                controls=[
                                    section_title(
                                        "Server status",
                                        "FastAPI is currently mocked",
                                    ),
                                    self.status,
                                    ft.Row(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.LINK,
                                                color=COLORS["primary"],
                                            ),
                                            self.url,
                                        ],
                                        spacing=8,
                                    ),
                                    self.server_button,
                                ],
                                spacing=16,
                            ),
                            padding=24,
                        ),
                        panel(
                            ft.Column(
                                controls=[
                                    section_title(
                                        "Runtime profile",
                                        "Loaded from the shared settings model",
                                    ),
                                    ft.Text("Host", color=COLORS["muted"]),
                                    self.host_value,
                                    ft.Text("Storage", color=COLORS["muted"]),
                                    self.storage_value,
                                ],
                                spacing=8,
                            ),
                            padding=24,
                        ),
                    ],
                    expand=True,
                    spacing=16,
                ),
                ft.Row(
                    controls=[
                        self.metric("Connected devices", "0", ft.Icons.DEVICES),
                        self.metric("Transferred files", "0", ft.Icons.FOLDER),
                        self.metric("Data transferred", "0 B", ft.Icons.DATA_USAGE),
                    ],
                    spacing=16,
                ),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "Quick actions",
                                "These actions are placeholders until FastAPI is connected",
                            ),
                            ft.Button(
                                content="Open upload page",
                                icon=ft.Icons.OPEN_IN_BROWSER,
                                disabled=True,
                            ),
                        ],
                        spacing=16,
                    ),
                ),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.refresh()

    def toggle_server(self, _):
        if not self.controller.initialized:
            return

        if self.controller.server_running:
            self.controller.stop_server()
        else:
            self.controller.start_server()

    @staticmethod
    def metric(title: str, value: str, icon) -> ft.Container:
        return panel(
            ft.Row(
                controls=[
                    ft.Icon(icon, color=COLORS["primary"], size=24),
                    ft.Column(
                        controls=[
                            ft.Text(title, color=COLORS["muted"], size=12),
                            ft.Text(
                                value,
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=COLORS["text"],
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=14,
            ),
        )

    def refresh(self) -> None:
        self.host_value.value = self.controller.settings.uvicorn.host
        self.storage_value.value = str(self.controller.settings.transmitter.storage_dir)

        if self.controller.server_running:
            self.status.value = "Running (mock)"
            self.status.color = COLORS["primary"]
            self.server_button.content = "Stop server"
            self.server_button.icon = ft.Icons.STOP
        else:
            self.status.value = (
                "Loading settings..." if not self.controller.initialized else "Stopped"
            )
            self.status.color = (
                COLORS["warning"]
                if not self.controller.initialized
                else COLORS["danger"]
            )
            self.server_button.content = "Start server"
            self.server_button.icon = ft.Icons.PLAY_ARROW

        self.server_button.disabled = not self.controller.initialized
        self.url.value = self.controller.server_url
