# marimo-pmprov Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a functional marimo anywidget "Source Control" plugin (Curated / Tree / Inspect tabs, sidebar + full-width tree surface, Student/Reviewer modes) running against mock data shaped like pmprov's real model, with zero runtime dependency on `pmprov`.

**Architecture:** A `ProvenanceSource` protocol (Python) decouples the widget from any data backend; `MockProvenanceSource` implements it with a realistic branching process-mining example. `ProvenancePanel` wraps one `anywidget.AnyWidget` with traitlets for tree data, mode, active tab, selection, commits, and restore round-trip. The frontend is vanilla TypeScript bundled with esbuild into a single JS/CSS pair checked into the Python package.

**Tech Stack:** Python 3.11+, `anywidget`, `marimo`, `traitlets`; TypeScript + esbuild (dev-only) for the frontend; `pytest` for Python tests.

## Global Constraints

- No `pmprov` import anywhere in `provenance_widget/` — verified by grep in the final task.
- `interfaces.py` dataclass field names/semantics must match pmprov's real model (`operationType`, `commandName`, `params`, `delta`, `parentStates`, `stepId`, `StepCategory` values) per pmprov's `MODEL.md`/`README.md` — new fields (`Annotation`, `Tag`) are additive only.
- Frontend: vanilla TS, no framework, bundled with esbuild to `provenance_widget/static/widget.js` + `widget.css`.
- Python package name: `provenance_widget`. Repo root: `new_prototype/marimo-pmprov/`.
- Every Python module gets a corresponding `tests/` file exercising its public behavior before being considered done.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `provenance_widget/__init__.py`
- Create: `.gitignore`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: installable package `provenance_widget`, `pytest` runnable from repo root.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "marimo-pmprov"
version = "0.1.0"
description = "A marimo anywidget for analytic provenance and annotation, decoupled from pmprov."
requires-python = ">=3.11"
dependencies = [
    "anywidget>=0.9",
    "marimo>=0.9",
    "traitlets>=5.14",
]

[project.optional-dependencies]
pmprov = ["pmprov @ git+https://github.com/<org>/pmprov.git@vX.Y.Z"]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["provenance_widget"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
node_modules/
dist/
*.egg-info/
.venv/
```

- [ ] **Step 3: Create empty package/test init files**

`provenance_widget/__init__.py`:
```python
"""marimo-pmprov: provenance and annotation sidebar widget for marimo notebooks."""
```

`tests/__init__.py`: empty file.

- [ ] **Step 4: Install in editable mode and verify pytest runs**

Run: `pip install -e ".[dev]"` then `pytest --collect-only`
Expected: no errors, "no tests ran" (0 collected) is fine at this point.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore provenance_widget/__init__.py tests/__init__.py
git commit -m "chore: scaffold provenance_widget package"
```

---

### Task 2: Core data model (`interfaces.py`)

**Files:**
- Create: `provenance_widget/interfaces.py`
- Test: `tests/test_interfaces.py`

**Interfaces:**
- Produces:
  - `class StepCategory(str, Enum)`: `DATA_LOADING`, `CLEANING`, `FEATURE_ENGINEERING`, `AGGREGATION`, `COMPARISON`, `ANALYSIS` (values match pmprov's `_internals/operation_types.py`).
  - `@dataclass Agent`: `agent_id: str`, `agent_type: str`, `display_name: str`.
  - `@dataclass ColumnAdded`: `name: str`, `dtype: str`. `@dataclass ColumnRemoved`: `name: str`, `dtype: str`.
  - `@dataclass Delta`: `columns_added: list[ColumnAdded]`, `columns_removed: list[ColumnRemoved]`, `row_count_before: int`, `row_count_after: int`; method `summary(self) -> str`.
  - `@dataclass Operation`: `operation_id: str`, `name: str`, `operation_type: str`, `command_name: str`, `category: StepCategory`.
  - `@dataclass ArtifactRef`: `artifact_id: str`, `artifact_name: str`, `granularity: str` (one of `"dataset"`, `"column"`, `"row_subset"`, `"cell"`, `"chart_selection"`), `detail: str | None` (e.g. column name).
  - `@dataclass Tag`: `name: str`, `color: str`.
  - `@dataclass Annotation`: `annotation_id: str`, `title: str`, `note: str`, `tags: list[Tag]`, `artifacts: list[ArtifactRef]`, `author: Agent`, `timestamp: str` (ISO 8601).
  - `@dataclass ProvenanceNode`: `state_id: str`, `parent_state_id: str | None`, `branch_id: str`, `operation: Operation`, `params: dict`, `delta: Delta`, `annotations: list[Annotation]`.
  - `@dataclass ProvenanceTree`: `nodes: dict[str, ProvenanceNode]` (keyed by `state_id`), `root_id: str`, `branches: dict[str, str]` (branch_id -> name); method `children_of(self, state_id: str) -> list[ProvenanceNode]`.
  - `class ProvenanceSource(Protocol)`: `def get_tree(self) -> ProvenanceTree: ...`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_interfaces.py
from provenance_widget.interfaces import (
    Agent, ArtifactRef, ColumnAdded, ColumnRemoved, Delta, Operation,
    ProvenanceNode, ProvenanceTree, StepCategory, Tag, Annotation,
)


def _agent():
    return Agent(agent_id="a1", agent_type="human", display_name="Student")


def test_delta_summary_reports_column_and_row_changes():
    delta = Delta(
        columns_added=[ColumnAdded(name="duration", dtype="float64")],
        columns_removed=[],
        row_count_before=1000,
        row_count_after=940,
    )
    summary = delta.summary()
    assert "duration" in summary
    assert "940" in summary


def test_tree_children_of_returns_direct_children_only():
    root = ProvenanceNode(
        state_id="s0", parent_state_id=None, branch_id="main",
        operation=Operation(operation_id="op0", name="load_event_log",
                             operation_type="IMPORT", command_name="load_event_log",
                             category=StepCategory.DATA_LOADING),
        params={}, delta=Delta([], [], 0, 1000), annotations=[],
    )
    child = ProvenanceNode(
        state_id="s1", parent_state_id="s0", branch_id="main",
        operation=Operation(operation_id="op1", name="Filter",
                             operation_type="FILTER", command_name="filter_duration",
                             category=StepCategory.CLEANING),
        params={"threshold": 120}, delta=Delta([], [], 1000, 940),
        annotations=[Annotation(
            annotation_id="ann1", title="Truncate outliers", note="...",
            tags=[Tag(name="cleaning", color="#0EA5E9")],
            artifacts=[ArtifactRef(artifact_id="art1", artifact_name="event_log",
                                    granularity="column", detail="duration")],
            author=_agent(), timestamp="2026-08-04T10:42:00",
        )],
    )
    grandchild = ProvenanceNode(
        state_id="s2", parent_state_id="s1", branch_id="main",
        operation=child.operation, params={}, delta=Delta([], [], 940, 940),
        annotations=[],
    )
    tree = ProvenanceTree(
        nodes={"s0": root, "s1": child, "s2": grandchild},
        root_id="s0", branches={"main": "main"},
    )
    assert [n.state_id for n in tree.children_of("s0")] == ["s1"]
    assert [n.state_id for n in tree.children_of("s1")] == ["s2"]
    assert tree.children_of("s2") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interfaces.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'provenance_widget.interfaces'`

- [ ] **Step 3: Write the implementation**

```python
# provenance_widget/interfaces.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class StepCategory(str, Enum):
    DATA_LOADING = "DATA_LOADING"
    CLEANING = "CLEANING"
    FEATURE_ENGINEERING = "FEATURE_ENGINEERING"
    AGGREGATION = "AGGREGATION"
    COMPARISON = "COMPARISON"
    ANALYSIS = "ANALYSIS"


@dataclass
class Agent:
    agent_id: str
    agent_type: str
    display_name: str


@dataclass
class ColumnAdded:
    name: str
    dtype: str


@dataclass
class ColumnRemoved:
    name: str
    dtype: str


@dataclass
class Delta:
    columns_added: list[ColumnAdded]
    columns_removed: list[ColumnRemoved]
    row_count_before: int
    row_count_after: int

    def summary(self) -> str:
        parts = []
        for c in self.columns_added:
            parts.append(f"+{c.name}")
        for c in self.columns_removed:
            parts.append(f"-{c.name}")
        parts.append(f"rows {self.row_count_before}->{self.row_count_after}")
        return ", ".join(parts)


@dataclass
class Operation:
    operation_id: str
    name: str
    operation_type: str
    command_name: str
    category: StepCategory


@dataclass
class ArtifactRef:
    artifact_id: str
    artifact_name: str
    granularity: str
    detail: str | None = None


@dataclass
class Tag:
    name: str
    color: str


@dataclass
class Annotation:
    annotation_id: str
    title: str
    note: str
    tags: list[Tag]
    artifacts: list[ArtifactRef]
    author: Agent
    timestamp: str


@dataclass
class ProvenanceNode:
    state_id: str
    parent_state_id: str | None
    branch_id: str
    operation: Operation
    params: dict
    delta: Delta
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class ProvenanceTree:
    nodes: dict[str, ProvenanceNode]
    root_id: str
    branches: dict[str, str]

    def children_of(self, state_id: str) -> list[ProvenanceNode]:
        return [n for n in self.nodes.values() if n.parent_state_id == state_id]


class ProvenanceSource(Protocol):
    def get_tree(self) -> ProvenanceTree: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_interfaces.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/interfaces.py tests/test_interfaces.py
git commit -m "feat: add ProvenanceSource protocol and provenance data model"
```

---

### Task 3: Mock provenance source

**Files:**
- Create: `provenance_widget/mock_source.py`
- Test: `tests/test_mock_source.py`

**Interfaces:**
- Consumes: `provenance_widget.interfaces` (`ProvenanceTree`, `ProvenanceNode`, `Operation`, `StepCategory`, `Delta`, `ColumnAdded`, `ColumnRemoved`, `ArtifactRef`, `Tag`, `Annotation`, `Agent`).
- Produces: `class MockProvenanceSource: def get_tree(self) -> ProvenanceTree`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mock_source.py
from provenance_widget.interfaces import StepCategory
from provenance_widget.mock_source import MockProvenanceSource


def test_mock_tree_has_import_root():
    tree = MockProvenanceSource().get_tree()
    root = tree.nodes[tree.root_id]
    assert root.operation.category == StepCategory.DATA_LOADING
    assert root.parent_state_id is None


def test_mock_tree_branches_into_rule_induction_and_conformance():
    tree = MockProvenanceSource().get_tree()
    categories = {n.operation.category for n in tree.nodes.values()}
    assert StepCategory.CLEANING in categories
    assert StepCategory.FEATURE_ENGINEERING in categories
    branch_names = set(tree.branches.values())
    assert len(branch_names) >= 2


def test_mock_tree_nodes_carry_annotations_with_tags_and_artifacts():
    tree = MockProvenanceSource().get_tree()
    annotated = [n for n in tree.nodes.values() if n.annotations]
    assert annotated, "expected at least one annotated node"
    ann = annotated[0].annotations[0]
    assert ann.tags
    assert ann.artifacts
    assert ann.artifacts[0].granularity in {
        "dataset", "column", "row_subset", "cell", "chart_selection",
    }


def test_get_tree_is_deterministic_across_calls():
    source = MockProvenanceSource()
    tree_a = source.get_tree()
    tree_b = source.get_tree()
    assert set(tree_a.nodes.keys()) == set(tree_b.nodes.keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mock_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'provenance_widget.mock_source'`

- [ ] **Step 3: Write the implementation**

```python
# provenance_widget/mock_source.py
from __future__ import annotations

from provenance_widget.interfaces import (
    Agent, Annotation, ArtifactRef, ColumnAdded, ColumnRemoved, Delta,
    Operation, ProvenanceNode, ProvenanceTree, StepCategory, Tag,
)

_STUDENT = Agent(agent_id="agent-student", agent_type="human", display_name="S")


def _op(op_id: str, name: str, op_type: str, command: str, category: StepCategory) -> Operation:
    return Operation(operation_id=op_id, name=name, operation_type=op_type,
                      command_name=command, category=category)


class MockProvenanceSource:
    """Deterministic in-memory ProvenanceSource for demoing the widget without pmprov."""

    def get_tree(self) -> ProvenanceTree:
        root = ProvenanceNode(
            state_id="s0", parent_state_id=None, branch_id="main",
            operation=_op("op0", "Load event log", "IMPORT", "load_event_log",
                          StepCategory.DATA_LOADING),
            params={"filepath": "data/rtfm_full.csv"},
            delta=Delta([ColumnAdded("case:concept:name", "object"),
                         ColumnAdded("concept:name", "object"),
                         ColumnAdded("time:timestamp", "datetime64[ns]")],
                        [], row_count_before=0, row_count_after=15214),
            annotations=[],
        )

        filtered = ProvenanceNode(
            state_id="s1", parent_state_id="s0", branch_id="main",
            operation=_op("op1", "Filter long traces", "FILTER", "filter_duration",
                          StepCategory.CLEANING),
            params={"threshold_hours": 120},
            delta=Delta([], [], row_count_before=15214, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-c8f2", title="Truncate outliers",
                note="Removed traces longer than 120h; distorted the mean duration.",
                tags=[Tag(name="cleaning", color="#0EA5E9"), Tag(name="v1.1", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="column", detail="duration")],
                author=_STUDENT, timestamp="2026-08-04T10:42:00",
            )],
        )

        enriched = ProvenanceNode(
            state_id="s2", parent_state_id="s1", branch_id="main",
            operation=_op("op2", "Calculate case cost", "ENRICHMENT", "add_attribute",
                          StepCategory.FEATURE_ENGINEERING),
            params={"output_col": "case_cost", "source": "resource_wage_matrix"},
            delta=Delta([ColumnAdded("case_cost", "float64")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-a911", title="Calculate case cost",
                note="Joined hourly wage matrix with resource trace logs.",
                tags=[Tag(name="cost", color="#10B981"), Tag(name="enrichment", color="#10B981")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="dataset")],
                author=_STUDENT, timestamp="2026-08-04T10:58:00",
            )],
        )

        rule_induction = ProvenanceNode(
            state_id="s3a", parent_state_id="s2", branch_id="branch-a",
            operation=_op("op3a", "Induce decision rules", "RULE_INDUCTION", "induce_rules",
                          StepCategory.ANALYSIS),
            params={"target_col": "is_long_case", "max_depth": 4},
            delta=Delta([ColumnAdded("predicted_outcome", "bool")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-d213", title="First rule set",
                note="Depth-4 tree overfits on resource attribute; needs pruning.",
                tags=[Tag(name="rules", color="#F59E0B")],
                artifacts=[ArtifactRef(artifact_id="art-event-log", artifact_name="event_log.csv",
                                        granularity="row_subset", detail="rows 1-4032")],
                author=_STUDENT, timestamp="2026-08-04T11:10:00",
            )],
        )

        conformance = ProvenanceNode(
            state_id="s3b", parent_state_id="s2", branch_id="branch-b",
            operation=_op("op3b", "Conformance check", "CONFORMANCE_CHECK", "check_conformance",
                          StepCategory.COMPARISON),
            params={"model": "petri_net_v1"},
            delta=Delta([ColumnAdded("fitness", "float64")], [],
                        row_count_before=14032, row_count_after=14032),
            annotations=[Annotation(
                annotation_id="ann-f004", title="Baseline fitness",
                note="Fitness 0.87 against the reference Petri net.",
                tags=[Tag(name="conformance", color="#F43F5E"), Tag(name="v1.1", color="#94A3B8")],
                artifacts=[ArtifactRef(artifact_id="art-process-map", artifact_name="Chart_ProcessMap",
                                        granularity="chart_selection")],
                author=_STUDENT, timestamp="2026-08-04T11:22:00",
            )],
        )

        return ProvenanceTree(
            nodes={n.state_id: n for n in [root, filtered, enriched, rule_induction, conformance]},
            root_id="s0",
            branches={"main": "main", "branch-a": "rule-induction", "branch-b": "conformance"},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mock_source.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/mock_source.py tests/test_mock_source.py
git commit -m "feat: add MockProvenanceSource with branching example tree"
```

---

### Task 4: Tree serialization for the frontend

**Files:**
- Create: `provenance_widget/serialize.py`
- Test: `tests/test_serialize.py`

**Interfaces:**
- Consumes: `ProvenanceTree`, `ProvenanceNode` from `provenance_widget.interfaces`.
- Produces: `def tree_to_json(tree: ProvenanceTree) -> dict` — a plain-dict/list structure (no dataclasses, no enums) safe to assign to an anywidget traitlet and `json.dumps`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_serialize.py
import json

from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.serialize import tree_to_json


def test_tree_to_json_is_json_serializable():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    json.dumps(payload)  # raises if not serializable


def test_tree_to_json_preserves_node_count_and_root():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    assert payload["rootId"] == tree.root_id
    assert len(payload["nodes"]) == len(tree.nodes)


def test_tree_to_json_node_has_flat_operation_category_string():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    node = payload["nodes"][tree.root_id]
    assert isinstance(node["operation"]["category"], str)
    assert node["operation"]["category"] == "DATA_LOADING"


def test_tree_to_json_node_includes_annotations_and_artifacts():
    tree = MockProvenanceSource().get_tree()
    payload = tree_to_json(tree)
    node = payload["nodes"]["s1"]
    assert node["annotations"][0]["title"] == "Truncate outliers"
    assert node["annotations"][0]["tags"][0]["name"] == "cleaning"
    assert node["annotations"][0]["artifacts"][0]["granularity"] == "column"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'provenance_widget.serialize'`

- [ ] **Step 3: Write the implementation**

```python
# provenance_widget/serialize.py
from __future__ import annotations

from dataclasses import asdict

from provenance_widget.interfaces import ProvenanceTree


def tree_to_json(tree: ProvenanceTree) -> dict:
    nodes = {}
    for state_id, node in tree.nodes.items():
        node_dict = asdict(node)
        node_dict["operation"]["category"] = node.operation.category.value
        nodes[state_id] = {
            "stateId": node_dict["state_id"],
            "parentStateId": node_dict["parent_state_id"],
            "branchId": node_dict["branch_id"],
            "operation": {
                "operationId": node_dict["operation"]["operation_id"],
                "name": node_dict["operation"]["name"],
                "operationType": node_dict["operation"]["operation_type"],
                "commandName": node_dict["operation"]["command_name"],
                "category": node_dict["operation"]["category"],
            },
            "params": node_dict["params"],
            "delta": {
                "columnsAdded": node_dict["delta"]["columns_added"],
                "columnsRemoved": node_dict["delta"]["columns_removed"],
                "rowCountBefore": node_dict["delta"]["row_count_before"],
                "rowCountAfter": node_dict["delta"]["row_count_after"],
                "summary": node.delta.summary(),
            },
            "annotations": [
                {
                    "annotationId": a["annotation_id"],
                    "title": a["title"],
                    "note": a["note"],
                    "tags": a["tags"],
                    "artifacts": [
                        {
                            "artifactId": ar["artifact_id"],
                            "artifactName": ar["artifact_name"],
                            "granularity": ar["granularity"],
                            "detail": ar["detail"],
                        }
                        for ar in a["artifacts"]
                    ],
                    "author": a["author"],
                    "timestamp": a["timestamp"],
                }
                for a in node_dict["annotations"]
            ],
        }
    return {
        "rootId": tree.root_id,
        "branches": tree.branches,
        "nodes": nodes,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_serialize.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/serialize.py tests/test_serialize.py
git commit -m "feat: add JSON serialization for ProvenanceTree traitlet payload"
```

---

### Task 5: Frontend build scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/build.mjs`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/theme.css`
- Create: `provenance_widget/static/.gitkeep`

**Interfaces:**
- Produces: `npm run build` in `frontend/` emits `provenance_widget/static/widget.js` + `provenance_widget/static/widget.css`. `main.ts` exports `default { render }` matching anywidget's ESM contract: `render({ model, el }) => void`.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "provenance-widget-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "node build.mjs",
    "watch": "node build.mjs --watch"
  },
  "devDependencies": {
    "esbuild": "^0.24.0",
    "typescript": "^5.6.0"
  }
}
```

- [ ] **Step 2: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Write `frontend/build.mjs`**

```javascript
import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: ["src/main.ts"],
  bundle: true,
  format: "esm",
  outfile: "../provenance_widget/static/widget.js",
  minify: !watch,
  sourcemap: watch,
  loader: { ".css": "css" },
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("watching...");
} else {
  await esbuild.build(options);
  console.log("build complete");
}
```

- [ ] **Step 4: Write minimal `frontend/src/main.ts`**

```typescript
import "./theme.css";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): void {
  const root = document.createElement("div");
  root.className = "pw-root";
  root.textContent = "provenance widget loading...";
  el.appendChild(root);
}

export default { render };
```

- [ ] **Step 5: Write minimal `frontend/src/theme.css`**

```css
.pw-root {
  font-family: ui-sans-serif, system-ui, sans-serif;
  color: #0F172A;
  background: #F8FAFC;
  padding: 8px;
  border-radius: 8px;
}

@media (prefers-color-scheme: dark) {
  .pw-root {
    color: #F8FAFC;
    background: #0F172A;
  }
}
```

- [ ] **Step 6: Install deps and build**

Run: `cd frontend && npm install && npm run build`
Expected: `provenance_widget/static/widget.js` created, "build complete" printed.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/build.mjs frontend/src/main.ts frontend/src/theme.css provenance_widget/static/.gitkeep
git commit -m "chore: scaffold esbuild frontend build"
```

Note: `provenance_widget/static/widget.js` is a build artifact — add `provenance_widget/static/*.js` and `*.css` to `.gitignore`'s exceptions later in Task 12 once the real bundle is ready to ship; for now leave the scaffold build untracked (`.gitignore` already covers `dist/`, add `provenance_widget/static/widget.js` and `widget.css` to `.gitignore` now too):

- [ ] **Step 8: Update `.gitignore`**

Add these lines to `.gitignore`:
```
provenance_widget/static/widget.js
provenance_widget/static/widget.css
provenance_widget/static/widget.js.map
```

- [ ] **Step 9: Commit the gitignore update**

```bash
git add .gitignore
git commit -m "chore: ignore built frontend bundle until packaging task"
```

---

### Task 6: AnyWidget core and ProvenancePanel façade

**Files:**
- Create: `provenance_widget/widget.py`
- Test: `tests/test_widget.py`

**Interfaces:**
- Consumes: `ProvenanceSource`, `tree_to_json` from Task 4.
- Produces:
  - `class ProvenanceWidget(anywidget.AnyWidget)` with traitlets: `tree = traitlets.Dict({}).tag(sync=True)`, `mode = traitlets.Unicode("student").tag(sync=True)`, `active_tab = traitlets.Unicode("curated").tag(sync=True)`, `selection = traitlets.Dict({}).tag(sync=True)`, `commits = traitlets.List([]).tag(sync=True)`, `restore_request = traitlets.Dict({}).tag(sync=True)`, `restore_ack = traitlets.Dict({}).tag(sync=True)`.
  - `class ProvenancePanel`: `__init__(self, source: ProvenanceSource, mode: str = "student")`; `.widget` (the `ProvenanceWidget` instance); `.sidebar(self)` returns the widget (marimo wraps it in `mo.sidebar` at call site — see Task 13); `.tree_surface(self)` returns the same widget instance (single shared widget, frontend switches surface via `active_tab`); `.commit_annotation(self, annotation_dict: dict) -> None` appends to `commits`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_widget.py
from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.widget import ProvenancePanel, ProvenanceWidget


def test_panel_loads_tree_from_source_into_widget():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert isinstance(panel.widget, ProvenanceWidget)
    assert panel.widget.tree["rootId"] == "s0"
    assert "s1" in panel.widget.tree["nodes"]


def test_panel_defaults_to_student_mode():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.mode == "student"


def test_panel_reviewer_mode_is_settable_at_construction():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    assert panel.widget.mode == "reviewer"


def test_commit_annotation_appends_to_commits_list():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.widget.commits == []
    panel.commit_annotation({"title": "New note", "note": "...", "tags": [], "artifacts": []})
    assert len(panel.widget.commits) == 1
    assert panel.widget.commits[0]["title"] == "New note"


def test_sidebar_and_tree_surface_return_the_same_widget_instance():
    panel = ProvenancePanel(source=MockProvenanceSource())
    assert panel.sidebar() is panel.tree_surface()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_widget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'provenance_widget.widget'`

- [ ] **Step 3: Write the implementation**

```python
# provenance_widget/widget.py
from __future__ import annotations

import pathlib

import anywidget
import traitlets

from provenance_widget.interfaces import ProvenanceSource
from provenance_widget.serialize import tree_to_json

_STATIC_DIR = pathlib.Path(__file__).parent / "static"


class ProvenanceWidget(anywidget.AnyWidget):
    _esm = _STATIC_DIR / "widget.js"
    _css = _STATIC_DIR / "widget.css"

    tree = traitlets.Dict({}).tag(sync=True)
    mode = traitlets.Unicode("student").tag(sync=True)
    active_tab = traitlets.Unicode("curated").tag(sync=True)
    selection = traitlets.Dict({}).tag(sync=True)
    commits = traitlets.List([]).tag(sync=True)
    restore_request = traitlets.Dict({}).tag(sync=True)
    restore_ack = traitlets.Dict({}).tag(sync=True)


class ProvenancePanel:
    """Python-side façade wrapping one ProvenanceWidget instance."""

    def __init__(self, source: ProvenanceSource, mode: str = "student"):
        self._source = source
        self.widget = ProvenanceWidget(tree=tree_to_json(source.get_tree()), mode=mode)

    def sidebar(self) -> ProvenanceWidget:
        return self.widget

    def tree_surface(self) -> ProvenanceWidget:
        return self.widget

    def commit_annotation(self, annotation_dict: dict) -> None:
        self.widget.commits = [*self.widget.commits, annotation_dict]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_widget.py -v`
Expected: PASS (5 passed) — note `_esm`/`_css` point at not-yet-built files, which is fine for these Python-only tests since `AnyWidget` reads them lazily on frontend render, not on construction.

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/widget.py tests/test_widget.py
git commit -m "feat: add ProvenanceWidget anywidget and ProvenancePanel facade"
```

---

### Task 7: Display wrapper functions (`display.py`) for artifact tagging

**Files:**
- Create: `provenance_widget/display.py`
- Test: `tests/test_display.py`

**Interfaces:**
- Consumes: `marimo` (`mo.ui.table`), `ArtifactRef` from `interfaces.py` (for the granularity vocabulary only).
- Produces: `def show_table(data, artifact_id: str, artifact_name: str) -> mo.Html` — renders an `mo.ui.table` wrapped in a container `div` carrying `data-pw-artifact-id`, `data-pw-artifact-name`, `data-pw-granularity="dataset"` attributes (granularity refines to `"column"`/`"row_subset"`/`"cell"` client-side based on the table's own selection, which `show_table` cannot know ahead of time — the wrapper only stamps the identity, not the live selection). `def show_chart(chart_html, artifact_id: str, artifact_name: str) -> mo.Html` — same wrapping for a pre-rendered chart `mo.Html`/altair chart, `data-pw-granularity="chart_selection"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_display.py
import marimo as mo

from provenance_widget.display import show_chart, show_table


def test_show_table_wraps_table_with_artifact_data_attributes():
    table = mo.ui.table(data=[{"a": 1}, {"a": 2}])
    wrapped = show_table(table, artifact_id="art-event-log", artifact_name="event_log.csv")
    html = wrapped.text
    assert 'data-pw-artifact-id="art-event-log"' in html
    assert 'data-pw-artifact-name="event_log.csv"' in html
    assert 'data-pw-granularity="dataset"' in html


def test_show_chart_wraps_with_chart_selection_granularity():
    chart_html = mo.Html("<div>fake-chart</div>")
    wrapped = show_chart(chart_html, artifact_id="art-process-map", artifact_name="Chart_ProcessMap")
    html = wrapped.text
    assert 'data-pw-artifact-id="art-process-map"' in html
    assert 'data-pw-granularity="chart_selection"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_display.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'provenance_widget.display'`

- [ ] **Step 3: Write the implementation**

```python
# provenance_widget/display.py
from __future__ import annotations

import marimo as mo


def _wrap(inner_html: str, artifact_id: str, artifact_name: str, granularity: str) -> mo.Html:
    return mo.Html(
        f'<div class="pw-annotatable" '
        f'data-pw-artifact-id="{artifact_id}" '
        f'data-pw-artifact-name="{artifact_name}" '
        f'data-pw-granularity="{granularity}">'
        f"{inner_html}"
        f"</div>"
    )


def show_table(table: "mo.ui.table", artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(table.text, artifact_id, artifact_name, granularity="dataset")


def show_chart(chart_html: mo.Html, artifact_id: str, artifact_name: str) -> mo.Html:
    return _wrap(chart_html.text, artifact_id, artifact_name, granularity="chart_selection")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_display.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/display.py tests/test_display.py
git commit -m "feat: add show_table/show_chart wrappers that tag artifacts for the picker"
```

---

### Task 8: Frontend shared components (node card, tag chip, artifact badge, segmented control)

**Files:**
- Create: `frontend/src/components/tag-chip.ts`
- Create: `frontend/src/components/artifact-badge.ts`
- Create: `frontend/src/components/node-card.ts`
- Create: `frontend/src/components/segmented-control.ts`
- Create: `frontend/src/types.ts`

**Interfaces:**
- Produces (in `types.ts`, matching Task 4's JSON shape exactly):
  ```typescript
  export interface Delta {
    columnsAdded: { name: string; dtype: string }[];
    columnsRemoved: { name: string; dtype: string }[];
    rowCountBefore: number;
    rowCountAfter: number;
    summary: string;
  }
  export interface ArtifactRefJson {
    artifactId: string; artifactName: string; granularity: string; detail: string | null;
  }
  export interface TagJson { name: string; color: string; }
  export interface AnnotationJson {
    annotationId: string; title: string; note: string;
    tags: TagJson[]; artifacts: ArtifactRefJson[];
    author: { agent_id: string; agent_type: string; display_name: string };
    timestamp: string;
  }
  export interface OperationJson {
    operationId: string; name: string; operationType: string;
    commandName: string; category: string;
  }
  export interface ProvenanceNodeJson {
    stateId: string; parentStateId: string | null; branchId: string;
    operation: OperationJson; params: Record<string, unknown>;
    delta: Delta; annotations: AnnotationJson[];
  }
  export interface ProvenanceTreeJson {
    rootId: string; branches: Record<string, string>;
    nodes: Record<string, ProvenanceNodeJson>;
  }
  export const CATEGORY_COLOR: Record<string, string> = {
    CLEANING: "#0EA5E9", FEATURE_ENGINEERING: "#10B981", ANALYSIS: "#F59E0B",
    COMPARISON: "#F43F5E", DATA_LOADING: "#8B5CF6", AGGREGATION: "#8B5CF6",
  };
  ```
  `tag-chip.ts` exports `function tagChip(tag: TagJson): HTMLElement`.
  `artifact-badge.ts` exports `function artifactBadge(ref: ArtifactRefJson): HTMLElement`.
  `node-card.ts` exports `function nodeCard(node: ProvenanceNodeJson, opts?: { onSelect?: () => void }): HTMLElement`.
  `segmented-control.ts` exports `function segmentedControl(options: string[], active: string, onChange: (value: string) => void): HTMLElement`.

- [ ] **Step 1: Write `frontend/src/types.ts`** (exact content shown in Interfaces above)

- [ ] **Step 2: Write `frontend/src/components/tag-chip.ts`**

```typescript
import type { TagJson } from "../types";

export function tagChip(tag: TagJson): HTMLElement {
  const el = document.createElement("span");
  el.className = "pw-tag-chip";
  el.textContent = `#${tag.name}`;
  el.style.setProperty("--chip-color", tag.color);
  return el;
}
```

- [ ] **Step 3: Write `frontend/src/components/artifact-badge.ts`**

```typescript
import type { ArtifactRefJson } from "../types";

const GRANULARITY_LABEL: Record<string, string> = {
  dataset: "Whole dataset",
  column: "Column",
  row_subset: "Row subset",
  cell: "Cell",
  chart_selection: "Chart selection",
};

export function artifactBadge(ref: ArtifactRefJson): HTMLElement {
  const el = document.createElement("span");
  el.className = "pw-artifact-badge";
  const label = GRANULARITY_LABEL[ref.granularity] ?? ref.granularity;
  el.textContent = ref.detail
    ? `${ref.artifactName} · ${label}: ${ref.detail}`
    : `${ref.artifactName} · ${label}`;
  el.dataset.artifactId = ref.artifactId;
  return el;
}
```

- [ ] **Step 4: Write `frontend/src/components/node-card.ts`**

```typescript
import type { ProvenanceNodeJson } from "../types";
import { CATEGORY_COLOR } from "../types";
import { tagChip } from "./tag-chip";
import { artifactBadge } from "./artifact-badge";

export function nodeCard(
  node: ProvenanceNodeJson,
  opts: { onSelect?: () => void } = {},
): HTMLElement {
  const card = document.createElement("div");
  card.className = "pw-node-card";
  card.dataset.stateId = node.stateId;
  card.style.setProperty("--category-color", CATEGORY_COLOR[node.operation.category] ?? "#64748B");

  const badge = document.createElement("div");
  badge.className = "pw-op-badge";
  badge.textContent = node.operation.category.replace("_", " ");
  card.appendChild(badge);

  const annotation = node.annotations[0];
  const title = document.createElement("div");
  title.className = "pw-node-title";
  title.textContent = annotation ? annotation.title : node.operation.name;
  card.appendChild(title);

  if (annotation) {
    const note = document.createElement("div");
    note.className = "pw-node-note";
    note.textContent = annotation.note;
    card.appendChild(note);

    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    annotation.tags.forEach((t) => tags.appendChild(tagChip(t)));
    card.appendChild(tags);

    const artifacts = document.createElement("div");
    artifacts.className = "pw-node-artifacts";
    annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
    card.appendChild(artifacts);
  }

  if (opts.onSelect) {
    card.addEventListener("click", opts.onSelect);
  }

  return card;
}
```

- [ ] **Step 5: Write `frontend/src/components/segmented-control.ts`**

```typescript
export function segmentedControl(
  options: string[],
  active: string,
  onChange: (value: string) => void,
): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "pw-segmented-control";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.textContent = opt;
    btn.className = opt === active ? "pw-segment pw-segment-active" : "pw-segment";
    btn.addEventListener("click", () => onChange(opt));
    wrap.appendChild(btn);
  });
  return wrap;
}
```

- [ ] **Step 6: Build and verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors, "build complete" printed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/
git commit -m "feat: add shared frontend components (node card, tag chip, artifact badge, segmented control)"
```

---

### Task 9: Curated tab view (commit rail + composer)

**Files:**
- Create: `frontend/src/views/curated.ts`

**Interfaces:**
- Consumes: `nodeCard`, `AnnotationJson`, `TagJson`, `ProvenanceTreeJson` from Task 8; `AnyModel` shape from Task 5's `main.ts`.
- Produces: `function renderCurated(container: HTMLElement, model: AnyModel): void` — renders the commit rail (all nodes' annotations, newest first by `timestamp`) + a composer form at the bottom that calls `model.set("commits", [...model.get("commits"), newAnnotation]); model.save_changes();` on submit. In `mode === "reviewer"`, the composer is omitted and each rendered annotation with tags shows a "Restore to @tag" button per tag instead.

- [ ] **Step 1: Write `frontend/src/views/curated.ts`**

```typescript
import type { AnnotationJson, ProvenanceTreeJson } from "../types";
import { tagChip } from "../components/tag-chip";
import { artifactBadge } from "../components/artifact-badge";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function allAnnotationsNewestFirst(tree: ProvenanceTreeJson): { stateId: string; annotation: AnnotationJson }[] {
  const rows: { stateId: string; annotation: AnnotationJson }[] = [];
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      rows.push({ stateId: node.stateId, annotation });
    }
  }
  for (const commit of model_commits) rows.push(commit);
  return rows.sort((a, b) => (a.annotation.timestamp < b.annotation.timestamp ? 1 : -1));
}

let model_commits: { stateId: string; annotation: AnnotationJson }[] = [];

function renderCommitCard(row: { stateId: string; annotation: AnnotationJson }, mode: string): HTMLElement {
  const card = document.createElement("div");
  card.className = "pw-commit-card";
  card.dataset.stateId = row.stateId;

  const title = document.createElement("div");
  title.className = "pw-node-title";
  title.textContent = row.annotation.title;
  card.appendChild(title);

  const tags = document.createElement("div");
  tags.className = "pw-node-tags";
  row.annotation.tags.forEach((t) => {
    const chip = tagChip(t);
    if (mode === "reviewer") {
      const restoreBtn = document.createElement("button");
      restoreBtn.className = "pw-restore-btn";
      restoreBtn.textContent = `Restore to @${t.name}`;
      chip.appendChild(restoreBtn);
    }
    tags.appendChild(chip);
  });
  card.appendChild(tags);

  const artifacts = document.createElement("div");
  artifacts.className = "pw-node-artifacts";
  row.annotation.artifacts.forEach((a) => artifacts.appendChild(artifactBadge(a)));
  card.appendChild(artifacts);

  return card;
}

function renderComposer(container: HTMLElement, model: AnyModel): HTMLElement {
  const composer = document.createElement("div");
  composer.className = "pw-composer";

  const noteField = document.createElement("textarea");
  noteField.placeholder = "Describe reasoning for this analytical step...";
  composer.appendChild(noteField);

  const tagField = document.createElement("input");
  tagField.placeholder = "#tags";
  composer.appendChild(tagField);

  const commitBtn = document.createElement("button");
  commitBtn.className = "pw-commit-btn";
  commitBtn.textContent = "Commit annotation";
  commitBtn.addEventListener("click", () => {
    const selection = model.get("selection") as Record<string, unknown>;
    const newAnnotation: AnnotationJson = {
      annotationId: `ann-${Date.now()}`,
      title: noteField.value.slice(0, 40) || "Untitled annotation",
      note: noteField.value,
      tags: tagField.value
        .split(" ")
        .filter(Boolean)
        .map((name) => ({ name: name.replace(/^#/, ""), color: "#64748B" })),
      artifacts: selection.artifactId
        ? [{
            artifactId: String(selection.artifactId),
            artifactName: String(selection.artifactName ?? ""),
            granularity: String(selection.granularity ?? "dataset"),
            detail: (selection.detail as string) ?? null,
          }]
        : [],
      author: { agent_id: "agent-student", agent_type: "human", display_name: "S" },
      timestamp: new Date().toISOString(),
    };
    const existing = model.get("commits") as unknown[];
    model.set("commits", [...existing, { stateId: "composer", annotation: newAnnotation }]);
    model.save_changes();
    noteField.value = "";
    tagField.value = "";
  });
  composer.appendChild(commitBtn);

  return composer;
}

export function renderCurated(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const mode = model.get("mode") as string;
  model_commits = model.get("commits") as { stateId: string; annotation: AnnotationJson }[];

  const rail = document.createElement("div");
  rail.className = "pw-commit-rail";
  allAnnotationsNewestFirst(tree).forEach((row) => rail.appendChild(renderCommitCard(row, mode)));
  container.appendChild(rail);

  if (mode === "student") {
    container.appendChild(renderComposer(container, model));
  }
}
```

- [ ] **Step 2: Build and verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/curated.ts
git commit -m "feat: add Curated tab commit rail and composer"
```

---

### Task 10: Tree tab (Miller columns + artifact legend + cross-highlight)

**Files:**
- Create: `frontend/src/views/tree.ts`

**Interfaces:**
- Consumes: `nodeCard`, `ProvenanceTreeJson` from Task 8; `AnyModel` shape.
- Produces: `function renderTree(container: HTMLElement, model: AnyModel): void` — renders breadcrumb, artifact legend, and horizontally-scrolling Miller columns. Clicking a `nodeCard` appends its children as the next column and updates the breadcrumb. Clicking a legend entry toggles `pw-dimmed` class on node cards whose annotations don't reference that artifact.

- [ ] **Step 1: Write `frontend/src/views/tree.ts`**

```typescript
import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { nodeCard } from "../components/node-card";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

function collectArtifacts(tree: ProvenanceTreeJson): { id: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const node of Object.values(tree.nodes)) {
    for (const annotation of node.annotations) {
      for (const ref of annotation.artifacts) {
        seen.set(ref.artifactId, ref.artifactName);
      }
    }
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }));
}

function nodeTouchesArtifact(node: ProvenanceNodeJson, artifactId: string): boolean {
  return node.annotations.some((a) => a.artifacts.some((r) => r.artifactId === artifactId));
}

export function renderTree(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  container.appendChild(breadcrumb);

  const legend = document.createElement("div");
  legend.className = "pw-artifact-legend";
  let activeArtifact: string | null = null;
  collectArtifacts(tree).forEach((artifact) => {
    const entry = document.createElement("button");
    entry.className = "pw-legend-entry";
    entry.textContent = artifact.name;
    entry.addEventListener("click", () => {
      activeArtifact = activeArtifact === artifact.id ? null : artifact.id;
      applyDimming();
    });
    legend.appendChild(entry);
  });
  container.appendChild(legend);

  const columnsWrap = document.createElement("div");
  columnsWrap.className = "pw-columns";
  container.appendChild(columnsWrap);

  const path: string[] = [tree.rootId];

  function applyDimming(): void {
    columnsWrap.querySelectorAll<HTMLElement>(".pw-node-card").forEach((card) => {
      const stateId = card.dataset.stateId!;
      const node = tree.nodes[stateId];
      const dim = activeArtifact !== null && !nodeTouchesArtifact(node, activeArtifact);
      card.classList.toggle("pw-dimmed", dim);
    });
  }

  function renderBreadcrumb(): void {
    breadcrumb.innerHTML = "";
    path.forEach((stateId, i) => {
      const node = tree.nodes[stateId];
      const crumb = document.createElement("span");
      crumb.className = "pw-breadcrumb-item";
      crumb.textContent = node.annotations[0]?.title ?? node.operation.name;
      breadcrumb.appendChild(crumb);
      if (i < path.length - 1) {
        const sep = document.createElement("span");
        sep.className = "pw-breadcrumb-sep";
        sep.textContent = ">";
        breadcrumb.appendChild(sep);
      }
    });
  }

  function renderColumns(): void {
    columnsWrap.innerHTML = "";
    path.forEach((stateId, columnIndex) => {
      const column = document.createElement("div");
      column.className = "pw-column";
      const children =
        columnIndex === 0
          ? [tree.nodes[stateId]]
          : Object.values(tree.nodes).filter((n) => n.parentStateId === path[columnIndex - 1]);
      children.forEach((node) => {
        const card = nodeCard(node, {
          onSelect: () => {
            path.splice(columnIndex + 1, path.length, node.stateId);
            model.set("selection", { pickedStateId: node.stateId });
            model.save_changes();
            renderBreadcrumb();
            renderColumns();
            applyDimming();
          },
        });
        column.appendChild(card);
      });
      columnsWrap.appendChild(column);
    });
    applyDimming();
  }

  renderBreadcrumb();
  renderColumns();
}
```

- [ ] **Step 2: Build and verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/tree.ts
git commit -m "feat: add Tree tab Miller-columns outliner with artifact legend"
```

---

### Task 11: Inspect tab (diff view)

**Files:**
- Create: `frontend/src/views/inspect.ts`

**Interfaces:**
- Consumes: `ProvenanceTreeJson`, `ProvenanceNodeJson`, `Delta` types from Task 8.
- Produces: `function renderInspect(container: HTMLElement, model: AnyModel): void` — shows the reproduction-recipe breadcrumb for `model.get("selection").pickedStateId` (falls back to the tree root if unset), a green/red-coded delta list vs. the parent node, and the annotation/tags panel.

- [ ] **Step 1: Write `frontend/src/views/inspect.ts`**

```typescript
import type { ProvenanceNodeJson, ProvenanceTreeJson } from "../types";
import { tagChip } from "../components/tag-chip";

interface AnyModel {
  get(key: string): unknown;
}

function reproductionPath(tree: ProvenanceTreeJson, stateId: string): ProvenanceNodeJson[] {
  const path: ProvenanceNodeJson[] = [];
  let current: string | null = stateId;
  while (current) {
    const node: ProvenanceNodeJson = tree.nodes[current];
    path.unshift(node);
    current = node.parentStateId;
  }
  return path;
}

export function renderInspect(container: HTMLElement, model: AnyModel): void {
  container.innerHTML = "";
  const tree = model.get("tree") as ProvenanceTreeJson;
  const selection = (model.get("selection") as { pickedStateId?: string }) ?? {};
  const stateId = selection.pickedStateId ?? tree.rootId;
  const node = tree.nodes[stateId];

  const breadcrumb = document.createElement("div");
  breadcrumb.className = "pw-breadcrumb";
  breadcrumb.textContent = reproductionPath(tree, stateId)
    .map((n) => n.operation.commandName)
    .join(" -> ");
  container.appendChild(breadcrumb);

  const diffPane = document.createElement("div");
  diffPane.className = "pw-diff-pane";
  node.delta.columnsAdded.forEach((c) => {
    const line = document.createElement("div");
    line.className = "pw-diff-line pw-diff-added";
    line.textContent = `+ ${c.name}: ${c.dtype}`;
    diffPane.appendChild(line);
  });
  node.delta.columnsRemoved.forEach((c) => {
    const line = document.createElement("div");
    line.className = "pw-diff-line pw-diff-removed";
    line.textContent = `- ${c.name}: ${c.dtype}`;
    diffPane.appendChild(line);
  });
  const rowLine = document.createElement("div");
  rowLine.className = "pw-diff-line";
  rowLine.textContent = `rows: ${node.delta.rowCountBefore} -> ${node.delta.rowCountAfter}`;
  diffPane.appendChild(rowLine);
  container.appendChild(diffPane);

  const annotationPane = document.createElement("div");
  annotationPane.className = "pw-annotation-pane";
  node.annotations.forEach((a) => {
    const title = document.createElement("div");
    title.className = "pw-node-title";
    title.textContent = a.title;
    annotationPane.appendChild(title);
    const note = document.createElement("div");
    note.className = "pw-node-note";
    note.textContent = a.note;
    annotationPane.appendChild(note);
    const tags = document.createElement("div");
    tags.className = "pw-node-tags";
    a.tags.forEach((t) => tags.appendChild(tagChip(t)));
    annotationPane.appendChild(tags);
  });
  container.appendChild(annotationPane);
}
```

- [ ] **Step 2: Build and verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/inspect.ts
git commit -m "feat: add Inspect tab diff view"
```

---

### Task 12: Notebook picker (document-level "pick from notebook")

**Files:**
- Create: `frontend/src/picker.ts`

**Interfaces:**
- Consumes: `AnyModel` shape.
- Produces: `function armPicker(model: AnyModel, onPicked: (selection: { artifactId: string; artifactName: string; granularity: string; detail: string | null }) => void): void` — attaches one-shot `mousemove`/`click` listeners on `document`, highlighting (`pw-picker-hover` class) the nearest ancestor with `data-pw-artifact-id` under the cursor, and on click reads that ancestor's `data-pw-*` attributes, removes the listeners, and calls `onPicked`.

- [ ] **Step 1: Write `frontend/src/picker.ts`**

```typescript
interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
}

interface PickedSelection {
  artifactId: string;
  artifactName: string;
  granularity: string;
  detail: string | null;
}

function findTaggedAncestor(el: EventTarget | null): HTMLElement | null {
  let node = el as HTMLElement | null;
  while (node) {
    if (node.dataset && node.dataset.pwArtifactId) return node;
    node = node.parentElement;
  }
  return null;
}

export function armPicker(model: AnyModel, onPicked: (selection: PickedSelection) => void): void {
  let lastHovered: HTMLElement | null = null;

  function onMouseMove(evt: MouseEvent): void {
    const target = findTaggedAncestor(evt.target);
    if (lastHovered && lastHovered !== target) {
      lastHovered.classList.remove("pw-picker-hover");
    }
    if (target) {
      target.classList.add("pw-picker-hover");
    }
    lastHovered = target;
  }

  function onClick(evt: MouseEvent): void {
    const target = findTaggedAncestor(evt.target);
    cleanup();
    if (!target) return;
    evt.preventDefault();
    evt.stopPropagation();
    onPicked({
      artifactId: target.dataset.pwArtifactId!,
      artifactName: target.dataset.pwArtifactName ?? "",
      granularity: target.dataset.pwGranularity ?? "dataset",
      detail: target.dataset.pwDetail ?? null,
    });
  }

  function cleanup(): void {
    document.removeEventListener("mousemove", onMouseMove, true);
    document.removeEventListener("click", onClick, true);
    if (lastHovered) lastHovered.classList.remove("pw-picker-hover");
  }

  document.addEventListener("mousemove", onMouseMove, true);
  document.addEventListener("click", onClick, true);
}
```

- [ ] **Step 2: Build and verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/picker.ts
git commit -m "feat: add document-level pick-from-notebook artifact picker"
```

---

### Task 13: Wire main.ts (tab routing, mode, restore banner) and full CSS

**Files:**
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/theme.css`

**Interfaces:**
- Consumes: `renderCurated`, `renderTree`, `renderInspect`, `armPicker`, `segmentedControl`, `CATEGORY_COLOR`.
- Produces: full `render({ model, el })` that mounts the segmented control, routes to the three views based on `model.get("active_tab")`, re-renders on `model.on("change:tree", ...)` / `change:mode` / `change:active_tab` / `change:commits`, shows a "Pick from notebook" button in the composer area that calls `armPicker`, and in reviewer mode shows a restore confirmation banner when `model.get("restore_request")` is non-empty.

- [ ] **Step 1: Rewrite `frontend/src/main.ts`**

```typescript
import "./theme.css";
import { segmentedControl } from "./components/segmented-control";
import { renderCurated } from "./views/curated";
import { renderTree } from "./views/tree";
import { renderInspect } from "./views/inspect";
import { armPicker } from "./picker";

interface AnyModel {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  save_changes(): void;
  on(event: string, callback: () => void): void;
}

function render({ model, el }: { model: AnyModel; el: HTMLElement }): void {
  el.innerHTML = "";
  const root = document.createElement("div");
  root.className = "pw-root";
  el.appendChild(root);

  const tabs = document.createElement("div");
  root.appendChild(tabs);

  const restoreBanner = document.createElement("div");
  restoreBanner.className = "pw-restore-banner";
  restoreBanner.style.display = "none";
  root.appendChild(restoreBanner);

  const body = document.createElement("div");
  body.className = "pw-body";
  root.appendChild(body);

  const pickerRow = document.createElement("div");
  pickerRow.className = "pw-picker-row";
  const pickBtn = document.createElement("button");
  pickBtn.className = "pw-pick-btn";
  pickBtn.textContent = "Pick from notebook";
  pickBtn.addEventListener("click", () => {
    armPicker(model, (selection) => {
      model.set("selection", selection);
      model.save_changes();
      renderBody();
    });
  });
  pickerRow.appendChild(pickBtn);

  function renderTabs(): void {
    tabs.innerHTML = "";
    const activeTab = model.get("active_tab") as string;
    tabs.appendChild(
      segmentedControl(["curated", "tree", "inspect"], activeTab, (value) => {
        model.set("active_tab", value);
        model.save_changes();
      }),
    );
  }

  function renderRestoreBanner(): void {
    const request = model.get("restore_request") as { tag?: string };
    if (model.get("mode") === "reviewer" && request && request.tag) {
      restoreBanner.style.display = "block";
      restoreBanner.textContent = `Restoring parameters to @${request.tag} — dependent marimo cells will re-run reactively.`;
    } else {
      restoreBanner.style.display = "none";
    }
  }

  function renderBody(): void {
    const activeTab = model.get("active_tab") as string;
    body.innerHTML = "";
    const view = document.createElement("div");
    body.appendChild(view);
    if (activeTab === "curated") {
      renderCurated(view, model);
      if (model.get("mode") === "student") body.appendChild(pickerRow);
    } else if (activeTab === "tree") {
      renderTree(view, model);
    } else {
      renderInspect(view, model);
    }
  }

  renderTabs();
  renderRestoreBanner();
  renderBody();

  model.on("change:active_tab", () => {
    renderTabs();
    renderBody();
  });
  model.on("change:mode", () => {
    renderBody();
    renderRestoreBanner();
  });
  model.on("change:tree", renderBody);
  model.on("change:commits", renderBody);
  model.on("change:restore_request", renderRestoreBanner);
}

export default { render };
```

- [ ] **Step 2: Extend `frontend/src/theme.css` with full component styles**

```css
.pw-root {
  font-family: ui-sans-serif, system-ui, sans-serif;
  color: #0F172A;
  background: #F8FAFC;
  padding: 8px;
  border-radius: 8px;
}
@media (prefers-color-scheme: dark) {
  .pw-root { color: #F8FAFC; background: #0F172A; }
}

.pw-segmented-control { display: flex; gap: 4px; margin-bottom: 8px; }
.pw-segment { border: 1px solid #94A3B8; background: transparent; border-radius: 6px; padding: 4px 10px; cursor: pointer; }
.pw-segment-active { background: #64748B; color: white; }

.pw-node-card, .pw-commit-card {
  border: 1px solid #E2E8F0;
  border-left: 4px solid var(--category-color, #64748B);
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
  cursor: pointer;
  background: white;
}
@media (prefers-color-scheme: dark) {
  .pw-node-card, .pw-commit-card { background: #1E293B; border-color: #334155; }
}
.pw-node-card.pw-dimmed { opacity: 0.25; }
.pw-node-card.pw-picker-hover, .pw-annotatable.pw-picker-hover { outline: 2px solid #F59E0B; }

.pw-op-badge { font-size: 11px; text-transform: uppercase; color: var(--category-color, #64748B); font-weight: 600; }
.pw-node-title { font-weight: 700; margin: 2px 0; }
.pw-node-note { font-size: 12px; color: #64748B; margin-bottom: 4px; }
.pw-node-tags, .pw-node-artifacts { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }

.pw-tag-chip {
  background: color-mix(in srgb, var(--chip-color, #64748B) 20%, transparent);
  color: var(--chip-color, #64748B);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
}
.pw-artifact-badge {
  border: 1px solid #94A3B8;
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 11px;
  font-family: ui-monospace, monospace;
}

.pw-columns { display: flex; overflow-x: auto; gap: 12px; }
.pw-column { min-width: 260px; }
.pw-breadcrumb { font-size: 12px; color: #64748B; margin-bottom: 8px; }
.pw-breadcrumb-sep { margin: 0 6px; }
.pw-artifact-legend { display: flex; gap: 6px; margin-bottom: 8px; }
.pw-legend-entry { border: 1px solid #94A3B8; border-radius: 6px; background: transparent; cursor: pointer; padding: 2px 8px; font-size: 12px; }

.pw-diff-pane { font-family: ui-monospace, monospace; font-size: 12px; margin: 8px 0; }
.pw-diff-added { color: #10B981; }
.pw-diff-removed { color: #F43F5E; }

.pw-composer { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid #E2E8F0; padding-top: 8px; margin-top: 8px; }
.pw-composer textarea { min-height: 60px; }
.pw-commit-btn { background: #0F172A; color: white; border: none; border-radius: 6px; padding: 8px; cursor: pointer; }
@media (prefers-color-scheme: dark) { .pw-commit-btn { background: #F8FAFC; color: #0F172A; } }

.pw-restore-banner { background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 6px; padding: 8px; margin-bottom: 8px; font-size: 13px; }
.pw-pick-btn { border: 1px dashed #94A3B8; background: transparent; border-radius: 6px; padding: 6px; cursor: pointer; margin-top: 4px; }
```

- [ ] **Step 3: Build and verify**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors, `provenance_widget/static/widget.js` and `widget.css` regenerated.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.ts frontend/src/theme.css
git commit -m "feat: wire tab routing, picker, and reviewer restore banner into main.ts"
```

---

### Task 14: Reviewer restore round-trip (Python side)

**Files:**
- Modify: `provenance_widget/widget.py`
- Modify: `tests/test_widget.py`

**Interfaces:**
- Consumes: existing `ProvenancePanel`.
- Produces: `ProvenancePanel.request_restore(self, tag: str) -> None` sets `widget.restore_request = {"tag": tag}`; `ProvenancePanel.acknowledge_restore(self) -> None` sets `widget.restore_ack = {"acknowledged": True}` and clears `restore_request` back to `{}` (simulating the reactive-rebuild completing, per the design doc's "simulated in mock mode" scope).

- [ ] **Step 1: Write the failing test (append to `tests/test_widget.py`)**

```python
def test_request_restore_sets_restore_request_with_tag():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.request_restore("v1.1")
    assert panel.widget.restore_request == {"tag": "v1.1"}


def test_acknowledge_restore_clears_request_and_sets_ack():
    panel = ProvenancePanel(source=MockProvenanceSource(), mode="reviewer")
    panel.request_restore("v1.1")
    panel.acknowledge_restore()
    assert panel.widget.restore_request == {}
    assert panel.widget.restore_ack == {"acknowledged": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_widget.py -v`
Expected: FAIL with `AttributeError: 'ProvenancePanel' object has no attribute 'request_restore'`

- [ ] **Step 3: Add methods to `ProvenancePanel` in `provenance_widget/widget.py`**

```python
    def request_restore(self, tag: str) -> None:
        self.widget.restore_request = {"tag": tag}

    def acknowledge_restore(self) -> None:
        self.widget.restore_ack = {"acknowledged": True}
        self.widget.restore_request = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_widget.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add provenance_widget/widget.py tests/test_widget.py
git commit -m "feat: add simulated reviewer restore round-trip to ProvenancePanel"
```

---

### Task 15: Demo notebook and marimo layout integration

**Files:**
- Create: `examples/demo_notebook.py`

**Interfaces:**
- Consumes: `ProvenancePanel`, `MockProvenanceSource`, `show_table` from prior tasks; `marimo` (`mo.sidebar`, `mo.ui.table`, `mo.md`).

- [ ] **Step 1: Write `examples/demo_notebook.py`**

```python
import marimo

__generated_with = "0.9.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    from provenance_widget.display import show_table
    from provenance_widget.mock_source import MockProvenanceSource
    from provenance_widget.widget import ProvenancePanel

    return MockProvenanceSource, ProvenancePanel, mo, pd, show_table


@app.cell
def _(MockProvenanceSource, ProvenancePanel, mo):
    mode_toggle = mo.ui.radio(options=["student", "reviewer"], value="student", label="Persona")
    panel = ProvenancePanel(source=MockProvenanceSource(), mode=mode_toggle.value)
    return mode_toggle, panel


@app.cell
def _(mo, panel):
    sidebar = mo.sidebar(panel.sidebar())
    return (sidebar,)


@app.cell
def _(mo, pd, show_table):
    event_log = pd.DataFrame({
        "case:concept:name": ["c1", "c1", "c2"],
        "concept:name": ["Register", "Approve", "Register"],
        "duration": [12.5, 40.2, 8.1],
    })
    table = mo.ui.table(event_log)
    annotated_table = show_table(table, artifact_id="art-event-log", artifact_name="event_log.csv")
    annotated_table
    return (event_log,)


@app.cell
def _(mode_toggle, sidebar, panel):
    mode_toggle
    sidebar
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Smoke-test the notebook runs under marimo**

Run: `python -m marimo run examples/demo_notebook.py --headless --port 0` (or `marimo edit examples/demo_notebook.py` interactively)
Expected: notebook starts without exceptions; if run headlessly, kill the process after confirming no traceback in the first few seconds of output.

- [ ] **Step 3: Commit**

```bash
git add examples/demo_notebook.py
git commit -m "docs: add demo marimo notebook using ProvenancePanel with mock data"
```

---

### Task 16: Package the frontend bundle and finish README

**Files:**
- Modify: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Produces: a committed `provenance_widget/static/widget.js` + `widget.css` (the shippable bundle) and a README covering installation into marimo, including the pmprov-extra note from the design doc.

- [ ] **Step 1: Rebuild the frontend bundle for shipping**

Run: `cd frontend && npm run build`
Expected: `provenance_widget/static/widget.js` and `widget.css` produced (minified, no sourcemap since `--watch` is not passed).

- [ ] **Step 2: Remove the bundle from `.gitignore`**

In `.gitignore`, delete these three lines added in Task 5:
```
provenance_widget/static/widget.js
provenance_widget/static/widget.css
provenance_widget/static/widget.js.map
```

- [ ] **Step 3: Write `README.md`**

```markdown
# marimo-pmprov

A marimo `anywidget` plugin that gives process-mining analysts a git-style
"Source Control" sidebar for analytic provenance and annotation: a curated
commit rail, a Miller-columns provenance tree, a diff inspector, and a
read-only Reviewer mode with tag-based state restore.

This package ships fully decoupled from the `pmprov` library — it runs out
of the box against a `MockProvenanceSource` whose data is shaped exactly
like pmprov's real model (see `provenance_widget/interfaces.py`), so no
`pmprov` install is required to try it or to develop against it.

## Install

```bash
pip install marimo-pmprov
```

This installs the widget with its `MockProvenanceSource` demo backend. See
`examples/demo_notebook.py` for a runnable notebook.

## Using it in a marimo notebook

```python
import marimo as mo
from provenance_widget.mock_source import MockProvenanceSource
from provenance_widget.widget import ProvenancePanel
from provenance_widget.display import show_table

panel = ProvenancePanel(source=MockProvenanceSource(), mode="student")
sidebar = mo.sidebar(panel.sidebar())

# tag any displayed table so the sidebar's "Pick from notebook" picker can target it
annotated_table = show_table(mo.ui.table(my_dataframe), artifact_id="art-1", artifact_name="my_dataframe")
```

## Connecting a real pmprov-backed history

The widget only depends on the `ProvenanceSource` protocol
(`provenance_widget.interfaces.ProvenanceSource`) — it never imports
`pmprov` directly. To back the sidebar with a real `pmprov.AnalysisHistory`
instead of mock data:

1. Implement a `PmprovAdapter` class with a `get_tree(self) -> ProvenanceTree`
   method that translates `AnalysisHistory.list_states()` /
   `ProvenanceTracker` data into the `ProvenanceTree` dataclasses in
   `provenance_widget/interfaces.py` (field names already mirror pmprov's
   model, per pmprov's `MODEL.md`). `Annotation`/`Tag` are new concepts not
   present in pmprov — the adapter is where you decide how they're sourced
   or persisted against a real history.
2. Install this package with the `pmprov` extra, which pins a specific
   pmprov version as a runtime dependency:

   ```bash
   pip install "marimo-pmprov[pmprov]"
   ```

   (Update the pinned `pmprov @ git+https://github.com/<org>/pmprov.git@vX.Y.Z`
   reference in `pyproject.toml` to the version you intend to depend on
   before installing.)
3. Pass your adapter instead of `MockProvenanceSource` to `ProvenancePanel`.

## Development

```bash
pip install -e ".[dev]"
pytest

cd frontend
npm install
npm run build   # or: npm run watch
```
```

- [ ] **Step 4: Verify final test suite and frontend build both pass**

Run: `pytest -v` and `cd frontend && npx tsc --noEmit && npm run build`
Expected: all Python tests pass, no TypeScript errors, build succeeds.

- [ ] **Step 5: Verify no pmprov import anywhere in the shipped package**

Run: `grep -rn "import pmprov\|from pmprov" provenance_widget/`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md provenance_widget/static/widget.js provenance_widget/static/widget.css
git commit -m "docs: add README and ship built frontend bundle"
```

---

## Self-Review Notes

- **Spec coverage:** sidebar + Curated/Tree/Inspect segmented control (Tasks 6, 13), commit rail + composer (Task 9), Miller columns + artifact legend + cross-highlight (Task 10), gutter "+"/picker affordances (Tasks 7, 12), Inspect diff view (Task 11), Reviewer mode + restore banner (Tasks 13–14), pmprov-shaped mock data (Tasks 2–3), decoupling via `ProvenanceSource` (Task 2), README install instructions incl. pmprov extra (Task 16). "Raw interactions toggle" from the original mockup brief is out of scope for this functional-mock-data iteration (there are no raw/automatic interaction events in the mock source to hide) — noted here rather than silently dropped.
- **Type consistency:** `ProvenanceTreeJson`/`ProvenanceNodeJson`/`AnnotationJson` field names in `types.ts` (Task 8) match `tree_to_json`'s output keys (Task 4) exactly (`stateId`, `parentStateId`, `operationId`, `operationType`, `commandName`, `rowCountBefore`, etc.) — verified by cross-reading both tasks.
- **Placeholder scan:** no TBD/TODO markers; every step has runnable code.
