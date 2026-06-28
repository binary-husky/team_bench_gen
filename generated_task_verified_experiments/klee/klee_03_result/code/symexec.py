"""
Lightweight symbolic / concolic execution engine (Python + z3).

Interprets a subset of the Python AST (arithmetic, comparisons, boolean
ops, if/elif/else, return, bool() short-circuit) with *symbolic* (z3) values.
At every `If` node the engine forks into the True and False arms, accumulates
path constraints, and asks z3 whether each arm is feasible (sat). When a
`return` is reached, the current path constraint set is solved for a concrete
model = one generated test input, and the sequence of branch decisions
(taken/untaken at each If, keyed by AST node id) is recorded as the
"execution path".

This mirrors the KLEE-style "one test input per feasible path" relationship
described in Cadar et al. 2008, but without the KLEE binary itself.

Only CPU + pip + z3-solver. No GPU, no KLEE.
"""
import ast
import z3

# z3 BitVec width used for all symbolic ints (wide enough to avoid overflow in toys)
BW = 32


def to_bv(v):
    if isinstance(v, bool):
        return z3.BitVecVal(1 if v else 0, BW)
    if isinstance(v, int):
        return z3.BitVecVal(v, BW)
    return v


def is_bool_val(v):
    return isinstance(v, (bool,)) or (z3.is_bool(v))


def as_bool(v):
    """Coerce a value to a z3 boolean expression (Python truth semantics)."""
    if isinstance(v, bool):
        return v
    if z3.is_bool(v):
        return v
    # non-zero integer -> True
    b = to_bv(v)
    return b != z3.BitVecVal(0, BW)


class SymExec:
    def __init__(self, tree, func_name, seed=0):
        self.tree = tree
        self.func_name = func_name
        self.seed = seed
        self.rng = z3.Random(seed) if hasattr(z3, 'Random') else None
        # results
        self.tests = []        # list of dict (concrete models)
        self.paths = []        # list of tuple(branch decisions)
        self.branch_edges = {}  # node_id -> set('T'/'F')
        self.total_if_nodes = set()
        # Pre-collect all If nodes (for coverage denominator)
        for node in ast.walk(self.tree):
            if isinstance(node, ast.If):
                self.total_if_nodes.add(id(node))

    # ---- AST evaluation -------------------------------------------------
    def run(self, args):
        """args: dict name->z3 expr. Returns (return_value, path_tuple)."""
        # find FunctionDef
        func = None
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == self.func_name:
                func = node
                break
        assert func is not None, f"function {self.func_name} not found"

        env = dict(args)
        path = []
        # execute statements; a Return raises a sentinel carrying the value
        try:
            self._exec_stmts(func.body, env, path)
        except _Return as r:
            val = r.value
            return val, tuple(path)
        return None, tuple(path)

    def _exec_stmts(self, stmts, env, path):
        for s in stmts:
            self._exec_stmt(s, env, path)

    def _exec_stmt(self, node, env, path):
        if isinstance(node, ast.Return):
            val = self._eval(node.value, env) if node.value is not None else None
            raise _Return(val)
        elif isinstance(node, ast.If):
            self._exec_if(node, env, path)
        elif isinstance(node, ast.Assign):
            val = self._eval(node.value, env)
            for tgt in node.targets:
                env[tgt.id] = val
        elif isinstance(node, ast.AugAssign):
            cur = env[node.target.id]
            rhs = self._eval(node.value, env)
            env[node.target.id] = self._binop(node.op, cur, rhs)
        elif isinstance(node, ast.Expr):
            self._eval(node.value, env)
        elif isinstance(node, ast.Pass):
            pass
        else:
            raise NotImplementedError(ast.dump(node))

    def _exec_if(self, node, env, path):
        cond = as_bool(self._eval(node.test, env))
        # record edge coverage (feasibility decided by caller via constraints)
        nid = id(node)
        # The forking/feasibility is handled by the driver (run_all).
        # Here we just execute the chosen arm; the driver calls us per-arm.
        raise _Branch(node, cond, env, path)

    # ---- expression evaluation -----------------------------------------
    def _eval(self, node, env):
        if node is None:
            return None
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return env[node.id]
        if isinstance(node, ast.BoolOp):
            return self._boolop(node, env)
        if isinstance(node, ast.UnaryOp):
            return self._unaryop(node, env)
        if isinstance(node, ast.BinOp):
            l = self._eval(node.left, env)
            r = self._eval(node.right, env)
            return self._binop(node.op, l, r)
        if isinstance(node, ast.Compare):
            return self._compare(node, env)
        if isinstance(node, ast.IfExp):
            cond = as_bool(self._eval(node.test, env))
            raise _BranchExpr(node, cond, env)
        raise NotImplementedError(ast.dump(node))

    def _boolop(self, node, env):
        # short-circuit; evaluate lazily but symbolically we need the chain
        vals = [self._eval(v, env) for v in node.values]
        if isinstance(node.op, ast.And):
            acc = as_bool(vals[0])
            for v in vals[1:]:
                acc = z3.And(acc, as_bool(v))
            return acc
        else:  # Or
            acc = as_bool(vals[0])
            for v in vals[1:]:
                acc = z3.Or(acc, as_bool(v))
            return acc

    def _unaryop(self, node, env):
        v = self._eval(node.operand, env)
        if isinstance(node.op, ast.Not):
            return z3.Not(as_bool(v))
        if isinstance(node.op, ast.USub):
            return -to_bv(v)
        if isinstance(node.op, ast.UAdd):
            return to_bv(v)
        raise NotImplementedError(ast.dump(node.op))

    def _binop(self, op, l, r):
        l = to_bv(l); r = to_bv(r)
        if isinstance(op, ast.Add): return l + r
        if isinstance(op, ast.Sub): return l - r
        if isinstance(op, ast.Mult): return l * r
        if isinstance(op, ast.FloorDiv) or isinstance(op, ast.Div): return l / r
        if isinstance(op, ast.Mod): return l % r
        if isinstance(op, ast.Lt): return l < r
        if isinstance(op, ast.LtE): return l <= r
        if isinstance(op, ast.Gt): return l > r
        if isinstance(op, ast.GtE): return l >= r
        if isinstance(op, ast.Eq): return l == r
        if isinstance(op, ast.NotEq): return l != r
        raise NotImplementedError(ast.dump(op))

    def _compare(self, node, env):
        left = self._eval(node.left, env)
        acc = None
        for op, comp in zip(node.ops, node.comparators):
            right = self._eval(comp, env)
            r = self._binop(op, left, right)
            acc = r if acc is None else z3.And(acc, r)
            left = right
        return acc


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Branch(Exception):
    """Raised at an If so the driver can fork on the (already-symbolic) cond."""
    def __init__(self, node, cond, env, path):
        self.node = node
        self.cond = cond
        self.env = dict(env)
        self.path = list(path)


class _BranchExpr(Exception):
    def __init__(self, node, cond, env):
        self.node = node
        self.cond = cond
        self.env = dict(env)


# ----------------------------------------------------------------------
def sat_check(constraints):
    s = z3.Solver()
    for c in constraints:
        s.add(c)
    return s.check() == z3.sat


def model_of(constraints, names):
    s = z3.Solver()
    for c in constraints:
        s.add(c)
    if s.check() != z3.sat:
        return None
    m = s.model()
    out = {}
    for n, sym in names.items():
        v = m.eval(sym, model_completion=True)
        out[n] = v.as_signed_long() if hasattr(v, 'as_signed_long') else int(str(v))
    return out


def enumerate_paths(source, func_name, arg_names, seed=0, max_paths=10000):
    """Tree-walk symbolic execution: fork at each If, prune infeasible paths
    with z3, collect one test input per feasible path."""
    tree = ast.parse(source)
    se = SymExec(tree, func_name, seed=seed)

    # symbolic arg vars
    syms = {n: z3.BitVec(f'{func_name}_{n}', BW) for n in arg_names}

    # worklist items: (env, constraints, path, pc_index_in_stmt_list, stmt_list)
    # Simpler: recursive exploration with explicit stack of (env, constraints, path, stmts)
    results = []  # (path_tuple, test_dict)

    def explore(env, constraints, path, stmts, idx):
        while idx < len(stmts):
            s = stmts[idx]
            try:
                se._exec_stmt(s, env, path)
                idx += 1
            except _Return as r:
                # feasible path reached return -> record
                if sat_check(constraints):
                    mdl = model_of(constraints, syms)
                    if mdl is not None:
                        results.append((tuple(path), mdl, constraints))
                return
            except _Branch as b:
                node = b.node
                nid = id(node)
                cond = b.cond
                t_cons = constraints + [cond]
                f_cons = constraints + [z3.Not(cond)]
                t_sat = sat_check(t_cons)
                f_sat = sat_check(f_cons)
                edges = se.branch_edges.setdefault(nid, set())
                if t_sat:
                    edges.add('T')
                if f_sat:
                    edges.add('F')
                order = [True, False]
                if seed % 2 == 1:
                    order = [False, True]
                for take in order:
                    c = t_cons if take else f_cons
                    if not (t_sat if take else f_sat):
                        continue
                    arm = node.body if take else (node.orelse if node.orelse else [])
                    new_env = dict(b.env)
                    new_path = list(b.path) + [('T' if take else 'F', nid)]
                    # arm statements, then continue with statements after the if
                    cont = list(arm) + list(stmts[idx + 1:])
                    explore(new_env, c, new_path, cont, 0)
                return
        # fell off end of stmts without return
        if sat_check(constraints):
            mdl = model_of(constraints, syms)
            if mdl is not None:
                results.append((tuple(path), mdl, constraints))

    # find function body
    func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            func = node
    explore(dict(syms), [], [], func.body, 0)

    # dedup paths (a path may be recorded twice via fall-through); keep first model
    seen = set()
    dedup = []
    for p, mdl, _ in results:
        if p in seen:
            continue
        seen.add(p)
        dedup.append((p, mdl))

    se.tests = [d for _, d in dedup]
    se.paths = [p for p, _ in dedup]
    return se


def branch_coverage(se):
    covered = sum(len(v) for v in se.branch_edges.values())
    total = 2 * len(se.total_if_nodes)
    return covered, total, (covered / total if total else 1.0)
