from app.core.localization import Localizer


class LocalizedView:
    """Share a localizer between a view's message lookups."""

    def set_language(self, language: str) -> None:
        self._localizer = Localizer(language)

    def tr(self, key: str, **values: object) -> str:
        localizer = getattr(self, "_localizer", None)
        if localizer is None:
            localizer = self._localizer = Localizer()
        return localizer.text(key, **values)
