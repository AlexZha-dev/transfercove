import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.update_service import (
    UpdateOperation,
    UpdateRelease,
    UpdateServiceError,
    UpdateViewState,
    VerifiedInstaller,
)
from app.services.windows_update_installer import InstallerFileError
from app.view.main_page import MainPage


@pytest.fixture
def view():
    release = UpdateRelease("0.3.0", "v0.3.0", "notes", "setup.exe", "", "")
    page = MainPage.__new__(MainPage)
    page.update_state = UpdateViewState(supported=True, release=release)
    page.update_service = SimpleNamespace(
        check_for_update=AsyncMock(return_value=release),
        download_and_verify=AsyncMock(
            return_value=VerifiedInstaller(Path("setup.exe"), "a" * 64, "0.3.0")
        ),
    )
    page._closing = False
    page._update_confirmation = None
    page._update_check_task = None
    page.controller = SimpleNamespace(
        notify=Mock(),
        close=AsyncMock(),
        settings=SimpleNamespace(app=SimpleNamespace(version="0.2.3")),
        settings_store=SimpleNamespace(
            get_last_update_check=AsyncMock(return_value=None),
            set_last_update_check=AsyncMock(),
        ),
    )
    page.page = SimpleNamespace(
        show_dialog=Mock(), pop_dialog=Mock(), window=SimpleNamespace(close=AsyncMock())
    )
    return page


def test_automatic_and_manual_checks_cannot_overlap_while_waiting_for_db(view):
    async def scenario():
        started, finish = asyncio.Event(), asyncio.Event()

        async def read():
            started.set()
            await finish.wait()

        view.controller.settings_store.get_last_update_check.side_effect = read
        first = asyncio.create_task(view.check_for_updates(manual=False))
        await started.wait()
        await view.check_for_updates()
        await view.update_action(None)
        assert view.update_state.operation == UpdateOperation.CHECKING
        view.update_service.download_and_verify.assert_not_called()
        finish.set()
        await first
        view.update_service.check_for_update.assert_awaited_once()
        assert not view.update_state.busy

    asyncio.run(scenario())


def test_double_download_and_check_during_download_are_ignored(view):
    async def scenario():
        started, finish = asyncio.Event(), asyncio.Event()
        result = view.update_service.download_and_verify.return_value

        async def download(_):
            started.set()
            await finish.wait()
            return result

        view.update_service.download_and_verify.side_effect = download
        first = asyncio.create_task(view.update_action(None))
        await started.wait()
        await view.update_action(None)
        await view.check_for_updates()
        view.update_service.download_and_verify.assert_awaited_once()
        view.update_service.check_for_update.assert_not_called()
        assert view.update_state.operation == UpdateOperation.DOWNLOADING
        finish.set()
        await first
        assert view.update_state.installer == result
        assert not view.update_state.busy

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["database", "check", "download"])
def test_errors_release_the_operation_and_allow_retry(view, operation):
    async def scenario():
        failing = {
            "database": view.controller.settings_store.set_last_update_check,
            "check": view.update_service.check_for_update,
            "download": view.update_service.download_and_verify,
        }[operation]
        failing.side_effect = UpdateServiceError("retry")
        action = (
            view.update_action if operation == "download" else view.check_for_updates
        )
        await action(None)
        assert not view.update_state.busy
        assert view.update_state.is_error
        failing.side_effect = None
        await action(None)
        assert not view.update_state.busy
        assert not view.update_state.is_error

    asyncio.run(scenario())


def prepare_confirmation(view):
    view.update_state.installer = view.update_service.download_and_verify.return_value
    view.show_update_install_confirmation()
    return view._update_confirmation[0]


def test_cancel_and_stale_dialog_events_do_not_affect_new_confirmation(view):
    token = prepare_confirmation(view)
    view.show_update_install_confirmation()
    assert view.page.show_dialog.call_count == 1
    view.cancel_update_install(token)
    assert not view.update_state.busy
    new_token = prepare_confirmation(view)
    view.cancel_update_install(token, dismissed=True)
    assert view.update_state.operation == UpdateOperation.CONFIRMING
    view.cancel_update_install(new_token, dismissed=True)
    assert not view.update_state.busy


def test_confirmation_launches_snapshot_once_and_closes_after_launch(monkeypatch, view):
    async def scenario():
        token = prepare_confirmation(view)
        snapshot = view.update_state.installer
        started, finish = asyncio.Event(), asyncio.Event()

        async def launch(installer):
            assert installer is snapshot
            started.set()
            await finish.wait()

        launcher = AsyncMock(side_effect=launch)
        monkeypatch.setattr("app.view.main_page.verify_and_launch", launcher)
        first = asyncio.create_task(view.confirm_update_install(None, token=token))
        await started.wait()
        await view.confirm_update_install(None, token=token)
        await view.check_for_updates()
        view.controller.close.assert_not_called()
        finish.set()
        await first
        launcher.assert_awaited_once()
        view.controller.close.assert_awaited_once()
        view.page.window.close.assert_awaited_once()
        assert view._closing

    asyncio.run(scenario())


@pytest.mark.parametrize("bad_file", [True, False])
def test_install_failure_keeps_app_open_and_invalidates_only_bad_downloads(
    monkeypatch, view, bad_file
):
    token = prepare_confirmation(view)
    error = (
        InstallerFileError("changed")
        if bad_file
        else UpdateServiceError("launch failed")
    )
    monkeypatch.setattr(
        "app.view.main_page.verify_and_launch", AsyncMock(side_effect=error)
    )
    asyncio.run(view.confirm_update_install(None, token=token))
    assert (view.update_state.installer is None) == bad_file
    assert not view.update_state.busy
    assert view.update_state.is_error
    view.controller.close.assert_not_called()
    view.page.window.close.assert_not_called()


def test_background_completion_does_not_change_closed_view(view):
    async def scenario():
        started, finish = asyncio.Event(), asyncio.Event()

        async def check():
            started.set()
            await finish.wait()
            return view.update_service.check_for_update.return_value

        view.update_service.check_for_update.side_effect = check
        task = asyncio.create_task(view.check_for_updates())
        await started.wait()
        await view.close()
        snapshot = vars(view.update_state).copy()
        notifications = view.controller.notify.call_count
        finish.set()
        await task
        assert vars(view.update_state) == snapshot
        assert view.controller.notify.call_count == notifications

    asyncio.run(scenario())
