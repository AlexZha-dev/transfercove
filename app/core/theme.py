from pathlib import Path

import flet as ft

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"


def brand_icon(size: int = 42) -> ft.Image:
    return ft.Image(
        src="icon.svg",
        width=size,
        height=size,
        semantics_label="WiFi Transmitter",
        fit=ft.BoxFit.CONTAIN,
    )


COLORS = {
    "background": "#07100C",
    "sidebar": "#0A1510",
    "panel": "#0E1D15",
    "panel_alt": "#13281C",
    "field": "#0A1710",
    "border": "#203C2B",
    "border_strong": "#375A43",
    "primary": "#6EF0A0",
    "primary_dark": "#163F28",
    "on_primary": "#06130B",
    "text": "#F1FBF4",
    "muted": "#8DA697",
    "muted_bright": "#B6CBBD",
    "danger": "#FF8F8F",
    "warning": "#FFC1A9",
}


def button_style(*, primary: bool = False, danger: bool = False) -> ft.ButtonStyle:
    background = COLORS["primary"] if primary else COLORS["panel_alt"]
    foreground = COLORS["on_primary"] if primary else COLORS["text"]
    if danger:
        background, foreground = "#30201D", COLORS["warning"]
    return ft.ButtonStyle(
        color={
            ft.ControlState.DEFAULT: foreground,
            ft.ControlState.DISABLED: COLORS["muted"],
        },
        bgcolor={
            ft.ControlState.DEFAULT: background,
            ft.ControlState.DISABLED: COLORS["panel_alt"],
        },
        overlay_color=ft.Colors.with_opacity(0.08, COLORS["text"]),
        elevation=0,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        shape=ft.RoundedRectangleBorder(radius=12),
        side=ft.BorderSide(1, background if primary else COLORS["border"]),
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
        animation_duration=180,
    )


def app_theme() -> ft.Theme:
    return ft.Theme(
        font_family="Segoe UI",
        color_scheme_seed=COLORS["primary"],
        color_scheme=ft.ColorScheme(
            primary=COLORS["primary"],
            on_primary=COLORS["on_primary"],
            primary_container=COLORS["primary_dark"],
            on_primary_container=COLORS["primary"],
            secondary=COLORS["primary"],
            surface=COLORS["panel"],
            on_surface=COLORS["text"],
            on_surface_variant=COLORS["muted_bright"],
            outline=COLORS["border_strong"],
            outline_variant=COLORS["border"],
            error=COLORS["danger"],
            surface_tint=ft.Colors.TRANSPARENT,
        ),
        scaffold_bgcolor=COLORS["background"],
        divider_color=COLORS["border"],
        button_theme=ft.ButtonTheme(style=button_style()),
        text_button_theme=ft.TextButtonTheme(
            style=ft.ButtonStyle(color=COLORS["muted_bright"])
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=4, radius=8, thumb_color=COLORS["border_strong"]
        ),
        switch_theme=ft.SwitchTheme(
            thumb_color={
                ft.ControlState.SELECTED: COLORS["on_primary"],
                ft.ControlState.DEFAULT: COLORS["muted"],
            },
            track_color={
                ft.ControlState.SELECTED: COLORS["primary"],
                ft.ControlState.DEFAULT: COLORS["panel_alt"],
            },
            track_outline_color={
                ft.ControlState.SELECTED: COLORS["primary"],
                ft.ControlState.DEFAULT: COLORS["border_strong"],
            },
        ),
    )


def panel(
    content: ft.Control, padding: int = 24, *, col: int | dict[str, int] = 12
) -> ft.Container:
    return ft.Container(
        content=content,
        col=col,
        padding=padding,
        bgcolor=COLORS["panel"],
        border=ft.Border.all(1, COLORS["border"]),
        border_radius=20,
    )


def eyebrow(value: str) -> ft.Text:
    return ft.Text(
        value.upper(),
        size=10,
        weight=ft.FontWeight.W_700,
        color=COLORS["primary"],
        style=ft.TextStyle(letter_spacing=1.8),
    )


def icon_badge(icon, *, size: int = 42) -> ft.Container:
    return ft.Container(
        content=ft.Icon(icon, size=size * 0.48, color=COLORS["primary"]),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor=COLORS["primary_dark"],
        border=ft.Border.all(1, COLORS["border_strong"]),
        border_radius=12,
    )


def text_field(label: str, value: str, **kwargs) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        text_size=13,
        color=COLORS["text"],
        label_style=ft.TextStyle(size=12, color=COLORS["muted"]),
        filled=True,
        fill_color=COLORS["field"],
        border_color=COLORS["border"],
        focused_border_color=COLORS["primary"],
        focused_border_width=1,
        border_radius=12,
        content_padding=ft.Padding.symmetric(horizontal=16, vertical=18),
        cursor_color=COLORS["primary"],
        selection_color=ft.Colors.with_opacity(0.25, COLORS["primary"]),
        **kwargs,
    )


def section_title(title: str, subtitle: str | None = None) -> ft.Column:
    controls: list[ft.Control] = [
        ft.Text(
            title,
            size=16,
            weight=ft.FontWeight.W_600,
            color=COLORS["text"],
        )
    ]

    if subtitle:
        controls.append(ft.Text(subtitle, color=COLORS["muted"], size=12))

    return ft.Column(controls=controls, spacing=4)
