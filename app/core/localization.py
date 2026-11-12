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
            if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", locale):
                raise ValueError("invalid locale identifier")
            if not all(
                isinstance(catalog.get(section), dict) for section in ("desktop", "web")
            ):
                raise ValueError("catalog sections must be objects")
            catalogs[locale.lower()] = catalog
        except OSError, ValueError, KeyError, TypeError:
            logger.exception("Invalid locale catalog: %s", path)
    return catalogs


def validate_catalogs(catalogs: dict[str, dict]) -> list[str]:
    """Report missing messages and mismatched interpolation fields."""
    errors = []
    english = catalogs.get("en")
    if not english:
        return ["Missing English catalog"]

    def check(reference, actual, path, language):
        if isinstance(reference, dict):
            if not isinstance(actual, dict):
                errors.append(f"{path}: expected object")
                return
            if "other" in reference and set(reference) <= {
                "zero",
                "one",
                "two",
                "few",
                "many",
                "other",
            }:
                try:
                    required = set(Locale.parse(language, sep="-").plural_form.tags) | {
                        "other"
                    }
                except UnknownLocaleError, ValueError:
                    required = {"other"}
                for key in required:
                    if key not in actual:
                        errors.append(f"{path}.{key}: missing")
                for key, value in actual.items():
                    check(
                        reference.get(key, reference["other"]),
                        value,
                        f"{path}.{key}",
                        language,
                    )
                return
            for key, value in reference.items():
                if key not in actual:
                    errors.append(f"{path}.{key}: missing")
                else:
                    check(value, actual[key], f"{path}.{key}", language)
        elif not isinstance(actual, str) or not actual:
            errors.append(f"{path}: expected non-empty string")
        elif set(re.findall(r"\{\{(\w+)\}\}", reference)) != set(
            re.findall(r"\{\{(\w+)\}\}", actual)
        ):
            errors.append(f"{path}: interpolation fields differ")

    for language, catalog in catalogs.items():
        for section in ("desktop", "web"):
            check(english[section], catalog[section], f"{language}.{section}", language)
    return errors


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


if __name__ == "__main__":
    catalogs = load_catalogs()
    errors = validate_catalogs(catalogs)
    errors.extend(
        f"Invalid catalog: {path.name}"
        for path in CATALOG_DIR.glob("*.json")
        if path.stem.lower() not in catalogs
    )
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("Locale catalogs are valid.")
