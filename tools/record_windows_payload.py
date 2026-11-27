"""Add files from a verified Windows release bundle to the upgrade inventory."""

import argparse
import hashlib
from pathlib import Path, PureWindowsPath

INVENTORY = (
    Path(__file__).resolve().parents[1] / "installer/windows/released-payload.txt"
)


def record_payload(bundle: Path, inventory: Path = INVENTORY) -> None:
    if not (bundle / "TransferCove.exe").is_file():
        raise ValueError(f"Missing TransferCove.exe in {bundle}")
    entries: dict[str, set[str]] = {}
    if inventory.exists():
        for line in inventory.read_text(encoding="utf-8").splitlines():
            name, hashes = line.split("|")
            entries[name] = set(hashes.split(",")) if hashes else set()
    for file in bundle.rglob("*"):
        if file.is_file():
            relative = PureWindowsPath(file.relative_to(bundle))
            if str(relative) in {
                "LICENSE",
                "THIRD-PARTY-NOTICES.txt",
                "SECURITY-NOTICE.txt",
            }:
                continue  # Installed separately from the Flet bundle.
            # These paths become literals in the Inno Setup script.
            if any(char in str(relative) for char in "'{}|\r\n"):
                raise ValueError(f"Unsupported installer filename: {relative}")
            with file.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            entries.setdefault(str(relative), set()).add(digest)
            for parent in relative.parents:
                if parent.parts:
                    entries.setdefault(str(parent) + "\\", set())
    # A directory follows all of its children so it can be removed if empty.
    lines = [
        f"{name}|{','.join(sorted(entries[name]))}"
        for name in sorted(entries, reverse=True)
    ]
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    record_payload(parser.parse_args().bundle)
