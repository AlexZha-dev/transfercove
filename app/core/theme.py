import flet as ft

COLORS = {
    "background": "#07100D",
    "sidebar": "#0A1511",
    "panel": "#0D1B16",
    "panel_alt": "#11251D",
    "border": "#204333",
    "primary": "#79F2A4",
    "primary_dark": "#1D6B47",
    "text": "#EDF9F0",
    "muted": "#8AA99A",
    "danger": "#FF8A8A",
    "warning": "#FFD166",
}


def panel(content: ft.Control, padding: int = 24) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=COLORS["panel"],
        border=ft.Border.all(1, COLORS["border"]),
        border_radius=18,
    )


def section_title(title: str, subtitle: str | None = None) -> ft.Column:
    controls: list[ft.Control] = [
        ft.Text(
            title,
            size=18,
            weight=ft.FontWeight.BOLD,
            color=COLORS["text"],
        )
    ]

    if subtitle:
        controls.append(ft.Text(subtitle, color=COLORS["muted"], size=13))

    return ft.Column(controls=controls, spacing=4)
