import zipfile
import io

import pytest

from provenance_widget.portable import relocate_artifacts, unpack_provenance, zip_provenance


def _folder(tmp_path, sizes):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "provenance.db").write_bytes(b"db")
    (tmp_path / "picked_elements.json").write_text("{}")
    for name, size in sizes.items():
        (tmp_path / "artifacts" / name).write_bytes(b"x" * size)
    return tmp_path


def _names(data):
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def test_small_values_and_the_history_always_go_in(tmp_path):
    data, left_out = zip_provenance(_folder(tmp_path, {"a.plotly.json": 100, "b.parquet": 200}))

    assert _names(data) == {"provenance.db", "picked_elements.json", "artifacts/a.plotly.json", "artifacts/b.parquet"}
    assert left_out == []


def test_a_value_over_the_limit_is_left_out_and_reported(tmp_path):
    data, left_out = zip_provenance(_folder(tmp_path, {"small.parquet": 100, "whole_log.parquet": 5000}), max_artifact_bytes=1000)

    assert "artifacts/whole_log.parquet" not in _names(data)
    assert "artifacts/small.parquet" in _names(data)
    assert left_out == [("whole_log.parquet", 5000)]


def test_the_largest_values_go_when_the_total_is_still_too_big(tmp_path):
    folder = _folder(tmp_path, {"a": 400, "b": 300, "c": 200})

    data, left_out = zip_provenance(folder, max_artifact_bytes=1000, max_total_bytes=550)

    assert _names(data) - {"provenance.db", "picked_elements.json"} == {"artifacts/b", "artifacts/c"} or \
        _names(data) - {"provenance.db", "picked_elements.json"} == {"artifacts/c"}
    assert left_out[0] == ("a", 400)


def test_a_folder_without_artifacts_still_zips(tmp_path):
    (tmp_path / "provenance.db").write_bytes(b"db")

    data, left_out = zip_provenance(tmp_path)

    assert _names(data) == {"provenance.db"} and left_out == []


def test_unpacking_refuses_a_member_outside_the_target(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", "no")

    with pytest.raises(ValueError):
        unpack_provenance(buffer.getvalue(), tmp_path / "target")

    assert not (tmp_path / "escape.txt").exists()


def test_a_zip_unpacks_back_to_the_same_files(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    data, _ = zip_provenance(_folder(source, {"a": 10}))

    unpack_provenance(data, tmp_path / "out")

    assert (tmp_path / "out" / "artifacts" / "a").read_bytes() == b"x" * 10


def test_relocating_without_a_database_changes_nothing(tmp_path):
    assert relocate_artifacts(tmp_path / "missing.db", tmp_path) == 0


def _database(path, refs):
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE artifact_states (artifact_state_id VARCHAR, artifact_id VARCHAR, content_ref VARCHAR)")
    con.execute("CREATE TABLE artifacts (artifact_id VARCHAR, name VARCHAR)")
    for number, (name, ref) in enumerate(refs.items()):
        con.execute("INSERT INTO artifact_states VALUES (?, ?, ?)", [f"s{number}", f"a{number}", ref])
        con.execute("INSERT INTO artifacts VALUES (?, ?)", [f"a{number}", name])
    con.close()


def test_relocating_points_paths_from_any_system_at_the_folder_next_to_the_database(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    _database(tmp_path / "provenance.db", {"x": "/marimo/provenance/artifacts/one.parquet", "y": r"C:\old\artifacts\two.pkl"})

    changed = relocate_artifacts(tmp_path / "provenance.db", tmp_path / "artifacts")

    con = duckdb.connect(str(tmp_path / "provenance.db"), read_only=True)
    refs = sorted(r[0] for r in con.execute("SELECT content_ref FROM artifact_states").fetchall())
    assert changed == 2
    assert refs == sorted([str(tmp_path / "artifacts" / "one.parquet"), str(tmp_path / "artifacts" / "two.pkl")])


def test_left_out_values_are_named_by_their_variable(tmp_path):
    folder = _folder(tmp_path, {"big.parquet": 5000})
    (folder / "provenance.db").unlink()
    _database(folder / "provenance.db", {"event_log": "/x/artifacts/big.parquet"})

    _, left_out = zip_provenance(folder, max_artifact_bytes=1000)

    assert left_out == [("event_log", 5000)]


def test_a_copy_of_the_whole_log_is_left_out_by_default_and_maps_and_tables_stay(tmp_path):
    folder = _folder(tmp_path, {"map.plotly.json": 20_000, "table.parquet": 4_000, "log_copy.parquet": 1_050_000})

    data, left_out = zip_provenance(folder)

    assert "artifacts/map.plotly.json" in _names(data) and "artifacts/table.parquet" in _names(data)
    assert "artifacts/log_copy.parquet" not in _names(data)
    assert left_out == [("log_copy.parquet", 1_050_000)]


def test_the_same_contents_make_the_same_zip_even_when_the_files_are_touched(tmp_path):
    import os

    folder = _folder(tmp_path, {"map.plotly.json": 100})
    first, _ = zip_provenance(folder)

    for path in folder.rglob("*"):
        if path.is_file():
            os.utime(path, (1_900_000_000, 1_900_000_000))

    assert zip_provenance(folder)[0] == first
