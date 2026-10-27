"""Static survey of the process-mining course code.

Parses every code cell of every notebook (and every .py file) under the
course folder and classifies each top-level statement by the *form* pmprov's
AST rewriter sees, because the form decides whether a step is tracked:

    x = f(...)        tracked          (Assign whose value is a Call)
    f(...)            tracked          (bare Call expression)
    df["c"] = ...     NOT tracked      (subscript assignment)
    a, b = f(...)     ?                (tuple unpacking)
    for/if/with/def   NOT tracked      (calls inside are not intercepted)

Usage:  python survey.py <course_dir> <out_dir>
Writes survey.json (machine readable) and survey.md (summary).
"""
from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {".venv", ".git", "__pycache__", "__marimo__", "node_modules"}


def code_units(path: Path):
    """Yield (unit_name, source) for each notebook cell / marimo cell / script."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") == "code":
                src = "".join(cell.get("source", []))
                yield f"cell{i}", src
        return
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        yield "module", text
        return
    marimo_cells = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and any("cell" in ast.unparse(d) for d in n.decorator_list)
    ]
    if marimo_cells:
        for n in marimo_cells:
            yield f"cell:{n.lineno}", "\n".join(ast.unparse(s) for s in n.body)
    else:
        yield "module", text


def strip_magics(src: str) -> tuple[str, int]:
    kept, magics = [], 0
    for line in src.splitlines():
        s = line.lstrip()
        if s.startswith(("%", "!")):
            magics += 1
            kept.append("pass")
        else:
            kept.append(line)
    return "\n".join(kept), magics


def dotted(node: ast.AST) -> str:
    """Callee as a dotted string; calls in the chain become `()`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{dotted(node.func)}()"
    if isinstance(node, ast.Subscript):
        return f"{dotted(node.value)}[]"
    return type(node).__name__


def callee_root(callee: str, aliases: dict[str, str]) -> str:
    head = callee.split(".")[0].split("(")[0].split("[")[0]
    return aliases.get(head, head)


def has_kw(call: ast.Call, name: str, value=True) -> bool:
    return any(k.arg == name and isinstance(k.value, ast.Constant) and k.value.value == value for k in call.keywords)


def all_calls(node: ast.AST):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)]


def classify(stmt: ast.stmt, aliases: dict[str, str]) -> dict:
    info: dict = {"line": stmt.lineno, "src": " ".join(ast.unparse(stmt).split())[:170]}
    calls = all_calls(stmt)
    info["has_lambda"] = any(isinstance(n, ast.Lambda) for n in ast.walk(stmt))
    info["inplace"] = any(has_kw(c, "inplace") for c in calls)

    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        info["form"] = "import"
    elif isinstance(stmt, ast.Assign):
        target = stmt.targets[0]
        value = stmt.value
        if len(stmt.targets) > 1:
            info["form"] = "assign_multi_target"
        elif isinstance(target, (ast.Tuple, ast.List)):
            info["form"] = "assign_unpack_call" if isinstance(value, ast.Call) else "assign_unpack_other"
        elif isinstance(target, ast.Subscript):
            info["form"] = "assign_subscript"
        elif isinstance(target, ast.Attribute):
            info["form"] = "assign_attribute"
        elif isinstance(value, ast.Call):
            info["form"] = "assign_call"
        elif isinstance(value, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            info["form"] = "assign_comprehension"
        elif isinstance(value, ast.Subscript):
            info["form"] = "assign_subscript_read"
        elif isinstance(value, ast.Attribute):
            info["form"] = "assign_attribute_read"
        elif isinstance(value, (ast.BinOp, ast.BoolOp, ast.UnaryOp, ast.Compare)):
            info["form"] = "assign_expression"
        elif isinstance(value, (ast.Constant, ast.List, ast.Dict, ast.Tuple, ast.Set)):
            info["form"] = "assign_literal"
        elif isinstance(value, ast.Name):
            info["form"] = "assign_alias"
        else:
            info["form"] = "assign_other"
        if isinstance(value, ast.Call):
            info["callee"] = dotted(value.func)
            info["chained"] = isinstance(value.func, ast.Attribute) and isinstance(value.func.value, ast.Call)
    elif isinstance(stmt, ast.AugAssign):
        info["form"] = "augassign"
    elif isinstance(stmt, ast.AnnAssign):
        info["form"] = "annassign"
    elif isinstance(stmt, ast.Expr):
        v = stmt.value
        if isinstance(v, ast.Call):
            info["form"] = "expr_call"
            info["callee"] = dotted(v.func)
            info["chained"] = isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Call)
        elif isinstance(v, ast.Constant):
            info["form"] = "expr_docstring_or_literal"
        else:
            info["form"] = "expr_value"  # bare name / subscript / attribute (notebook display)
            info["expr_kind"] = type(v).__name__
    elif isinstance(stmt, ast.For):
        info["form"] = "for"
    elif isinstance(stmt, ast.While):
        info["form"] = "while"
    elif isinstance(stmt, ast.If):
        info["form"] = "if"
    elif isinstance(stmt, ast.With):
        info["form"] = "with"
    elif isinstance(stmt, ast.Try):
        info["form"] = "try"
    elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        info["form"] = "def"
    elif isinstance(stmt, ast.ClassDef):
        info["form"] = "class"
    elif isinstance(stmt, ast.Delete):
        info["form"] = "del"
    else:
        info["form"] = type(stmt).__name__.lower()

    if info["form"] in {"for", "while", "if", "with", "try", "def", "class"}:
        inner = sorted({dotted(c.func) for c in calls})
        info["inner_calls"] = inner[:12]
        info["inner_call_count"] = len(calls)
    return info


def collect_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                aliases[a.asname or a.name] = f"{n.module}.{a.name}"
    return aliases


def survey(course: Path) -> dict:
    files = []
    for path in sorted(course.rglob("*")):
        if path.suffix not in {".ipynb", ".py"} or any(p in SKIP_DIRS for p in path.parts):
            continue
        rel = str(path.relative_to(course))
        stmts, magics, syntax_errors, cells = [], 0, 0, 0
        aliases: dict[str, str] = {}
        for unit, src in code_units(path):
            cells += 1
            src, m = strip_magics(src)
            magics += m
            try:
                tree = ast.parse(src)
            except SyntaxError:
                syntax_errors += 1
                continue
            aliases.update(collect_aliases(tree))
            for s in tree.body:
                d = classify(s, aliases)
                d["unit"] = unit
                if "callee" in d:
                    d["root"] = callee_root(d["callee"], aliases)
                stmts.append(d)
        files.append({
            "file": rel, "cells": cells, "magics": magics,
            "syntax_errors": syntax_errors, "statements": stmts,
            "imports": sorted(set(aliases.values())),
        })
    return {"files": files}


def summarise(data: dict) -> str:
    forms, callees, roots = Counter(), Counter(), Counter()
    per_form_examples: dict[str, set] = defaultdict(set)
    inplace = chained = lambdas = 0
    libs = Counter()
    for f in data["files"]:
        for imp in f["imports"]:
            libs[imp.split(".")[0]] += 1
        for s in f["statements"]:
            forms[s["form"]] += 1
            inplace += bool(s.get("inplace"))
            chained += bool(s.get("chained"))
            lambdas += bool(s.get("has_lambda"))
            if "callee" in s:
                callees[s["callee"]] += 1
                roots[s["root"].split(".")[0]] += 1
                per_form_examples[s["form"]].add(s["callee"])
    total = sum(forms.values())
    out = ["# Course code survey", "",
           f"{len(data['files'])} files, {sum(f['cells'] for f in data['files'])} code units, "
           f"{total} top-level statements, {sum(f['magics'] for f in data['files'])} magic lines, "
           f"{sum(f['syntax_errors'] for f in data['files'])} unparsable units.", "",
           "## Statement forms (what pmprov's rewriter sees)", "",
           "| form | count | share |", "|---|---:|---:|"]
    for form, n in forms.most_common():
        out.append(f"| {form} | {n} | {100 * n / total:.1f}% |")
    out += ["", f"Statements using `inplace=`: {inplace}; chained callee (`a.b().c()`): {chained}; with a lambda: {lambdas}.", "",
            "## Libraries imported (files)", ""]
    out += [f"- {lib}: {n}" for lib, n in libs.most_common()]
    out += ["", "## Callee roots", ""]
    out += [f"- {r}: {n}" for r, n in roots.most_common(15)]
    out += ["", "## Most frequent tracked-form callees", ""]
    out += [f"- `{c}` x{n}" for c, n in callees.most_common(40)]
    out += ["", "## Per file", "", "| file | cells | statements | assign_call | expr_call | assign_subscript | containers |", "|---|---:|---:|---:|---:|---:|---:|"]
    for f in data["files"]:
        c = Counter(s["form"] for s in f["statements"])
        containers = sum(c[k] for k in ("for", "while", "if", "with", "try", "def", "class"))
        out.append(f"| {f['file']} | {f['cells']} | {len(f['statements'])} | {c['assign_call']} | {c['expr_call']} | {c['assign_subscript']} | {containers} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    course = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    data = survey(course)
    (out_dir / "survey.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    md = summarise(data)
    (out_dir / "survey.md").write_text(md, encoding="utf-8")
    print(md)
