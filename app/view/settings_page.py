from pathlib import Path

import flet as ft
from pydantic import ValidationError

from app.controller.controller import AppController
from app.core.settings import (
    AppConfig,
    DesktopConfig,
    Settings,
    TransmitterSettings,
    UvicornConfig,
)
from app.core.theme import COLORS, panel, section_title


class SettingsPage:
    def __init__(
        self,
        controller: AppController,
        go_back,
        page: ft.Page,
    ) -> None:
        self.controller = controller
        self.go_back = go_back
        self.page = page
        self.directory_picker = ft.FilePicker()
        self.page.overlay.append(self.directory_picker)

        settings = controller.settings

        self.app_title = ft.TextField(
            label="Application title",
            value=settings.app.title,
            expand=True,
        )
        self.app_description = ft.TextField(
            label="Description",
            value=settings.app.description,
            multiline=True,
            min_lines=2,
            expand=True,
        )
        self.app_version = ft.TextField(
            label="Version",
            value=settings.app.version,
            expand=True,
        )
        self.app_debug = ft.Switch(
            label="Debug mode",
            value=settings.app.debug,
        )

        self.host = ft.TextField(
            label="Bind host",
            value=settings.uvicorn.host,
            expand=True,
        )
        self.port = ft.TextField(
            label="Port",
            value=str(settings.uvicorn.port),
            expand=True,
        )
        self.log_level = ft.TextField(
            label="Log level",
            value=settings.uvicorn.log_level,
            expand=True,
        )
        self.reload = ft.Switch(
            label="Uvicorn reload",
            value=settings.uvicorn.reload,
        )

        self.storage_path = ft.TextField(
            label="Storage directory",
            value=str(settings.transmitter.storage_dir),
            expand=True,
        )
        self.database_url = ft.TextField(
            label="Database URL",
            value=settings.transmitter.database_url,
            expand=True,
        )

        self.language = ft.Dropdown(
            label="Language",
            value=settings.desktop.language,
            options=[
                ft.DropdownOption(key="en", text="English"),
                ft.DropdownOption(key="ru", text="Русский"),
            ],
        )
        self.auto_start = ft.Switch(
            label="Start server with application",
            value=settings.desktop.auto_start,
        )
        self.open_browser = ft.Switch(
            label="Open upload page after start",
            value=settings.desktop.open_browser,
        )

        self.message = ft.Text()

        self.root = ft.Column(
            controls=[
                ft.Text(
                    "Settings",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                ),
                ft.Text(
                    "Configure the desktop application and FastAPI runtime",
                    color=COLORS["muted"],
                ),
                ft.Divider(color=COLORS["border"]),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "Application",
                                "Values from APP__* in .env",
                            ),
                            ft.Row(
                                controls=[self.app_title, self.app_version],
                                spacing=12,
                            ),
                            self.app_description,
                            self.app_debug,
                        ],
                        spacing=16,
                    )
                ),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "Server",
                                "Values from UVICORN__* in .env",
                            ),
                            ft.Row(
                                controls=[self.host, self.port],
                                spacing=12,
                            ),
                            ft.Row(
                                controls=[self.log_level, self.reload],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=16,
                    )
                ),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "Transmitter",
                                "Values from TRANSMITTER__* in .env",
                            ),
                            ft.Row(
                                controls=[
                                    self.storage_path,
                                    ft.IconButton(
                                        icon=ft.Icons.FOLDER_OPEN,
                                        tooltip="Choose storage directory",
                                        on_click=self.choose_directory,
                                    ),
                                ]
                            ),
                            self.database_url,
                        ],
                        spacing=16,
                    )
                ),
                panel(
                    ft.Column(
                        controls=[
                            section_title(
                                "Desktop",
                                "Settings used by the Flet application",
                            ),
                            self.language,
                            self.auto_start,
                            self.open_browser,
                        ],
                        spacing=16,
                    )
                ),
                ft.Row(
                    controls=[
                        ft.Button(
                            content="Save changes",
                            icon=ft.Icons.SAVE,
                            on_click=self.save,
                        ),
                        ft.TextButton(
                            content="Back",
                            on_click=lambda _: self.go_back(),
                        ),
                        self.message,
                    ],
                    spacing=12,
                ),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def refresh(self) -> None:
        settings = self.controller.settings

        self.app_title.value = settings.app.title
        self.app_description.value = settings.app.description
        self.app_version.value = settings.app.version
        self.app_debug.value = settings.app.debug
        self.host.value = settings.uvicorn.host
        self.port.value = str(settings.uvicorn.port)
        self.log_level.value = settings.uvicorn.log_level
        self.reload.value = settings.uvicorn.reload
        self.storage_path.value = str(settings.transmitter.storage_dir)
        self.database_url.value = settings.transmitter.database_url
        self.language.value = settings.desktop.language
        self.auto_start.value = settings.desktop.auto_start
        self.open_browser.value = settings.desktop.open_browser

    async def save(self, _):
        try:
            settings = Settings(
                app=AppConfig(
                    title=self.app_title.value or "WIFI TRANSMITTER",
                    description=self.app_description.value or "",
                    version=self.app_version.value or "0.1.0",
                    debug=self.app_debug.value,
                ),
                uvicorn=UvicornConfig(
                    host=self.host.value or "127.0.0.1",
                    port=int(self.port.value or "8000"),
                    log_level=self.log_level.value or "info",
                    reload=self.reload.value,
                ),
                transmitter=TransmitterSettings(
                    storage_dir=Path(self.storage_path.value or ".data/files"),
                    database_url=self.database_url.value
                    or "sqlite+aiosqlite:///./.data/files.db",
                ),
                desktop=DesktopConfig(
                    language=self.language.value or "en",
                    auto_start=self.auto_start.value,
                    open_browser=self.open_browser.value,
                ),
            )

            server_started = await self.controller.save_settings(settings)
            self.message.value = (
                "Settings saved"
                if server_started
                else "Settings saved, but the server did not start"
            )
            self.message.color = (
                COLORS["primary"] if server_started else COLORS["danger"]
            )

        except (ValueError, ValidationError) as error:
            self.message.value = f"Invalid settings: {error}"
            self.message.color = COLORS["danger"]

        self.page.update()

    async def choose_directory(self, _):
        current_path = Path(self.storage_path.value or ".").expanduser()
        initial_directory = current_path if current_path.is_dir() else current_path.parent

        selected_path = await self.directory_picker.get_directory_path(
            dialog_title="Select storage directory",
            initial_directory=str(initial_directory.resolve()),
        )

        if selected_path:
            self.storage_path.value = selected_path
            self.page.update()

    def dispose(self) -> None:
        if self.directory_picker in self.page.overlay:
            self.page.overlay.remove(self.directory_picker)
