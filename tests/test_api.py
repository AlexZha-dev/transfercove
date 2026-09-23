from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health_endpoint_reports_ready(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_page_and_static_assets_are_available(client: TestClient) -> None:
    page = client.get("/")
    stylesheet = client.get("/static/upload.css")
    script = client.get("/static/upload.js")

    assert page.status_code == 200
    assert "TransferCove" in page.text
    assert stylesheet.status_code == 200
    assert "--green:" in stylesheet.text
    assert script.status_code == 200
    assert "XMLHttpRequest" in script.text


def test_upload_endpoint_persists_file_and_metadata(client: TestClient) -> None:
    response = client.post(
        "/v1/files",
        files={"file": ("greeting.txt", b"hello from pytest", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "greeting.txt"
    assert payload["size"] == len(b"hello from pytest")
    assert payload["content_type"] == "text/plain"
    assert payload["upload"]["remaining_seconds"] == 0

    storage_dir = Path(client.app.state.settings.transmitter.storage_dir)
    stored_files = list(storage_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].suffix == ".txt"
    assert stored_files[0].read_bytes() == b"hello from pytest"


def test_upload_endpoint_requires_a_file(client: TestClient) -> None:
    response = client.post("/v1/files", data={})

    assert response.status_code == 422
