import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.settings import Settings
from app.server.manager import ServerState
from app.view.main_page import MainPage
from app.view.settings_page import SettingsPage


def make_view(monkeypatch, language="en", *, server_started=True):
    settings = Settings()
    settings.desktop.language = language
    controller = SimpleNamespace(
        settings=settings,
        initialized=True,
        server_state=ServerState.STOPPED,
        server_running=False,
        last_error=None,
        server_url="http://127.0.0.1:8000/",
        advertised_host="127.0.0.1",
        subscribe=Mock(),
        initialize=AsyncMock(),
    )

    async def save(saved):
        controller.settings = saved
        return server_started

    controller.save_settings = AsyncMock(side_effect=save)
    page = SimpleNamespace(
        window=SimpleNamespace(),
        services=[],
        add=Mock(),
        update=Mock(),
        show_dialog=Mock(),
        width=1200,
        web=False,
    )
    monkeypatch.setattr("app.view.main_page.AppController", lambda: controller)
    view = MainPage(page)
    view.security_notice_was_acknowledged = AsyncMock(return_value=True)
    view.start_server_automatically = AsyncMock()
    asyncio.run(view.initialize())
    return view, controller


@pytest.mark.parametrize("server_started", [True, False])
def test_saved_language_updates_desktop_immediately(monkeypatch, server_started):
    view, controller = make_view(monkeypatch, server_started=server_started)
    view.show_settings()
    old_settings = view.current_view
    old_settings.language.value = "ru"
    asyncio.run(old_settings.save(None))

    assert controller.settings.desktop.language == "ru"
    assert view.active_route == "settings"
    assert isinstance(view.current_view, SettingsPage)
    assert view.route_title.value == "Настройки"
    assert view.current_view.save_button.content == "Сохранить изменения"
    assert view.current_view.message.value == (
        "Настройки сохранены"
        if server_started
        else "Настройки сохранены, но сервер не запустился"
    )
    assert len(view.page.services) == 2
    view.show_home()
    assert view.route_title.value == "Главная"
    assert view.current_view.server_button.content == "Запустить сервер"
    view.show_settings()
    view.current_view.language.value = "en"
    asyncio.run(view.current_view.save(None))
    assert view.route_title.value == "Settings"
    assert controller.settings.desktop.language == "en"


def test_initial_language_and_unknown_locale(monkeypatch):
    view, _ = make_view(monkeypatch, "ru")
    assert view.route_title.value == "Главная"
    view.show_security_notice()
    assert (
        view.page.show_dialog.call_args.args[0].title.value
        == "Предупреждение безопасности"
    )
    view._set_update_status("update_downloading", version="1.2.3")
    view.show_settings()
    assert view.current_view.update_status.value == "Загрузка версии 1.2.3..."
    view, _ = make_view(monkeypatch, "not-a-language")
    assert view.route_title.value == "Dashboard"


def test_invalid_settings_do_not_apply_language(monkeypatch):
    view, controller = make_view(monkeypatch)
    view.show_settings()
    settings = view.current_view
    settings.language.value = "ru"
    settings.port.value = "invalid"
    asyncio.run(settings.save(None))
    assert controller.settings.desktop.language == "en"
    assert view.current_view is settings
    assert view.route_title.value == "Settings"


@pytest.mark.parametrize(
    ("language", "dashboard", "settings_label", "save_label"),
    [
        ("es", "Panel", "Configuración", "Guardar cambios"),
        ("pt", "Painel", "Configurações", "Salvar alterações"),
        ("de", "Übersicht", "Einstellungen", "Änderungen speichern"),
        ("fr", "Tableau de bord", "Paramètres", "Enregistrer les modifications"),
        ("uk", "Головна", "Налаштування", "Зберегти зміни"),
    ],
)
def test_added_language_is_selectable_and_applies_after_save(
    monkeypatch, language, dashboard, settings_label, save_label
):
    view, controller = make_view(monkeypatch)
    view.show_settings()
    settings = view.current_view
    assert language in {option.key for option in settings.language.options}
    settings.language.value = language
    asyncio.run(settings.save(None))

    assert controller.settings.desktop.language == language
    assert view.route_title.value == settings_label
    assert view.current_view.save_button.content == save_label
    view.show_home()
    assert view.route_title.value == dashboard

    restarted, _ = make_view(monkeypatch, language)
    assert restarted.route_title.value == dashboard
