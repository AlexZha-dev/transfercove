# Translation catalogs

The application currently includes English (`en`), Russian (`ru`), Spanish
(`es`), Brazilian Portuguese (`pt`), German (`de`), French (`fr`), and
Ukrainian (`uk`). Regional variants such as `es-MX`, `pt-BR`, and `fr-CA`
fall back to their base-language catalog when no regional catalog exists.

The upload page loads locale catalogs from `app/locales/`. Each UTF-8 JSON
file has an `id` matching its filename, a native-language `name`, and `web`
and `desktop` objects. Use a BCP 47 language tag, for example `pt-BR.json`.

Copy `en.json` to a new file, update its `id` and `name`, and translate the
messages without changing keys or placeholders such as `{{filename}}`.
File names, paths, and other substituted values must remain unchanged.
Plural objects use CLDR categories such as `one`, `few`, `many`, and `other`;
include every category used by the language. The browser chooses the form
using `Intl.PluralRules`.

Run `poetry run python -m app.core.localization` and the localization tests
before submitting a translation. Missing messages fall back to English at
runtime, but the validator reports them for translators. Restart the server
after adding a catalog and reload the upload page to see the new language.

Translate both the `desktop` and `web` sections. Desktop translations are
applied after settings are saved and restored when the app restarts. The upload
page has a separate language preference stored by the browser. Diagnostic
details stay in application logs; names, paths and other user values are not
translated.
