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
        self.removed = {}  # key -> revision of the removal mark
        self.puts = 0
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
                if found is None and self._key() in owner.removed:
                    mark = owner.removed[self._key()]
                    body = json.dumps({"detail": "removed", "removed": True, "revision": mark}).encode()
                    return self._send(404, body, {"X-Provenance-Removed": str(mark), "Content-Type": "application/json"})
                if found is None:
                    return self._send(404)
                self._send(200, found[1], {"ETag": f'"{found[0]}"'})

            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.puts += 1
                if owner.force_status:
                    return self._send(owner.force_status)
                if owner.reject_keys or not self._key():
                    return self._send(401)
                mark = owner.removed.get(self._key())
                revision = owner.stored[self._key()][0] if self._key() in owner.stored else (mark or 0)
                match = self.headers.get("If-Match", "").strip('"')
                if mark is not None and self._key() not in owner.stored and not (match.isdigit() and int(match) >= mark):
                    body = json.dumps({"detail": "this work was removed", "removed": True, "revision": mark, "removed_at": "2026-11-23T10:00:00+00:00"}).encode()
                    return self._send(410, body, {"Content-Type": "application/json"})
                if match.isdigit() and int(match) != revision:
                    return self._send(409, json.dumps({"revision": revision}).encode(), {"Content-Type": "application/json"})
                owner.stored[self._key()] = (revision + 1, body)
                self._send(200, json.dumps({"revision": revision + 1}).encode(), {"Content-Type": "application/json"})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def remove(self, key):
        """The instructor removes a student's work: the counter continues, and the mark is the next revision."""
        current = self.stored[key][0] if key in self.stored else self.removed.get(key, 0)
        self.removed[key] = current + 1
        self.stored.pop(key, None)

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


def test_a_closed_course_is_a_status_and_the_saver_does_not_keep_trying(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder, debounce=0.2, poll=0.1)
    service.force_status = 423  # what the server answers once the course has closed

    assert sync.push() is False
    assert sync.status.state == "closed" and "closed" in sync.status.message.lower() and "kept" in sync.status.message.lower()

    service.force_status = None
    sync.start()
    try:
        (folder / "provenance.db").write_bytes(b"changed")
        time.sleep(1.0)
        assert sync._thread.is_alive()  # the saver is still running; it just has nothing it can do
    finally:
        sync.stop(flush=False)


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

    pytest.importorskip("tracker", reason="pmprov not installed")
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


def _wait_for(condition, seconds=6):
    deadline = time.time() + seconds
    while not condition() and time.time() < deadline:
        time.sleep(0.02)
    return condition()


def test_a_change_waiting_to_be_saved_says_so_until_it_is_saved(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder, debounce=1.0, poll=0.1)
    sync.start()
    try:
        assert _wait_for(lambda: sync.status.state == "saved")  # what was there at the start is saved once
        (folder / "provenance.db").write_bytes(b"a new note")
        assert _wait_for(lambda: sync.status.state == "pending", seconds=3)
        assert "wait" in sync.status.message.lower()
        assert _wait_for(lambda: sync.status.state == "saved" and sync.status.revision >= 2)
    finally:
        sync.stop(flush=False)


def test_a_change_that_leaves_the_contents_as_they_were_does_not_stay_pending(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder, debounce=0.3, poll=0.1)
    sync.start()
    try:
        assert _wait_for(lambda: sync.status.state == "saved")
        revision = sync.status.revision
        (folder / "provenance.db").write_bytes((folder / "provenance.db").read_bytes())  # touched, not changed
        time.sleep(1.0)
        assert sync.status.state == "saved" and sync.status.revision == revision
    finally:
        sync.stop(flush=False)


def test_a_note_is_on_the_server_within_a_few_seconds_by_default(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync(service.url, KEY, folder)

    assert sync.debounce <= 2.0 and sync.poll <= 1.0


def _wait_for(condition, seconds=8):
    deadline = time.time() + seconds
    while not condition() and time.time() < deadline:
        time.sleep(0.05)
    return condition()


def test_work_done_while_offline_is_sent_by_itself_when_the_connection_is_back(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    sync = Sync("http://127.0.0.1:9", KEY, folder, debounce=0.2, poll=0.1, timeout=1)  # nobody is listening there
    sync.start()
    try:
        (folder / "provenance.db").write_bytes(b"first annotation, offline")
        assert _wait_for(lambda: sync.status.state == "offline")
        (folder / "provenance.db").write_bytes(b"second annotation, still offline")
        time.sleep(1.5)
        assert service.stored == {} and sync.status.state == "offline"  # nothing reached the server, nothing was dropped

        sync.url = service.url  # the connection is back; nobody touches the notebook
        assert _wait_for(lambda: KEY in service.stored)
    finally:
        sync.stop(flush=False)

    assert zipfile.ZipFile(io.BytesIO(service.stored[KEY][1])).read("provenance.db") == b"second annotation, still offline"
    assert sync.status.state == "saved"


def test_a_notebook_opened_offline_keeps_its_work_and_sends_it_later(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"work done before the connection dropped")
    sync = Sync("http://127.0.0.1:9", KEY, folder, timeout=1)

    assert sync.restore() == "failed" and sync.status.state == "offline"
    assert (folder / "provenance.db").read_bytes() == b"work done before the connection dropped"  # not replaced by anything

    sync.url = service.url
    assert sync.push() is True
    assert zipfile.ZipFile(io.BytesIO(service.stored[KEY][1])).read("provenance.db") == b"work done before the connection dropped"


def test_a_notebook_opened_offline_with_no_copy_never_replaces_what_the_server_has(service, tmp_path):
    earlier = Sync(service.url, KEY, _history(tmp_path / "other computer" / "provenance", b"weeks of work"))
    assert earlier.push() is True
    folder = tmp_path / "provenance"
    sync = Sync("http://127.0.0.1:9", KEY, folder, timeout=1)
    assert sync.restore() == "failed"  # the server could not be reached, and this computer has no copy
    _history(folder, b"started again from nothing")

    sync.url = service.url  # the connection is back
    assert sync.push() is False

    assert zipfile.ZipFile(io.BytesIO(service.stored[KEY][1])).read("provenance.db") == b"weeks of work"
    assert sync.status.state == "conflict" and "reload" in sync.status.message.lower()


def test_after_such_a_conflict_nothing_more_is_sent_and_a_reload_brings_the_saved_work_back(service, tmp_path):
    Sync(service.url, KEY, _history(tmp_path / "other computer" / "provenance", b"weeks of work")).push()
    folder = _history(tmp_path / "provenance", b"started again from nothing")
    sync = Sync(service.url, KEY, folder)
    assert sync.push() is False and sync.status.state == "conflict"
    service.force_status = 500  # any further request would now show as "offline"
    (folder / "provenance.db").write_bytes(b"more offline work")
    assert sync.push() is False and sync.status.state == "conflict"
    service.force_status = None

    assert Sync(service.url, KEY, folder).restore() == "restored"  # what a reload of the notebook does

    assert (folder / "provenance.db").read_bytes() == b"weeks of work"
    aside = [p for p in tmp_path.iterdir() if p.name.startswith("provenance.unsynced-")]
    assert len(aside) == 1 and (aside[0] / "provenance.db").read_bytes() == b"more offline work"


def test_starting_a_saver_stops_the_one_started_earlier_for_the_same_folder(service, tmp_path):
    folder = _history(tmp_path / "provenance")
    first = Sync(service.url, KEY, folder, debounce=0.2, poll=0.1)
    second = Sync(service.url, KEY, folder, debounce=0.2, poll=0.1)
    first.start()
    try:
        second.start()  # the notebook's cell ran again
        assert _wait_for(lambda: not first._thread.is_alive())
        (folder / "provenance.db").write_bytes(b"a change")
        assert _wait_for(lambda: KEY in service.stored and service.stored[KEY][0] >= 1)
        time.sleep(1)
        saved_once = service.stored[KEY][0]
        (folder / "provenance.db").write_bytes(b"another change")
        assert _wait_for(lambda: service.stored[KEY][0] > saved_once)
        time.sleep(1)
        assert service.stored[KEY][0] == saved_once + 1  # one saver, so one save for one change
    finally:
        first.stop(flush=False)
        second.stop(flush=False)


def _after_a_removal(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"old work")
    Sync(service.url, KEY, folder).push()
    service.remove(KEY)
    sync = Sync(service.url, KEY, folder)
    return folder, sync, sync.restore()


def test_a_removed_history_is_set_aside_and_the_notebook_starts_empty(service, tmp_path):
    folder, sync, outcome = _after_a_removal(service, tmp_path)

    assert outcome == "empty"
    assert not (folder / "provenance.db").exists()
    aside = list(tmp_path.glob("provenance.removed-*"))
    assert len(aside) == 1 and (aside[0] / "provenance.db").read_bytes() == b"old work"
    assert sync.status.state == "removed"
    assert sync.status.message == (
        "Your saved work was removed from the course server. This notebook starts empty; "
        "the earlier copy on this computer was set aside."
    )


def test_after_a_removal_the_first_save_builds_on_the_mark(service, tmp_path):
    folder, sync, _ = _after_a_removal(service, tmp_path)
    _history(folder, b"fresh work")

    assert sync.push() is True
    assert service.stored[KEY][0] == 3
    assert sync.status.state == "saved"


def test_a_stale_save_that_meets_a_removal_is_set_aside_not_retried(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"old work")
    sync = Sync(service.url, KEY, folder)
    sync.push()
    service.remove(KEY)
    (folder / "provenance.db").write_bytes(b"changed after the removal")
    puts = service.puts

    assert sync.push() is False
    assert service.puts == puts + 1
    assert sync.status.state == "removed"
    assert not (folder / "provenance.db").exists()
    assert len(list(tmp_path.glob("provenance.removed-*"))) == 1


def test_work_started_after_the_removal_is_kept(service, tmp_path):
    folder, _, _ = _after_a_removal(service, tmp_path)
    _history(folder, b"fresh work")

    again = Sync(service.url, KEY, folder)
    assert again.restore() == "kept-local"
    assert (folder / "provenance.db").read_bytes() == b"fresh work"
    assert again.push() is True
    assert service.stored[KEY][0] == 3


def _unmovable(monkeypatch):
    def refuse(*args, **kwargs):
        raise PermissionError("in use")

    monkeypatch.setattr("provenance_widget.sync.shutil.move", refuse)


def test_a_removal_met_while_the_folder_is_in_use_is_reported_not_raised(service, tmp_path, monkeypatch):
    folder = _history(tmp_path / "provenance", b"old work")
    sync = Sync(service.url, KEY, folder)
    sync.push()
    service.remove(KEY)
    (folder / "provenance.db").write_bytes(b"changed after the removal")
    _unmovable(monkeypatch)

    assert sync.push() is False
    assert sync.status.state == "removed"
    assert sync.status.message == (
        "Your saved work was removed from the course server. Reload this page to start empty; "
        "the earlier copy on this computer will be set aside."
    )
    assert (folder / "provenance.db").exists()
    puts = service.puts
    assert sync.push() is False
    assert service.puts == puts


def test_the_next_restore_sets_the_marked_folder_aside(service, tmp_path, monkeypatch):
    folder = _history(tmp_path / "provenance", b"old work")
    sync = Sync(service.url, KEY, folder)
    sync.push()
    service.remove(KEY)
    (folder / "provenance.db").write_bytes(b"changed after the removal")
    with monkeypatch.context() as patch:
        _unmovable(patch)
        sync.push()

    again = Sync(service.url, KEY, folder)
    assert again.restore() == "empty"
    assert not (folder / "provenance.db").exists()
    aside = list(tmp_path.glob("provenance.removed-*"))
    assert len(aside) == 1 and (aside[0] / "provenance.db").read_bytes() == b"changed after the removal"
    _history(folder, b"fresh work")
    assert again.push() is True
    assert service.stored[KEY][0] == 3


def test_a_malformed_removed_header_does_not_raise(service, tmp_path):
    folder = _history(tmp_path / "provenance", b"old work")
    service.removed[KEY] = "not-a-number"

    outcome = Sync(service.url, KEY, folder).restore()

    assert outcome in ("empty", "kept-local")
