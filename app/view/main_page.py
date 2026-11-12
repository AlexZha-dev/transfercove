import asyncio
import datetime
import logging
import webbrowser
from typing import Protocol

import flet as ft

from app.controller.controller import AppController
from app.core.security import SECURITY_NOTICE_PREFERENCE_KEY
from app.core.settings import is_windows_packaged_build
from app.core.theme import (
    ASSETS_DIR,
    COLORS,
    app_theme,
    brand_icon,
    button_style,
    eyebrow,
)
from app.server.manager import ServerState
from app.services.update_service import (
    UpdateOperation,
    UpdateService,
    UpdateServiceError,
    UpdateViewState,
    VerifiedInstaller,
    should_check_for_updates,
)
from app.services.windows_update_installer import InstallerFileError, verify_and_launch
from app.view.home_page import HomePage
from app.view.localized import LocalizedView
from app.view.settings_page import SettingsPage

logger = logging.getLogger(__name__)


class View(Protocol):
    @property
    def root(self) -> ft.Control: ...

    def refresh(self) -> None: ...

    def dispose(self) -> None: ...


class MainPage(LocalizedView):
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.controller = AppController()
        self.file_picker = ft.FilePicker()
        self.security_preferences = ft.SharedPreferences()
        self.content = ft.Container(expand=True)
        self.current_view: View | None = None
        self.active_route = "home"
        self._start_after_security_acknowledgement = False
        self.update_state = UpdateViewState(supported=is_windows_packaged_build())
        self.update_service: UpdateService | None = None
        self._update_check_task: asyncio.Task | None = None
        self._closing = False
        self._update_confirmation: tuple[object, VerifiedInstaller] | None = None
        self._build_chrome()

    def _build_chrome(self) -> None:
        self.route_title = ft.Text(
            self.tr("dashboard_67b696"), size=13, color=COLORS["text"]
        )
        self.connection_text = ft.Text(size=11, weight=ft.FontWeight.W_600)
        self.connection_dot = ft.Container(width=6, height=6, border_radius=3)
        self.nav_labels: list[ft.Control] = []
        self.nav_buttons: dict[str, ft.TextButton] = {}
        self.sidebar = self.build_sidebar()
        self.mobile_nav_buttons: list[ft.IconButton] = [
            ft.IconButton(
                icon=ft.Icons.GRID_VIEW_ROUNDED,
                tooltip=self.tr("dashboard_67b696"),
                on_click=self.show_home,
            ),
            ft.IconButton(
                icon=ft.Icons.TUNE_ROUNDED,
                tooltip=self.tr("settings_74a883"),
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
                ft.Text(self.tr("workspace_87bb59"), size=12, color=COLORS["muted"]),
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
        self.page.window.on_event = self.on_window_event
        self.page.services.append(self.file_picker)
        self.page.services.append(self.security_preferences)

        await self.controller.initialize()
        self.set_language(self.controller.settings.desktop.language)
        self._build_chrome()
        if self.update_state.supported:
            try:
                self.update_service = UpdateService(
                    self.controller.settings.app.version
                )
            except ValueError:
                logger.exception("The installed application version is invalid")
                self._set_update_status(
                    "update_checks_are_unavailable_for_this_ver_f77165"
                )
                self.update_state.is_error = True
        self.controller.subscribe(self.refresh_current_view)
        self.main_column = ft.Column([self.topbar, self.content], spacing=0, expand=True)
        self.layout = ft.Row(
            controls=[
                self.sidebar,
                self.main_column,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.page.add(self.layout)
        self.show_home()
        self.resize()

        if self.update_state.supported and self.update_service is not None:
            self._update_check_task = asyncio.create_task(
                self.check_for_updates(manual=False)
            )

        if await self.security_notice_was_acknowledged():
            await self.start_server_automatically()
        else:
            self.show_security_notice()

    async def security_notice_was_acknowledged(self) -> bool:
        """Return whether this user has acknowledged the security limitations."""

        try:
            acknowledged = await self.security_preferences.get(
                SECURITY_NOTICE_PREFERENCE_KEY
            )
        except ft.FletUnsupportedPlatformException:
            return False
        return acknowledged is True

    def show_security_notice(self) -> None:
        """Show the first-run acknowledgement before an automatic server start."""

        self._start_after_security_acknowledgement = (
            self.controller.settings.desktop.auto_start
        )
        dialog = ft.AlertDialog(
            modal=True,
            icon=ft.Icon(
                ft.Icons.WARNING_AMBER_ROUNDED,
                color=COLORS["warning"],
                size=30,
            ),
            title=ft.Text(self.tr("security_notice_772833")),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            self.tr(
                                "transfercove_does_not_encrypt_network_traf_a8452d"
                            ),
                            size=13,
                            color=COLORS["muted_bright"],
                        ),
                        ft.Container(
                            content=ft.Text(
                                self.tr(
                                    "continue_only_if_you_understand_these_limi_ef104f"
                                ),
                                size=12,
                                color=COLORS["warning"],
                                weight=ft.FontWeight.W_600,
                            ),
                            padding=12,
                            bgcolor="#30201D",
                            border=ft.Border.all(1, "#5B3930"),
                            border_radius=10,
                        ),
                    ],
                    tight=True,
                    spacing=16,
                ),
                width=500,
            ),
            actions=[
                ft.Button(
                    self.tr("i_understand_860296"),
                    icon=ft.Icons.CHECK_ROUNDED,
                    style=button_style(primary=True),
                    on_click=self.acknowledge_security_notice,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            semantics_label=self.tr("transfercove_security_notice_c3bec2"),
        )
        self.page.show_dialog(dialog)

    async def acknowledge_security_notice(self, _) -> None:
        """Persist acknowledgement and continue any configured automatic start."""

        try:
            await self.security_preferences.set(SECURITY_NOTICE_PREFERENCE_KEY, True)
        except ft.FletUnsupportedPlatformException:
            # The dialog is still informative on a platform without persistence.
            pass

        self.page.pop_dialog()
        await self.start_server_automatically()

    async def start_server_automatically(self) -> None:
        if not self._start_after_security_acknowledgement and not (
            self.controller.settings.desktop.auto_start
        ):
            return

        self._start_after_security_acknowledgement = False
        started = await self.controller.start_server()
        if started and self.controller.settings.desktop.open_browser:
            webbrowser.open(self.controller.server_url)

    def build_sidebar(self) -> ft.Container:
        self.brand_text = ft.Column(
            controls=[
                ft.Text(
                    "Transfer",
                    size=20,
                    weight=ft.FontWeight.W_700,
                    color=COLORS["text"],
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
        self.sidebar_label = eyebrow(self.tr("workspace_87bb59"))
        for route, label, icon, callback in [
            (
                "home",
                self.tr("dashboard_67b696"),
                ft.Icons.GRID_VIEW_ROUNDED,
                self.show_home,
            ),
            (
                "settings",
                self.tr("settings_74a883"),
                ft.Icons.TUNE_ROUNDED,
                self.show_settings,
            ),
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
                                self.tr("made_for_your_network_9330e5"),
                                size=11,
                                color=COLORS["muted_bright"],
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        self.tr("your_devices_one_connection_616278"),
                        size=11,
                        color=COLORS["muted"],
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
            self.tr("settings_74a883")
            if self.active_route == "settings"
            else self.tr("dashboard_67b696")
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
            ServerState.RUNNING: self.tr("server_online_ae7534"),
            ServerState.STARTING: self.tr("starting_server_8a0f9d"),
            ServerState.STOPPING: self.tr("stopping_server_ae3b82"),
            ServerState.ERROR: self.tr("server_error_dfe0c2"),
        }.get(state, self.tr("server_offline_87ba7b"))
        self.connection_text.color = color
        self.connection_dot.bgcolor = color
        if self.current_view is not None:
            self.current_view.refresh()
        self.page.update()

    def show_home(self, _=None) -> None:
        self.dispose_current_view()
        self.active_route = "home"
        self.current_view = HomePage(self.controller, self.show_settings, self.page)
        self.mount_view()

    def show_settings(self, _=None) -> None:
        self.dispose_current_view()
        self.active_route = "settings"
        self.current_view = SettingsPage(
            self.controller,
            self.show_home,
            self.page,
            self.file_picker,
            self.update_state,
            self.check_for_updates,
            self.update_action,
            self.language_saved,
        )
        self.mount_view()

    def language_saved(self, message: str, color: str) -> None:
        """Rebuild translated controls after the settings event has finished."""
        self.set_language(self.controller.settings.desktop.language)
        self._build_chrome()
        self.layout.controls[0] = self.sidebar
        self.main_column.controls[0] = self.topbar
        self.show_settings()
        assert isinstance(self.current_view, SettingsPage)
        self.current_view.message.value = message
        self.current_view.message.color = color
        self.current_view.message.visible = True
        self.resize()

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

    def _notify_updates(self) -> None:
        if not self._closing:
            self.controller.notify()

    def _set_update_status(self, key: str, **values: object) -> None:
        self.update_state.status_key = key
        self.update_state.status_values = values
        self.update_state.status = self.tr(key, **values)

    def _begin_update_operation(self, operation: UpdateOperation) -> bool:
        # All event handlers run on the UI loop. Claim the operation before any await.
        if (
            self._closing
            or not self.update_state.supported
            or self.update_service is None
            or self.update_state.busy
        ):
            return False
        self.update_state.operation = operation
        return True

    def _finish_update_operation(self) -> None:
        if not self._closing:
            self.update_state.operation = UpdateOperation.IDLE
            self._notify_updates()

    async def check_for_updates(self, _=None, *, manual: bool = True) -> None:
        service = self.update_service
        if service is None or not self._begin_update_operation(
            UpdateOperation.CHECKING
        ):
            return
        self._set_update_status("checking_github_for_stable_releases_c824dd")
        self.update_state.is_error = False
        self._notify_updates()
        try:
            now = datetime.datetime.now(datetime.UTC)
            if not manual:
                last_checked_at = (
                    await self.controller.settings_store.get_last_update_check()
                )
                if self._closing:
                    return
                if not should_check_for_updates(last_checked_at, now):
                    self._set_update_status(
                        "updates_were_checked_within_the_last_24_ho_d7d791"
                    )
                    return
            await self.controller.settings_store.set_last_update_check(now)
            if self._closing:
                return
            self.update_state.release = None
            self.update_state.installer = None
            release = await service.check_for_update()
            if self._closing:
                return
            self.update_state.release = release
            if release is not None:
                self._set_update_status("a_stable_update_is_available_72eac6")
            else:
                self._set_update_status(
                    "update_none", version=self.controller.settings.app.version
                )
        except UpdateServiceError:
            logger.exception("Could not check for application updates")
            if not self._closing:
                self._set_update_status("update_failed")
                self.update_state.is_error = True
        except Exception:
            logger.exception("Could not check for application updates")
            if not self._closing:
                self._set_update_status(
                    "the_update_check_failed_use_check_for_upda_ddb467"
                )
                self.update_state.is_error = True
        finally:
            self._finish_update_operation()

    async def update_action(self, _) -> None:
        release = self.update_state.release
        service = self.update_service
        if release is None:
            return
        if self.update_state.installer is not None:
            self.show_update_install_confirmation()
            return
        if service is None or not self._begin_update_operation(
            UpdateOperation.DOWNLOADING
        ):
            return
        self._set_update_status("update_downloading", version=release.version)
        self.update_state.is_error = False
        self._notify_updates()
        try:
            installer = await service.download_and_verify(release)
            if self._closing:
                return
            self.update_state.installer = installer
            self._set_update_status("update_downloaded", version=release.version)
        except UpdateServiceError:
            logger.exception("Could not download an application update")
            if not self._closing:
                self._set_update_status("update_failed")
                self.update_state.is_error = True
        except Exception:
            logger.exception("Could not download an application update")
            if not self._closing:
                self._set_update_status(
                    "the_update_download_failed_retry_the_downl_25156f"
                )
                self.update_state.is_error = True
        finally:
            self._finish_update_operation()

    def show_update_install_confirmation(self) -> None:
        release = self.update_state.release
        installer = self.update_state.installer
        if release is None or installer is None or installer.version != release.version:
            return
        if not self._begin_update_operation(UpdateOperation.CONFIRMING):
            return
        token = object()
        self._update_confirmation = (token, installer)

        async def confirm(event):
            await self.confirm_update_install(event, token=token)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.tr("install_transfercove_update_db2d86")),
            content=ft.Text(self.tr("install_confirmation", version=installer.version)),
            actions=[
                ft.TextButton(
                    self.tr("cancel_19766e"),
                    on_click=lambda _: self.cancel_update_install(token),
                ),
                ft.Button(
                    self.tr("close_and_install_1af572"),
                    style=button_style(primary=True),
                    on_click=confirm,
                ),
            ],
            on_dismiss=lambda _: self.cancel_update_install(token, dismissed=True),
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._notify_updates()
        try:
            self.page.show_dialog(dialog)
        except Exception:
            self._update_confirmation = None
            self._finish_update_operation()
            raise

    def cancel_update_install(self, token: object, *, dismissed: bool = False) -> None:
        confirmation = self._update_confirmation
        if (
            self._closing
            or confirmation is None
            or confirmation[0] is not token
            or self.update_state.operation != UpdateOperation.CONFIRMING
        ):
            return
        self._update_confirmation = None
        if not dismissed:
            self.page.pop_dialog()
        self._finish_update_operation()

    async def confirm_update_install(self, _, *, token: object) -> None:
        confirmation = self._update_confirmation
        if (
            self._closing
            or confirmation is None
            or confirmation[0] is not token
            or self.update_state.operation != UpdateOperation.CONFIRMING
        ):
            return
        installer = confirmation[1]
        self._update_confirmation = None
        self.update_state.operation = UpdateOperation.INSTALLING
        self.page.pop_dialog()
        self._set_update_status("verifying_the_installer_before_launch_06f377")
        self.update_state.is_error = False
        self._notify_updates()
        try:
            await verify_and_launch(installer)
        except InstallerFileError:
            logger.exception("Downloaded installer is invalid")
            if not self._closing:
                self.update_state.installer = None
                self._set_update_status("update_failed")
                self.update_state.is_error = True
        except UpdateServiceError:
            logger.exception("Could not install the application update")
            if not self._closing:
                self._set_update_status("update_failed")
                self.update_state.is_error = True
        except Exception:
            logger.exception("Could not install the application update")
            if not self._closing:
                self._set_update_status(
                    "the_installer_could_not_be_started_retry_t_88f033"
                )
                self.update_state.is_error = True
        else:
            if not self._closing:
                try:
                    await self.close()
                except Exception:
                    logger.exception(
                        "Could not fully stop TransferCove before the update"
                    )
                await self.page.window.close()
        finally:
            self._finish_update_operation()

    async def on_window_event(self, event: ft.WindowEvent) -> None:
        if event.type == ft.WindowEventType.CLOSE:
            await self.close()

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._update_confirmation = None
        if self._update_check_task is not None and not self._update_check_task.done():
            self._update_check_task.cancel()
        await self.controller.close()


async def main(page: ft.Page) -> None:
    application = MainPage(page)
    await application.initialize()
    # The installed Flet application captures stdout in console.log.
    print(
        f"TransferCove desktop initialized version={application.controller.settings.app.version}",
        flush=True,
    )


def run() -> None:
    ft.run(main, assets_dir=str(ASSETS_DIR))
