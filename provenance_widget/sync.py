"""Keep a provenance folder safe on a server (provenance-sync), so it outlives the notebook's own files.

A hosted notebook can lose its files when its kernel restarts, it is forked or it sits idle. `Sync` stores the same small zip
that `portable.zip_provenance` makes under the student's key, restores it when a notebook opens with nothing (or something
older), and saves new work in the background. It never raises into the notebook: whatever goes wrong becomes `status`, in
words a student can act on.

The key is held in memory only. It is not written into the provenance folder (which travels in the zip) or the notebook.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .portable import unpack_provenance, zip_provenance


@dataclass
class SyncStatus:
    state: str = "idle"  # idle | saved | pending | offline | unauthorized | too-large | closed | busy | conflict | removed
    message: str = "Not saved to the course server yet."
    revision: int = 0
    saved_at: str | None = None


_MESSAGES = {
    "busy": "Your work could not be read to save it just now. It will be tried again in a moment.",
    "saved": "Your work is saved on the course server.",
    "pending": "Saving your latest changes… please wait a moment before closing this page.",
    "offline": "The course server could not be reached. Your work is kept in this notebook and will be saved when it is back.",
    "unauthorized": "The key was not accepted. Check that you pasted it completely, or ask your instructor.",
    "too-large": "Your work is too large for the course server. Tell your instructor.",
    "conflict": "The course server already has work saved with your key, and it could not be loaded when this notebook opened. "
    "Reload this page to load it. What you did since opening this page is kept in a separate folder on this computer.",
    "removed": "Your saved work was removed from the course server. This notebook starts empty; "
    "the earlier copy on this computer was set aside.",
    "removed-in-use": "Your saved work was removed from the course server. Reload this page to start empty; "
    "the earlier copy on this computer will be set aside.",
    "closed": "This course is closed, so your work is no longer saved. What you saved before is kept.",
}


@contextlib.contextmanager
def _storage_quiet(timeout: float = 30.0):
    """Hold pmprov's connection lock while the provenance folder is read.

    pmprov keeps that lock for as long as a DuckDB connection is open, so while it is held nothing has `provenance.db` open.
    That matters on Windows, where an open DuckDB file cannot be read, and gives a consistent copy everywhere. Without pmprov
    there is nothing to wait for.
    """
    try:
        from tracker.storage import _connect_lock
    except Exception:
        yield
        return
    acquired = _connect_lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        if acquired:
            _connect_lock.release()


# The saver running for each folder, so that a notebook cell that runs again does not leave two of them saving the same work.
_running: dict[str, "Sync"] = {}
_running_lock = threading.Lock()


def _as_revision(value) -> int:
    try:
        return max(int(str(value).strip().strip('"')), 0)
    except (TypeError, ValueError):
        return 0


def _revision_in(body: bytes) -> int:
    try:
        return _as_revision(json.loads(body or b"{}").get("revision"))
    except (ValueError, AttributeError):
        return 0


class _Failure(Exception):
    def __init__(self, state: str) -> None:
        self.state = state


class Sync:
    def __init__(
        self,
        url: str,
        key: str,
        folder,
        *,
        settle=None,
        debounce: float = 2.0,
        poll: float = 1.0,
        timeout: float = 20.0,
    ) -> None:
        self.url = url.rstrip("/")
        self._key = key.strip()
        self.folder = Path(folder)
        self.settle = settle
        self.debounce, self.poll, self.timeout = debounce, poll, timeout
        self.status = SyncStatus()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._removed = False  # the server's copy was removed and this folder could not be moved yet: nothing is sent
        self._conflict = False  # the server has work this folder was not built on: nothing is sent until a restore settles it

    # --- what this folder was last known to match -----------------------------------------------------------------
    @property
    def _state_path(self) -> Path:
        return self.folder.with_name(self.folder.name + ".sync.json")

    @property
    def _key_hash(self) -> str:
        return hashlib.sha256(self._key.encode()).hexdigest()

    def _read_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self, revision: int, sha256: str, removed: int | None = None) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"key_hash": self._key_hash, "revision": revision, "sha256": sha256}
        if removed is not None:
            record["removed"] = removed  # this folder was built on work the server removed; the next restore sets it aside
        self._state_path.write_text(json.dumps(record), encoding="utf-8")

    def _local_zip(self) -> tuple[bytes, str]:
        with _storage_quiet():
            data, _ = zip_provenance(self.folder)
        return data, hashlib.sha256(data).hexdigest()

    def _has_history(self) -> bool:
        return (self.folder / "provenance.db").exists()

    # --- talking to the server ---------------------------------------------------------------------------------------
    def _request(self, method: str, body: bytes | None = None, if_match: int | None = None):
        headers = {"Authorization": f"Bearer {self._key}"}
        if body is not None:
            headers["Content-Type"] = "application/zip"
        if if_match is not None:
            headers["If-Match"] = f'"{if_match}"'
        request = urllib.request.Request(self.url + "/v1/provenance", data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as problem:
            return problem.code, problem.read(), problem.headers
        except (urllib.error.URLError, OSError, TimeoutError):
            raise _Failure("offline")

    def _fail(self, state: str) -> None:
        self.status = SyncStatus(state, _MESSAGES[state], self.status.revision, self.status.saved_at)

    def _refused(self, code: int) -> _Failure:
        if code in (401, 403, 429):
            return _Failure("unauthorized")
        if code == 413:
            return _Failure("too-large")
        if code == 423:
            return _Failure("closed")  # the course's closing time has passed: saving is over, and retrying would not help
        return _Failure("offline")

    # --- opening a notebook --------------------------------------------------------------------------------------------
    def restore(self) -> str:
        """Bring the student's stored work into the folder if the folder has none, or only an older copy.

        Returns "restored", "kept-local" (the folder is the newer copy), "empty" (nothing stored for this student) or
        "failed" (see `status`). Run it before anything opens the provenance database.
        """
        with self._lock:
            self._conflict = False
            self._removed = False
            marked = self._marked_removed()
            if marked is None:
                return "failed"
            outcome = self._restore_from_server()
            if marked and outcome == "empty":
                self.status = SyncStatus("removed", _MESSAGES["removed"], self.status.revision, self.status.saved_at)
            return outcome

    def _marked_removed(self) -> bool | None:
        """Set aside a folder that an earlier push found removed but could not move. None when it still cannot be moved."""
        state = self._read_state()
        if state.get("removed") is None or state.get("key_hash") != self._key_hash or not self._has_history():
            return False
        try:
            self._put_aside("removed")
        except OSError:
            self._fail("busy")
            return None
        return True

    def _restore_from_server(self) -> str:
        try:
            code, data, headers = self._request("GET")
        except _Failure as problem:
            self._fail(problem.state)
            return "failed"
        if code == 404 and headers.get("X-Provenance-Removed") is not None:
            return self._after_removal(_as_revision(headers.get("X-Provenance-Removed")))
        if code == 404:
            return self._without_remote()
        if code != 200:
            self._fail(self._refused(code).state)
            return "failed"
        remote = int(str(headers.get("ETag", '"0"')).strip('"') or 0)
        state = self._read_state()
        same_owner = state.get("key_hash") == self._key_hash

        if self._has_history() and same_owner:
            _, local_hash = self._local_zip()
            if state.get("revision") == remote or local_hash != state.get("sha256"):
                self._remember(remote, state.get("sha256", ""))
                return "kept-local"  # this folder is the latest copy, or has work the server has not seen
        if self._has_history():
            self._put_aside("unsynced" if not state else "foreign")
        self._install(data, remote)
        return "restored"

    def _after_removal(self, mark: int) -> str:
        """The server's copy was removed (revision `mark`): work saved before that is set aside, work begun after it is kept."""
        state = self._read_state()
        if self._has_history():
            built_after = state.get("key_hash") == self._key_hash and state.get("revision", 0) >= mark
            if built_after:
                self._write_state(mark, state.get("sha256", ""))
                self.status = SyncStatus("idle", self.status.message, mark, self.status.saved_at)
                return "kept-local"
            self._set_aside_for_removal(mark)
            return "empty"
        self._write_state(mark, "")  # nothing here to set aside; the next save builds on the mark
        self.status = SyncStatus("idle", self.status.message, mark, self.status.saved_at)
        return "empty"

    def _set_aside_for_removal(self, mark: int) -> None:
        """Move the folder aside. If it is in use and cannot be moved, mark it for the next restore instead of raising."""
        try:
            self._put_aside("removed")
        except OSError:
            self._removed = True
            self._write_state(mark, "", removed=mark)
            self.status = SyncStatus("removed", _MESSAGES["removed-in-use"], mark, self.status.saved_at)
            return
        self._write_state(mark, "")
        self.status = SyncStatus("removed", _MESSAGES["removed"], mark, self.status.saved_at)

    def _without_remote(self) -> str:
        """The server has nothing for this key."""
        state = self._read_state()
        if self._has_history() and state and state.get("key_hash") != self._key_hash:
            self._put_aside("foreign")  # someone else's history: never upload it under this key
            return "empty"
        self._remember(0, "")
        return "kept-local" if self._has_history() else "empty"

    def _remember(self, revision: int, sha256: str) -> None:
        self._write_state(revision, sha256)
        self.status = SyncStatus("saved" if revision else "idle", self.status.message, revision, self.status.saved_at)
        if revision:
            self.status.message = _MESSAGES["saved"]

    def _put_aside(self, why: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        shutil.move(str(self.folder), str(self.folder.with_name(f"{self.folder.name}.{why}-{stamp}")))
        self._state_path.unlink(missing_ok=True)

    def _install(self, data: bytes, revision: int) -> None:
        if self.folder.exists():
            shutil.rmtree(self.folder)
        unpack_provenance(data, self.folder)
        _, local_hash = self._local_zip()
        self._remember(revision, local_hash)

    # --- saving ---------------------------------------------------------------------------------------------------------
    def push(self) -> bool:
        """Send the folder if it changed since the last save. True when something was stored."""
        with self._lock:
            if not self._has_history() or self._conflict or self._removed:
                return False
            state = self._read_state()
            try:
                data, local_hash = self._local_zip()
            except OSError:
                self._fail("busy")  # the files could not be read this time; the next attempt usually can
                return False
            owned = state.get("key_hash") == self._key_hash
            if owned and state.get("sha256") == local_hash:
                return False
            # Without a record of what the server holds (it could not be reached when the notebook opened), 0 says "only if
            # nothing is stored yet": saved work is never replaced by a folder that was not built on it.
            known = state.get("revision") if owned else None
            note = ""
            try:
                code, body, _ = self._request("PUT", data, if_match=0 if known is None else known)
                if code == 410:
                    # the server's copy was removed after this folder was built: set it aside instead of resending it
                    mark = _revision_in(body)
                    self._set_aside_for_removal(mark)
                    return False
                if code == 409 and known is None:
                    self._conflict = True
                    self._fail("conflict")
                    return False
                if code == 409:
                    # another tab or device saved in between: the latest save wins, and the student is told
                    current = json.loads(body or b"{}").get("revision")
                    code, body, _ = self._request("PUT", data, if_match=current)
                    note = " A copy saved from another tab or device was replaced."
                if code != 200:
                    raise self._refused(code)
            except _Failure as problem:
                self._fail(problem.state)
                return False
            revision = int(json.loads(body)["revision"])
            self._write_state(revision, local_hash)
            self.status = SyncStatus(
                "saved", _MESSAGES["saved"] + note, revision, datetime.now(timezone.utc).isoformat(timespec="seconds")
            )
            return True

    # --- saving by itself ----------------------------------------------------------------------------------------------
    def _fingerprint(self) -> tuple:
        return tuple(
            sorted((str(p.relative_to(self.folder)), p.stat().st_size, p.stat().st_mtime_ns) for p in self.folder.rglob("*") if p.is_file())
        ) if self.folder.exists() else ()

    def _mark_pending(self) -> None:
        """The folder changed and the change is not on the server yet: say so, so nobody closes the page too early."""
        if self.status.state in ("idle", "saved"):
            self.status = SyncStatus("pending", _MESSAGES["pending"], self.status.revision, self.status.saved_at)

    def _clear_pending(self) -> None:
        """The change turned out not to need saving (the contents are what the server has)."""
        if self.status.state == "pending":
            saved = self.status.revision > 0
            self.status = SyncStatus(
                "saved" if saved else "idle",
                _MESSAGES["saved"] if saved else SyncStatus.message,
                self.status.revision,
                self.status.saved_at,
            )

    def _settle(self) -> None:
        if self.settle is not None:
            try:
                self.settle()
            except Exception:
                pass

    def start(self) -> None:
        """Save changes in the background, a few seconds after the last one."""
        if self._thread is not None and self._thread.is_alive():
            return
        with _running_lock:
            earlier = _running.get(str(self.folder.resolve()))
            _running[str(self.folder.resolve())] = self
        if earlier is not None and earlier is not self:
            earlier._stop.set()  # it ends at its next pass; this one saves whatever it had not
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pmprov-sync", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        seen, changed_at, pending = None, time.monotonic(), True  # whatever is there at the start is saved once
        while not self._stop.wait(self.poll):
            try:
                current = self._fingerprint()
                if current != seen:
                    seen, changed_at, pending = current, time.monotonic(), True
                    self._mark_pending()
                elif pending and time.monotonic() - changed_at >= self.debounce:
                    self._settle()
                    pushed = self.push()
                    self._clear_pending()
                    pending = not pushed and self.status.state in ("busy", "offline")  # try again if it could not
                    seen = self._fingerprint()
                    changed_at = time.monotonic()
            except Exception:
                # the saver must outlive any one failed attempt; the next pass tries again
                changed_at = time.monotonic()

    def stop(self, flush: bool = True) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.timeout + 5)
        if flush:
            self._settle()
            self.push()
