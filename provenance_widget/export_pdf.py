"""Annotated-analysis report: the annotation history as an academic-style PDF.

`collect_rows()` merges the annotations the sidebar shows (committed ones and
those on tree nodes, minus removed, with edits applied) in time order, and
`build_pdf()` lays them out with reportlab (the optional ``pdf`` extra). The
artifact an annotation targets is drawn the way the analysis shows it: a table
for a DataFrame, an image for a matplotlib / Altair / Plotly figure.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from xml.sax.saxutils import escape

from .element_snapshot import figure_png

_FONT_DIR = Path(__file__).parent / "fonts"
_FONT = "PWSans"
_INK, _MUTED, _RULE, _ACCENT, _CHIP = "#1F2937", "#6B7280", "#E5E7EB", "#0369A1", "#E0F2FE"
_MAX_TABLE_ROWS = 10
_MAX_TABLE_COLUMNS = 7
_MAX_CELL_CHARS = 28
_MAX_TEXT_LINES = 40


class PdfUnavailable(RuntimeError):
    """reportlab is not installed."""


@dataclass
class Row:
    state_id: str
    annotation: dict
    step: int | None = None
    operation: str | None = None
    params: dict = field(default_factory=dict)
    own_params: dict = field(default_factory=dict)  # what this step itself was called with


def _time_of(timestamp: str) -> float:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def collect_rows(
    tree: dict,
    commits: list[dict],
    removed: list[str],
    edited: dict[str, dict],
    aliases: dict[str, str],
) -> list[Row]:
    """Every visible annotation, oldest first, with the step it belongs to.

    Mirrors the sidebar's list (`collectAnnotations` in the frontend): a
    committed annotation also comes back stored on its tree node, and only the
    commit's version is kept.
    """
    nodes = tree.get("nodes") or {}
    hidden = set(removed)
    stored_copies = set(aliases.values())
    seen: set[str] = set()
    entries: list[tuple[str, dict]] = []

    def add(state_id: str, annotation: dict) -> None:
        annotation_id = annotation.get("annotationId")
        if annotation_id in hidden or annotation_id in seen:
            return
        seen.add(annotation_id)
        entries.append((state_id, {**annotation, **edited.get(annotation_id, {})}))

    for commit in commits:
        add(commit.get("stateId"), commit.get("annotation") or {})
    for node in nodes.values():
        for annotation in node.get("annotations") or []:
            if annotation.get("annotationId") not in stored_copies:
                add(node["stateId"], annotation)

    entries.sort(key=lambda entry: _time_of(entry[1].get("timestamp", "")))
    return [_row(state_id, annotation, nodes) for state_id, annotation in entries]


def _row(state_id: str, annotation: dict, nodes: dict) -> Row:
    path: list[dict] = []
    current = state_id
    while current in nodes:
        path.append(nodes[current])
        current = nodes[current].get("parentStateId")
    # settings in force at this state: the latest value of each parameter on the
    # path, leaving out the first step's (how the data was loaded, not a setting)
    params: dict = {}
    for node in reversed(path[:-1] if len(path) > 1 else path):
        params.update(node.get("params") or {})
    node = nodes.get(state_id)
    return Row(
        state_id=state_id,
        annotation=annotation,
        step=len(path) or None,
        operation=(node or {}).get("operation", {}).get("name"),
        params=params,
        own_params=dict((node or {}).get("params") or {}),
    )


# --- fonts and text -----------------------------------------------------

_glyphs: set[int] | None = None


def _register_fonts() -> None:
    """Source Sans (SIL Open Font License), shipped in provenance_widget/fonts/."""
    global _glyphs
    if _glyphs is not None:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    faces = {
        _FONT: "SourceSansPro-Regular.ttf",
        f"{_FONT}-Semibold": "SourceSansPro-Semibold.ttf",
        f"{_FONT}-Italic": "SourceSansPro-It.ttf",
        f"{_FONT}-SemiboldItalic": "SourceSansPro-SemiboldIt.ttf",
    }
    for name, filename in faces.items():
        pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / filename)))
    pdfmetrics.registerFontFamily(
        _FONT, normal=_FONT, bold=f"{_FONT}-Semibold", italic=f"{_FONT}-Italic", boldItalic=f"{_FONT}-SemiboldItalic"
    )
    _glyphs = set(pdfmetrics.getFont(_FONT).face.charToGlyph)


def _safe(text: Any) -> str:
    """The text with any character the font cannot draw replaced by '?'."""
    _register_fonts()
    return "".join(c if ord(c) in _glyphs or c in "\n\t" else "?" for c in str(text))


def _para(text: Any) -> str:
    return escape(_safe(text)).replace("\n", "<br/>")


def _clip(value: Any, limit: int = 48) -> str:
    text = str(value)
    return text if len(text) <= limit else "..." + text[-(limit - 3):]


# --- artifact rendering -------------------------------------------------


def _image(png: bytes, width: float):
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image

    pixel_w, pixel_h = ImageReader(io.BytesIO(png)).getSize()
    drawn_w = min(width * 0.9, pixel_w * 0.5)  # small images stay small, large ones fit the column
    return Image(io.BytesIO(png), width=drawn_w, height=drawn_w * pixel_h / pixel_w, hAlign="LEFT")


_figure_png = figure_png


def _format_cell(value: Any) -> str | None:
    """A cell as the marimo table shows it; None for a missing value."""
    if value is None or (isinstance(value, float) and value != value) or str(value) in ("NaT", "<NA>"):
        return None
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() and abs(value) < 1e15 else f"{value:.6g}"
    if hasattr(value, "strftime"):
        midnight = (value.hour, value.minute, value.second) == (0, 0, 0)
        return value.strftime("%Y-%m-%d" if midnight else "%Y-%m-%d %H:%M")
    text = _safe(value)
    return text if len(text) <= _MAX_CELL_CHARS else text[: _MAX_CELL_CHARS - 1] + "..."


def _looks_numeric(column: Any) -> bool:
    values = [v for v in column if v not in ("", None)]
    if not values:
        return False
    try:
        for value in values:
            float(str(value).replace(",", ""))
    except ValueError:
        return False
    return True


def _table(frame: Any, width: float, styles: dict):
    """The first rows of a DataFrame laid out like a marimo table; returns (flowable, caption detail).

    Column name over a small dtype, numbers right-aligned, missing values in
    grey, light row rules and a rounded outline.
    """
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    total_rows, total_columns = frame.shape
    # a snapshot of a picked table is text; it reports the size of the table it was taken from
    from_snapshot = "pw_total_rows" in frame.attrs
    if from_snapshot:
        total_rows = frame.attrs.get("pw_total_rows") or total_rows
        total_columns = frame.attrs.get("pw_total_columns") or total_columns
    head = frame.head(_MAX_TABLE_ROWS)
    columns = list(head.columns)[:_MAX_TABLE_COLUMNS]
    if from_snapshot:
        numeric = [_looks_numeric(head[c]) for c in columns]
    else:
        numeric = [head[c].dtype.kind in "iufc" for c in columns]

    header = [
        Paragraph(
            _para(c) if from_snapshot else f"{_para(c)}<br/><font size='6.5' color='{_MUTED}'>{_para(head[c].dtype)}</font>",
            styles["th_num" if n else "th"],
        )
        for c, n in zip(columns, numeric)
    ]
    body = []
    for row in head[columns].itertuples(index=False):
        cells = []
        for value, n in zip(row, numeric):
            text = _format_cell(value)
            style = styles["td_num" if n else "td"]
            cells.append(
                Paragraph("<font color='#9CA3AF'><i>NaN</i></font>", style)
                if text is None
                else Paragraph(escape(text), style)
            )
        body.append(cells)

    # column widths follow the content, within limits
    weights = []
    for column in columns:
        longest = max(
            [len(str(column)), len(str(head[column].dtype))] + [len(_format_cell(v) or "NaN") for v in head[column]]
        )
        weights.append(min(max(longest, 11), 22))
    total = sum(weights)
    table = Table([header, *body], colWidths=[width * w / total for w in weights], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#D1D5DB")),
                ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor(_RULE)),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
                ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    table.hAlign = "LEFT"
    detail = f"first {len(head)} of {total_rows:,} rows"
    if total_columns > len(columns):
        detail += f", {len(columns)} of {total_columns} columns"
    return table, detail


def render_artifact(obj: Any, width: float, styles: dict):
    """(flowable, kind, detail) for a value, kind being 'Table' or 'Figure'. Never raises."""
    from reportlab.platypus import Preformatted

    if isinstance(obj, _Png):
        try:
            return _image(bytes(obj), width), "Figure", ""
        except Exception:
            pass
    if isinstance(obj, _Text):
        lines = [line for chunk in obj.splitlines() or [""] for line in (chunk[i : i + 110] for i in range(0, max(len(chunk), 1), 110))]
        if len(lines) > _MAX_TEXT_LINES:
            lines = [*lines[:_MAX_TEXT_LINES], "..."]
        return Preformatted("\n".join(line.encode("ascii", "replace").decode() for line in lines), styles["mono"]), "Text", ""
    if hasattr(obj, "head") and hasattr(obj, "shape") and hasattr(obj, "columns") and len(obj.shape) == 2:
        try:
            table, detail = _table(obj, width, styles)
            return table, "Table", detail
        except Exception:
            pass
    png = _figure_png(obj)
    if png is not None:
        try:
            return _image(png, width), "Figure", ""
        except Exception:
            pass
    if type(obj).__module__.startswith("plotly"):
        text = "Interactive Plotly figure: install the kaleido package to embed it as an image."
        return Preformatted(text, styles["mono"]), "Figure", ""
    lines = repr(obj).encode("ascii", "replace").decode().splitlines()
    if len(lines) > _MAX_TEXT_LINES:
        lines = [*lines[:_MAX_TEXT_LINES], "..."]
    return Preformatted("\n".join(line[:110] for line in lines), styles["mono"]), "Table", ""


# --- document -----------------------------------------------------------


def _styles():
    from reportlab.lib.styles import ParagraphStyle

    def style(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **{"fontName": _FONT, "textColor": _INK, **kw})

    semibold = f"{_FONT}-Semibold"
    return {
        "title": style("title", fontName=semibold, fontSize=24, leading=28, spaceAfter=4),
        "byline": style("byline", fontSize=10.5, leading=14, textColor=_MUTED, spaceAfter=16),
        "box": style("box", fontSize=10, leading=14),
        "section": style("section", fontName=semibold, fontSize=14, leading=18, spaceBefore=14, spaceAfter=4),
        "entry": style("entry", fontName=semibold, fontSize=12.5, leading=16, spaceBefore=12, spaceAfter=1),
        "meta": style("meta", fontSize=9, leading=12, textColor=_MUTED, spaceAfter=4),
        "body": style("body", fontSize=10.5, leading=15, spaceBefore=2, spaceAfter=4),
        "field": style("field", fontSize=9.5, leading=13, spaceAfter=1),
        "tags": style("tags", fontSize=9.5, leading=15, spaceAfter=2),
        "caption": style("caption", fontSize=8.5, leading=11, textColor=_MUTED, spaceBefore=3, spaceAfter=10),
        "th": style("th", fontName=semibold, fontSize=8, leading=9.5),
        "th_num": style("th_num", fontName=semibold, fontSize=8, leading=9.5, alignment=2),
        "td": style("td", fontSize=8, leading=9.5),
        "td_num": style("td_num", fontSize=8, leading=9.5, alignment=2),
        "mono": style("mono", fontName="Courier", fontSize=7.5, leading=9),
    }


class _Text(str):
    """Plain text a picked element showed, drawn as a monospaced block."""


class _Png(bytes):
    """A picture a picked element showed."""


def _snapshot_value(ref: dict):
    """What the picked element showed, rebuilt from its snapshot, or None when the target carries none."""
    snapshot = ref.get("snapshot") if isinstance(ref, dict) else None
    if not isinstance(snapshot, dict):
        return None
    kind = snapshot.get("kind") or ("table" if snapshot.get("columns") else None)  # older targets had tables only
    if kind == "table" and snapshot.get("columns"):
        import pandas as pd

        frame = pd.DataFrame(snapshot.get("rows") or [], columns=snapshot["columns"])
        frame.attrs["pw_total_rows"] = snapshot.get("total_rows")
        frame.attrs["pw_total_columns"] = snapshot.get("total_columns")
        return frame
    if kind == "text" and snapshot.get("text"):
        return _Text(snapshot["text"])
    if kind == "image" and snapshot.get("png"):
        try:
            return _Png(base64.b64decode(snapshot["png"]))
        except Exception:
            return None
    return None


_MAX_SETTINGS = 6
_MAX_SETTING_CHARS = 40


def _readable_settings(params: dict) -> list[tuple[str, str]]:
    """The settings worth printing: short scalar values the analyst chose.

    Tracked functions also record their data arguments (frames, column lists, truncated reprs); those say nothing
    about what the step did, so they are left out.
    """
    settings: list[tuple[str, str]] = []
    for key, value in params.items():
        name = str(key)
        if name.startswith("_") or isinstance(value, (dict, list, tuple, set, frozenset)) or value is None:
            continue
        text = str(value)
        if "..." in text or "<" in text or len(text) > _MAX_SETTING_CHARS or "\n" in text:
            continue
        settings.append((name.replace("_", " "), text))
    return settings[-_MAX_SETTINGS:]


def _operation_label(name: str | None) -> str:
    """A step's function name as words: `_cell_TXez_filtered_log` -> `filtered log`."""
    if not name:
        return ""
    label = re.sub(r"^_*cell_[A-Za-z0-9]+_", "", name).strip("_").replace("_", " ")
    # a chained call is recorded whole ("set summary[[...]].sort values(...)"): keep what it starts with
    label = re.split(r"[\[(]", label, maxsplit=1)[0].strip(" .")
    if len(label) > 40:
        label = label[:39].rstrip() + "…"
    return label or name


def _stamp(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().strftime("%d %b %Y, %H:%M")
    except (ValueError, AttributeError):
        return timestamp or "unknown time"


def _display_name(ref: dict, step: int | None) -> str:
    """The target's name; a stored annotation only knows its state id, which says nothing to a reader."""
    name = ref.get("artifactName") or ref.get("artifactId") or "artifact"
    if name == ref.get("artifactId") and len(name) > 12:
        return f"output of step {step}" if step else "output of this step"
    return name


def _target_text(ref: dict, step: int | None) -> str:
    text = _display_name(ref, step)
    granularity = (ref.get("granularity") or "").replace("_", " ")
    if granularity:
        text += f" ({granularity})"
    if ref.get("detail"):
        text += f": {ref['detail']}"
    return text


def _field(label: str, value: str) -> str:
    return f"<font color='{_MUTED}'>{_para(label)}</font>&nbsp;&nbsp;{_para(value)}"


def build_pdf(
    rows: list[Row],
    resolve: Callable[[Row, dict], Any] | None = None,
    *,
    title: str = "Annotated analysis report",
    compress: bool = True,
    stores_outputs: bool = True,
    include_authors: bool = False,
    include_settings: bool = False,
) -> bytes:
    """Lay the rows out as a PDF.

    *resolve(row, artifact_ref)* returns the value an annotation's target had at
    its state (a DataFrame, figure, ...), or None when it cannot be recovered.
    *stores_outputs* is False for a source that records no outputs at all (the
    demo source): the report then says so once instead of failing per annotation.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import CondPageBreak, HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise PdfUnavailable('PDF export needs reportlab: pip install "marimo-pmprov[pdf]"') from exc

    _register_fonts()
    styles = _styles()
    page_w, _ = A4
    margin = 2.2 * cm
    width = page_w - 2 * margin
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin + 0.3 * cm,
        title=title,
        author="marimo-pmprov",
        pageCompression=1 if compress else 0,
    )

    def box(text: str, background: str, border: str) -> Table:
        cell = Table([[Paragraph(text, styles["box"])]], colWidths=[width])
        cell.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(border)),
                    ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return cell

    authors = (
        sorted({(r.annotation.get("author") or {}).get("display_name", "") for r in rows} - {""})
        if include_authors
        else []
    )
    stamps = [r.annotation.get("timestamp", "") for r in rows if r.annotation.get("timestamp")]
    byline = [datetime.now().strftime("%d %B %Y")]
    if authors:
        byline.insert(0, ", ".join(authors))
    story: list = [Paragraph(_para(title), styles["title"]), Paragraph(_para("  ·  ".join(byline)), styles["byline"])]

    steps = {r.step for r in rows if r.step}
    summary = (
        f"<b>{len(rows)}</b> annotation{'s' if len(rows) != 1 else ''}"
        + (f" across <b>{len(steps)}</b> analysis step{'s' if len(steps) != 1 else ''}" if steps else "")
        + (f", written between {_stamp(min(stamps, key=_time_of))} and {_stamp(max(stamps, key=_time_of))}" if stamps else "")
        + ". Entries are listed in the order they were written, each with its tags, the step in the provenance "
        "record and the output it targets as the analysis showed it at that step."
    )
    story += [box(summary, "#F8FAFC", _RULE), Spacer(1, 6)]
    if not stores_outputs:
        notice = "<b>Demo source.</b> " + _para(
            "This provenance source does not store outputs, so the tables and figures the annotations "
            "refer to are not included. Use a pmprov-backed history to embed them."
        )
        story += [box(notice, "#FFFBEB", "#FCD34D"), Spacer(1, 6)]
    story.append(Paragraph("Annotations", styles["section"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=_RULE, spaceAfter=2))

    if not rows:
        story.append(Paragraph("No annotations have been recorded yet.", styles["body"]))

    counters = {"Table": 0, "Figure": 0, "Text": 0}
    for number, row in enumerate(rows, start=1):
        annotation = row.annotation
        note = annotation.get("note") or ""
        entry_title = (annotation.get("title") or "").strip()
        # the sidebar titles an annotation with the first characters of its note
        heading = "" if not entry_title or note.strip().startswith(entry_title.rstrip(". ")) else entry_title
        meta = [_stamp(annotation.get("timestamp", ""))]
        if row.step:
            meta.append(f"Step {row.step}" + (f": {_operation_label(row.operation)}" if row.operation else ""))
        else:
            meta.append("Step not recorded")
        author = (annotation.get("author") or {}).get("display_name")
        if include_authors and author and len(authors) > 1:  # with a single author, the byline already says it
            meta.append(author)
        block: list = [
            Paragraph(
                f"<font color='{_MUTED}'>{number}</font>&nbsp;&nbsp;{_para(heading or 'Annotation')}", styles["entry"]
            ),
            Paragraph(_para("  ·  ".join(meta)), styles["meta"]),
        ]
        if note.strip():
            block.append(Paragraph(_para(note), styles["body"]))
        tags = [t.get("name", "") for t in annotation.get("tags") or [] if t.get("name")]
        if tags:
            chips = "&nbsp;&nbsp;".join(
                f"<font color='{_ACCENT}' backColor='{_CHIP}'>&nbsp;#{_para(t)}&nbsp;</font>" for t in tags
            )
            block.append(Paragraph(chips, styles["tags"]))
        refs = annotation.get("artifacts") or []
        if refs:
            for ref in refs:
                block.append(Paragraph(_field("Target", _target_text(ref, row.step)), styles["field"]))
        else:
            block.append(Paragraph(_field("Target", "the whole analysis at this step"), styles["field"]))
        settings = (
            ", ".join(f"{key} = {value}" for key, value in _readable_settings(row.own_params))
            if include_settings
            else ""
        )
        if settings:
            block.append(Paragraph(_field("Settings", settings), styles["field"]))

        for ref in refs:
            snapshot = _snapshot_value(ref)
            # the table the analyst picked, as shown, wins over looking a variable up by step: a table built
            # inside a display cell is not bound to any recorded step
            value = snapshot if snapshot is not None else (resolve(row, ref) if resolve else None)
            name = _display_name(ref, row.step)
            if value is None and not stores_outputs:
                continue
            if value is None:
                what = name if name.startswith("output of") else f"The output {name}"
                block.append(Paragraph(_para(f"{what[0].upper() + what[1:]} could not be recovered."), styles["field"]))
                continue
            flowable, kind, detail = render_artifact(value, width, styles)
            counters[kind] += 1
            label = name[0].upper() + name[1:] if name.startswith("output") else name
            caption = f"<font name='{_FONT}-Semibold' color='{_INK}'>{kind} {counters[kind]}.</font> {_para(label)}"
            if row.step and not name.startswith("output of step"):
                caption += _para(f" at step {row.step}")
            if detail:
                caption += _para(f" ({detail})")
            block += [Spacer(1, 6), KeepTogether([flowable, Paragraph(caption, styles["caption"])])]
        block.append(HRFlowable(width="100%", thickness=0.4, color=_RULE, spaceBefore=4))
        # start an entry on a fresh page rather than strand its heading above a table or chart
        story.append(CondPageBreak((9 if refs else 4) * cm))
        story += block

    def draw_page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(_FONT, 8.5)
        canvas.setFillColor(colors.HexColor(_MUTED))
        canvas.drawRightString(page_w - margin, margin / 2, str(doc.page))
        canvas.drawString(margin, margin / 2, _safe(title)[:90])
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()
