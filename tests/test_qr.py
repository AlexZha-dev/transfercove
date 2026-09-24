from app.core.qr import make_qr_svg


def test_make_qr_svg_returns_a_standalone_svg() -> None:
    result = make_qr_svg("http://192.168.1.42:8000/")

    assert result.startswith(b"<?xml")
    assert b"<svg" in result
    assert b"id=\"qr-path\"" in result
