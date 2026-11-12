"""Catalog discovery and locale-aware messages for the desktop and web UI."""

import json
import logging
import re
from pathlib import Path

from babel import Locale, UnknownLocaleError
from babel.numbers import format_decimal

logger = logging.getLogger(__name__)
CATALOG_DIR = Path(__file__).resolve().parents[1] / "locales"


def load_catalogs(directory: Path = CATALOG_DIR) -> dict[str, dict]:
    catalogs = {}
    for path in sorted(directory.glob("*.json")):
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
            locale = catalog["id"]
            if not isinstance(locale, str) or path.stem.lower() != locale.lower():
                raise ValueError("catalog id must match filename")
            if not isinstance(catalog["name"], str):
                raise ValueError("catalog name must be a string")
            catalogs[locale.lower()] = catalog
        except OSError, ValueError, KeyError, TypeError:
            logger.exception("Invalid locale catalog: %s", path)
    return catalogs


def resolve_locale(requested: str | None, catalogs: dict[str, dict]) -> str:
    candidate = (requested or "en").replace("_", "-").lower()
    while candidate:
        if candidate in catalogs:
            return candidate
        candidate = candidate.rpartition("-")[0]
    return "en"


class Localizer:
    def __init__(self, language: str = "en", catalogs: dict[str, dict] | None = None):
        self.catalogs = catalogs if catalogs is not None else load_catalogs()
        self.language = resolve_locale(language, self.catalogs)

    def text(self, key: str, **values: object) -> str:
        english = self.catalogs.get("en", {}).get("desktop", {})
        messages = self.catalogs.get(self.language, {}).get("desktop", {})
        message = messages.get(key, english.get(key, ""))
        if not isinstance(message, str):
            message = english.get(key, "")
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m[1], m[0])), message)

    def number(self, value: int | float) -> str:
        try:
            locale = Locale.parse(self.language, sep="-")
        except UnknownLocaleError, ValueError:
            locale = Locale.parse("en")
        return format_decimal(value, locale=locale)
