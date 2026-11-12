from pathlib import Path

import flet as ft
from pydantic import ValidationError

from app.controller.controller import AppController
from app.core.localization import load_catalogs, resolve_locale
from app.core.network import get_lan_ipv4
from app.core.settings import (
    AppConfig,
    DesktopConfig,
    Settings,
    TransmitterSettings,
    UploadLimits,
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
from app.services.update_service import UpdateViewState
from app.view.localized import LocalizedView


class SettingsPage(LocalizedView):
    def __init__(
        self,
        controller: AppController,
        go_back,
        page: ft.Page,
        file_picker: ft.FilePicker | None = None,
        update_state: UpdateViewState | None = None,
        check_updates=None,
        update_action=None,
        language_saved=None,
    ) -> None:
        self.controller = controller
        self.set_language(controller.settings.desktop.language)
        self.language_saved = language_saved
        self.go_back = go_back
        self.page = page
        self.file_picker = file_picker or ft.FilePicker()
        self.update_state = update_state or UpdateViewState(supported=False)
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
        self.update_status = ft.Text(size=12, color=COLORS["muted_bright"])
        self.update_release_version = ft.Text(
            size=13, color=COLORS["primary"], weight=ft.FontWeight.W_600
        )
        self.update_release_notes = ft.Text(
            size=12, color=COLORS["muted_bright"], selectable=True
        )
        self.update_release_info = ft.Column(
            [self.update_release_version, self.update_release_notes],
            spacing=8,
            visible=False,
        )
        self.check_updates_button = ft.Button(
            self.tr("check_for_updates_f26f32"),
            icon=ft.Icons.UPDATE,
            style=button_style(),
            on_click=check_updates,
        )
        self.update_action_button = ft.Button(
            self.tr("download_and_install_b697d4"),
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            style=button_style(primary=True),
            on_click=update_action,
            visible=False,
        )
        self.update_controls = ft.Column(
            controls=[
                self.update_status,
                self.update_release_info,
                ft.Row(
                    [self.check_updates_button, self.update_action_button],
                    spacing=10,
                    run_spacing=8,
                    wrap=True,
                ),
            ],
            spacing=10,
            visible=self.update_state.supported,
        )
        self.host = text_field(
            self.tr("bind_host_afcc60"), settings.uvicorn.host, expand=3
        )
        self.port = text_field(
            self.tr("port_72e9a5"),
            str(settings.uvicorn.port),
            expand=2,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.reload = ft.Switch(
            value=settings.uvicorn.reload, tooltip=self.tr("server_reload_ddf1ad")
        )
        self.detect_host_button = ft.Button(
            self.tr("use_current_lan_address_804df3"),
            icon=ft.Icons.LAN_ROUNDED,
            style=button_style(),
            height=42,
            on_click=self.use_lan_address,
        )
        self.storage_path = text_field(
            self.tr("storage_directory_e5e630"),
            str(settings.transmitter.storage_dir),
            expand=True,
        )
        limits = settings.upload_limits
        self.max_file_mib = text_field(
            self.tr("maximum_file_size_mib_a081ee"), str(limits.max_file_mib)
        )
        self.max_concurrent = text_field(
            self.tr("simultaneous_uploads_2349fd"), str(limits.max_concurrent)
        )
        self.reserve_mib = text_field(
            self.tr("free_disk_reserve_mib_fe08df"), str(limits.reserve_mib)
        )
        self.idle_timeout = text_field(
            self.tr("upload_inactivity_timeout_seconds_610284"),
            str(limits.idle_timeout_seconds),
        )
        catalogs = load_catalogs()
        self.language = ft.Dropdown(
            label=self.tr("language_a4fe65"),
            value=resolve_locale(settings.desktop.language, catalogs),
            options=[
                ft.DropdownOption(key=locale, text=catalog["name"])
                for locale, catalog in catalogs.items()
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
            value=settings.desktop.auto_start,
            tooltip=self.tr("start_automatically_80e5b9"),
        )
        self.open_browser = ft.Switch(
            value=settings.desktop.open_browser,
            tooltip=self.tr("open_browser_after_start_916a58"),
        )
        self.message = ft.Text(size=12, visible=False)
        self.save_button = ft.Button(
            self.tr("save_changes_dd0ae7"),
            icon=ft.Icons.CHECK_ROUNDED,
            style=button_style(primary=True),
            height=46,
            on_click=self.save,
        )

        self.root = ft.Column(
            controls=[
                ft.Column(
                    [
                        eyebrow(self.tr("your_workspace_4d0260")),
                        ft.Text(
                            self.tr("make_it_yours_ddd1f0"),
                            size=36,
                            weight=ft.FontWeight.W_700,
                            color=COLORS["text"],
                            style=ft.TextStyle(letter_spacing=-1),
                        ),
                        ft.Text(
                            self.tr(
                                "a_few_preferences_for_a_smoother_connectio_9967ed"
                            ),
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
                                    self.tr("connection_639a40"),
                                    self.tr(
                                        "choose_how_devices_reach_your_server_3dcdca"
                                    ),
                                    ft.Icons.ROUTER_ROUNDED,
                                    [
                                        ft.Row([self.host, self.port], spacing=12),
                                        self.detect_host_button,
                                        ft.Text(
                                            self.tr(
                                                "use_this_when_other_devices_should_connect_2a1df5"
                                            ),
                                            size=12,
                                            color=COLORS["muted"],
                                        ),
                                        self.toggle_row(
                                            self.tr("server_reload_ddf1ad"),
                                            self.tr(
                                                "applies_when_running_the_server_separately_1db5f8"
                                            ),
                                            self.reload,
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    self.tr("storage_a69c4d"),
                                    self.tr("a_home_for_everything_you_receive_774056"),
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
                                                    tooltip=self.tr(
                                                        "enter_a_path_in_web_mode_f48e23"
                                                    )
                                                    if self.page.web
                                                    else self.tr(
                                                        "choose_storage_directory_9a4f4e"
                                                    ),
                                                    on_click=self.choose_directory,
                                                    disabled=self.page.web,
                                                ),
                                            ],
                                            spacing=8,
                                        ),
                                        ft.Text(
                                            self.tr(
                                                "new_uploads_are_saved_to_this_folder_8c05f9"
                                            ),
                                            size=12,
                                            color=COLORS["muted"],
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    self.tr("upload_limits_420f44"),
                                    self.tr(
                                        "protect_storage_while_receiving_files_02e264"
                                    ),
                                    ft.Icons.SECURITY_ROUNDED,
                                    [
                                        self.max_file_mib,
                                        self.max_concurrent,
                                        self.reserve_mib,
                                        self.idle_timeout,
                                    ],
                                ),
                                self.settings_section(
                                    self.tr("desktop_9bd88f"),
                                    self.tr("settle_into_your_own_workflow_233e14"),
                                    ft.Icons.COMPUTER_ROUNDED,
                                    [
                                        self.language,
                                        self.toggle_row(
                                            self.tr("start_automatically_80e5b9"),
                                            self.tr(
                                                "start_the_server_when_the_app_opens_8ae568"
                                            ),
                                            self.auto_start,
                                        ),
                                        self.toggle_row(
                                            self.tr("open_browser_b84a7d"),
                                            self.tr(
                                                "open_the_upload_page_after_starting_654856"
                                            ),
                                            self.open_browser,
                                        ),
                                    ],
                                ),
                                self.settings_section(
                                    self.tr("about_this_app_147cb2"),
                                    self.tr("application_information_bc0a7c"),
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
                                        self.update_controls,
                                    ],
                                ),
                                self.settings_section(
                                    self.tr("security_8f6fb4"),
                                    self.tr(
                                        "important_limitations_before_sharing_files_d9e96f"
                                    ),
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
                                                        f"{self.tr('security_notice_772833')}: "
                                                        f"{self.tr('transfercove_does_not_encrypt_network_traf_a8452d')}",
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
                                    self.tr(
                                        "saving_settings_restarts_the_server_if_it__e752ef"
                                    ),
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
                                        self.tr("back_to_dashboard_b59e0c"),
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
        self.app_description.value = (
            self.tr("default_description")
            if application.description == AppConfig.model_fields["description"].default
            else application.description
        )
        self.app_version.value = self.tr("version_label", version=application.version)
        self.app_debug.value = self.tr(
            "debug_label",
            state=self.tr("on_b8d31e") if application.debug else self.tr("off_b4dc66"),
        )
        update_state = self.update_state
        self.update_controls.visible = update_state.supported
        self.update_status.value = self.tr(
            update_state.status_key, **update_state.status_values
        )
        self.update_status.color = (
            COLORS["danger"] if update_state.is_error else COLORS["muted_bright"]
        )
        busy = update_state.busy
        self.check_updates_button.disabled = busy
        self.check_updates_button.content = (
            self.tr("checking_2e5f79")
            if update_state.checking
            else self.tr("check_for_updates_f26f32")
        )
        release = update_state.release
        self.update_release_info.visible = release is not None
        self.update_action_button.visible = release is not None
        self.update_action_button.disabled = busy
        if release is not None:
            self.update_release_version.value = self.tr(
                "version_available", version=release.version
            )
            self.update_release_notes.value = release.release_notes or self.tr(
                "no_release_notes_provided_e1291b"
            )
            self.update_action_button.content = (
                self.tr("install_update_cada42")
                if update_state.installer is not None
                else self.tr("download_and_install_b697d4")
            )
        else:
            self.update_release_version.value = ""
            self.update_release_notes.value = ""

    async def save(self, _):
        changed_language = False
        self.save_button.disabled = True
        self.save_button.content = self.tr("saving_dc85af")
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
                upload_limits=UploadLimits(
                    max_file_mib=int(self.max_file_mib.value or ""),
                    max_concurrent=int(self.max_concurrent.value or ""),
                    reserve_mib=int(self.reserve_mib.value or ""),
                    idle_timeout_seconds=int(self.idle_timeout.value or ""),
                ),
                desktop=DesktopConfig(
                    language=self.language.value or "en",
                    auto_start=self.auto_start.value,
                    open_browser=self.open_browser.value,
                ),
            )

            server_started = await self.controller.save_settings(settings)
            changed_language = self._localizer.language != resolve_locale(
                settings.desktop.language, self._localizer.catalogs
            )
            self.set_language(settings.desktop.language)
            self.message.value = (
                self.tr("settings_saved_74a7f5")
                if server_started
                else self.tr("settings_saved_but_the_server_did_not_star_e6c22d")
            )
            self.message.color = (
                COLORS["primary"] if server_started else COLORS["danger"]
            )

        except ValueError, ValidationError:
            self.message.value = self.tr("invalid_settings")
            self.message.color = COLORS["danger"]
        finally:
            self.save_button.disabled = False
            self.save_button.content = self.tr("save_changes_dd0ae7")
            self.message.visible = True
            self.page.update()
        if changed_language and self.language_saved is not None:
            self.language_saved(self.message.value, self.message.color)

    def use_lan_address(self, _):
        address = get_lan_ipv4()
        if address is None:
            self.message.value = self.tr(
                "could_not_detect_a_private_lan_ipv4_addres_369f4c"
            )
            self.message.color = COLORS["warning"]
        else:
            self.host.value = address
            self.message.value = self.tr("lan_inserted", address=address)
            self.message.color = COLORS["primary"]
        self.message.visible = True
        self.page.update()

    async def choose_directory(self, _):
        if self.page.web:
            self.message.value = self.tr(
                "directory_picker_is_available_only_in_the__7bcc04"
            )
            self.message.color = COLORS["warning"]
            self.message.visible = True
            self.page.update()
            return

        initial_directory = self._get_initial_directory(self.storage_path.value)

        try:
            selected_path = await self.file_picker.get_directory_path(
                dialog_title=self.tr("select_storage_directory_0b27dd"),
                initial_directory=initial_directory,
            )
        except ft.FletUnsupportedPlatformException:
            self.message.value = self.tr(
                "directory_picker_is_not_supported_on_this__839023"
            )
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
