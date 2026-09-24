from pathlib import Path

import flet as ft
from pydantic import ValidationError

from app.controller.controller import AppController
from app.core.network import get_lan_ipv4
from app.core.security import SECURITY_NOTICE_DETAILS, SECURITY_NOTICE_TITLE
from app.core.settings import (
    DesktopConfig,
    Settings,
    TransmitterSettings,
    UvicornConfig,
)
from app.core.theme import (
    COLORS,
    button_style,
    eyebrow,
    icon_badge,
    panel,
    section_title,
    text_field,
)


class SettingsPage:
    def __init__(
        self,
        controller: AppController,
        go_back,
        page: ft.Page,
        file_picker: ft.FilePicker | None = None,
    ) -> None:
        self.controller = controller
        self.go_back = go_back
        self.page = page
        self.file_picker = file_picker or ft.FilePicker()
        if file_picker is None:
            self.page.services.append(self.file_picker)
        settings = controller.settings

        self.app_title = ft.Text(
            settings.app.title,
            size=20,
            weight=ft.FontWeight.W_600,
            color=COLORS["text"],
            selectable=True,
        )
        self.app_description = ft.Text(
            settings.app.description,
            size=13,
            color=COLORS["muted_bright"],
            selectable=True,
        )
        self.app_version = ft.Text(size=12, color=COLORS["primary"], selectable=True)
        self.app_debug = ft.Text(size=12, color=COLORS["muted"])
        self.host = text_field("Bind host", settings.uvicorn.host, expand=3)
        self.port = text_field(
            "Port",
            str(settings.uvicorn.port),
            expand=2,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.reload = ft.Switch(value=settings.uvicorn.reload, tooltip="Server reload")
        self.detect_host_button = ft.Button(
            "Use current LAN address",
            icon=ft.Icons.LAN_ROUNDED,
            style=button_style(),
            height=42,
            on_click=self.use_lan_address,
        )
        self.storage_path = text_field(
            "Storage directory",
            str(settings.transmitter.storage_dir),
            expand=True,
        )
        self.language = ft.Dropdown(
            label="Language",
            value=settings.desktop.language,
            options=[
                ft.DropdownOption(key="en", text="English"),
                ft.DropdownOption(key="ru", text="Русский"),
            ],
            text_size=13,
            color=COLORS["text"],
            label_style=ft.TextStyle(size=12, color=COLORS["muted"]),
            filled=True,
            fill_color=COLORS["field"],
            bgcolor=COLORS["panel"],
            border_color=COLORS["border"],
            focused_border_color=COLORS["primary"],
            border_radius=12,
            content_padding=16,
            expanded_insets=0,
        )
        self.auto_start = ft.Switch(
            value=settings.desktop.auto_start, tooltip="Start automatically"
        )
        self.open_browser = ft.Switch(
            value=settings.desktop.open_browser, tooltip="Open browser after start"
        )
        self.message = ft.Text(size=12, visible=False)
        self.save_button = ft.Button(
            "Save changes",
            icon=ft.Icons.CHECK_ROUNDED,
            style=button_style(primary=True),
            height=46,
            on_click=self.save,
        )

        self.root = ft.Column(
            controls=[
                ft.Column(
                    [
                        eyebrow("Your workspace"),
                        ft.Text(
                            "Make it yours.",
                            size=36,
                            weight=ft.FontWeight.W_700,
                            color=COLORS["text"],
                            style=ft.TextStyle(letter_spacing=-1),
                        ),
                        ft.Text(
                            "A few preferences for a smoother connection.",
                            size=14,
                            color=COLORS["muted"],
                        ),
                    ],
                    spacing=10,
                ),
                ft.Column(
                    controls=[
                        ft.ResponsiveRow(
                            controls=[
                                self.settings_section(
                                    "Connection",
                                    "Choose how devices reach your server.",
                                    ft.Icons.ROUTER_ROUNDED,
                                    [
                                        ft.Row([self.host, self.port], spacing=12),
                                        self.detect_host_button,
                                        ft.Text(
                                            "Use this when other devices should connect over the same local network.",
                                            size=12,
                                            color=COLORS["muted"],
                                        ),
                                        self.toggle_row(
                                            "Server reload",
                                            "Applies when running the server separately.",
                                            self.reload,
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    "Storage",
                                    "A home for everything you receive.",
                                    ft.Icons.FOLDER_OPEN_ROUNDED,
                                    [
                                        ft.Row(
                                            [
                                                self.storage_path,
                                                ft.IconButton(
                                                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                                    icon_color=COLORS["primary"],
                                                    bgcolor=COLORS["primary_dark"],
                                                    style=ft.ButtonStyle(
                                                        shape=ft.RoundedRectangleBorder(
                                                            radius=12
                                                        )
                                                    ),
                                                    tooltip="Enter a path in web mode"
                                                    if self.page.web
                                                    else "Choose storage directory",
                                                    on_click=self.choose_directory,
                                                    disabled=self.page.web,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text(
                                            "New uploads are saved to this folder.",
                                            size=12,
                                            color=COLORS["muted"],
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    "Desktop",
                                    "Settle into your own workflow.",
                                    ft.Icons.COMPUTER_ROUNDED,
                                    [
                                        self.language,
                                        self.toggle_row(
                                            "Start automatically",
                                            "Start the server when the app opens.",
                                            self.auto_start,
                                        ),
                                        self.toggle_row(
                                            "Open browser",
                                            "Open the upload page after starting.",
                                            self.open_browser,
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    "About this app",
                                    "Application information",
                                    ft.Icons.INFO_OUTLINE_ROUNDED,
                                    [
                                        self.app_title,
                                        self.app_description,
                                        ft.Row(
                                            [self.app_version, self.app_debug],
                                            spacing=20,
                                            run_spacing=10,
                                            wrap=True,
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    "Security",
                                    "Important limitations before sharing files.",
                                    ft.Icons.WARNING_AMBER_ROUNDED,
                                    [
                                        ft.Container(
                                            content=ft.Row(
                                                controls=[
                                                    ft.Icon(
                                                        ft.Icons.WARNING_AMBER_ROUNDED,
                                                        size=20,
                                                        color=COLORS["warning"],
                                                    ),
                                                    ft.Text(
                                                        f"{SECURITY_NOTICE_TITLE}: "
                                                        f"{SECURITY_NOTICE_DETAILS}",
                                                        size=12,
                                                        color=COLORS["muted_bright"],
                                                        expand=True,
                                                    ),
                                                ],
                                                spacing=12,
                                                vertical_alignment=ft.CrossAxisAlignment.START,
                                            ),
                                            padding=16,
                                            bgcolor="#261A17",
                                            border=ft.Border.all(1, "#5B3930"),
                                            border_radius=12,
                                        )
                                    ],
                                ),
                            ],
                            spacing=18,
                            run_spacing=18,
                        ),
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.INFO_OUTLINE_ROUNDED,
                                    size=16,
                                    color=COLORS["muted"],
                                ),
                                ft.Text(
                                    "Saving settings restarts the server if it is running.",
                                    size=12,
                                    color=COLORS["muted"],
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=20,
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    self.save_button,
                                    ft.TextButton(
                                        "Back to dashboard",
                                        on_click=lambda _: self.go_back(),
                                    ),
                                ],
                                spacing=12,
                                run_spacing=8,
                                wrap=True,
                            ),
                            self.message,
                        ],
                        spacing=10,
                    ),
                    padding=ft.Padding.only(top=18),
                    border=ft.Border(top=ft.BorderSide(1, COLORS["border"])),
                ),
            ],
            spacing=26,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.refresh()

    @staticmethod
    def settings_section(title, subtitle, icon, controls) -> ft.Container:
        return panel(
            ft.Column(
                controls=[
                    ft.Row(
                        [
                            icon_badge(icon),
                            ft.Container(section_title(title, subtitle), expand=True),
                        ],
                        spacing=14,
                    ),
                    ft.Divider(height=1, color=COLORS["border"]),
                    *controls,
                ],
                spacing=20,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            col={"xs": 12, "md": 6},
        )

    @staticmethod
    def toggle_row(title: str, description: str, switch: ft.Switch) -> ft.Row:
        return ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(
                            title,
                            size=13,
                            color=COLORS["text"],
                            weight=ft.FontWeight.W_500,
                        ),
                        ft.Text(description, size=11, color=COLORS["muted"]),
                    ],
                    spacing=4,
                    expand=True,
                ),
                switch,
            ],
            spacing=12,
        )

    def refresh(self) -> None:
        """Refresh application info without changing unsaved preferences."""
        application = self.controller.settings.app
        self.app_title.value = application.title
        self.app_description.value = application.description
        self.app_version.value = f"Version {application.version}"
        self.app_debug.value = f"Debug mode: {'on' if application.debug else 'off'}"

    async def save(self, _):
        self.save_button.disabled = True
        self.save_button.content = "Saving..."
        self.message.visible = False
        self.page.update()
        try:
            current_settings = self.controller.settings
            settings = Settings(
                app=current_settings.app.model_copy(deep=True),
                uvicorn=UvicornConfig(
                    host=self.host.value or "127.0.0.1",
                    port=int(self.port.value or "8000"),
                    log_level=current_settings.uvicorn.log_level,
                    reload=self.reload.value,
                ),
                transmitter=TransmitterSettings(
                    storage_dir=Path(self.storage_path.value or ".data/files"),
                    database_url=current_settings.transmitter.database_url,
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
        finally:
            self.save_button.disabled = False
            self.save_button.content = "Save changes"
            self.message.visible = True
            self.page.update()

    def use_lan_address(self, _):
        address = get_lan_ipv4()
        if address is None:
            self.message.value = (
                "Could not detect a private LAN IPv4 address. Check your network connection."
            )
            self.message.color = COLORS["warning"]
        else:
            self.host.value = address
            self.message.value = (
                f"LAN address {address} inserted. Save settings to apply it."
            )
            self.message.color = COLORS["primary"]
        self.message.visible = True
        self.page.update()

    async def choose_directory(self, _):
        if self.page.web:
            self.message.value = (
                "Directory picker is available only in the desktop app. "
                "Enter the path manually."
            )
            self.message.color = COLORS["warning"]
            self.message.visible = True
            self.page.update()
            return

        initial_directory = self._get_initial_directory(self.storage_path.value)

        try:
            selected_path = await self.file_picker.get_directory_path(
                dialog_title="Select storage directory",
                initial_directory=initial_directory,
            )
        except ft.FletUnsupportedPlatformException:
            self.message.value = "Directory picker is not supported on this platform."
            self.message.color = COLORS["warning"]
            self.message.visible = True
            self.page.update()
            return

        if selected_path:
            self.storage_path.value = selected_path
            self.page.update()

    @staticmethod
    def _get_initial_directory(storage_path: str | None) -> str | None:
        current_path = Path(storage_path or ".").expanduser()
        candidates = [
            current_path if current_path.is_dir() else current_path.parent,
            Path.home(),
            Path.cwd(),
        ]

        for candidate in candidates:
            try:
                if candidate.is_dir():
                    return str(candidate.resolve())
            except OSError:
                continue

        return None

    def dispose(self) -> None:
        """Release page-specific resources before switching views."""
