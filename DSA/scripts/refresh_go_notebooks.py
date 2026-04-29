#!/usr/bin/env python3
"""
Rebuild topic notebooks under DSA/GoDSA (maintainer tool).

Markdown cells are copied and lightly adjusted for this track. Code cells become one Go cell
with a block comment and generated Go. `*_solutions.ipynb` uses a solution emitter (working Go
when translation succeeds, otherwise `//` reference steps plus a default return) so explanations
stay in markdown and implementations stay visible in code.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from go_solution_emitter import emit_solution_function_go

# refresh_go_notebooks.py lives at DSA/scripts/ → repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
PY_DSA = ROOT / "DSA" / "PythonDSA"
GO_DSA = ROOT / "DSA" / "GoDSA"

GO_META = {
    "kernelspec": {"display_name": "Go", "language": "go", "name": "go"},
    "language_info": {
        "name": "go",
        "file_extension": ".go",
        "mimetype": "text/x-go",
        "pygments_lexer": "go",
    },
}

HEADER = """\
import (
	"fmt"
	"reflect"
	"strings"
	"unicode"
)

func mapHasIntInt(m map[int]int, k int) bool {
	_, ok := m[k]
	return ok
}

func mapHasByteInt(m map[byte]int, k byte) bool {
	_, ok := m[k]
	return ok
}

func eq(msg string, a, b interface{}) {
	if !reflect.DeepEqual(a, b) {
		panic(fmt.Sprintf("%s: %#v != %#v", msg, a, b))
	}
}

func isNil(msg string, v interface{}) {
	if v == nil {
		return
	}
	rv := reflect.ValueOf(v)
	switch rv.Kind() {
	case reflect.Ptr, reflect.Map, reflect.Slice, reflect.Interface, reflect.Chan, reflect.Func:
		if rv.IsNil() {
			return
		}
	}
	panic(msg)
}
"""


def snake_to_exported(name: str) -> str:
    parts = name.split("_")
    return "".join(p[:1].upper() + p[1:] for p in parts)


def unwrap_slice(node: ast.expr) -> ast.expr:
    if isinstance(node, ast.Tuple) and node.elts:
        return node.elts[0]
    return node


def annotation_to_go(ann: ast.expr | None) -> str:
    if ann is None:
        return ""
    if isinstance(ann, ast.Constant) and ann.value is None:
        return ""
    if isinstance(ann, ast.Name):
        if ann.id == "list":
            return "[]interface{}"
        return {
            "int": "int",
            "str": "string",
            "bool": "bool",
            "float": "float64",
        }.get(ann.id, ann.id)
    if isinstance(ann, ast.Subscript):
        val = ann.value
        sl = unwrap_slice(ann.slice)
        if isinstance(val, ast.Name) and val.id == "Optional":
            inner = annotation_to_go(sl)
            return "*" + inner.lstrip("*")
        if isinstance(val, ast.Name) and val.id == "List":
            inner = annotation_to_go(sl)
            if inner == "int":
                return "[]int"
            if inner == "string" or inner == "str":
                return "[]string"
            return "[]" + inner
        if isinstance(val, ast.Name) and val.id == "list":
            inner = unwrap_slice(sl)
            if isinstance(inner, ast.Name) and inner.id == "int":
                return "[]int"
            if isinstance(inner, ast.Name) and inner.id == "str":
                return "[]string"
            if isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name) and inner.value.id == "list":
                inner2 = unwrap_slice(inner.slice)
                if isinstance(inner2, ast.Name) and inner2.id == "int":
                    return "[][]int"
                if isinstance(inner2, ast.Name) and inner2.id == "str":
                    return "[][]string"
            j = annotation_to_go(inner)
            if j == "[]int":
                return "[][]int"
            if j == "int":
                return "[]int"
            if j == "string":
                return "[]string"
            return "[]" + j
        if isinstance(val, ast.Name) and val.id == "dict":
            return "map[string]interface{}"
    if isinstance(ann, ast.Tuple):
        return "interface{}"
    return "interface{}"


def params_to_go(args: ast.arguments, skip_self: bool = True) -> str:
    parts: list[str] = []
    for a in args.args:
        if skip_self and a.arg == "self":
            continue
        ann = a.annotation
        gt = annotation_to_go(ann) if ann else "interface{}"
        parts.append(f"{a.arg} {gt}")
    return ", ".join(parts)


def stmt_to_go_body(stmts: list[ast.stmt], indent: str = "\t") -> str:
    lines: list[str] = []
    for st in stmts:
        if isinstance(st, ast.Pass):
            lines.append(indent + 'panic("TODO")')
        elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        elif isinstance(st, ast.Raise):
            lines.append(indent + 'panic("TODO")')
        elif isinstance(st, ast.Return) and st.value is None:
            lines.append(indent + "return")
        else:
            lines.append(indent + "// TODO: implement from specification above")
            break
    if not lines:
        lines.append(indent + 'panic("TODO")')
    return "\n".join(lines)


def function_to_go(fn: ast.FunctionDef) -> str:
    ret = annotation_to_go(fn.returns)
    name = snake_to_exported(fn.name)
    params = params_to_go(fn.args, skip_self=True)
    body = stmt_to_go_body(fn.body)
    if ret:
        return f"func {name}({params}) {ret} {{\n{body}\n}}"
    return f"func {name}({params}) {{\n{body}\n}}"


def class_to_go(cls: ast.ClassDef) -> str:
    if cls.name == "Node":
        return """type Node struct {
	Val       int
	Neighbors []*Node
}
"""
    if cls.name == "TreeNode":
        return """type TreeNode struct {
	Val   int
	Left  *TreeNode
	Right *TreeNode
}
"""
    lines = [f"type {cls.name} struct {{"]
    for item in cls.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            gt = annotation_to_go(item.annotation) if item.annotation else "interface{}"
            lines.append(f"\t{item.target.id} {gt}")
        elif isinstance(item, ast.FunctionDef) and item.name == "__init__":
            continue
        elif isinstance(item, ast.Pass):
            continue
    lines.append("}")
    return "\n".join(lines) + "\n"


def _const_go(e: ast.expr) -> str | None:
    if isinstance(e, ast.Constant):
        v = e.value
        if v is None:
            return "nil"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v)
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        inner = _const_go(e.operand)
        return "-" + inner if inner else None
    return None


def _list_needs_iface(node: ast.List) -> bool:
    for e in node.elts:
        if isinstance(e, ast.Constant) and e.value is None:
            return True
        if isinstance(e, ast.List) and _list_needs_iface(e):
            return True
        if not isinstance(e, ast.Constant):
            return True
        if not isinstance(e.value, int):
            return True
    return False


def _list_to_go_grid_strings(node: ast.List) -> str | None:
    if not node.elts or not all(isinstance(e, ast.List) for e in node.elts):
        return None
    rows: list[str] = []
    for row in node.elts:
        assert isinstance(row, ast.List)
        if not all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in row.elts):
            return None
        cells = ", ".join(json.dumps(x.value) for x in row.elts)
        rows.append("{" + cells + "}")
    return "[][]string{" + ", ".join(rows) + "}"


def _list_to_go_int(node: ast.List) -> str | None:
    if not all(isinstance(e, ast.Constant) and isinstance(e.value, int) for e in node.elts):
        return None
    return "[]int{" + ", ".join(str(e.value) for e in node.elts) + "}"


def _list_to_go_iface_flat(node: ast.List) -> str | None:
    parts: list[str] = []
    for e in node.elts:
        if isinstance(e, ast.List):
            inner = _list_to_go_iface_flat(e)
            if inner is None:
                return None
            parts.append(inner)
            continue
        c = _const_go(e)
        if c is not None:
            parts.append(c)
            continue
        return None
    return "[]interface{}{" + ", ".join(parts) + "}"


def py_literal_to_go_expr(node: ast.expr, iface_list: bool = False) -> str | None:
    if isinstance(node, ast.Constant):
        v = node.value
        if v is None:
            return "nil"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v)
    if isinstance(node, ast.List):
        g = _list_to_go_grid_strings(node)
        if g is not None:
            return g
        if iface_list or _list_needs_iface(node):
            return _list_to_go_iface_flat(node)
        li = _list_to_go_int(node)
        if li is not None:
            return li
        return _list_to_go_iface_flat(node)
    if isinstance(node, ast.Tuple):
        return py_literal_to_go_expr(ast.List(elts=list(node.elts), ctx=ast.Load()), iface_list=iface_list)
    if isinstance(node, ast.ListComp):
        return None
    if isinstance(node, ast.Call):
        return call_to_go(node)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = py_literal_to_go_expr(node.operand, iface_list=iface_list)
        if inner:
            return "-" + inner.lstrip()
    return None


def call_to_go(node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Name):
        return None
    fname = snake_to_exported(node.func.id)
    args: list[str] = []
    for a in node.args:
        iface = fname == "BuildTree"
        j = py_literal_to_go_expr(a, iface_list=iface)
        if j is None:
            return None
        args.append(j)
    return fname + "(" + ", ".join(args) + ")"


def assert_msg(node: ast.Assert) -> str:
    if node.msg is None:
        return '"assert failed"'
    if isinstance(node.msg, ast.Constant) and isinstance(node.msg.value, str):
        return json.dumps(node.msg.value)
    return '"assert failed"'


def assert_to_go(node: ast.Assert) -> str | None:
    msg = assert_msg(node)
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Is):
        comp = test.comparators[0]
        if isinstance(comp, ast.Constant) and comp.value is None:
            lj = py_literal_to_go_expr(test.left)
            if lj:
                return f"isNil({msg}, {lj})"
        return None
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    left, right = test.left, test.comparators[0]
    if isinstance(left, ast.Name) or isinstance(right, ast.Name):
        return None
    lj = py_literal_to_go_expr(left)
    rj = py_literal_to_go_expr(right)
    if lj and rj:
        return f"eq({msg}, {lj}, {rj})"
    return None


def _neutralize_markdown_line(line: str) -> str:
    s = line.replace("```python", "```")
    s = re.sub(r"(?i)\bpython's\b", "the", s)
    s = re.sub(r"(?i)\bin python\b", "", s)
    s = re.sub(r"(?i)\bpython\b(?!\s*dsa\b)", "", s)
    s = re.sub(r" {2,}", " ", s)
    return s


def clone_markdown(cell: dict[str, Any]) -> dict[str, Any]:
    raw = list(cell["source"])
    return {
        "cell_type": "markdown",
        "metadata": dict(cell.get("metadata") or {}),
        "source": [_neutralize_markdown_line(x) for x in raw],
    }


def spec_cell_to_go(src: str, *, solutions: bool = False) -> str:
    src = src.rstrip() + "\n"
    lines = [_neutralize_markdown_line(ln) for ln in src.splitlines()]
    title = "Reference solution (notation)" if solutions else "Original exercise specification (reference)"
    py_comment = f"/*\n * --- {title} ---\n" + "".join(
        " * " + (ln.replace("*/", "* /") + "\n") for ln in lines
    ) + " */\n\n"

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return py_comment + "// Could not parse specification; implement manually from comment above.\n"

    go_chunks: list[str] = []
    declared: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            go_chunks.append("// Source imports: " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.FunctionDef):
            if solutions:
                go_chunks.append(emit_solution_function_go(node))
            else:
                go_chunks.append(function_to_go(node))
        elif isinstance(node, ast.ClassDef):
            go_chunks.append(class_to_go(node))
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                tname = node.targets[0].id
                vj = py_literal_to_go_expr(node.value)
                if vj:
                    if tname in declared:
                        go_chunks.append(f"{tname} = {vj}")
                    else:
                        go_chunks.append(f"{tname} := {vj}")
                        declared.add(tname)
                else:
                    go_chunks.append("// " + ast.unparse(node).replace("\n", " ") + "  → implement in Go")
            else:
                go_chunks.append("// " + ast.unparse(node).replace("\n", " ") + "  → implement in Go")
        elif isinstance(node, ast.AnnAssign):
            go_chunks.append("// " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.AugAssign):
            go_chunks.append("// " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.Assert):
            g = assert_to_go(node)
            if g:
                go_chunks.append(g)
            else:
                go_chunks.append("// assert: " + ast.unparse(node))
        elif isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                go_chunks.append('fmt.Println("All tests passed!")')
            else:
                go_chunks.append("// expr: " + ast.unparse(node))
        elif isinstance(node, ast.If | ast.For | ast.While | ast.With):
            go_chunks.append("// " + ast.unparse(node).split("\n")[0] + " … → implement in Go")
        else:
            go_chunks.append("// " + type(node).__name__ + ": " + ast.unparse(node)[:120])

    if not go_chunks:
        go_chunks.append("// (empty specification cell)")

    return py_comment + "\n".join(go_chunks) + "\n"


def make_code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [source],
    }


def transform_notebook_for_go(py_path: Path) -> dict[str, Any] | None:
    rel = py_path.relative_to(PY_DSA)
    if rel.as_posix() == "notebooks/getting_started.ipynb":
        return None
    solutions = py_path.name.endswith("_solutions.ipynb")
    data = json.loads(py_path.read_text(encoding="utf-8"))
    out_cells: list[dict[str, Any]] = []
    header_done = False
    for cell in data.get("cells", []):
        if cell.get("cell_type") == "markdown":
            out_cells.append(clone_markdown(cell))
            continue
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source") or [])
        if not src.strip():
            continue
        if not header_done:
            out_cells.append(make_code_cell(HEADER))
            header_done = True
        out_cells.append(make_code_cell(spec_cell_to_go(src, solutions=solutions)))
    return {
        "cells": out_cells,
        "metadata": GO_META,
        "nbformat": data.get("nbformat", 4),
        "nbformat_minor": data.get("nbformat_minor", 5),
    }


def main() -> int:
    if not PY_DSA.is_dir():
        print("Missing", PY_DSA, file=sys.stderr)
        return 1
    count = 0
    for py_path in sorted(PY_DSA.rglob("*.ipynb")):
        out = transform_notebook_for_go(py_path)
        if out is None:
            continue
        go_path = GO_DSA / py_path.relative_to(PY_DSA)
        go_path.parent.mkdir(parents=True, exist_ok=True)
        go_path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        count += 1
        print("wrote", go_path.relative_to(ROOT))
    print("total", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
