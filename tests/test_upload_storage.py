import asyncio
import tempfile
from io import BytesIO
from threading import Event
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from app.core.upload_limits import (
    DiskSpaceGuard,
    LimitedMultipartParser,
    UploadLimitError,
)


@pytest.mark.parametrize(
    ("chunks", "available", "accepted"),
    [
        ([b"12345678", b"12345678"], 110, False),
        ([b"12345678", b"12345678"], 116, True),
        ([b"123456789", b"xyz\r\n--abX"], 118, False),
        ([b"123456789", b"xyz\r\n--abX"], 119, True),
    ],
)
def test_spooling_preserves_reserve_across_buffered_and_fragmented_writes(
    monkeypatch, chunks, available, accepted
):
    opened = []
    observed_free = []

    class TrackedSpool(tempfile.SpooledTemporaryFile):
        disk_bytes = 0

        def write(self, data):
            result = super().write(data)
            if self._rolled:
                self.disk_bytes = self.tell()
            observed_free.append(usage(None).free)
            return result

    def spool(*args, **kwargs):
        file = TrackedSpool(*args, **kwargs)
        opened.append(file)
        return file

    def usage(_path):
        return SimpleNamespace(
            free=available - sum(f.disk_bytes for f in opened if not f.closed)
        )

    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", spool)
    monkeypatch.setattr("app.core.upload_limits.shutil.disk_usage", usage)
    monkeypatch.setattr(LimitedMultipartParser, "spool_max_size", 8)

    async def body():
        yield b'--abc\r\nContent-Disposition: form-data; name="file"; filename="x"\r\n\r\n'
        for chunk in chunks:
            yield chunk
        yield b"\r\n--abc--\r\n"

    async def scenario():
        parser = LimitedMultipartParser(
            Headers({"content-type": "multipart/form-data; boundary=abc"}),
            body(),
            max_bytes=1000,
            reserve=100,
        )
        if accepted:
            form = await parser.parse()
            try:
                assert await form["file"].read() == b"".join(chunks)
            finally:
                await form.close()
        else:
            with pytest.raises(UploadLimitError) as error:
                await parser.parse()
            assert error.value.status_code == 507

    asyncio.run(scenario())
    assert opened and all(file.closed for file in opened)
    assert min(observed_free) >= 100


@pytest.mark.parametrize("cancel_first", [False, True])
def test_concurrent_writes_wait_for_flush_even_when_cancelled(
    tmp_path, monkeypatch, cancel_first
):
    entered = Event()
    release = Event()
    checks = []
    disk = SimpleNamespace(free=110)

    def usage(_path):
        checks.append(disk.free)
        return SimpleNamespace(free=disk.free)

    class SlowBufferedFile(BytesIO):
        def write(self, data):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release the pending disk write")
            return super().write(data)

        def flush(self):
            disk.free -= len(self.getvalue())

    monkeypatch.setattr("app.core.upload_limits.shutil.disk_usage", usage)

    async def scenario():
        guard = DiskSpaceGuard()
        first_file, second_file = SlowBufferedFile(), BytesIO()
        first = asyncio.create_task(guard.write(first_file, tmp_path, 100, b"12345678"))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            second = asyncio.create_task(
                guard.write(second_file, tmp_path, 100, b"12345678")
            )
            if cancel_first:
                # Repeated cancellation must not detach the worker from cleanup.
                first.cancel()
                await asyncio.sleep(0)
                first.cancel()
            await asyncio.sleep(0.02)
            assert not first.done()
            assert not second.done()
            assert checks == [110]
            release.set()
            if cancel_first:
                with pytest.raises(asyncio.CancelledError):
                    await first
            else:
                await first
            with pytest.raises(UploadLimitError) as error:
                await second
            assert error.value.status_code == 507
            assert first_file.getvalue() == b"12345678"
            assert second_file.getvalue() == b""
            assert disk.free == 102
            # Rejected writes release the guard, too.
            await guard.write(second_file, tmp_path, 100, b"ok")
        finally:
            release.set()
            await asyncio.gather(
                *[task for task in (first, second) if task is not None],
                return_exceptions=True,
            )
            first_file.close()
            second_file.close()

    asyncio.run(scenario())
