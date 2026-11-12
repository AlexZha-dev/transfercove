import ast
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.localization import (
    Localizer,
    load_catalogs,
    resolve_locale,
    validate_catalogs,
)


def test_locale_matching_and_english_fallback():
    catalogs = {
        "en": {"desktop": {"greeting": "Hello, {{name}}"}},
        "pt": {"desktop": {}},
        "pt-br": {"desktop": {"greeting": "Olá, {{name}}"}},
    }
    assert resolve_locale("pt-BR", catalogs) == "pt-br"
    assert resolve_locale("pt-PT", catalogs) == "pt"
    assert resolve_locale("zz", catalogs) == "en"
    assert Localizer("pt-PT", catalogs).text("greeting", name="A.txt") == "Hello, A.txt"
    assert Localizer("pt-BR", catalogs).text("greeting", name="A.txt") == "Olá, A.txt"


def test_catalog_discovery_ignores_invalid_files(tmp_path):
    (tmp_path / "en.json").write_text(
        json.dumps({"id": "en", "name": "English", "desktop": {}, "web": {}}),
        encoding="utf-8",
    )
    (tmp_path / "ru.json").write_text("invalid JSON", encoding="utf-8")
    assert list(load_catalogs(tmp_path)) == ["en"]


def test_upload_catalogs_have_matching_keys_and_parameters():
    import re

    catalogs = load_catalogs()
    english = catalogs["en"]["web"]
    russian = catalogs["ru"]["web"]
    assert set(english) == set(russian)
    for key, value in english.items():
        translated = russian[key]
        if isinstance(value, dict):
            assert {"one", "few", "many", "other"} <= set(translated)
            for form in translated.values():
                assert set(re.findall(r"\{\{(\w+)\}\}", form)) == set(
                    re.findall(r"\{\{(\w+)\}\}", value["other"])
                )
        else:
            assert isinstance(translated, str) and translated
            assert set(re.findall(r"\{\{(\w+)\}\}", translated)) == set(
                re.findall(r"\{\{(\w+)\}\}", value)
            )


def test_catalog_validation_detects_missing_messages_and_bad_placeholders():
    catalogs = load_catalogs()
    assert validate_catalogs(catalogs) == []
    catalogs["ru"]["web"].pop("network")
    catalogs["ru"]["web"]["savedAs"] = "Сохранено: {{name}}"
    errors = validate_catalogs(catalogs)
    assert "ru.web.network: missing" in errors
    assert "ru.web.savedAs: interpolation fields differ" in errors


def test_locale_endpoint_exposes_discovered_catalogs(client):
    response = client.get("/locales")
    assert response.status_code == 200
    assert response.json()["ru"]["web"]["language"] == "Язык"


def test_english_desktop_catalog_cannot_be_empty():
    catalogs = load_catalogs()
    catalogs["en"]["desktop"] = {}
    assert "en.desktop: catalog must not be empty" in validate_catalogs(catalogs)


def test_desktop_translation_keys_exist_in_all_catalogs():
    catalogs = load_catalogs()
    for path in Path("app/view").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            if node.func.attr not in {"tr", "_set_update_status"} or not node.args:
                continue
            key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                for language, catalog in catalogs.items():
                    assert key.value in catalog["desktop"], (path, language, key.value)


def test_web_fallback_for_missing_empty_and_invalid_messages():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the browser translation functions")
    script = Path("app/static/upload.js").read_text(encoding="utf-8")
    functions = script[
        script.index("function getMessage(") : script.index(
            "function applyTranslations("
        )
    ]
    javascript = (
        """
const catalogs = {en: {web: {greeting: "Hello {{name}}", fileCount: {other: "{{count}} files"}}}};
let activeLanguage = "ru";
let messages = {};
"""
        + functions
        + """
const results = [];
for (const value of [undefined, "", "   ", 42, {}, "Привет {{name}}"]) {
    messages.greeting = value;
    results.push(t("greeting", {name: "A.txt"}));
}
console.log(JSON.stringify(results));
"""
    )
    result = subprocess.run(
        [node, "-e", javascript], check=True, capture_output=True, encoding="utf-8"
    )
    assert json.loads(result.stdout) == ["Hello A.txt"] * 5 + ["Привет A.txt"]
