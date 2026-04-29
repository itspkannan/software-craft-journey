"""
Best-effort Python AST → Go function bodies for *_solutions.ipynb cells.
Falls back to full solution as // comments + a compiling default return.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field


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
            return "*" + annotation_to_go(sl).lstrip("*")
        if isinstance(val, ast.Name) and val.id == "List":
            inner = annotation_to_go(sl)
            if inner == "int":
                return "[]int"
            if inner in ("string", "str"):
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
        gt = annotation_to_go(a.annotation) if a.annotation else "interface{}"
        parts.append(f"{a.arg} {gt}")
    return ", ".join(parts)


@dataclass
class EmitEnv:
    types: dict[str, str] = field(default_factory=dict)
    int_slices: set[str] = field(default_factory=set)
    assigned: set[str] = field(default_factory=set)

    def copy(self) -> EmitEnv:
        return EmitEnv(
            types=dict(self.types),
            int_slices=set(self.int_slices),
            assigned=set(self.assigned),
        )


def _length_expr(name: str, env: EmitEnv) -> str:
    return f"len({name})"


def _emit_expr(node: ast.expr | None, env: EmitEnv) -> str | None:
    if node is None:
        return None
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
    if isinstance(node, ast.Name):
        if node.id == "True":
            return "true"
        if node.id == "False":
            return "false"
        if node.id == "None":
            return "nil"
        return node.id
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            inner = _emit_expr(node.operand, env)
            return f"!({inner})" if inner else None
        if isinstance(node.op, ast.USub):
            inner = _emit_expr(node.operand, env)
            return f"(-({inner}))" if inner else None
    if isinstance(node, ast.BinOp):
        L = _emit_expr(node.left, env)
        R = _emit_expr(node.right, env)
        if L is None or R is None:
            return None
        if isinstance(node.op, ast.Add):
            return f"({L} + {R})"
        if isinstance(node.op, ast.Sub):
            return f"({L} - {R})"
        if isinstance(node.op, ast.Mult):
            return f"({L} * {R})"
        if isinstance(node.op, ast.Div):
            return f"(float64({L}) / float64({R}))"
        if isinstance(node.op, ast.FloorDiv):
            return f"({L} / {R})"
        if isinstance(node.op, ast.Mod):
            return f"({L} % {R})"
    if isinstance(node, ast.BoolOp):
        parts: list[str] = []
        for v in node.values:
            e = _emit_expr(v, env)
            if e is None:
                return None
            parts.append(e)
        joiner = " && " if isinstance(node.op, ast.And) else " || "
        return "(" + joiner.join(parts) + ")"
    if isinstance(node, ast.IfExp):
        return None
    if isinstance(node, ast.Compare):
        return _emit_compare(node, env)
    if isinstance(node, ast.Subscript):
        return _emit_subscript(node, env)
    if isinstance(node, ast.Call):
        return _emit_call(node, env)
    if isinstance(node, ast.List):
        if not node.elts:
            return "[]int{}"
        if all(isinstance(e, ast.Constant) and isinstance(e.value, int) for e in node.elts):
            inner = ", ".join(str(e.value) for e in node.elts)  # type: ignore
            return f"[]int{{{inner}}}"
        parts: list[str] = []
        for e in node.elts:
            ex = _emit_expr(e, env)
            if ex is None:
                return None
            parts.append(ex)
        return "[]int{" + ", ".join(parts) + "}"
    if isinstance(node, ast.Attribute):
        return _emit_attribute(node, env)
    if isinstance(node, ast.Dict) and not node.keys:
        return None
    return None


def _emit_attribute(node: ast.Attribute, env: EmitEnv) -> str | None:
    if node.attr == "lower":
        ch = _string_rune_access(node.value, env)
        if ch:
            return f"unicode.ToLower({ch})"
    base = _emit_expr(node.value, env)
    if base is None:
        return None
    if node.attr == "lower":
        return f"strings.ToLower({base})"
    if node.attr == "upper":
        return f"strings.ToUpper({base})"
    return None


def _string_rune_access(value: ast.expr, env: EmitEnv) -> str | None:
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
        vn = value.value.id
        if env.types.get(vn) != "string":
            return None
        idx = value.slice
        if isinstance(idx, ast.Name):
            return f"rune({vn}[{idx.id}])"
        ij = _emit_expr(idx, env) if isinstance(idx, ast.expr) else None
        if ij:
            return f"rune({vn}[{ij}])"
    return None


def _root_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _emit_subscript(node: ast.Subscript, env: EmitEnv) -> str | None:
    val = _emit_expr(node.value, env)
    if val is None:
        return None
    sl = node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, int):
        idx_js = str(sl.value)
    elif isinstance(sl, ast.Name):
        idx_js = sl.id
    else:
        idx_js = _emit_expr(sl, env) if isinstance(sl, ast.expr) else None
    if idx_js is None:
        return None
    return f"{val}[{idx_js}]"


def _emit_compare(node: ast.Compare, env: EmitEnv) -> str | None:
    parts: list[str] = []
    cur_left = node.left
    for i, op in enumerate(node.ops):
        right = node.comparators[i]
        L = _emit_expr(cur_left, env)
        R = _emit_expr(right, env)
        if L is None or R is None:
            return None
        if isinstance(op, ast.Eq):
            parts.append(f"({L} == {R})")
        elif isinstance(op, ast.NotEq):
            parts.append(f"({L} != {R})")
        elif isinstance(op, ast.Lt):
            parts.append(f"({L} < {R})")
        elif isinstance(op, ast.LtE):
            parts.append(f"({L} <= {R})")
        elif isinstance(op, ast.Gt):
            parts.append(f"({L} > {R})")
        elif isinstance(op, ast.GtE):
            parts.append(f"({L} >= {R})")
        elif isinstance(op, ast.Is):
            if isinstance(right, ast.Constant) and right.value is None:
                parts.append(f"({L} == nil)")
            else:
                return None
        elif isinstance(op, ast.IsNot):
            if isinstance(right, ast.Constant) and right.value is None:
                parts.append(f"({L} != nil)")
            else:
                return None
        elif isinstance(op, ast.In):
            inner = _emit_in(L, right, env)
            if inner is None:
                return None
            parts.append(inner)
        elif isinstance(op, ast.NotIn):
            inner = _emit_in(L, right, env)
            if inner is None:
                return None
            parts.append(f"!({inner})")
        else:
            return None
        cur_left = right
    if not parts:
        return None
    return "(" + " && ".join(parts) + ")"


def _emit_in(left_go: str, right: ast.expr, env: EmitEnv) -> str | None:
    if isinstance(right, ast.Name):
        rt = env.types.get(right.id, "")
        if rt == "map[int]int" or rt.startswith("map[int]int"):
            return f"mapHasIntInt({right.id}, {left_go})"
        if rt == "map[byte]int" or rt.startswith("map[byte]int"):
            return f"mapHasByteInt({right.id}, {left_go})"
        if rt.startswith("map["):
            return None
    return None


def _emit_call(node: ast.Call, env: EmitEnv) -> str | None:
    if isinstance(node.func, ast.Attribute) and not node.args:
        ch = _string_rune_access(node.func.value, env)
        if ch and node.func.attr == "isalnum":
            return f"(unicode.IsLetter({ch}) || unicode.IsDigit({ch}))"
    if isinstance(node.func, ast.Name):
        fn = node.func.id
        if fn == "len" and node.args and isinstance(node.args[0], ast.Name):
            return _length_expr(node.args[0].id, env)
        if fn in ("min", "max") and len(node.args) == 2:
            a = _emit_expr(node.args[0], env)
            b = _emit_expr(node.args[1], env)
            if a and b:
                return f"{fn}({a}, {b})"
        if fn == "abs" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                return f"max({a}, -({a}))"
        if fn == "int" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                return f"int({a})"
        if fn == "set":
            return None
        if fn == "float" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value == "inf":
                return "1e308"
            a = _emit_expr(a0, env)
            if a:
                return f"float64({a})"
        cname = snake_to_exported(fn)
        args = [_emit_expr(a, env) for a in node.args]
        if any(x is None for x in args):
            return None
        return f"{cname}(" + ", ".join(args) + ")"
    return None


def _declare_local(target: str, go_type: str, env: EmitEnv) -> None:
    env.types[target] = go_type
    if go_type == "[]int":
        env.int_slices.add(target)


def _infer_map_type(name: str) -> str:
    n = name.lower()
    if "char" in n or "freq" in n or "last" in n:
        return "map[byte]int"
    return "map[int]int"


def _emit_assign(st: ast.Assign, env: EmitEnv, ind: str) -> list[str] | None:
    if len(st.targets) != 1:
        return None
    if isinstance(st.targets[0], ast.Tuple) and isinstance(st.value, ast.Tuple):
        tgts = st.targets[0].elts
        vals = st.value.elts
        if len(tgts) != len(vals):
            return None
        if not all(isinstance(t, ast.Name) for t in tgts):
            return None
        names = [t.id for t in tgts]  # type: ignore
        rhss = []
        for ve in vals:
            g = _emit_expr(ve, env)
            if g is None:
                return None
            rhss.append(g)
        lhs = ", ".join(names)
        rhs = ", ".join(rhss)
        for nm in names:
            env.types[nm] = "var"
            env.assigned.add(nm)
        return [ind + f"{lhs} := {rhs}"]
    if isinstance(st.targets[0], ast.Subscript):
        sub = st.targets[0]
        if isinstance(sub.value, ast.Name) and isinstance(sub.slice, ast.Name):
            m, k = sub.value.id, sub.slice.id
            rhs = _emit_expr(st.value, env)
            if rhs is None:
                return None
            mt = env.types.get(m, "")
            if mt == "map[int]int" or mt.startswith("map[int]int"):
                return [ind + f"{m}[{k}] = {rhs}"]
            if mt == "map[byte]int" or mt.startswith("map[byte]int"):
                return [ind + f"{m}[{k}] = {rhs}"]
        return None
    if not isinstance(st.targets[0], ast.Name):
        return None
    tgt = st.targets[0].id
    val = st.value
    if isinstance(val, ast.Dict) and not val.keys:
        jt = _infer_map_type(tgt)
        _declare_local(tgt, jt, env)
        env.assigned.add(tgt)
        return [ind + f"{tgt} := make({jt})"]
    if isinstance(val, ast.List) and not val.elts:
        _declare_local(tgt, "[]int", env)
        env.assigned.add(tgt)
        return [ind + f"var {tgt} []int"]
    rhs = _emit_expr(val, env)
    if rhs is None:
        return None
    if tgt in env.assigned:
        return [ind + f"{tgt} = {rhs}"]
    if rhs.startswith("[]int{") or rhs == "[]int{}":
        _declare_local(tgt, "[]int", env)
        env.assigned.add(tgt)
        return [ind + f"{tgt} := {rhs}"]
    if "make(map[int]int)" in rhs or rhs.startswith("make(map"):
        jt = _infer_map_type(tgt)
        _declare_local(tgt, jt, env)
        env.assigned.add(tgt)
        return [ind + f"{tgt} := {rhs}"]
    if isinstance(val, ast.Constant) and isinstance(val.value, float):
        _declare_local(tgt, "float64", env)
    elif isinstance(val, ast.Constant) and isinstance(val.value, int):
        _declare_local(tgt, "int", env)
    elif isinstance(val, ast.Constant) and isinstance(val.value, bool):
        _declare_local(tgt, "bool", env)
    env.assigned.add(tgt)
    return [ind + f"{tgt} := {rhs}"]


def _emit_augassign(st: ast.AugAssign, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    t = st.target.id
    rhs = _emit_expr(st.value, env)
    if rhs is None:
        return None
    if isinstance(st.op, ast.Add):
        return [ind + f"{t} += {rhs}"]
    if isinstance(st.op, ast.Sub):
        return [ind + f"{t} -= {rhs}"]
    if isinstance(st.op, ast.Mult):
        return [ind + f"{t} *= {rhs}"]
    return None


def _emit_annassign(st: ast.AnnAssign, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    tgt = st.target.id
    gt = annotation_to_go(st.annotation)
    if st.value is None:
        return None
    rhs = _emit_expr(st.value, env)
    if rhs is None:
        return None
    _declare_local(tgt, gt, env)
    if gt == "[]int":
        env.int_slices.add(tgt)
    env.assigned.add(tgt)
    return [ind + f"var {tgt} {gt} = {rhs}"]


def _emit_if(st: ast.If, env: EmitEnv, ind: str) -> list[str] | None:
    cond = _emit_expr(st.test, env)
    if cond is None:
        return None
    then_body = _emit_block(st.body, env, ind+"\t")
    if then_body is None:
        return None
    lines = [ind + f"if {cond} {{"] + then_body
    if not st.orelse:
        lines.append(ind + "}")
        return lines
    lines.append(ind + "} else {")
    if len(st.orelse) == 1 and isinstance(st.orelse[0], ast.If):
        sub = _emit_if(st.orelse[0], env, ind+"\t")
        if sub is None:
            return None
        lines.extend(sub)
    else:
        ob = _emit_block(st.orelse, env, ind+"\t")
        if ob is None:
            return None
        lines.extend(ob)
    lines.append(ind + "}")
    return lines


def _emit_while(st: ast.While, env: EmitEnv, ind: str) -> list[str] | None:
    cond = _emit_expr(st.test, env)
    if cond is None:
        return None
    body = _emit_block(st.body, env, ind+"\t")
    if body is None:
        return None
    return [ind + f"for {cond} {{"] + body + [ind + "}"]


def _emit_for_range(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    iv = st.target.id
    args = st.iter.args  # type: ignore
    if len(args) == 1:
        hi = _emit_expr(args[0], env)
        if not hi:
            return None
        inner = env.copy()
        inner.types[iv] = "int"
        body = _emit_block(st.body, inner, ind+"\t")
        if body is None:
            return None
        return [ind + f"for {iv} := 0; {iv} < {hi}; {iv}++ {{"] + body + [ind + "}"]
    if len(args) == 2:
        lo = _emit_expr(args[0], env)
        hi = _emit_expr(args[1], env)
        if not lo or not hi:
            return None
        inner = env.copy()
        inner.types[iv] = "int"
        body = _emit_block(st.body, inner, ind+"\t")
        if body is None:
            return None
        return [ind + f"for {iv} := {lo}; {iv} < {hi}; {iv}++ {{"] + body + [ind + "}"]
    if len(args) == 3:
        lo = _emit_expr(args[0], env)
        hi = _emit_expr(args[1], env)
        stp = _emit_expr(args[2], env)
        if not lo or not hi or not stp:
            return None
        inner = env.copy()
        inner.types[iv] = "int"
        body = _emit_block(st.body, inner, ind+"\t")
        if body is None:
            return None
        return [ind + f"for {iv} := {lo}; {iv} < {hi}; {iv} += {stp} {{"] + body + [ind + "}"]
    return None


def _emit_for_enumerate(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if not (isinstance(st.target, ast.Tuple) and len(st.target.elts) == 2):
        return None
    e0, e1 = st.target.elts
    if not (isinstance(e0, ast.Name) and isinstance(e1, ast.Name)):
        return None
    i_n, v_n = e0.id, e1.id
    if not isinstance(st.iter, ast.Call) or not st.iter.args:
        return None
    seq = st.iter.args[0]
    if not isinstance(seq, ast.Name):
        return None
    seq_n = seq.id
    inner = env.copy()
    inner.types[i_n] = "int"
    inner.types[v_n] = "int"
    body = _emit_block(st.body, inner, ind+"\t")
    if body is None:
        return None
    return (
        [ind + f"for {i_n} := 0; {i_n} < len({seq_n}); {i_n}++ {{", ind + f"\t{v_n} := {seq_n}[{i_n}]"]
        + body
        + [ind + "}"]
    )


def _emit_for_each(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name) or not isinstance(st.iter, ast.Name):
        return None
    v, seq = st.target.id, st.iter.id
    inner = env.copy()
    inner.types[v] = "int"
    body = _emit_block(st.body, inner, ind+"\t")
    if body is None:
        return None
    return [ind + f"for _, {v} := range {seq} {{"] + body + [ind + "}"]


def _emit_for(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if isinstance(st.iter, ast.Call) and isinstance(st.iter.func, ast.Name) and st.iter.func.id == "range":
        return _emit_for_range(st, env, ind)
    if isinstance(st.iter, ast.Call) and isinstance(st.iter.func, ast.Name) and st.iter.func.id == "enumerate":
        return _emit_for_enumerate(st, env, ind)
    if isinstance(st.iter, ast.Name):
        return _emit_for_each(st, env, ind)
    return None


def _emit_stmt(st: ast.stmt, env: EmitEnv, ind: str) -> list[str] | None:
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
        return []
    if isinstance(st, ast.Pass):
        return []
    if isinstance(st, ast.Assign):
        return _emit_assign(st, env, ind)
    if isinstance(st, ast.AugAssign):
        return _emit_augassign(st, env, ind)
    if isinstance(st, ast.AnnAssign):
        return _emit_annassign(st, env, ind)
    if isinstance(st, ast.Return):
        if st.value is None:
            return [ind + "return"]
        v = _emit_expr(st.value, env)
        if v is None:
            return None
        return [ind + f"return {v}"]
    if isinstance(st, ast.If):
        return _emit_if(st, env, ind)
    if isinstance(st, ast.While):
        return _emit_while(st, env, ind)
    if isinstance(st, ast.For):
        return _emit_for(st, env, ind)
    if isinstance(st, ast.Break):
        return [ind + "break"]
    if isinstance(st, ast.Continue):
        return [ind + "continue"]
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
        if isinstance(st.value.func, ast.Name) and st.value.func.id == "print":
            parts = [_emit_expr(a, env) for a in st.value.args]
            if any(p is None for p in parts):
                return None
            if len(parts) == 1:
                return [ind + f"fmt.Println({parts[0]})"]
            return [ind + "fmt.Println(" + ", ".join(parts) + ")"]
        c = _emit_call(st.value, env)
        if c is None:
            return None
        return [ind + c]
    return None


def _emit_block(stmts: list[ast.stmt], env: EmitEnv, ind: str) -> list[str] | None:
    lines: list[str] = []
    for st in stmts:
        chunk = _emit_stmt(st, env, ind)
        if chunk is None:
            return None
        lines.extend(chunk)
    return lines


def _build_param_env(fn: ast.FunctionDef) -> EmitEnv:
    env = EmitEnv()
    for a in fn.args.args:
        if a.arg == "self":
            continue
        gt = annotation_to_go(a.annotation) if a.annotation else "interface{}"
        env.types[a.arg] = gt
        env.assigned.add(a.arg)
        if gt == "[]int":
            env.int_slices.add(a.arg)
    return env


def _default_return_line(fn: ast.FunctionDef) -> str:
    ret = annotation_to_go(fn.returns)
    if ret == "" or ret == "interface{}":
        return "return"
    if ret == "bool":
        return "return false"
    if ret == "int":
        return "return 0"
    if ret == "float64":
        return "return 0"
    if ret == "[]int":
        return "return nil"
    if ret == "string":
        return 'return ""'
    if ret == "[][]int":
        return "return nil"
    return "return nil"


def function_python_as_go_comments(fn: ast.FunctionDef) -> str:
    ret = annotation_to_go(fn.returns)
    name = snake_to_exported(fn.name)
    params = params_to_go(fn.args, skip_self=True)
    sig = f"func {name}({params}) {ret} {{\n" if ret else f"func {name}({params}) {{\n"
    lines = ["\t// --- Reference solution (course notation; translate to Go) ---"]
    for st in fn.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        for ln in ast.unparse(st).split("\n"):
            lines.append("\t// " + ln.replace("*/", "* /"))
    lines.append("\t" + _default_return_line(fn))
    body = "\n".join(lines)
    return sig + body + "\n}\n"


def emit_solution_function_go(fn: ast.FunctionDef) -> str:
    ret = annotation_to_go(fn.returns)
    name = snake_to_exported(fn.name)
    params = params_to_go(fn.args, skip_self=True)
    env = _build_param_env(fn)
    body_stmts: list[ast.stmt] = []
    for st in fn.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        body_stmts.append(st)
    body_lines = _emit_block(body_stmts, env, "\t")
    if body_lines is None:
        return function_python_as_go_comments(fn)
    body = "\n".join(body_lines)
    if ret:
        return f"func {name}({params}) {ret} {{\n{body}\n}}\n"
    return f"func {name}({params}) {{\n{body}\n}}\n"
