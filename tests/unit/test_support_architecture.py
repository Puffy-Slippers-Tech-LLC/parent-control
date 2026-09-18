"""Keep reusable test infrastructure independent of collected test-case modules."""

import ast

import pytest

from tests.support.paths import ROOT

CASE_PATHS = tuple(sorted((ROOT / "tests").rglob("test_*.py")))
SUPPORT_PATHS = tuple(sorted((ROOT / "tests/support").rglob("*.py")))


def case_module_names(paths):
    # Integration contains executable harness helpers, not pytest case modules.
    # Keep inspecting those files below, but allow tests to import their APIs.
    return {path.stem for path in paths
            if path.relative_to(ROOT / "tests").parts[0] != "integration"}


CASE_MODULES = case_module_names(CASE_PATHS)


@pytest.mark.parametrize("directory,expected", [
    ("integration", set()),
    ("unit", {"test_account_password"}),
    ("component", {"test_account_password"}),
    ("ui", {"test_account_password"}),
    ("fixtures", {"test_account_password"}),
    ("system", {"test_account_password"}),
    ("e2e", {"test_account_password"}),
])
def test_case_module_classification_distinguishes_harness_helpers(directory, expected):
    path = ROOT / "tests" / directory / "test_account_password.py"
    assert case_module_names([path]) == expected


@pytest.mark.parametrize("path", (*CASE_PATHS, *SUPPORT_PATHS),
                         ids=lambda path: path.relative_to(ROOT).as_posix())
def test_helpers_do_not_import_collected_case_modules(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f'{node.module}.{alias.name}' for alias in node.names)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "__import__" and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            imports.append(node.args[0].value)
    assert not [name for name in imports if name.split(".")[-1] in CASE_MODULES], (
        "Move reusable fixtures into tests/support; import the module under test directly."
    )


@pytest.mark.parametrize("path", CASE_PATHS,
                         ids=lambda path: path.relative_to(ROOT).as_posix())
def test_case_import_bootstrapping_uses_the_shared_configuration(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        function = node.value.func
        assert not (isinstance(function, ast.Attribute)
                    and isinstance(function.value, ast.Attribute)
                    and isinstance(function.value.value, ast.Name)
                    and function.value.value.id == "sys"
                    and function.value.attr == "path"), (
            "Use pyproject.toml pythonpath or tests.support.modules for standalone scripts."
        )
