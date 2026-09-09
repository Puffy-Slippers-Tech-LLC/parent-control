"""Exercise the compiled module through real libpam with private configuration."""

import ctypes
import subprocess

import pytest

from tests.support.paths import ROOT


@pytest.fixture(scope="module")
def pam_modules(tmp_path_factory):
    build = tmp_path_factory.mktemp("onpc-pam-runtime")
    modules = []
    for source in ("tools/pam_oh_no_parent_control.c",
                   "tests/support/pam_runtime_fixture.c"):
        output = build / (source.rsplit("/", 1)[-1] + ".so")
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
             "-o", str(output), str(ROOT / source), "-lpam"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        modules.append(output)
    return modules


def run_pam(confdir, service="gdm-password"):
    """Load only our two test-local modules; never open a real login session."""
    pam = ctypes.CDLL("libpam.so.0")

    class Conversation(ctypes.Structure):
        _fields_ = [("conv", ctypes.c_void_p), ("appdata_ptr", ctypes.c_void_p)]

    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.POINTER(Conversation), ctypes.c_char_p,
                                    ctypes.POINTER(ctypes.c_void_p)]
    for name in ("pam_acct_mgmt", "pam_open_session", "pam_close_session", "pam_end"):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    handle = ctypes.c_void_p()
    conversation = Conversation()
    assert pam.pam_start_confdir(service.encode(), b"private-account-canary",
                                ctypes.byref(conversation), str(confdir).encode(),
                                ctypes.byref(handle)) == 0
    try:
        account_result = pam.pam_acct_mgmt(handle, 0)
        session_result = None
        if account_result == 0:
            session_result = pam.pam_open_session(handle, 0)
            if session_result == 0:
                assert pam.pam_close_session(handle, 0) == 0
        return account_result, session_result
    finally:
        assert pam.pam_end(handle, 0) == 0


@pytest.mark.parametrize("service", [
    "gdm-password", "gdm-autologin", "gdm-fingerprint", "gdm-smartcard",
])
@pytest.mark.parametrize("remaining", ["1", "120", "infinity", None])
def test_runtime_cap_is_removed_before_session_creation(
        pam_modules, tmp_path, remaining, service):
    product, fixture = pam_modules
    seed = f" seed={remaining}" if remaining is not None else ""
    expected = "infinity" if remaining is not None else "absent"
    (tmp_path / service).write_text(
        f"account required {fixture} memory{seed}\n"
        f"account required {product}\n"
        # Repeating account reconciliation must remain harmless.
        f"account required {product}\n"
        f"session required {fixture} {expected}\n"
    )
    assert run_pam(tmp_path, service) == (0, 0)


@pytest.mark.parametrize("service", ["login", "sshd", "sudo", "systemd-user"])
def test_non_gdm_services_keep_the_runtime_cap(pam_modules, tmp_path, service):
    product, fixture = pam_modules
    (tmp_path / service).write_text(
        f"account required {fixture} memory seed=1\n"
        f"account required {product}\n"
        f"session required {fixture} 1\n"
    )
    assert run_pam(tmp_path, service) == (0, 0)


@pytest.mark.parametrize("policy", ["expired", "error"])
def test_removing_cap_does_not_override_an_account_denial(pam_modules, tmp_path, policy):
    product, fixture = pam_modules
    (tmp_path / "gdm-password").write_text(
        f"account required {fixture} memory seed=1 {policy}\n"
        f"account required {product}\n"
        f"session required {fixture} infinity\n"
    )
    account_result, session_result = run_pam(tmp_path)
    assert account_result != 0
    assert session_result is None


def test_without_account_hook_one_second_cap_reaches_session(pam_modules, tmp_path):
    _product, fixture = pam_modules
    (tmp_path / "gdm-password").write_text(
        f"account required {fixture} memory seed=1\n"
        f"session required {fixture} infinity\n"
    )
    account_result, session_result = run_pam(tmp_path)
    assert account_result == 0
    assert session_result != 0


@pytest.mark.parametrize("bypass", [None, 0, 1, 2, 3])
def test_packaged_account_stack_scopes_cap_to_malcontent_accounts(
        pam_modules, tmp_path, bypass):
    product, fixture = pam_modules
    profile = (ROOT / "data/pam-configs/oh-no-parent-control-session-limits").read_text()
    account = profile.split("\nAccount:\n", 1)[1].split("\nSession", 1)[0]
    lines = [f"account required {fixture} memory seed=37"]
    gates = 0
    for line in account.splitlines():
        if not line.strip():
            continue
        if "pam_succeed_if.so" in line or "pam_exec.so" in line:
            control = line[:line.index("]") + 1].strip()
            result = "success" if gates == bypass else "ignore"
            lines.append(f"account {control} {fixture} {result}")
            gates += 1
        elif "pam_malcontent.so" in line:
            # Unexpected calls on bypass paths fail the real PAM transaction.
            operation = "seed=1" if bypass is None else "error"
            lines.append(f"account required {fixture} {operation}")
        elif "pam_oh_no_parent_control.so" in line:
            lines.append(f"account required {product}")
        else:
            pytest.fail("unhandled packaged PAM entry")
    assert gates == 4
    expected = "infinity" if bypass is None else "37"
    lines.append(f"session required {fixture} {expected}")
    (tmp_path / "gdm-password").write_text("\n".join(lines) + "\n")
    assert run_pam(tmp_path) == (0, 0)
