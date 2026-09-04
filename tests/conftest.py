"""Shared pytest classification for the host-safe test suite."""

from pathlib import Path

from hypothesis import settings

# Generated broker tests must be reproducible in CI and on a developer's
# machine. Keep the profile bounded because installed-system behavior belongs
# to later plan stages; this stage exercises host-safe policy transactions.
settings.register_profile(
    "onpc",
    settings(
        database=None,
        deadline=None,
        derandomize=True,
        max_examples=80,
        stateful_step_count=30,
    ),
)
settings.load_profile("onpc")


# These tests protect source/configuration interfaces.  They remain valuable,
# but are deliberately distinct from runtime acceptance tests in traceability.
CONTRACT_MODULES = frozenset(
    {
        "test_child_preview.py",
        "test_installer.py",
        "test_integration_harness.py",
        "test_kiosk_rendering.py",
        "test_package_activation.py",
        "test_prepare_vm_contract.py",
        "test_service_contract.py",
        "test_systemd_unit.py",
    }
)


def pytest_collection_modifyitems(items):
    """Give every collected test one explicit, understandable test layer."""

    for item in items:
        filename = Path(str(item.fspath)).name
        if "component" in Path(str(item.fspath)).parts:
            item.add_marker("component")
        else:
            item.add_marker("contract" if filename in CONTRACT_MODULES else "unit")
