"""
Best-effort Python AST → Java method bodies for *_solutions.ipynb cells.
Used only when rebuilding JavaDSA solution notebooks; returns None when unsupported.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field

# Re-use annotation / naming helpers from the main refresh script without circular import:
# duplicated minimal logic via late import in emit_solution_function_java only if needed.
# Here we duplicate snake_to_camel and annotation_to_java signatures by importing refresh module
# would run main — instead duplicate small helpers:


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
            return annotation_to_java(sl)
        if isinstance(val, ast.Name) and val.id == "List":
            inner = annotation_to_java(sl)
            if inner == "int":
                return "int[]"
            if inner == "str":
                return "List<String>"
            if isinstance(sl, ast.Subscript) and isinstance(sl.value, ast.Name) and sl.value.id == "list":
                inner2 = unwrap_slice(sl.slice)
                if isinstance(inner2, ast.Name) and inner2.id == "str":
                    return "List<List<String>>"
            return f"List<{inner}>" if inner not in ("int", "String") else inner
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


@dataclass
class EmitEnv:
    """Variable → Java type string for locals + parameters."""

    types: dict[str, str] = field(default_factory=dict)
    int_arrays: set[str] = field(default_factory=set)

    def copy(self) -> EmitEnv:
        return EmitEnv(types=dict(self.types), int_arrays=set(self.int_arrays))


def _length_expr(name: str, env: EmitEnv) -> str:
    if name in env.int_arrays:
        return f"{name}.length"
    t = env.types.get(name, "")
    if t == "String":
        return f"{name}.length()"
    return f"{name}.size()"


def _emit_expr(node: ast.expr | None, env: EmitEnv) -> str | None:
    if node is None:
        return None
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
    if isinstance(node, ast.Name):
        if node.id == "True":
            return "true"
        if node.id == "False":
            return "false"
        if node.id == "None":
            return "null"
        return node.id
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            inner = _emit_expr(node.operand, env)
            return f"(!({inner}))" if inner else None
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
            return f"((double) {L} / (double) {R})"
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
        t = _emit_expr(node.test, env)
        y = _emit_expr(node.body, env)
        n = _emit_expr(node.orelse, env)
        if t and y and n:
            return f"({t} ? {y} : {n})"
        return None
    if isinstance(node, ast.Compare):
        return _emit_compare(node, env)
    if isinstance(node, ast.Subscript):
        return _emit_subscript(node, env)
    if isinstance(node, ast.Call):
        return _emit_call(node, env)
    if isinstance(node, ast.List):
        if not node.elts:
            return "new int[0]"
        if all(isinstance(e, ast.Constant) and isinstance(e.value, int) for e in node.elts):
            inner = ", ".join(str(e.value) for e in node.elts)  # type: ignore
            return f"new int[] {{{inner}}}"
        parts: list[str] = []
        for e in node.elts:
            ex = _emit_expr(e, env)
            if ex is None:
                return None
            parts.append(ex)
        return "new int[] {" + ", ".join(parts) + "}"
    if isinstance(node, ast.Tuple):
        return None
    if isinstance(node, ast.Attribute):
        return _emit_attribute(node, env)
    if isinstance(node, ast.ListComp):
        return None
    if isinstance(node, ast.Dict):
        if node.keys:
            return None
        return None
    return None


def _emit_attribute(node: ast.Attribute, env: EmitEnv) -> str | None:
    if node.attr == "lower":
        ch = _string_char_access(node.value, env)
        if ch:
            return f"Character.toLowerCase({ch})"
    if node.attr == "upper":
        ch = _string_char_access(node.value, env)
        if ch:
            return f"Character.toUpperCase({ch})"
    base = _emit_expr(node.value, env)
    if base is None:
        return None
    if node.attr == "append" and isinstance(node.value, ast.Name):
        return None  # handled as call on bound method
    if node.attr == "pop":
        return None
    if node.attr == "popleft":
        return None
    if node.attr == "lower":
        return f"{base}.toLowerCase()"
    if node.attr == "upper":
        return f"{base}.toUpperCase()"
    if node.attr == "isalnum":
        return f"Character.isLetterOrDigit({base}.charAt(0))" if env.types.get(_root_name(node.value)) == "String" else None
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
    idx_js: str | None
    if isinstance(sl, ast.Constant) and isinstance(sl.value, int):
        idx_js = str(sl.value)
    elif isinstance(sl, ast.Name):
        idx_js = sl.id
    else:
        idx_js = _emit_expr(sl, env) if isinstance(sl, ast.expr) else None
    if idx_js is None:
        return None
    vn = _root_name(node.value)
    t = env.types.get(vn or "", "") if vn else ""
    if vn and vn in env.int_arrays:
        return f"{val}[{idx_js}]"
    if t.startswith("Map<"):
        return f"{val}.get({idx_js})"
    if t.startswith("List<") or t.startswith("ArrayList"):
        return f"{val}.get({idx_js})"
    if t == "String":
        return f"{val}.charAt({idx_js})"
    if vn:
        return f"{val}.get({idx_js})"
    return None


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
                parts.append(f"({L} == null)")
            else:
                return None
        elif isinstance(op, ast.IsNot):
            if isinstance(right, ast.Constant) and right.value is None:
                parts.append(f"({L} != null)")
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
            parts.append(f"(!({inner}))")
        else:
            return None
        cur_left = right
    if not parts:
        return None
    return "(" + " && ".join(parts) + ")"


def _emit_in(left_java: str, right: ast.expr, env: EmitEnv) -> str | None:
    if isinstance(right, ast.Name):
        rt = env.types.get(right.id, "")
        if rt.startswith("Map<") or "Map<" in rt:
            return f"{right.id}.containsKey({left_java})"
        if rt.startswith("List") or rt.startswith("ArrayList") or rt.startswith("Set"):
            return f"{right.id}.contains({left_java})"
        if right.id in env.int_arrays:
            return None
    return None


def _string_char_access(value: ast.expr, env: EmitEnv) -> str | None:
    """Expression usable as Java char for Character.* helpers (String + index)."""
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
        vn = value.value.id
        if env.types.get(vn) != "String":
            return None
        idx = value.slice
        if isinstance(idx, ast.Name):
            return f"{vn}.charAt({idx.id})"
        ij = _emit_expr(idx, env) if isinstance(idx, ast.expr) else None
        if ij:
            return f"{vn}.charAt({ij})"
    return None


def _emit_call(node: ast.Call, env: EmitEnv) -> str | None:
    if isinstance(node.func, ast.Attribute) and not node.args:
        ch = _string_char_access(node.func.value, env)
        if ch:
            if node.func.attr == "isalnum":
                return f"Character.isLetterOrDigit({ch})"
            if node.func.attr == "isdigit":
                return f"Character.isDigit({ch})"
            if node.func.attr == "isalpha":
                return f"Character.isLetter({ch})"
            if node.func.attr == "lower":
                return f"Character.toLowerCase({ch})"
            if node.func.attr == "upper":
                return f"Character.toUpperCase({ch})"
    if isinstance(node.func, ast.Name):
        fn = node.func.id
        if fn == "len" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Name):
                return _length_expr(a0.id, env)
        if fn in ("min", "max") and len(node.args) == 2:
            a = _emit_expr(node.args[0], env)
            b = _emit_expr(node.args[1], env)
            if a and b:
                return f"Math.{fn}({a}, {b})"
        if fn == "abs" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                return f"Math.abs({a})"
        if fn == "int" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                return f"(int) ({a})"
        if fn == "float" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value == "inf":
                return "Double.POSITIVE_INFINITY"
            a = _emit_expr(a0, env)
            if a:
                return f"(double) ({a})"
        if fn == "str" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                return f"String.valueOf({a})"
        if fn == "len":
            return None
        if fn == "sum" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.GeneratorExp):
                return _emit_sum_generator(a0, env)
        if fn == "sorted" and node.args:
            a = _emit_expr(node.args[0], env)
            if a:
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Name) and node.args[1].id == "reverse":
                    rev = _emit_expr(node.keywords[0].value, env) if node.keywords else "false"
                    if node.keywords and node.keywords[0].arg == "reverse":
                        rev = _emit_expr(node.keywords[0].value, env)
                    else:
                        rev = "false"
                    return f"{a}.stream().sorted().toList()" if rev == "false" else None
                return f"{a}.stream().sorted().toList()"
        # heuristics for user-defined helpers still named in snake_case
        cname = snake_to_camel(fn)
        args = [_emit_expr(a, env) for a in node.args]
        if any(x is None for x in args):
            return None
        return f"{cname}(" + ", ".join(args) + ")"
    if isinstance(node.func, ast.Attribute) and node.func.attr == "append":
        return None
    if isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "setdefault", "add", "remove", "popleft"):
        return None
    return None


def _emit_sum_generator(gen: ast.GeneratorExp, env: EmitEnv) -> str | None:
    if len(gen.generators) != 1:
        return None
    g = gen.generators[0]
    if g.is_async or g.ifs:
        return None
    if not isinstance(g.iter, ast.Call) or not isinstance(g.iter.func, ast.Name) or g.iter.func.id != "range":
        return None
    elt = _emit_expr(gen.elt, env)
    if elt is None:
        return None
    rargs = g.iter.args
    if len(rargs) == 1:
        hi = _emit_expr(rargs[0], env)
        if not hi:
            return None
        return f"IntStream.range(0, {hi}).map(i -> {elt}).sum()"
    if len(rargs) == 2:
        lo = _emit_expr(rargs[0], env)
        hi = _emit_expr(rargs[1], env)
        if not lo or not hi:
            return None
        return f"IntStream.range({lo}, {hi}).map(i -> {elt}).sum()"
    return None


def _declare_local(target: str, java_type: str, env: EmitEnv) -> None:
    env.types[target] = java_type
    if java_type == "int[]":
        env.int_arrays.add(target)


def _infer_empty_dict_type(name: str) -> str:
    if name in ("seen", "mp", "cnt", "freq", "memo", "cache", "parent", "dist"):
        return "Map<Integer, Integer>"
    return "Map<Integer, Integer>"


def _infer_empty_list_type(name: str) -> str:
    if "pair" in name or "pairs" in name or "edge" in name:
        return "List<List<Integer>>"
    return "List<Integer>"


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
            return [ind + "return;"]
        v = _emit_expr(st.value, env)
        if v is None:
            return None
        return [ind + f"return {v};"]
    if isinstance(st, ast.If):
        return _emit_if(st, env, ind)
    if isinstance(st, ast.While):
        return _emit_while(st, env, ind)
    if isinstance(st, ast.For):
        return _emit_for(st, env, ind)
    if isinstance(st, ast.Break):
        return [ind + "break;"]
    if isinstance(st, ast.Continue):
        return [ind + "continue;"]
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
        if isinstance(st.value.func, ast.Name) and st.value.func.id == "print":
            if not st.value.args:
                return [ind + 'System.out.println();']
            parts = [_emit_expr(a, env) for a in st.value.args]
            if any(p is None for p in parts):
                return None
            if len(parts) == 1:
                return [ind + f"System.out.println({parts[0]});"]
            return [ind + "System.out.println(" + ' + " " + '.join(parts) + ");"]
        # bare call e.g. helper()
        c = _emit_call(st.value, env)
        if c is None:
            return None
        return [ind + c + ";"]
    return None


def _emit_assign(st: ast.Assign, env: EmitEnv, ind: str) -> list[str] | None:
    if len(st.targets) != 1:
        return None
    if isinstance(st.targets[0], ast.Tuple) and isinstance(st.value, ast.Tuple):
        tgts = st.targets[0].elts
        vals = st.value.elts
        if len(tgts) != len(vals):
            return None
        lines: list[str] = []
        for te, ve in zip(tgts, vals):
            if not isinstance(te, ast.Name):
                return None
            rhs = _emit_expr(ve, env)
            if rhs is None:
                return None
            nm = te.id
            if nm in env.types:
                lines.append(ind + f"{nm} = {rhs};")
            else:
                lines.append(ind + f"var {nm} = {rhs};")
                env.types[nm] = "var"
        return lines
    if isinstance(st.targets[0], ast.Subscript):
        sub = st.targets[0]
        if isinstance(sub.value, ast.Name) and isinstance(sub.slice, ast.Name):
            m = sub.value.id
            k = sub.slice.id
            rhs = _emit_expr(st.value, env)
            if rhs is None:
                return None
            mt = env.types.get(m, "")
            if mt.startswith("Map<"):
                return [ind + f"{m}.put({k}, {rhs});"]
        return None
    if not isinstance(st.targets[0], ast.Name):
        return None
    tgt = st.targets[0].id
    val = st.value
    if isinstance(val, ast.Dict) and not val.keys:
        jt = _infer_empty_dict_type(tgt)
        _declare_local(tgt, jt, env)
        return [ind + f"{jt} {tgt} = new HashMap<>();"]
    if isinstance(val, ast.List) and not val.elts:
        jt = _infer_empty_list_type(tgt)
        _declare_local(tgt, jt, env)
        if jt == "List<Integer>":
            return [ind + f"List<Integer> {tgt} = new ArrayList<>();"]
        return [ind + f"{jt} {tgt} = new ArrayList<>();"]
    rhs = _emit_expr(val, env)
    if rhs is None:
        return None
    if tgt in env.types:
        return [ind + f"{tgt} = {rhs};"]
    # infer type from rhs heuristics
    if "new int[]" in rhs or rhs.startswith("new int[]"):
        _declare_local(tgt, "int[]", env)
        return [ind + f"int[] {tgt} = {rhs};"]
    if rhs == "new int[0]":
        _declare_local(tgt, "int[]", env)
        return [ind + f"int[] {tgt} = {rhs};"]
    if rhs.startswith("new HashMap"):
        jt = _infer_empty_dict_type(tgt)
        _declare_local(tgt, jt, env)
        return [ind + f"{jt} {tgt} = {rhs};"]
    if rhs.endswith("()") and "Deque" in rhs:
        _declare_local(tgt, "ArrayDeque<Integer>", env)
        return [ind + f"ArrayDeque<Integer> {tgt} = {rhs};"]
    return [ind + f"var {tgt} = {rhs};"]


def _emit_augassign(st: ast.AugAssign, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    t = st.target.id
    rhs = _emit_expr(st.value, env)
    if rhs is None:
        return None
    if isinstance(st.op, ast.Add):
        return [ind + f"{t} += {rhs};"]
    if isinstance(st.op, ast.Sub):
        return [ind + f"{t} -= {rhs};"]
    if isinstance(st.op, ast.Mult):
        return [ind + f"{t} *= {rhs};"]
    return None


def _emit_annassign(st: ast.AnnAssign, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    tgt = st.target.id
    jt = annotation_to_java(st.annotation)
    if st.value is None:
        return None
    rhs = _emit_expr(st.value, env)
    if rhs is None:
        return None
    _declare_local(tgt, jt, env)
    if jt == "int[]":
        env.int_arrays.add(tgt)
    return [ind + f"{jt} {tgt} = {rhs};"]


def _emit_if(st: ast.If, env: EmitEnv, ind: str) -> list[str] | None:
    cond = _emit_expr(st.test, env)
    if cond is None:
        return None
    then_body = _emit_block(st.body, env, ind + "    ")
    if then_body is None:
        return None
    lines = [ind + f"if ({cond}) {{"] + then_body
    if not st.orelse:
        lines.append(ind + "}")
        return lines
    lines.append(ind + "} else {")
    if len(st.orelse) == 1 and isinstance(st.orelse[0], ast.If):
        sub = _emit_if(st.orelse[0], env, ind + "    ")
        if sub is None:
            return None
        lines.extend(sub)
    else:
        ob = _emit_block(st.orelse, env, ind + "    ")
        if ob is None:
            return None
        lines.extend(ob)
    lines.append(ind + "}")
    return lines


def _emit_while(st: ast.While, env: EmitEnv, ind: str) -> list[str] | None:
    cond = _emit_expr(st.test, env)
    if cond is None:
        return None
    body = _emit_block(st.body, env, ind + "    ")
    if body is None:
        return None
    return [ind + f"while ({cond}) {{"] + body + [ind + "}"]


def _emit_for(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if isinstance(st.iter, ast.Call) and isinstance(st.iter.func, ast.Name) and st.iter.func.id == "range":
        return _emit_for_range(st, env, ind)
    if isinstance(st.iter, ast.Call) and isinstance(st.iter.func, ast.Name) and st.iter.func.id == "enumerate":
        return _emit_for_enumerate(st, env, ind)
    if isinstance(st.iter, ast.Name):
        return _emit_for_each(st, env, ind)
    return None


def _emit_for_range(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    iv = st.target.id
    args = st.iter.args  # type: ignore
    if len(args) == 1:
        hi = _emit_expr(args[0], env)
        if not hi:
            return None
        inner_env = env.copy()
        inner_env.types[iv] = "int"
        body = _emit_block(st.body, inner_env, ind + "    ")
        if body is None:
            return None
        return [ind + f"for (int {iv} = 0; {iv} < {hi}; {iv}++) {{"] + body + [ind + "}"]
    if len(args) == 2:
        lo = _emit_expr(args[0], env)
        hi = _emit_expr(args[1], env)
        if not lo or not hi:
            return None
        inner_env = env.copy()
        inner_env.types[iv] = "int"
        body = _emit_block(st.body, inner_env, ind + "    ")
        if body is None:
            return None
        return [ind + f"for (int {iv} = {lo}; {iv} < {hi}; {iv}++) {{"] + body + [ind + "}"]
    if len(args) == 3:
        lo = _emit_expr(args[0], env)
        hi = _emit_expr(args[1], env)
        stp = _emit_expr(args[2], env)
        if not lo or not hi or not stp:
            return None
        inner_env = env.copy()
        inner_env.types[iv] = "int"
        body = _emit_block(st.body, inner_env, ind + "    ")
        if body is None:
            return None
        return [ind + f"for (int {iv} = {lo}; {iv} < {hi}; {iv} += {stp}) {{"] + body + [ind + "}"]
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
    inner_env = env.copy()
    inner_env.types[i_n] = "int"
    if seq_n in env.int_arrays:
        inner_env.types[v_n] = "int"
        body = _emit_block(st.body, inner_env, ind + "    ")
        if body is None:
            return None
        return (
            [ind + f"for (int {i_n} = 0; {i_n} < {seq_n}.length; {i_n}++) {{", ind + f"    int {v_n} = {seq_n}[{i_n}];"]
            + body
            + [ind + "}"]
        )
    inner_env.types[v_n] = "int"
    body = _emit_block(st.body, inner_env, ind + "    ")
    if body is None:
        return None
    return (
        [ind + f"for (int {i_n} = 0; {i_n} < {seq_n}.size(); {i_n}++) {{", ind + f"    int {v_n} = {seq_n}.get({i_n});"]
        + body
        + [ind + "}"]
    )


def _emit_for_each(st: ast.For, env: EmitEnv, ind: str) -> list[str] | None:
    if not isinstance(st.target, ast.Name):
        return None
    v = st.target.id
    if not isinstance(st.iter, ast.Name):
        return None
    seq = st.iter.id
    inner = env.copy()
    if seq in env.int_arrays:
        inner.types[v] = "int"
        body = _emit_block(st.body, inner, ind + "    ")
        if body is None:
            return None
        return [ind + f"for (int {v} : {seq}) {{"] + body + [ind + "}"]
    inner.types[v] = "int"
    body = _emit_block(st.body, inner, ind + "    ")
    if body is None:
        return None
    return [ind + f"for (int {v} : {seq}) {{"] + body + [ind + "}"]


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
        jt = annotation_to_java(a.annotation) if a.annotation else "Object"
        env.types[a.arg] = jt
        if jt == "int[]":
            env.int_arrays.add(a.arg)
    return env


def emit_solution_function_java(fn: ast.FunctionDef) -> str:
    """Full `static Type name(...) { ... }` — AST translation when possible, else commented steps + default return."""
    ret = annotation_to_java(fn.returns)
    if ret == "int[]":
        ret_ty = "int[]"
    elif ret == "void":
        ret_ty = "void"
    else:
        ret_ty = ret
    name = snake_to_camel(fn.name)
    params = params_to_java(fn.args, skip_self=True)
    env = _build_param_env(fn)
    body_stmts: list[ast.stmt] = []
    for st in fn.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        body_stmts.append(st)
    body_lines = _emit_block(body_stmts, env, "        ")
    if body_lines is None:
        return function_python_as_java_comments(fn)
    body = "\n".join(body_lines)
    return f"static {ret_ty} {name}({params}) {{\n{body}\n}}"


def _default_return_line(fn: ast.FunctionDef) -> str:
    ret = annotation_to_java(fn.returns)
    if ret in ("void", "None"):
        return "return;"
    if ret == "boolean":
        return "return false;"
    if ret == "int":
        return "return 0;"
    if ret == "long":
        return "return 0L;"
    if ret == "double":
        return "return 0.0;"
    if ret == "int[]":
        return "return new int[0];"
    if ret == "String":
        return 'return "";'
    if "ListNode" in ret or ret == "ListNode":
        return "return null;"
    if ret.startswith("List<") or ret.startswith("Map<"):
        return "return null;"
    return "return null;"


def function_python_as_java_comments(fn: ast.FunctionDef) -> str:
    """When AST→Java fails, keep the full solution visible as // lines plus a compiling default return."""
    ret = annotation_to_java(fn.returns)
    ret_ty = "int[]" if ret == "int[]" else ("void" if ret in ("void", "None") else ret)
    name = snake_to_camel(fn.name)
    params = params_to_java(fn.args, skip_self=True)
    lines: list[str] = ["        // --- Reference solution (course notation; translate to Java) ---"]
    for st in fn.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            continue
        for ln in ast.unparse(st).split("\n"):
            lines.append("        // " + ln.replace("*/", "* /"))
    lines.append("        " + _default_return_line(fn))
    body = "\n".join(lines)
    return f"static {ret_ty} {name}({params}) {{\n{body}\n}}"
