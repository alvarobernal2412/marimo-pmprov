import http.server
import io
import json
import threading
import time
import zipfile

import pytest

from provenance_widget.portable import zip_provenance
from provenance_widget.sync import Sync

KEY = "ana-bpm-course-2026-k3m9q2xa"


class FakeService:
    """The few routes of provenance-sync that the client uses, with a switch for each way it can go wrong."""

    def __init__(self):
        self.stored = {}  # key -> (revision, bytes)
        self.reject_keys = False
        self.force_status = None
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _key(self):
                header = self.headers.get("Authorization", "")
                return header[7:] if header.startswith("Bearer ") else ""

            def _send(self, status, body=b"", headers=None):
                self.send_response(status)
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if owner.force_status:
                    return self._send(owner.force_status)
                if owner.reject_keys or not self._key():
                    return self._send(401)
                found = owner.stored.get(self._key())
                if found is None:
                    return self._send(404)
                self._send(200, found[1], {"ETag": f'"{found[0]}"'})

            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if owner.force_status:
                    return self._send(owner.force_status)
                if owner.reject_keys or not self._key():
                    return self._send(401)
                revision = owner.stored.get(self._key(), (0, b""))[0]
                match = self.headers.get("If-Match", "").strip('"')
                if match.isdigit() and int(match) != revision:
                    return self._send(409, json.dumps({"revision": revision}).encode(), {"Content-Type": "application/json"})
                owner.stored[self._key()] = (revision + 1, body)
                self._send(200, json.dumps({"revision": revision + 1}).encode(), {"Content-Type": "application/json"})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def service():
    fake = FakeService()
    yield fake
    fake.stop()


def _history(folder, content=b"db"):
    (folder / "artifacts").mkdir(parents=True, exist_ok=True)
    (folder / "provenance.db").write_bytes(content)
    (folder / "artifacts" / "a.parquet").write_bytes(b"x" * 50)
    return folder


def _names(data):
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def test_pushing_stores_the_zip_under_the_students_key(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder)

    assert sync.push() is True

    revision, data = service.stored[KEY]
    assert revision == 1 and _names(data) == {"provenance.db", "artifacts/a.parquet"}
    assert sync.status.state == "saved" and sync.status.revision == 1


def test_an_unchanged_history_is_not_sent_again(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder)
    sync.push()

    assert sync.push() is False
    assert service.stored[KEY][0] == 1
    (folder / "provenance.db").write_bytes(b"db, then more")
    assert sync.push() is True and service.stored[KEY][0] == 2


def test_a_new_notebook_gets_the_students_work_back(service, tmp_path):
    first = _history(tmp_path / "one" / "provenance", b"first session")
    Sync(service.url, KEY, first).push()

    second = tmp_path / "two" / "provenance"
    outcome = Sync(service.url, KEY, second).restore()

    assert outcome == "restored"
    assert (second / "provenance.db").read_bytes() == b"first session"


def test_a_student_with_nothing_stored_starts_empty(service, tmp_path):
    folder = tmp_path / "provenance"
    assert Sync(service.url, KEY, folder).restore() == "empty"
    assert not (folder / "provenance.db").exists()


def test_a_restarted_notebook_keeps_its_own_newer_copy(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"v1")
    Sync(service.url, KEY, folder).push()
    (folder / "provenance.db").write_bytes(b"v2, not sent yet")

    outcome = Sync(service.url, KEY, folder).restore()  # a new Sync object, as after a kernel restart

    assert outcome == "kept-local"
    assert (folder / "provenance.db").read_bytes() == b"v2, not sent yet"


def test_a_copy_that_is_behind_the_server_is_replaced(service, tmp_path):
    other = _history(tmp_path / "other" / "provenance", b"v1")
    one = Sync(service.url, KEY, other)
    one.push()
    mine = tmp_path / "mine" / "provenance"
    Sync(service.url, KEY, mine).restore()
    (other / "provenance.db").write_bytes(b"v2 from another tab")
    one.push()

    outcome = Sync(service.url, KEY, mine).restore()

    assert outcome == "restored" and (mine / "provenance.db").read_bytes() == b"v2 from another tab"


def test_work_that_was_never_synced_is_not_lost_to_a_restore(service, tmp_path):
    Sync(service.url, KEY, _history(tmp_path / "elsewhere" / "provenance", b"on the server")).push()
    folder = _history(tmp_path / "provenance", b"local work, never synced")

    outcome = Sync(service.url, KEY, folder).restore()

    assert outcome == "restored" and (folder / "provenance.db").read_bytes() == b"on the server"
    saved = [p for p in tmp_path.iterdir() if p.name.startswith("provenance.unsynced")]
    assert len(saved) == 1 and (saved[0] / "provenance.db").read_bytes() == b"local work, never synced"


def test_another_students_local_copy_is_never_uploaded_under_this_key(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"ben's work")
    Sync(service.url, "ben-bpm-course-2026-aaaaaaaa", folder).push()

    outcome = Sync(service.url, KEY, folder).restore()

    assert outcome == "empty"
    assert not (folder / "provenance.db").exists()
    assert KEY not in service.stored


def test_a_wrong_key_is_reported_in_plain_words_and_does_not_raise(service, tmp_path):
    service.reject_keys = True
    sync = Sync(service.url, KEY, _history(tmp_path / "provenance"))

    assert sync.push() is False
    assert sync.status.state == "unauthorized" and "key" in sync.status.message.lower()
    assert sync.restore() == "failed"


def test_no_connection_is_not_fatal_and_the_next_push_succeeds(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync("http://127.0.0.1:9", KEY, folder, timeout=2)
    assert sync.push() is False and sync.status.state == "offline"

    sync.url = service.url
    assert sync.push() is True and sync.status.state == "saved"


def test_a_server_error_is_reported_as_offline(service, tmp_path):
    service.force_status = 503
    sync = Sync(service.url, KEY, _history(tmp_path / "provenance"))
    assert sync.push() is False and sync.status.state == "offline"


def test_two_tabs_saving_at_once_end_with_the_latest_and_say_so(service, tmp_path):
    a = _history(tmp_path / "a" / "provenance", b"a1")
    one = Sync(service.url, KEY, a)
    one.push()
    b = tmp_path / "b" / "provenance"
    two = Sync(service.url, KEY, b)
    two.restore()
    (a / "provenance.db").write_bytes(b"a2")
    one.push()
    (b / "provenance.db").write_bytes(b"b2")

    assert two.push() is True

    assert service.stored[KEY][1] != b""
    assert two.status.state == "saved" and "another" in two.status.message.lower()


def test_the_key_is_never_written_into_the_provenance_folder(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder)
    sync.push()
    sync.restore()

    for path in folder.rglob("*"):
        if path.is_file():
            assert KEY.encode() not in path.read_bytes()
    assert KEY.encode() not in service.stored[KEY][1]


def test_the_background_saver_sends_changes_after_a_pause_and_flushes_on_stop(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    settled = []
    sync = Sync(service.url, KEY, folder, settle=lambda: settled.append(1), debounce=0.3, poll=0.1)
    sync.start()
    try:
        (folder / "provenance.db").write_bytes(b"changed")
        deadline = time.time() + 5
        while service.stored.get(KEY, (0,))[0] < 1 and time.time() < deadline:
            time.sleep(0.05)
        assert service.stored[KEY][0] >= 1 and settled

        (folder / "provenance.db").write_bytes(b"changed again, right before closing")
    finally:
        sync.stop(flush=True)

    assert zipfile.ZipFile(io.BytesIO(service.stored[KEY][1])).read("provenance.db") == b"changed again, right before closing"


def test_the_zip_sent_leaves_out_what_zip_provenance_leaves_out(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    (folder / "artifacts" / "whole_log.parquet").write_bytes(b"y" * 3_000_000)

    Sync(service.url, KEY, folder).push()

    assert "artifacts/whole_log.parquet" not in _names(service.stored[KEY][1])
    assert zip_provenance(folder)[1][0][1] == 3_000_000


def test_a_folder_that_cannot_be_read_right_now_is_a_status_not_a_crash(service, tmp_path, monkeypatch):
    import provenance_widget.sync as sync_module

    def locked(folder):
        raise PermissionError("provenance.db is open in another connection")

    monkeypatch.setattr(sync_module, "zip_provenance", locked)
    sync = Sync(service.url, KEY, _history(tmp_path / "provenance"))

    assert sync.push() is False
    assert sync.status.state == "busy" and "again" in sync.status.message.lower()


def test_the_background_saver_survives_a_failed_attempt_and_saves_later(service, tmp_path, monkeypatch):
    import provenance_widget.sync as sync_module

    real = sync_module.zip_provenance
    attempts = []

    def sometimes_locked(folder):
        attempts.append(1)
        if len(attempts) <= 2:
            raise PermissionError("locked")
        return real(folder)

    monkeypatch.setattr(sync_module, "zip_provenance", sometimes_locked)
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder, debounce=0.2, poll=0.1)
    sync.start()
    try:
        deadline = time.time() + 8
        while service.stored.get(KEY, (0,))[0] < 1 and time.time() < deadline:
            time.sleep(0.1)
        assert KEY in service.stored  # a later attempt got through; the thread did not die on the first
        assert sync._thread.is_alive()
    finally:
        sync.stop(flush=False)


def test_reading_the_folder_waits_for_pmprovs_connection_lock(service, tmp_path):
    import threading

    from tracker.storage import _connect_lock

    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder)
    finished = threading.Event()

    _connect_lock.acquire()  # a pmprov connection is open: the database file must not be read now
    try:
        worker = threading.Thread(target=lambda: (sync.push(), finished.set()))
        worker.start()
        assert not finished.wait(0.5)
    finally:
        _connect_lock.release()
    assert finished.wait(5)
    worker.join()
