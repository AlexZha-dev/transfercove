"""Run the production Setup script with a small payload and isolated HKCU identity."""

import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Setup")
ROOT = Path(__file__).resolve().parents[1]
SILENT = ["/CURRENTUSER", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART"]


def run(args):
    return subprocess.run(
        list(map(str, args)),
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=120,
    )


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    compiler = Path(
        os.environ.get("ISCC_PATH")
        or Path(os.environ["ProgramFiles(x86)"]) / "Inno Setup 6/ISCC.exe"
    )
    if not compiler.exists():
        pytest.skip("Inno Setup compiler unavailable")
    root = tmp_path_factory.mktemp("setup-build")
    (root / "pyproject.toml").write_text(
        '[project]\nversion = "0.3.3"\n', encoding="utf-8"
    )
    source = root / "installer/windows"
    source.mkdir(parents=True)
    bundle = root / "build/windows"
    bundle.mkdir(parents=True)
    identity = "{" + str(uuid.uuid4()).upper() + "}"
    name = "TransferCove-test-" + identity[1:9]
    for relative in (
        "assets/icon.ico",
        "LICENSE",
        "THIRD-PARTY-NOTICES.txt",
        "installer/windows/SECURITY-NOTICE.txt",
    ):
        (root / relative).parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / relative, root / relative)

    def compile_script(script, filename):
        result = run([compiler, "/Q", f"/O{root}", f"/F{filename}", script])
        assert result.returncode == 0, result.stdout + result.stderr
        return root / (filename + ".exe")

    # Real PE version resources let the tests vary the EXE independently of HKCU.
    versions = {}
    for version in ("0.3.2", "0.3.3", "0.3.4", "0.3.3.42"):
        stub = root / "version.iss"
        stub.write_text(
            f"[Setup]\nAppName=Fixture\nAppVersion={version}\nVersionInfoVersion={version}\n"
            "CreateAppDir=no\nUninstallable=no\nPrivilegesRequired=lowest\n",
            encoding="utf-8",
        )
        versions[version] = compile_script(stub, version)
    shutil.copyfile(versions["0.3.3"], bundle / "TransferCove.exe")
    template = (ROOT / "installer/windows/TransferCove.iss").read_text(encoding="utf-8")
    template = template.replace("{A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF}", identity)
    template = template.replace(
        '#define MyAppName "TransferCove"', f'#define MyAppName "{name}"'
    )
    # This handler exists only in the test copy. Event attributes run before the
    # primary handler, so the failure occurs after the successful preflight.
    script = source / "TransferCove.iss"
    script.write_text(
        template
        + """
function SetFixtureAttributes(Path: String; Attr: LongWord): Boolean;
  external 'SetFileAttributesW@kernel32.dll stdcall';
<event('CurStepChanged')>
procedure IntroduceLateFailure(Step: TSetupStep);
begin
  if (Step = ssPostInstall) and (ExpandConstant('{param:latefailure|0}') = '1') then
    if not SetFixtureAttributes(ExpandConstant('{app}\\late.dat'), 1) then
      RaiseException('Could not set up read-only fixture');
end;
""",
        encoding="utf-8",
    )
    digest = hashlib.sha256(b"published").hexdigest()
    retired = ["modified.dat", "late.dat", r"junction\old.dat", "good.dat"]
    (source / "released-payload.txt").write_text(
        "".join(f"{path}|{digest}\n" for path in retired), encoding="utf-8"
    )
    return SimpleNamespace(
        setup=compile_script(script, "candidate"),
        versions=versions,
        root=root,
        compiler=compiler,
        key=rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{identity}_is1",
    )


@pytest.mark.parametrize(
    ("project", "binary", "override", "expected"),
    [
        ('[project]\nversion = "0.3.3"\n', "0.3.3", None, True),
        ('[project]\nversion = "0.3.3"\n', "0.3.3.42", None, True),
        ('[project]\nversion = "0.3.3"\n', "0.3.4", None, False),
        ('[project]\nversion = "0.3.3"\n', None, None, False),
        ('[project]\nname = "test"\n', "0.3.3", None, False),
        ('[project]\nversion = "0.3.x"\n', "0.3.3", None, False),
        ('[project]\nversion = "0.3.3"\nversion = "0.3.3"\n', "0.3.3", None, False),
        ('[project]\nversion = "0.3.3"\n', "0.3.3", "0.3.4", False),
    ],
)
def test_compile_checks_project_and_exe_versions(
    package, tmp_path, project, binary, override, expected
):
    shutil.copytree(package.root / "installer", tmp_path / "installer")
    shutil.copytree(package.root / "assets", tmp_path / "assets")
    shutil.copyfile(package.root / "LICENSE", tmp_path / "LICENSE")
    shutil.copyfile(
        package.root / "THIRD-PARTY-NOTICES.txt", tmp_path / "THIRD-PARTY-NOTICES.txt"
    )
    (tmp_path / "pyproject.toml").write_text(project, encoding="utf-8")
    bundle = tmp_path / "build/windows"
    bundle.mkdir(parents=True)
    if binary:
        shutil.copyfile(package.versions[binary], bundle / "TransferCove.exe")
    args = [package.compiler, "/Q", f"/O{tmp_path}", "/Fversion-test"]
    if override:
        args.append(f"/DMyAppVersion={override}")
    result = run([*args, tmp_path / "installer/windows/TransferCove.iss"])
    assert (result.returncode == 0) is expected, result.stdout + result.stderr
    if binary == "0.3.4":
        assert "0.3.3" in result.stderr and "0.3.4" in result.stderr


def test_installer_build_script_rejects_stale_payload(package, tmp_path, monkeypatch):
    poetry = shutil.which("poetry")
    if not poetry:
        pytest.skip("Poetry unavailable")
    shutil.copytree(package.root / "installer", tmp_path / "installer")
    shutil.copytree(package.root / "assets", tmp_path / "assets")
    shutil.copyfile(package.root / "LICENSE", tmp_path / "LICENSE")
    shutil.copyfile(
        package.root / "THIRD-PARTY-NOTICES.txt", tmp_path / "THIRD-PARTY-NOTICES.txt"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "transfercove"\nversion = "0.3.3"\n', encoding="utf-8"
    )
    scripts = tmp_path / ".github/scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(
        ROOT / ".github/scripts/build-installer.ps1", scripts / "build-installer.ps1"
    )
    bundle = tmp_path / "build/windows"
    bundle.mkdir(parents=True)
    exe = bundle / "TransferCove.exe"
    shutil.copyfile(package.versions["0.3.4"], exe)
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        scripts / "build-installer.ps1",
        "-CompilerPath",
        package.compiler,
    ]
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    stale = run(args)
    assert stale.returncode != 0
    assert "0.3.3" in stale.stdout + stale.stderr
    assert "0.3.4" in stale.stdout + stale.stderr
    shutil.copyfile(package.versions["0.3.3"], exe)
    valid = run(args)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    output = tmp_path / "dist/installer/TransferCove-Setup-0.3.3.exe"
    assert output.is_file()
    assert output.with_suffix(".exe.sha256").is_file()
    monkeypatch.setenv("TRANSFERCOVE_TEST_INSTALLER", str(output))
    metadata = run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Item -LiteralPath $env:TRANSFERCOVE_TEST_INSTALLER).VersionInfo.FileVersion",
        ]
    )
    assert metadata.returncode == 0, metadata.stderr
    assert metadata.stdout.strip().startswith("0.3.3")


@pytest.fixture
def target(package, tmp_path):
    import winreg

    directory = tmp_path / "installed"
    directory.mkdir()
    shutil.copyfile(package.versions["0.3.2"], directory / "TransferCove.exe")
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        package.key,
        0,
        winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
    ) as key:
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(directory))
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "0.3.2")
    try:
        yield directory
    finally:
        uninstaller = directory / "unins000.exe"
        if uninstaller.exists():
            result = run([uninstaller, *SILENT])
            assert result.returncode == 0, result.stderr
        try:
            winreg.DeleteKeyEx(
                winreg.HKEY_CURRENT_USER, package.key, winreg.KEY_WOW64_64KEY
            )
        except FileNotFoundError:
            pass


def install(package, target, *arguments):
    log = target.parent / "setup.log"
    result = run([package.setup, *SILENT, f"/DIR={target}", f"/LOG={log}", *arguments])
    return result.returncode, log.read_text(encoding="utf-8-sig")


def test_cleanup_failures_and_repair(package, target):
    import _winapi
    import ctypes
    from ctypes import wintypes

    for name in ("good.dat", "late.dat"):
        (target / name).write_bytes(b"published")
    (target / "modified.dat").write_bytes(b"my changes")
    (target / "personal.txt").write_text("keep")
    external = target.parent / "external"
    external.mkdir()
    (external / "old.dat").write_bytes(b"published")
    _winapi.CreateJunction(str(external), str(target / "junction"))
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(
        str(target / "late.dat"), 0x80000000, 1, None, 3, 0, None
    )
    assert handle != wintypes.HANDLE(-1).value
    try:
        code, log = install(package, target)
        assert code == 7 and "late.dat" in log, log
        assert (target / "good.dat").read_bytes() == b"published"
        assert (target / "TransferCove.exe").read_bytes() == package.versions[
            "0.3.2"
        ].read_bytes()
    finally:
        kernel.CloseHandle(wintypes.HANDLE(handle))
    try:
        code, log = install(package, target, "/latefailure=1")
        assert code == 20 and "late.dat" in log, log
        assert (target / "late.dat").exists()
        assert not (target / "good.dat").exists()
        assert (target / "TransferCove.exe").read_bytes() == package.versions[
            "0.3.3"
        ].read_bytes()
    finally:
        assert kernel.SetFileAttributesW(str(target / "late.dat"), 0x80)
    code, log = install(package, target)
    assert code == 0, log
    assert not (target / "late.dat").exists()
    assert (target / "modified.dat").read_bytes() == b"my changes"
    assert (target / "personal.txt").read_text() == "keep"
    assert (external / "old.dat").read_bytes() == b"published"


@pytest.mark.parametrize(
    ("display", "exe", "same_directory", "expected_code"),
    [
        ("0.3.2+42", "0.3.2", True, 0),
        ("0.3.3+42", "0.3.3", True, 0),
        ("0.3.3.42", "0.3.3", True, 0),
        ("0.3.4+1", "0.3.2", True, 7),
        ("0.3.2", "0.3.4", True, 7),
        ("unknown", "0.3.2", True, 0),
        ("unknown", "0.3.2", False, 7),
        ("0.3.2+42suffix", None, True, 7),
        ("0.3.2.0.99", None, True, 7),
        (None, None, True, 7),
    ],
)
def test_version_sources(package, target, display, exe, same_directory, expected_code):
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        package.key,
        0,
        winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
    ) as key:
        if display is None:
            winreg.DeleteValue(key, "DisplayVersion")
        else:
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, display)
        if not same_directory:
            winreg.SetValueEx(
                key, "InstallLocation", 0, winreg.REG_SZ, str(target.parent / "other")
            )
    binary = target / "TransferCove.exe"
    if exe:
        shutil.copyfile(package.versions[exe], binary)
    else:
        binary.unlink()
    code, log = install(package, target)
    assert code == expected_code, log
    if expected_code == 0:
        assert binary.read_bytes() == package.versions["0.3.3"].read_bytes()
    elif exe:
        assert binary.read_bytes() == package.versions[exe].read_bytes()
    else:
        assert not binary.exists()
