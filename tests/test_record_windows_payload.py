import hashlib

from tools.record_windows_payload import record_payload


def test_inventory_preserves_release_hashes_and_is_reproducible(tmp_path):
    bundle = tmp_path / "bundle"
    module = bundle / "app" / "module.pyc"
    module.parent.mkdir(parents=True)
    (bundle / "TransferCove.exe").write_bytes(b"exe")
    manifest = tmp_path / "released.txt"
    versions = (b"old", b"new")
    for version in versions:
        module.write_bytes(version)
        record_payload(bundle, manifest)
    expected = sorted(hashlib.sha256(version).hexdigest() for version in versions)
    rows = manifest.read_text().splitlines()
    assert r"app\module.pyc|" + ",".join(expected) in rows
    assert rows.index("app\\|") > rows.index(r"app\module.pyc|" + ",".join(expected))
    previous = manifest.read_bytes()
    record_payload(bundle, manifest)
    assert manifest.read_bytes() == previous
