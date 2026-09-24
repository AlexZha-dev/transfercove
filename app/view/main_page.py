import webbrowser
from typing import Protocol

import flet as ft

from app.controller.controller import AppController
from app.core.theme import ASSETS_DIR, COLORS, app_theme, brand_icon, eyebrow
from app.server.manager import ServerState
from app.view.home_page import HomePage
from app.view.settings_page import SettingsPage


class View(Protocol):
    @property
    def root(self) -> ft.Control: ...

    def refresh(self) -> None: ...

    def dispose(self) -> None: ...


class MainPage:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.controller = AppController()
        self.file_picker = ft.FilePicker()
        self.content = ft.Container(expand=True)
        self.current_view: View | None = None
        self.active_route = "home"
        self.route_title = ft.Text("Dashboard", size=13, color=COLORS["text"])
        self.connection_text = ft.Text(size=11, weight=ft.FontWeight.W_600)
        self.connection_dot = ft.Container(width=6, height=6, border_radius=3)
        self.nav_labels: list[ft.Control] = []
        self.nav_buttons: dict[str, ft.TextButton] = {}
        self.sidebar = self.build_sidebar()
        self.mobile_nav_buttons: list[ft.IconButton] = [
            ft.IconButton(
                icon=ft.Icons.GRID_VIEW_ROUNDED,
                tooltip="Dashboard",
                on_click=self.show_home,
            ),
            ft.IconButton(
                icon=ft.Icons.TUNE_ROUNDED,
                tooltip="Settings",
                on_click=self.show_settings,
            ),
        ]
        mobile_nav_controls: list[ft.Control] = []
        mobile_nav_controls.extend(self.mobile_nav_buttons)
        self.mobile_nav = ft.Row(
            controls=mobile_nav_controls,
            spacing=0,
            visible=False,
        )
        self.breadcrumb = ft.Row(
            controls=[
                ft.Text("Workspace", size=12, color=COLORS["muted"]),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=15, color=COLORS["border_strong"]),
                self.route_title,
            ],
            spacing=10,
        )
        self.topbar = ft.Container(
            border=ft.Border(bottom=ft.BorderSide(1, COLORS["border"])),
            content=ft.Row(
                controls=[
                    self.mobile_nav,
                    self.breadcrumb,
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Row(
                            [self.connection_dot, self.connection_text],
                            spacing=8,
                            tight=True,
                        ),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        bgcolor=COLORS["panel"],
                        border=ft.Border.all(1, COLORS["border"]),
                        border_radius=30,
                    ),
                ],
                spacing=0,
            ),
        )

    async def initialize(self) -> None:
        self.page.title = "TransferCove"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.theme = app_theme()
        self.page.dark_theme = app_theme()
        self.page.bgcolor = COLORS["background"]
        self.page.padding = 0
        self.page.spacing = 0
        self.page.window.min_width = 380
        self.page.window.min_height = 600
        self.page.window.icon = str(ASSETS_DIR / "icon.ico")
        self.page.on_resize = self.resize
        self.page.services.append(self.file_picker)

        await self.controller.initialize()
        self.controller.subscribe(self.refresh_current_view)
        self.page.add(
            ft.Row(
                controls=[
                    self.sidebar,
                    ft.Column([self.topbar, self.content], spacing=0, expand=True),
                ],
                expand=True,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        )
        self.show_home()
        self.resize()

        if self.controller.settings.desktop.auto_start:
            started = await self.controller.start_server()
            if started and self.controller.settings.desktop.open_browser:
                webbrowser.open(self.controller.server_url)

    def build_sidebar(self) -> ft.Container:
        self.brand_text = ft.Column(
            controls=[
                ft.Text(
                    "Transfer", size=20, weight=ft.FontWeight.W_700, color=COLORS["text"]
                ),
                ft.Text(
                    "COVE",
                    size=9,
                    color=COLORS["muted"],
                    style=ft.TextStyle(letter_spacing=1.7),
                ),
            ],
            spacing=0,
        )
        self.sidebar_label = eyebrow("Workspace")
        for route, label, icon, callback in [
            ("home", "Dashboard", ft.Icons.GRID_VIEW_ROUNDED, self.show_home),
            ("settings", "Settings", ft.Icons.TUNE_ROUNDED, self.show_settings),
        ]:
            text = ft.Text(label, size=13, weight=ft.FontWeight.W_600, expand=True)
            self.nav_labels.append(text)
            self.nav_buttons[route] = ft.TextButton(
                content=ft.Row([ft.Icon(icon, size=20), text], spacing=12),
                height=48,
                tooltip=label,
                on_click=callback,
            )
        self.sidebar_footer = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.WIFI_ROUNDED, size=15, color=COLORS["primary"]
                            ),
                            ft.Text(
                                "Made for your network",
                                size=11,
                                color=COLORS["muted_bright"],
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "Your devices. One connection.", size=11, color=COLORS["muted"]
                    ),
                ],
                spacing=8,
            ),
            padding=ft.Padding.only(top=20),
            border=ft.Border(top=ft.BorderSide(1, COLORS["border"])),
        )
        return ft.Container(
            width=232,
            bgcolor=COLORS["sidebar"],
            border=ft.Border(right=ft.BorderSide(1, COLORS["border"])),
            content=ft.Column(
                controls=[
                    ft.Row([brand_icon(), self.brand_text], spacing=12),
                    ft.Container(height=28),
                    self.sidebar_label,
                    *self.nav_buttons.values(),
                    ft.Container(expand=True),
                    self.sidebar_footer,
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def update_navigation(self) -> None:
        self.route_title.value = (
            "Settings" if self.active_route == "settings" else "Dashboard"
        )
        for route, button in self.nav_buttons.items():
            selected = route == self.active_route
            button.style = ft.ButtonStyle(
                color=COLORS["primary"] if selected else COLORS["muted"],
                bgcolor=COLORS["primary_dark"] if selected else ft.Colors.TRANSPARENT,
                overlay_color=ft.Colors.with_opacity(0.06, COLORS["primary"]),
                padding=12,
                shape=ft.RoundedRectangleBorder(radius=12),
                alignment=ft.Alignment.CENTER_LEFT,
            )
        for index, button in enumerate(self.mobile_nav_buttons):
            selected = (index == 0) == (self.active_route == "home")
            button.icon_color = COLORS["primary"] if selected else COLORS["muted"]
            button.bgcolor = (
                COLORS["primary_dark"] if selected else ft.Colors.TRANSPARENT
            )

    def refresh_current_view(self) -> None:
        state = self.controller.server_state
        color = {
            ServerState.RUNNING: COLORS["primary"],
            ServerState.STARTING: COLORS["warning"],
            ServerState.STOPPING: COLORS["warning"],
            ServerState.ERROR: COLORS["danger"],
        }.get(state, COLORS["muted"])
        self.connection_text.value = {
            ServerState.RUNNING: "Server online",
            ServerState.STARTING: "Starting server",
            ServerState.STOPPING: "Stopping server",
            ServerState.ERROR: "Server error",
        }.get(state, "Server offline")
        self.connection_text.color = color
        self.connection_dot.bgcolor = color
        if self.current_view is not None:
            self.current_view.refresh()
        self.page.update()

    def show_home(self, _=None) -> None:
        self.dispose_current_view()
        self.active_route = "home"
        self.current_view = HomePage(self.controller, self.show_settings)
        self.mount_view()

    def show_settings(self, _=None) -> None:
        self.dispose_current_view()
        self.active_route = "settings"
        self.current_view = SettingsPage(
            self.controller, self.show_home, self.page, self.file_picker
        )
        self.mount_view()

    def mount_view(self) -> None:
        current_view = self.current_view
        if current_view is None:
            return
        self.content.content = current_view.root
        self.content.gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_RIGHT,
            end=ft.Alignment.BOTTOM_LEFT,
            colors=["#0C1C12", COLORS["background"], COLORS["background"]],
        )
        self.update_navigation()
        self.refresh_current_view()

    def resize(self, _=None) -> None:
        width = self.page.width or 1200
        compact = width < 1000
        mobile = width < 620
        self.sidebar.visible = not mobile
        self.sidebar.width = 80 if compact else 232
        self.sidebar.padding = ft.Padding.symmetric(
            horizontal=16 if compact else 20, vertical=28
        )
        for control in [
            self.brand_text,
            self.sidebar_label,
            self.sidebar_footer,
            *self.nav_labels,
        ]:
            control.visible = not compact
        self.mobile_nav.visible = mobile
        self.breadcrumb.visible = not mobile
        self.topbar.padding = ft.Padding.symmetric(
            horizontal=16 if mobile else 32, vertical=16
        )
        self.content.padding = 20 if mobile else 32
        self.page.update()

    def dispose_current_view(self) -> None:
        if self.current_view is not None:
            self.current_view.dispose()

    async def close(self) -> None:
        await self.controller.close()


async def main(page: ft.Page) -> None:
    application = MainPage(page)
    await application.initialize()


def run() -> None:
    ft.run(main, assets_dir=str(ASSETS_DIR))
