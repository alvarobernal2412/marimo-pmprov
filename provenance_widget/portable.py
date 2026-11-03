"""Moving a stored history between machines: zip it small, unzip it safely, point its artifacts at the new folder.

A history is a folder with `provenance.db` and an `artifacts/` folder (see guides/portable-provenance.md). The helpers
here do not need pmprov; the one that reads the database (`relocate_artifacts`) and the names in `zip_provenance`
use duckdb when it is installed.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

DEFAULT_MAX_ARTIFACT_BYTES = 500_000
DEFAULT_MAX_TOTAL_BYTES = 25_000_000


def _artifact_names(db_path: Path) -> dict[str, str]:
    """Artifact file name -> name of the variable it holds, as far as the database says (empty if unreadable)."""
    try:
        import duckdb

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT s.content_ref, a.name FROM artifact_states s JOIN artifacts a ON a.artifact_id = s.artifact_id"
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return {}
    return {re.split(r"[\\/]", ref)[-1]: name for ref, name in rows}


def zip_provenance(
    folder,
    max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> tuple[bytes, list[tuple[str, int]]]:
    """Zip a provenance folder, leaving out the stored values that are too big to carry around.

    The steps, the notes and the small values (tables, figures, text) always go in. A stored value larger than
    `max_artifact_bytes`, typically a whole event log or a copy of it a step produced, is left out, and so are the
    largest remaining ones if the artifacts still add up to more than `max_total_bytes`. A step whose value was left
    out still shows in the history; only its value cannot be restored there.

    Returns the zip file's bytes and the values left out as (name, size in bytes), biggest first. Let pending writes
    land before calling this, or the zip misses them.
    """
    folder = Path(folder)
    artifacts = folder / "artifacts"
    files = sorted(p for p in artifacts.glob("*") if p.is_file()) if artifacts.is_dir() else []
    keep = [p for p in files if p.stat().st_size <= max_artifact_bytes]
    keep.sort(key=lambda p: p.stat().st_size)
    while keep and sum(p.stat().st_size for p in keep) > max_total_bytes:
        keep.pop()  # the largest first
    names = _artifact_names(folder / "provenance.db")
    left_out = sorted(
        ((names.get(p.name, p.name), p.stat().st_size) for p in set(files) - set(keep)), key=lambda item: -item[1]
    )
    members = [p for p in folder.rglob("*") if p.is_file() and (artifacts not in p.parents or p in keep)]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(members):
            archive.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue(), left_out


def unpack_provenance(zip_bytes: bytes, target) -> None:
    """Unzip a provenance zip into `target`, refusing any member that would land outside it."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for member in archive.infolist():
            destination = (root / member.filename).resolve()
            if destination != root and root not in destination.parents:
                raise ValueError(f"unsafe path in the zip file: {member.filename}")
        archive.extractall(root)


def relocate_artifacts(db_path, artifact_dir) -> int:
    """Point the stored artifacts at `artifact_dir`, by file name. Returns how many paths were changed.

    pmprov stores the absolute path of every artifact file, so a folder that was copied or downloaded still points
    at the machine it was recorded on. Run it before pmprov opens the database.
    """
    if not Path(db_path).exists():
        return 0
    import duckdb

    try:
        con = duckdb.connect(str(db_path))
        try:
            changed = 0
            for artifact_state_id, ref in con.execute("SELECT artifact_state_id, content_ref FROM artifact_states").fetchall():
                new = str(Path(artifact_dir) / re.split(r"[\\/]", ref)[-1])
                if new != ref:
                    con.execute("UPDATE artifact_states SET content_ref = ? WHERE artifact_state_id = ?", [new, artifact_state_id])
                    changed += 1
            return changed
        finally:
            con.close()
    except Exception:
        return 0  # no history stored yet
