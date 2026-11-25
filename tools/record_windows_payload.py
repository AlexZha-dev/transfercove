"""Add files from a verified Windows release bundle to the upgrade inventory."""

import argparse
from pathlib import Path, PureWindowsPath

INVENTORY = (
    Path(__file__).resolve().parents[1] / "installer/windows/released-payload.txt"
)


def record_payload(bundle: Path) -> None:
    if not (bundle / "TransferCove.exe").is_file():
        raise ValueError(f"Missing TransferCove.exe in {bundle}")
    paths = set(INVENTORY.read_text(encoding="utf-8").splitlines())
    for file in bundle.rglob("*"):
        if file.is_file():
            relative = PureWindowsPath(file.relative_to(bundle))
            # These paths become literals in the Inno Setup script.
            if any(char in str(relative) for char in "'{}"):
                raise ValueError(f"Unsupported installer filename: {relative}")
            paths.add(str(relative))
            paths.update(str(p) + "\\" for p in relative.parents if p.parts)
    # A directory follows all of its children so it can be removed if empty.
    INVENTORY.write_text(
        "\n".join(sorted(paths, reverse=True)) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    record_payload(parser.parse_args().bundle)
