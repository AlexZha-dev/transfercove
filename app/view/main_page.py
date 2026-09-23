import webbrowser

import flet as ft

from app.controller.controller import AppController
from app.core.theme import COLORS
from app.view.home_page import HomePage
from app.view.settings_page import SettingsPage


class MainPage:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.controller = AppController()
        self.content = ft.Container(expand=True)
        self.current_view = None

    async def initialize(self) -> None:
        self.page.title = "WiFi Transmitter"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = COLORS["background"]
        self.page.padding = 0

        await self.controller.initialize()
        self.controller.subscribe(self.refresh_current_view)

        self.page.add(
            ft.Row(
                controls=[
                    self.sidebar,
                    ft.VerticalDivider(width=1, color=COLORS["border"]),
                    self.content,
                ],
                expand=True,
                spacing=0,
            )
        )
        self.show_home()

        if self.controller.settings.desktop.auto_start:
            started = await self.controller.start_server()
            if started and self.controller.settings.desktop.open_browser:
                webbrowser.open(self.controller.server_url)

    @property
    def sidebar(self) -> ft.Container:
        return ft.Container(
            width=240,
            bgcolor=COLORS["sidebar"],
            padding=24,
            content=ft.Column(
                controls=[
                    ft.Text(
                        "WIFI",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["primary"],
                    ),
                    ft.Text(
                        "TRANSMITTER",
                        size=12,
                        color=COLORS["muted"],
                    ),
                    ft.Divider(color=COLORS["border"]),
                    ft.Button(
                        content="Dashboard",
                        icon=ft.Icons.DASHBOARD,
                        on_click=self.show_home,
                    ),
                    ft.Button(
                        content="Settings",
                        icon=ft.Icons.SETTINGS,
                        on_click=self.show_settings,
                    ),
                ],
                spacing=12,
            ),
        )

    def refresh_current_view(self) -> None:
        if self.current_view and hasattr(self.current_view, "refresh"):
            self.current_view.refresh()
        self.page.update()

    def show_home(self, _=None) -> None:
        self.current_view = HomePage(
            controller=self.controller,
            open_settings=self.show_settings,
        )
        self.content.content = ft.Container(
            content=self.current_view.root,
            padding=32,
            expand=True,
        )
        self.page.update()

    def show_settings(self, _=None) -> None:
        self.current_view = SettingsPage(
            controller=self.controller,
            go_back=self.show_home,
            page=self.page,
        )
        self.content.content = ft.Container(
            content=self.current_view.root,
            padding=32,
            expand=True,
        )
        self.page.update()

    async def close(self) -> None:
        await self.controller.close()


async def main(page: ft.Page) -> None:
    application = MainPage(page)
    await application.initialize()


def run() -> None:
    ft.run(main)
