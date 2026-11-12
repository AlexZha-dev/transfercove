import webbrowser

import flet as ft

from app.controller.controller import AppController
from app.core.qr import make_qr_svg
from app.core.theme import (
    COLORS,
    button_style,
    eyebrow,
    icon_badge,
    panel,
    section_title,
)
from app.server.manager import ServerErrorCode, ServerState
from app.view.localized import LocalizedView


class HomePage(LocalizedView):
    def __init__(self, controller: AppController, open_settings, page: ft.Page) -> None:
        self.controller = controller
        self.set_language(controller.settings.desktop.language)
        self.open_settings = open_settings
        self.page = page

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
            content=self.tr("start_server_7b7da6"),
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=self.toggle_server,
            style=button_style(primary=True),
            height=46,
        )
        self.open_upload_button = ft.Button(
            content=self.tr("open_upload_page_b75d1f"),
            icon=ft.Icons.ARROW_OUTWARD_ROUNDED,
            on_click=self.open_upload_page,
            style=button_style(),
            height=46,
            disabled=True,
        )
        self.copy_link_button = ft.IconButton(
            icon=ft.Icons.CONTENT_COPY_ROUNDED,
            icon_color=COLORS["primary"],
            tooltip=self.tr("copy_upload_link_fa26cd"),
            on_click=self.copy_link,
        )
        self.qr_code_button = ft.IconButton(
            icon=ft.Icons.QR_CODE_ROUNDED,
            icon_color=COLORS["primary"],
            tooltip=self.tr("show_qr_code_f5cb68"),
            on_click=self.show_qr_code,
        )
        self.signal_icon = ft.Icon(
            ft.Icons.WIFI_ROUNDED, size=52, color=COLORS["primary"]
        )
        self.signal_caption = ft.Text(
            self.tr("waiting_to_connect_4a7b0f"),
            size=9,
            color=COLORS["muted"],
            style=ft.TextStyle(letter_spacing=1.5),
        )

        server_card = panel(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            eyebrow(self.tr("transfer_server_429458")),
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
                                                self.copy_link_button,
                                                self.qr_code_button,
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
        security_notice = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED,
                            size=22,
                            color=COLORS["warning"],
                        ),
                        width=42,
                        height=42,
                        alignment=ft.Alignment.CENTER,
                        bgcolor="#3A261F",
                        border_radius=12,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                self.tr("security_notice_772833"),
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["text"],
                            ),
                            ft.Text(
                                self.tr(
                                    "transfers_use_plain_http_without_encryptio_8b9266"
                                ),
                                size=12,
                                color=COLORS["muted_bright"],
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=16,
            bgcolor="#261A17",
            border=ft.Border.all(1, "#5B3930"),
            border_radius=16,
        )

        self.root = ft.Column(
            controls=[
                ft.Column(
                    controls=[
                        eyebrow(self.tr("local_file_transfer_ed8d11")),
                        ft.Text(
                            spans=[
                                ft.TextSpan(self.tr("your_files_cfcaea")),
                                ft.TextSpan(
                                    self.tr("your_network_c168a2"),
                                    style=ft.TextStyle(color=COLORS["primary"]),
                                ),
                            ],
                            size=38,
                            weight=ft.FontWeight.W_700,
                            color=COLORS["text"],
                            style=ft.TextStyle(letter_spacing=-1.4, height=1.15),
                        ),
                        ft.Text(
                            self.tr(
                                "a_simple_space_to_share_files_between_your_cfb5bc"
                            ),
                            size=14,
                            color=COLORS["muted"],
                        ),
                    ],
                    spacing=12,
                ),
                security_notice,
                server_card,
                ft.Row(
                    controls=[
                        section_title(self.tr("connection_details_51bfff")),
                        ft.TextButton(
                            self.tr("configure_6defaf"),
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
                            self.tr("access_address_1f5f3f"),
                            self.host_value,
                            self.tr("use_this_address_on_another_device_f5152f"),
                            ft.Icons.LAN_ROUNDED,
                            {"xs": 12, "sm": 6, "md": 4},
                        ),
                        self.detail_card(
                            self.tr("port_72e9a5"),
                            self.port_value,
                            self.tr("incoming_file_transfers_6edc42"),
                            ft.Icons.SETTINGS_ETHERNET_ROUNDED,
                            {"xs": 12, "sm": 6, "md": 3},
                        ),
                        self.detail_card(
                            self.tr("save_location_311e14"),
                            self.storage_value,
                            self.tr("files_arrive_here_c96a62"),
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
                                self.tr("from_one_device_to_another_5f1809"),
                                self.tr("three_small_steps_all_on_your_network_331e0f"),
                            ),
                            ft.ResponsiveRow(
                                controls=[
                                    self.step(
                                        "01",
                                        self.tr("start_your_server_72a512"),
                                        self.tr(
                                            "your_computer_becomes_the_receiver_c5bce8"
                                        ),
                                    ),
                                    self.step(
                                        "02",
                                        self.tr("open_the_upload_page_2dfaa7"),
                                        self.tr(
                                            "use_the_receiver_s_lan_address_on_the_same_cd8c56"
                                        ),
                                    ),
                                    self.step(
                                        "03",
                                        self.tr("drop_your_files_f76f95"),
                                        self.tr(
                                            "uploaded_files_go_to_your_save_location_157962"
                                        ),
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
                                self.tr(
                                    "transfercove_a_direct_connection_to_your_d_3c9d48"
                                ),
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

    async def copy_link(self, _):
        try:
            await self.page.clipboard.set(self.controller.server_url)
        except ft.FletUnsupportedPlatformException:
            self._show_snackbar(
                self.tr("clipboard_is_not_available_on_this_platfor_17c4fa"),
                warning=True,
            )
        else:
            self._show_snackbar(self.tr("upload_link_copied_to_the_clipboard_aea0cd"))

    def show_qr_code(self, _):
        url = self.controller.server_url
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(self.tr("scan_to_open_the_upload_page_a7e61b")),
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Image(
                            src=make_qr_svg(url),
                            width=260,
                            height=260,
                            fit=ft.BoxFit.CONTAIN,
                            semantics_label=self.tr("qr_for", url=url),
                        ),
                        padding=12,
                        bgcolor="#FFFFFF",
                        border_radius=12,
                    ),
                    ft.Text(
                        url,
                        size=12,
                        color=COLORS["muted_bright"],
                        selectable=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            actions=[
                ft.TextButton(self.tr("copy_link_dbf362"), on_click=self.copy_link),
                ft.TextButton(
                    self.tr("close_7d9eb7"), on_click=lambda _: self.page.pop_dialog()
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    def _show_snackbar(self, message: str, *, warning: bool = False) -> None:
        self.page.show_dialog(
            ft.SnackBar(
                message,
                bgcolor=COLORS["warning"] if warning else COLORS["primary_dark"],
                duration=2500,
            )
        )

    def refresh(self) -> None:
        settings = self.controller.settings
        self.host_value.value = self.controller.advertised_host
        self.port_value.value = str(settings.uvicorn.port)
        self.storage_value.value = str(settings.transmitter.storage_dir)
        self.storage_value.tooltip = str(settings.transmitter.storage_dir)
        self.url.value = self.controller.server_url
        loopback = settings.uvicorn.host.strip().lower() in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        self.network_hint.value = (
            self.tr("currently_available_on_this_computer_only__bf510d")
            if loopback
            else self.tr("on_another_device_open_this_computer_s_lan_35a938")
        )

        if not loopback and self.controller.advertised_host == "127.0.0.1":
            self.network_hint.value = self.tr(
                "the_lan_address_could_not_be_detected_chec_3c92ee"
            )

        state = self.controller.server_state
        label, headline, description, color = {
            ServerState.RUNNING: (
                self.tr("online_0d21bd"),
                self.tr("ready_to_receive_6e1cc0"),
                self.tr("your_server_is_running_open_the_upload_pag_7556e0"),
                COLORS["primary"],
            ),
            ServerState.STARTING: (
                self.tr("starting_aeed4d"),
                self.tr("making_the_connection_40a12d"),
                self.tr("your_file_transfer_server_will_be_ready_in_fb72ce"),
                COLORS["warning"],
            ),
            ServerState.STOPPING: (
                self.tr("stopping_a71ee1"),
                self.tr("wrapping_things_up_78ab3e"),
                self.tr("waiting_for_your_server_to_finish_shutting_2070bb"),
                COLORS["warning"],
            ),
            ServerState.ERROR: (
                self.tr("needs_attention_c1ebc7"),
                self.tr("let_s_try_that_again_5d2389"),
                self.tr("the_server_could_not_start_check_the_detai_0f2c95"),
                COLORS["danger"],
            ),
            ServerState.STOPPED: (
                self.tr("offline_a17947"),
                self.tr("ready_when_you_are_182bf2"),
                self.tr("start_your_server_and_give_your_files_a_pl_89a83c"),
                COLORS["muted_bright"],
            ),
        }[state]
        if not self.controller.initialized:
            label, headline = (
                self.tr("loading_dc3808"),
                self.tr("getting_things_ready_0d53d6"),
            )
            description, color = (
                self.tr("loading_your_saved_settings_bff31c"),
                COLORS["warning"],
            )
        self.status.value, self.status.color = label, color
        self.status_dot.bgcolor = color
        self.headline.value, self.description.value = headline, description
        self.signal_icon.color = (
            COLORS["primary"] if state == ServerState.RUNNING else COLORS["muted"]
        )
        self.signal_caption.value = (
            self.tr("connected_ready_7176f3")
            if state == ServerState.RUNNING
            else label.upper()
        )
        self.signal_caption.color = color
        error = self.controller.last_error
        error_key = (
            {
                ServerErrorCode.STORAGE_UNAVAILABLE: "server_error_storage",
                ServerErrorCode.STARTUP_TIMEOUT: "server_error_timeout",
            }.get(error.code, "server_error_details")
            if error
            else "server_error_details"
        )
        self.error.value = self.tr(error_key) if error else ""
        self.error.visible = state == ServerState.ERROR and bool(
            self.controller.last_error
        )
        busy = state in {ServerState.STARTING, ServerState.STOPPING}
        running = state == ServerState.RUNNING
        self.server_button.content = (
            f"{label}..."
            if busy
            else (
                self.tr("stop_server_a21bf6")
                if running
                else self.tr("start_server_7b7da6")
            )
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
