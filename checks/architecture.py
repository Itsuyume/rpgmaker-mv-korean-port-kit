"""Check local imports, cycles and size limits without importing application code."""

import ast
from graphlib import CycleError, TopologicalSorter
from importlib.util import resolve_name
from pathlib import Path
import sys


LEAVES = {"pq_catalog.model", "pq_catalog.schema", "pq_catalog.tokens"}
CONTROL = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
           ast.AsyncWith, ast.Match)


def sources(root: Path) -> dict[str, Path]:
    result = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part in {"tests", "__pycache__"} for part in relative.parts):
            continue
        parts = relative.with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        if name:
            result[name] = path
    return result


def imported_modules(tree: ast.AST, name: str, package_file: bool) -> set[str]:
    result = set()
    package = name if package_file else name.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = "." * node.level + (node.module or "")
            module = resolve_name(base, package) if node.level else base
            result.add(module)
            result.update(module + "." + alias.name for alias in node.names)
    return result


def flow_depth(node: ast.AST, depth: int = 0) -> int:
    if isinstance(node, ast.If):
        body = [flow_depth(child, depth + 1) for child in node.body]
        # Python represents an elif chain as nested If nodes in orelse.
        alternate_depth = depth if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) else depth + 1
        alternate = [flow_depth(child, alternate_depth) for child in node.orelse]
        return max([depth + 1, *body, *alternate])
    depth += isinstance(node, CONTROL)
    children = [flow_depth(child, depth) for child in ast.iter_child_nodes(node)]
    return max([depth, *children])


def size_errors(name: str, path: Path, tree: ast.AST) -> list[str]:
    if name.startswith("runtime.shared."):
        return []
    errors = []
    if len(path.read_text(encoding="utf-8").splitlines()) > 300:
        errors.append(name + ": file exceeds 300 lines")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        label = name + "." + node.name
        if node.end_lineno is None or node.end_lineno - node.lineno + 1 > 70:
            errors.append(label + ": function exceeds 70 lines")
        if flow_depth(node) > 4:
            errors.append(label + ": control flow exceeds four levels")
        decisions = sum(isinstance(item, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                         ast.ExceptHandler, ast.IfExp, ast.comprehension))
                        for item in ast.walk(node))
        decisions += sum(len(item.values) - 1 for item in ast.walk(node) if isinstance(item, ast.BoolOp))
        if decisions > 20:
            errors.append(label + ": more than 20 decision paths")
    return errors


def check(root: Path) -> list[str]:
    files = sources(root)
    graph: dict[str, set[str]] = {}
    errors = []
    for name, path in files.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = imported_modules(tree, name, path.name == "__init__.py")
        local = imports & files.keys()
        graph[name] = local
        errors.extend(size_errors(name, path, tree))
        if name in LEAVES and local:
            errors.append(name + ": leaf imports another local module")
        if name.startswith("runtime.") and any(item.startswith("pq_catalog") for item in local):
            errors.append(name + ": runtime imports catalog")
        foreign = {item for item in local if item.startswith("runtime") and item != "runtime.shared.archive"}
        if name.startswith("pq_catalog.") and foreign:
            errors.append(name + ": catalog imports a runtime implementation module")
        if path.name == "__init__.py" and any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body):
            errors.append(name + ": package initializer must not re-export modules")
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError as error:
        errors.append("Import cycle: " + " -> ".join(error.args[1]))
    return errors


if __name__ == "__main__":
    problems = check(Path(__file__).resolve().parents[1])
    for problem in problems:
        print(problem, file=sys.stderr)
    print("Architecture checks: " + ("failed" if problems else "passed"))
    raise SystemExit(bool(problems))
