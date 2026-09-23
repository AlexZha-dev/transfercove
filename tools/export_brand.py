"""Export the shared SVG to PNG and multi-size ICO (requires Playwright)."""

import argparse
import base64
import struct
from pathlib import Path

from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Optional path to a Chromium executable")
    args = parser.parse_args()
    source = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    sizes = (16, 32, 48, 64, 128, 180, 256, 1024)
    frames = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=args.browser, headless=True
        )
        page = browser.new_page(device_scale_factor=1)
        for size in sizes:
            encoded = page.evaluate(
                """async ({source, size}) => {
                    const url = URL.createObjectURL(new Blob([source], {type: 'image/svg+xml'}));
                    const image = new Image();
                    image.src = url;
                    await image.decode();
                    const canvas = document.createElement('canvas');
                    canvas.width = canvas.height = size;
                    canvas.getContext('2d').drawImage(image, 0, 0, size, size);
                    URL.revokeObjectURL(url);
                    return canvas.toDataURL('image/png').split(',')[1];
                }""",
                {"source": source, "size": size},
            )
            frames[size] = base64.b64decode(encoded)
        browser.close()

    (ASSETS / "icon.png").write_bytes(frames[1024])
    (ASSETS / "favicon.png").write_bytes(frames[32])
    (ASSETS / "apple-touch-icon.png").write_bytes(frames[180])

    # Windows ICO stores a directory followed by independently rendered PNGs.
    icon_sizes = (16, 32, 48, 64, 128, 256)
    offset = 6 + 16 * len(icon_sizes)
    directory = bytearray(struct.pack("<HHH", 0, 1, len(icon_sizes)))
    for size in icon_sizes:
        frame = frames[size]
        dimension = size if size < 256 else 0
        directory.extend(
            struct.pack(
                "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(frame), offset
            )
        )
        offset += len(frame)
    (ASSETS / "icon.ico").write_bytes(
        bytes(directory) + b"".join(frames[size] for size in icon_sizes)
    )
    print("Exported icon.png, favicon.png, apple-touch-icon.png and icon.ico")


if __name__ == "__main__":
    main()
