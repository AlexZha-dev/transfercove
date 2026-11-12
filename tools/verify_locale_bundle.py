"""Check that the Windows application contains every source locale catalog."""

from pathlib import Path


def main() -> None:
    source = Path("app/locales")
    destination = Path("build/windows/app/app/locales")
    catalogs = sorted(source.glob("*.json"))
    if not catalogs:
        raise SystemExit("No source locale catalogs found")
    for catalog in catalogs:
        bundled = destination / catalog.name
        if not bundled.is_file() or bundled.read_bytes() != catalog.read_bytes():
            raise SystemExit(f"Missing or outdated bundled locale: {catalog.name}")
    print(f"Verified {len(catalogs)} bundled locale catalogs.")


if __name__ == "__main__":
    main()
