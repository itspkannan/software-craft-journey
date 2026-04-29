#!/usr/bin/env python3
"""
Rebuild topic notebooks under DSA/JavaDSA (maintainer tool).

Markdown cells are copied and lightly adjusted for this track. Each specification code cell
becomes one Java cell: a block comment with the reference spec, then Java stubs and tests
where automated translation applies.
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
from java_solution_emitter import emit_solution_function_java

# refresh_java_notebooks.py lives at DSA/scripts/ → repo root is parents[2]
ROOT = Path(__file__).resolve().parents[2]
PY_DSA = ROOT / "DSA" / "PythonDSA"
JAVA_DSA = ROOT / "DSA" / "JavaDSA"

JAVA_META = {
    "kernelspec": {
        "display_name": "Java",
        "language": "java",
        "name": "java",
    },
    "language_info": {
        "name": "java",
        "file_extension": ".java",
        "mimetype": "text/x-java-source",
        "pygments_lexer": "java",
    },
}

HEADER = """\
import java.util.*;
import java.util.stream.*;
import java.util.function.*;

/** Test helpers (assertions always checked; not dependent on -ea). */
final class T {
    static void eq(String m, int a, int b) { if (a != b) throw new AssertionError(m + ": " + a + " != " + b); }
    static void eq(String m, long a, long b) { if (a != b) throw new AssertionError(m + ": " + a + " != " + b); }
    static void eq(String m, boolean a, boolean b) { if (a != b) throw new AssertionError(m); }
    static void eq(String m, String a, String b) { if (!Objects.equals(a, b)) throw new AssertionError(m + ": " + a + " != " + b); }
    static void eq(String m, int[] a, int[] b) {
        if (!Arrays.equals(a, b)) throw new AssertionError(m + ": " + Arrays.toString(a) + " != " + Arrays.toString(b));
    }
    static void eq(String m, List<Integer> a, int[] b) { eq(m, ia(a), b); }
    static void eq(String m, double a, double b) { if (Double.compare(a, b) != 0) throw new AssertionError(m); }
    static void eq(String m, List<Integer> a, List<Integer> b) { if (!a.equals(b)) throw new AssertionError(m + ": " + a + " != " + b); }
    static void eq(String m, List<List<String>> a, List<List<String>> b) { if (!a.equals(b)) throw new AssertionError(m); }
    static void eq(String m, List<List<Integer>> a, List<List<Integer>> b) { if (!a.equals(b)) throw new AssertionError(m); }
    static void eqDeep(String m, Object a, Object b) { if (!Objects.deepEquals(a, b)) throw new AssertionError(m + ": " + a + " vs " + b); }
    static void isNull(String m, Object a) { if (a != null) throw new AssertionError(m); }
    static void isTrue(String m, boolean b) { if (!b) throw new AssertionError(m); }
    static List<Integer> il(int... xs) { return Arrays.stream(xs).boxed().toList(); }
    static int[] ia(List<Integer> xs) { return xs.stream().mapToInt(i -> i).toArray(); }
}
"""


def snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def unwrap_slice(node: ast.expr) -> ast.expr:
    if isinstance(node, ast.Tuple) and node.elts:
        return node.elts[0]
    return node


def annotation_to_java(ann: ast.expr | None) -> str:
    if ann is None:
        return "void"
    if isinstance(ann, ast.Name):
        if ann.id == "list":
            return "List<Integer>"
        return {
            "int": "int",
            "str": "String",
            "bool": "boolean",
            "float": "double",
            "None": "void",
        }.get(ann.id, ann.id)
    if isinstance(ann, ast.Subscript):
        val = ann.value
        sl = unwrap_slice(ann.slice)
        if isinstance(val, ast.Name) and val.id == "Optional":
            inner = annotation_to_java(sl)
            return inner
        if isinstance(val, ast.Name) and val.id == "List":
            inner = annotation_to_java(sl)
            return "List<" + inner_box(inner) + ">"
        if isinstance(val, ast.Name) and val.id == "list":
            inner = unwrap_slice(sl)
            if isinstance(inner, ast.Name) and inner.id == "int":
                return "int[]"
            if isinstance(inner, ast.Name) and inner.id == "str":
                return "List<String>"
            if isinstance(inner, ast.Subscript) and isinstance(inner.value, ast.Name) and inner.value.id == "list":
                inner2 = unwrap_slice(inner.slice)
                if isinstance(inner2, ast.Name) and inner2.id == "int":
                    return "List<List<Integer>>"
                if isinstance(inner2, ast.Name) and inner2.id == "str":
                    return "List<List<String>>"
            j = annotation_to_java(inner)
            if j == "int[]":
                return "List<List<Integer>>"
            return "List<" + inner_box(j) + ">"
        if isinstance(val, ast.Name) and val.id == "dict":
            return "Map<String, Object>"
    if isinstance(ann, ast.Tuple):
        return "Object"
    return "Object"


def inner_box(j: str) -> str:
    if j == "int":
        return "Integer"
    if j == "boolean":
        return "Boolean"
    if j == "long":
        return "Long"
    if j == "double":
        return "Double"
    return j


def params_to_java(args: ast.arguments, skip_self: bool = True) -> str:
    parts: list[str] = []
    for a in args.args:
        if skip_self and a.arg == "self":
            continue
        ann = a.annotation
        jt = annotation_to_java(ann) if ann else "Object"
        if jt == "int[]":
            parts.append(f"int[] {a.arg}")
        elif jt == "String[]":
            parts.append(f"String[] {a.arg}")
        else:
            parts.append(f"{jt} {a.arg}")
    return ", ".join(parts)


def stmt_to_java_body(stmts: list[ast.stmt], indent: str = "    ") -> str:
    lines: list[str] = []
    for st in stmts:
        if isinstance(st, ast.Pass):
            lines.append(indent + "throw new UnsupportedOperationException();")
        elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        elif isinstance(st, ast.Raise):
            lines.append(indent + "throw new UnsupportedOperationException();")
        elif isinstance(st, ast.Return) and st.value is None:
            lines.append(indent + "return;")
        else:
            lines.append(indent + "// TODO: implement from specification above")
            break
    if not lines:
        lines.append(indent + "throw new UnsupportedOperationException();")
    return "\n".join(lines)


def function_to_java(fn: ast.FunctionDef) -> str:
    ret = annotation_to_java(fn.returns)
    if ret == "int[]":
        ret_ty = "int[]"
    elif ret == "void":
        ret_ty = "void"
    else:
        ret_ty = ret
    name = snake_to_camel(fn.name)
    params = params_to_java(fn.args, skip_self=True)
    body = stmt_to_java_body(fn.body)
    return f"static {ret_ty} {name}({params}) {{\n{body}\n}}"


def class_to_java(cls: ast.ClassDef) -> str:
    if cls.name == "Node":
        return """class Node {
    int val;
    List<Node> neighbors;
    Node() { this(0); }
    Node(int val) {
        this.val = val;
        this.neighbors = new ArrayList<>();
    }
    Node(int val, List<Node> neighbors) {
        this.val = val;
        this.neighbors = neighbors != null ? neighbors : new ArrayList<>();
    }
}
"""
    if cls.name == "TreeNode":
        return """class TreeNode {
    int val;
    TreeNode left, right;
    TreeNode() { this(0, null, null); }
    TreeNode(int val) { this(val, null, null); }
    TreeNode(int val, TreeNode left, TreeNode right) {
        this.val = val;
        this.left = left;
        this.right = right;
    }
}
"""
    lines = [f"class {cls.name} {{"]
    for item in cls.body:
        if isinstance(item, ast.FunctionDef):
            if item.name == "__init__":
                params = params_to_java(item.args, skip_self=True)
                body = stmt_to_java_body(item.body, indent="        ")
                lines.append(f"    {cls.name}({params}) {{\n{body}\n    }}")
                continue
            ret = annotation_to_java(item.returns)
            ret_ty = "void" if ret == "void" else ret
            params = params_to_java(item.args, skip_self=True)
            body = stmt_to_java_body(item.body, indent="        ")
            lines.append(f"    {ret_ty} {item.name}({params}) {{\n{body}\n    }}")
        elif isinstance(item, ast.Pass):
            continue
        elif isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
            continue
    lines.append("}")
    return "\n".join(lines)


def _const_elt_java(e: ast.expr) -> str | None:
    if isinstance(e, ast.Constant):
        v = e.value
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v)
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        inner = _const_elt_java(e.operand)
        return "-" + inner if inner else None
    return None


def _list_to_java(node: ast.List) -> str | None:
    if not node.elts:
        return "Arrays.asList()"
    all_int_nonnull = all(
        isinstance(e, ast.Constant) and isinstance(e.value, int) for e in node.elts
    )
    any_null = any(isinstance(e, ast.Constant) and e.value is None for e in node.elts)
    if all_int_nonnull and not any_null:
        return "new int[] {" + ", ".join(str(e.value) for e in node.elts) + "}"  # type: ignore
    parts: list[str] = []
    for e in node.elts:
        if isinstance(e, ast.List):
            inner = _list_to_java(e)
            if inner is None:
                return None
            parts.append(inner)
            continue
        cj = _const_elt_java(e)
        if cj is not None:
            parts.append(cj)
            continue
        return None
    return "Arrays.asList(" + ", ".join(parts) + ")"


def py_literal_to_java_expr(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant):
        v = node.value
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v)
    if isinstance(node, ast.List):
        return _list_to_java(node)
    if isinstance(node, ast.Tuple):
        return py_literal_to_java_expr(ast.List(elts=list(node.elts), ctx=ast.Load()))
    if isinstance(node, ast.ListComp):
        return None
    if isinstance(node, ast.Call):
        return call_to_java(node)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Compare):
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = py_literal_to_java_expr(node.operand)
        if inner:
            return "-" + inner.lstrip()
    return None


def call_to_java(node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Name):
        return None
    fname = snake_to_camel(node.func.id)
    args: list[str] = []
    for a in node.args:
        j = py_literal_to_java_expr(a)
        if j is None:
            return None
        if fname == "buildTree" and j.startswith("new int[]"):
            j = "java.util.Arrays.stream(" + j + ").boxed().toList()"
        args.append(j)
    return fname + "(" + ", ".join(args) + ")"


def assert_msg(node: ast.Assert) -> str:
    if node.msg is None:
        return '"assert failed"'
    if isinstance(node.msg, ast.Constant) and isinstance(node.msg.value, str):
        return json.dumps(node.msg.value)
    return '"assert failed"'


def assert_to_java(node: ast.Assert) -> str | None:
    msg = assert_msg(node)
    test = node.test
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Is):
        comp = test.comparators[0]
        if isinstance(comp, ast.Constant) and comp.value is None:
            lj = py_literal_to_java_expr(test.left)
            if lj:
                return f"T.isNull({msg}, {lj});"
        return None
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    left, right = test.left, test.comparators[0]
    if isinstance(left, ast.Name) or isinstance(right, ast.Name):
        return None
    lj = py_literal_to_java_expr(left)
    rj = py_literal_to_java_expr(right)
    if lj and rj:
        if isinstance(right, ast.List) and any(isinstance(x, ast.List) for x in right.elts):
            return f"T.eqDeep({msg}, {lj}, {rj});"
        if isinstance(right, ast.List) and not right.elts:
            return f"T.eqDeep({msg}, {lj}, {rj});"
        if isinstance(right, ast.Constant) and isinstance(right.value, bool):
            return f"T.eq({msg}, {lj}, {rj});"
        if isinstance(right, ast.Constant) and isinstance(right.value, int):
            return f"T.eq({msg}, {lj}, {rj});"
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            return f"T.eq({msg}, {lj}, {rj});"
        if isinstance(right, ast.List) and right.elts and all(isinstance(x, ast.Constant) and isinstance(x.value, int) for x in right.elts):
            return f"T.eq({msg}, {lj}, {rj});"
        if isinstance(right, ast.List):
            return f"T.eqDeep({msg}, {lj}, {rj});"
        if isinstance(right, ast.Name):
            return f"T.eqDeep({msg}, {lj}, {rj});"
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


def spec_cell_to_java(src: str, *, solutions: bool = False) -> str:
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

    java_chunks: list[str] = []
    declared_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append("from " + node.module)
            java_chunks.append("// Source imports: " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.FunctionDef):
            if solutions:
                java_chunks.append(emit_solution_function_java(node))
            else:
                java_chunks.append(function_to_java(node))
        elif isinstance(node, ast.ClassDef):
            java_chunks.append(class_to_java(node))
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                tname = node.targets[0].id
                vj = py_literal_to_java_expr(node.value)
                if vj:
                    if tname in declared_names:
                        java_chunks.append(f"{tname} = {vj};")
                    else:
                        java_chunks.append(f"var {tname} = {vj};")
                        declared_names.add(tname)
                else:
                    java_chunks.append("// " + ast.unparse(node).replace("\n", " ") + "  → implement in Java")
            else:
                java_chunks.append("// " + ast.unparse(node).replace("\n", " ") + "  → implement in Java")
        elif isinstance(node, ast.AnnAssign):
            java_chunks.append("// " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.AugAssign):
            java_chunks.append("// " + ast.unparse(node).replace("\n", " "))
        elif isinstance(node, ast.Assert):
            j = assert_to_java(node)
            if j:
                java_chunks.append(j)
            else:
                java_chunks.append("// assert: " + ast.unparse(node))
        elif isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "print":
                java_chunks.append('System.out.println("All tests passed!");')
            else:
                java_chunks.append("// expr: " + ast.unparse(node))
        elif isinstance(node, ast.If | ast.For | ast.While | ast.With):
            java_chunks.append("// " + ast.unparse(node).split("\n")[0] + " … → implement in Java")
        else:
            java_chunks.append("// " + type(node).__name__ + ": " + ast.unparse(node)[:120])

    if not java_chunks:
        java_chunks.append("// (empty specification cell)")

    return py_comment + "\n".join(java_chunks) + "\n"


def make_code_cell(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [source] if not source.endswith("\n") else [source],
    }


def transform_notebook_for_java(py_path: Path) -> dict[str, Any] | None:
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
        out_cells.append(make_code_cell(spec_cell_to_java(src, solutions=solutions)))
    return {
        "cells": out_cells,
        "metadata": JAVA_META,
        "nbformat": data.get("nbformat", 4),
        "nbformat_minor": data.get("nbformat_minor", 5),
    }


def main() -> int:
    if not PY_DSA.is_dir():
        print("Missing", PY_DSA, file=sys.stderr)
        return 1
    count = 0
    for py_path in sorted(PY_DSA.rglob("*.ipynb")):
        out = transform_notebook_for_java(py_path)
        if out is None:
            continue
        ja_path = JAVA_DSA / py_path.relative_to(PY_DSA)
        ja_path.parent.mkdir(parents=True, exist_ok=True)
        ja_path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        count += 1
        print("wrote", ja_path.relative_to(ROOT))
    print("total", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
