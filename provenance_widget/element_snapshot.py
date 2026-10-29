"""What a picked element carries into an annotation (and so into the exported report), as plain JSON.

A snapshot is {"kind": "table" | "text" | "image", ...}; `snapshot_of()` builds one from the value an element shows
and the report draws it back (see export_pdf.py). Targets without a snapshot (or with an unknown kind) fall back to
looking the output up at the recorded step.
"""
from __future__ import annotations

import base64
import io
from typing import Any

SNAPSHOT_ROWS = 20
SNAPSHOT_COLUMNS = 12
SNAPSHOT_CELL_CHARS = 60
SNAPSHOT_TEXT_CHARS = 2000
SNAPSHOT_IMAGE_MAX_BYTES = 600_000  # a snapshot travels in the page, the widget state and the annotation target
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def figure_png(obj: Any, dpi: int = 200, scale: float = 2) -> bytes | None:
    """PNG bytes for a matplotlib, Altair, Plotly or PIL figure, else None."""
    module = type(obj).__module__
    try:
        if module.startswith("matplotlib"):
            figure = obj if hasattr(obj, "savefig") else getattr(obj, "figure", None) or obj.get_figure()
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
            return buffer.getvalue()
        if module.startswith("altair"):
            import vl_convert

            return vl_convert.vegalite_to_png(obj.to_dict(), scale=scale)
        if module.startswith("plotly"):
            return obj.to_image(format="png", scale=scale)  # needs the kaleido package
        if module.startswith("PIL"):
            buffer = io.BytesIO()
            obj.save(buffer, format="PNG")
            return buffer.getvalue()
    except Exception:
        return None
    return None


def _cell(value) -> str:
    try:
        if value is None or value != value:  # None or NaN
            return ""
    except Exception:
        pass
    text = str(value)
    return text if len(text) <= SNAPSHOT_CELL_CHARS else text[: SNAPSHOT_CELL_CHARS - 1] + "…"


def table_snapshot(data) -> dict | None:
    """The head of a table as {"kind": "table", "columns", "rows", "total_rows", "total_columns"}, or None."""
    try:
        frame = data
        if not hasattr(frame, "iloc"):
            if hasattr(frame, "to_pandas"):
                frame = frame.to_pandas()
            else:
                import pandas as pd

                frame = pd.DataFrame(frame)
        # a named index (e.g. the activity of a per-activity summary) is shown by marimo as a column
        if any(name is not None for name in frame.index.names):
            frame = frame.reset_index()
        # marimo adds bookkeeping columns (such as _marimo_row_id) that its table does not show
        frame = frame.drop(columns=[c for c in frame.columns if str(c).startswith("_marimo_")])
        head = frame.iloc[:SNAPSHOT_ROWS, :SNAPSHOT_COLUMNS]
        return {
            "kind": "table",
            "columns": [str(c) for c in head.columns],
            "rows": [[_cell(v) for v in row] for row in head.itertuples(index=False, name=None)],
            "total_rows": int(len(frame)),
            "total_columns": int(frame.shape[1]),
        }
    except Exception:
        return None


def text_snapshot(value: Any) -> dict | None:
    try:
        text = value if isinstance(value, str) else repr(value)
    except Exception:
        return None
    if len(text) > SNAPSHOT_TEXT_CHARS:
        text = text[: SNAPSHOT_TEXT_CHARS - 1] + "…"
    return {"kind": "text", "text": text}


def image_snapshot(png: bytes | None) -> dict | None:
    if not png or len(png) > SNAPSHOT_IMAGE_MAX_BYTES:
        return None
    return {"kind": "image", "png": base64.b64encode(png).decode("ascii")}


def snapshot_of(value: Any) -> dict | None:
    """A snapshot of whatever an element shows: a table, a figure / image, or plain text. None if unsupported."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return image_snapshot(bytes(value)) if bytes(value[:8]) == _PNG_MAGIC else None
    if isinstance(value, (str, int, float, bool, dict, list, tuple)):
        return text_snapshot(value)
    if hasattr(value, "columns") and hasattr(value, "shape") and len(value.shape) == 2:
        return table_snapshot(value)
    # reduced resolution: the picture has to travel with the annotation
    return image_snapshot(figure_png(value, dpi=110, scale=1.5))
