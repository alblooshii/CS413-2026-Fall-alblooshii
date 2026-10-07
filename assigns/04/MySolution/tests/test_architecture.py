"""Architectural boundaries, checked from the import graph (static, via ast)."""
import ast
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "lambda_ui"


def imports(module: str) -> set[str]:
    """Top-level names imported by lambda_ui/<module>.py (relative imports -> module name)."""
    tree = ast.parse((PKG / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:                       # from .x import y  /  from . import x
                found.update([node.module.split(".")[0]] if node.module
                             else [a.name for a in node.names])
            else:
                found.add(node.module.split(".")[0])
    return found


class Boundaries(unittest.TestCase):
    def test_contract_depends_on_nothing_in_the_app(self):
        self.assertFalse(imports("contract") & {"model", "controller", "view", "web",
                                                "backend", "reader", "worker", "lambda1", "flask"})

    def test_model_is_independent_of_web_views_and_language_tools(self):
        self.assertFalse(imports("model") & {"flask", "controller", "view", "web", "backend",
                                             "reader", "worker", "lambda1", "subprocess"})

    def test_controller_knows_backend_only_through_the_contract(self):
        self.assertFalse(imports("controller") & {"flask", "view", "web", "backend",
                                                  "reader", "worker", "lambda1", "subprocess"})

    def test_view_does_not_depend_on_how_tools_are_invoked(self):
        self.assertFalse(imports("view") & {"flask", "controller", "web", "backend",
                                            "reader", "worker", "lambda1", "subprocess"})

    def test_only_the_composition_root_builds_the_real_backend(self):
        users = {p.stem for p in PKG.glob("*.py")
                 if p.stem not in {"backend"} and "backend" in imports(p.stem)}
        self.assertEqual(users, {"web"})

    def test_only_reader_and_worker_touch_lambda1(self):
        users = {p.stem for p in PKG.glob("*.py") if "lambda1" in imports(p.stem)}
        self.assertEqual(users, {"reader", "worker"})

    def test_browser_code_contains_no_language_logic(self):
        js = (PKG / "static" / "app.js").read_text(encoding="utf-8")
        for token in ("D0E", "D0V", "fvset", "evaluate", "eval(", "innerHTML"):
            self.assertNotIn(token, js)


if __name__ == "__main__":
    unittest.main()
