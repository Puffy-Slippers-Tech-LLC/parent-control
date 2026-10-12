"""Kiosk routing policy and real PAM transactions, without a live login or bus."""

import ctypes
from contextlib import contextmanager
import fcntl
import importlib.machinery
import importlib.util
import json
import multiprocessing
import os
import shlex
import subprocess
import time
from types import SimpleNamespace

import pytest

from tests.support.paths import ROOT


def test_legacy_pam_entry_ignores_python_startup_environment(tmp_path):
    entry = tmp_path / "login-check"
    entry.write_bytes((ROOT / "tools/oh-no-parent-control-login-check").read_bytes())
    # Package staging installs this source as an executable; the checkout
    # source itself deliberately has no executable mode bit.
    entry.chmod(0o700)
    marker = tmp_path / "startup-executed"
    (tmp_path / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    environment = dict(os.environ, PYTHONPATH=str(tmp_path),
                       PAM_USER="ordinary-private-account", PAM_SERVICE="sshd")
    result = subprocess.run(
        [str(entry)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert not marker.exists()


@pytest.fixture
def routing(monkeypatch):
    loader = importlib.machinery.SourceFileLoader(
        "onpc_kiosk_login", str(ROOT / "tools/oh-no-parent-control-login-check"))
    helper = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(helper)
    state = SimpleNamespace(session=helper.SESSION, transport="wayland", calls=[],
                            records=[], fault=None, no_write=False)
    monkeypatch.setenv("PAM_USER", helper.KIOSK_USER)
    monkeypatch.setenv("PAM_SERVICE", "gdm-password")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=12345))
    monkeypatch.setattr(helper.syslog, "syslog", lambda level, text: state.records.append(text))

    def command(argv, **kwargs):
        assert argv[:4] == ["/usr/bin/busctl", "--system", "--timeout=4",
                            "--allow-interactive-authorization=no"]
        assert kwargs == dict(check=True, capture_output=True, text=True,
                              timeout=5, env=helper.ENVIRONMENT)
        assert argv[5:8] == [helper.BUS, "/org/freedesktop/Accounts/User12345", helper.INTERFACE]
        state.calls.append(argv[4:])
        if state.fault:
            raise state.fault
        if argv[4] == "get-property":
            assert argv[8:] == ["Session", "SessionType"]
            output = f"s {shlex.quote(state.session)}\ns {shlex.quote(state.transport)}\n"
        else:
            assert argv[4] == "call" and argv[9] == "s"
            if not state.no_write:
                if argv[8] == "SetSession":
                    state.session = argv[10]
                elif argv[8] == "SetSessionType":
                    state.transport = argv[10]
                else:
                    pytest.fail("unexpected AccountsService mutation")
            output = ""
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(helper.subprocess, "run", command)
    return helper, state


def test_dedicated_selection_must_be_saved_between_account_and_open(routing):
    helper, state = routing
    assert helper.main(["--kiosk-account"]) == 0
    assert state.session == helper.PENDING_SESSION
    # Model GDM's public SetSession call after account authorization.
    state.session = helper.SESSION
    assert helper.main(["--kiosk-session"]) == 0
    assert "outcome=armed" in state.records[0]
    assert "outcome=allowed" in state.records[-1]


@pytest.mark.parametrize("selected", ["ubuntu", "gnome", "", None])
def test_desktop_fallback_or_failed_gdm_save_is_denied_and_default_restored(routing, selected):
    helper, state = routing
    assert helper.main(["--kiosk-account"]) == 0
    if selected is not None:
        state.session = selected
    assert helper.main(["--kiosk-session"]) == 1
    assert (state.session, state.transport) == (helper.SESSION, "wayland")
    assert "outcome=denied" in state.records[-1]
    assert "recovery=restored" in state.records[-1]


@pytest.mark.parametrize("session,transport", [("ubuntu", ""), ("", "wayland"),
                                               ("oh-no-parent-control", "x11"),
                                               ("oh-no-parent-control-verification-pending", "wayland")])
def test_bad_default_or_aborted_transaction_is_repaired_but_not_admitted(routing, session, transport):
    helper, state = routing
    state.session, state.transport = session, transport
    assert helper.main(["--kiosk-account"]) == 1
    assert (state.session, state.transport) == (helper.SESSION, "wayland")
    assert helper.main(["--kiosk-account"]) == 0


@pytest.mark.parametrize("transport", ["x11", "", "tty"])
def test_actual_transport_is_checked_in_pam_environment(routing, monkeypatch, transport):
    helper, state = routing
    monkeypatch.setenv("XDG_SESSION_TYPE", transport)
    assert helper.main(["--kiosk-session"]) == 1
    assert "outcome=denied" in state.records[-1]


@pytest.mark.parametrize("fault", [OSError("private-identity"),
                                  subprocess.TimeoutExpired("private-identity", 5),
                                  subprocess.CalledProcessError(1, "busctl", stderr="private-identity")])
def test_indeterminate_policy_fails_closed_without_logging_exception_text(routing, fault):
    helper, state = routing
    state.fault = fault
    assert helper.main(["--kiosk-account"]) == 1
    assert "outcome=unavailable" in state.records[-1]
    assert "private-identity" not in " ".join(state.records)


def test_successful_but_uncommitted_marker_write_is_denied(routing):
    helper, state = routing
    state.no_write = True
    assert helper.main(["--kiosk-account"]) == 1
    assert "outcome=unavailable" in state.records[-1]


def test_failed_recovery_and_unknown_metadata_are_logged_as_categories(routing):
    helper, state = routing
    state.session = "private-identity with spaces"
    state.transport = "private-transport"
    state.no_write = True
    assert helper.main(["--kiosk-account"]) == 1
    assert "session=other type=other recovery=failed" in state.records[-1]
    assert "private" not in " ".join(state.records)


@pytest.mark.parametrize("user,service,expected", [
    ("ordinary-private-account", "sshd", 0),
    ("oh-no-parent-control", "systemd-user", 0),
    ("oh-no-parent-control", "sshd", 1),
    ("oh-no-parent-control", "gdm-autologin", 1),
    ("oh-no-parent-control", "gdm-password", 0),
])
def test_service_guard_does_not_query_accounts_service(routing, monkeypatch, user, service, expected):
    helper, state = routing
    monkeypatch.setenv("PAM_USER", user)
    monkeypatch.setenv("PAM_SERVICE", service)
    assert helper.main([]) == expected
    assert state.calls == []


def test_explicit_checks_require_root(routing, monkeypatch):
    helper, state = routing
    monkeypatch.setattr(helper.os, "geteuid", lambda: 12345)
    assert helper.main(["--kiosk-account"]) == 1
    assert state.calls == []


@pytest.fixture(scope="module")
def native_module(tmp_path_factory):
    directory = tmp_path_factory.mktemp("onpc-kiosk-pam")
    helper = directory / "helper"
    module = directory / "pam-kiosk.so"
    subprocess.run([
        "cc", "-shared", "-fPIC", "-Wall", "-Wextra", "-Werror",
        f'-DLOGIN_CHECK_PATH="{helper}"',
        '-DKIOSK_ACCOUNT_NAME="private-account-canary"',
        f'-DKIOSK_LOGIN_LOCK_PATH="{directory / "lock"}"',
        f"-DKIOSK_LOGIN_LOCK_OWNER={os.getuid()}",
        "-DKIOSK_LOGIN_TIMEOUT_SECONDS=1",
        "-o", str(module), str(ROOT / "tools/pam_oh_no_parent_control.c"), "-lpam",
    ], check=True, capture_output=True, text=True, timeout=30)
    helper.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys, time
directory = pathlib.Path(__file__).parent
with (directory / "calls").open("a") as stream:
    stream.write(json.dumps([sys.argv[1:], {key: os.environ.get(key, "") for key in
        ("PAM_USER", "PAM_SERVICE", "XDG_SESSION_TYPE")}]) + "\\n")
status = int((directory / "status").read_text())
if status == 99:
    time.sleep(10)
if status == 98:
    (directory / "ready").touch()
    deadline = time.monotonic() + 3
    while not (directory / "release").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
sys.exit(status)
''')
    helper.chmod(0o700)
    return module, directory


@pytest.fixture
def native(native_module, tmp_path):
    module, directory = native_module
    (directory / "status").write_text("0")
    (directory / "calls").write_text("")
    for name in ("ready", "release"):
        (directory / name).unlink(missing_ok=True)
    lock = directory / "lock"
    # All previous PAM handles have ended before fixture cleanup/reuse.
    lock.unlink(missing_ok=True)
    pam = ctypes.CDLL("libpam.so.0")

    class Conversation(ctypes.Structure):
        _fields_ = [("conv", ctypes.c_void_p), ("data", ctypes.c_void_p)]

    pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                    ctypes.POINTER(Conversation), ctypes.c_char_p,
                                    ctypes.POINTER(ctypes.c_void_p)]
    for name in ("pam_acct_mgmt", "pam_open_session", "pam_end"):
        getattr(pam, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
    pam.pam_putenv.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

    @contextmanager
    def transaction(user="private-account-canary", service="gdm-password", transport="wayland"):
        (tmp_path / service).write_text(
            f"account required {module} kiosk\nsession required {module} kiosk\n")
        handle = ctypes.c_void_p()
        conversation = Conversation()
        assert pam.pam_start_confdir(service.encode(), user.encode(), ctypes.byref(conversation),
                                    str(tmp_path).encode(), ctypes.byref(handle)) == 0
        try:
            if transport is not None:
                assert pam.pam_putenv(handle, f"XDG_SESSION_TYPE={transport}".encode()) == 0
            yield handle
        finally:
            assert pam.pam_end(handle, 0) == 0

    return SimpleNamespace(pam=pam, transaction=transaction, directory=directory, lock=lock,
                           calls=lambda: [json.loads(line) for line in
                                          (directory / "calls").read_text().splitlines()])


def test_real_pam_binds_stages_and_passes_only_pam_transport(native, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "poisoned-process-environment")
    with native.transaction(transport=None) as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) == 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert [call[0] for call in native.calls()] == [["--kiosk-account"], ["--kiosk-session"]]
    assert native.calls()[1][1] == dict(PAM_USER="private-account-canary",
                                       PAM_SERVICE="gdm-password", XDG_SESSION_TYPE="")


def test_real_pam_rejects_open_without_successful_account_check(native):
    with native.transaction() as handle:
        assert native.pam.pam_open_session(handle, 0) != 0
        (native.directory / "status").write_text("1")
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        (native.directory / "status").write_text("0")
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert len(native.calls()) == 1


def test_real_pam_serializes_logins_and_releases_lock_on_abort(native):
    with native.transaction() as first:
        assert native.pam.pam_acct_mgmt(first, 0) == 0
        with native.transaction() as second:
            assert native.pam.pam_acct_mgmt(second, 0) != 0
            assert native.pam.pam_open_session(second, 0) != 0
    with native.transaction() as retry:
        assert native.pam.pam_acct_mgmt(retry, 0) == 0
        assert native.pam.pam_open_session(retry, 0) == 0


@pytest.mark.parametrize("fault", ["symlink", "mode", "directory"])
def test_real_pam_refuses_unsafe_lock_paths(native, fault):
    if fault == "symlink":
        native.lock.symlink_to(native.directory / "status")
    elif fault == "mode":
        native.lock.touch(mode=0o666)
    else:
        native.lock.mkdir()
    try:
        with native.transaction() as handle:
            assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.calls() == []
    finally:
        if fault == "directory":
            native.lock.rmdir()


def test_real_pam_bounds_and_reaps_helper_timeout(native):
    (native.directory / "status").write_text("99")
    started = time.monotonic()
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) != 0
        assert native.pam.pam_open_session(handle, 0) != 0
    assert 1 <= time.monotonic() - started < 5
    assert len(native.calls()) == 1


def test_real_pam_denies_session_helper_failure_and_releases_lock(native):
    with native.transaction() as handle:
        assert native.pam.pam_acct_mgmt(handle, 0) == 0
        (native.directory / "status").write_text("1")
        assert native.pam.pam_open_session(handle, 0) != 0
        (native.directory / "status").write_text("0")
        with native.transaction() as retry:
            assert native.pam.pam_acct_mgmt(retry, 0) == 0
            assert native.pam.pam_open_session(retry, 0) == 0


def test_aborted_pam_worker_cannot_unlock_a_still_running_routing_helper(native):
    (native.directory / "status").write_text("98")

    def account_worker():
        # Also exercise a worker with closed stdin: its lock may occupy fd 0
        # and must survive the helper's /dev/null stdio redirection.
        os.close(0)
        with native.transaction() as handle:
            native.pam.pam_acct_mgmt(handle, 0)

    # This is the only signalled process: our explicitly spawned, retained
    # Process identity. The helper exits itself after release or its own bound.
    worker = multiprocessing.get_context("fork").Process(target=account_worker)
    worker.start()
    try:
        deadline = time.monotonic() + 3
        while not (native.directory / "ready").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (native.directory / "ready").exists()
        worker.kill()
        worker.join(timeout=3)
        assert not worker.is_alive()
        (native.directory / "status").write_text("0")
        with native.transaction() as retry:
            assert native.pam.pam_acct_mgmt(retry, 0) != 0
    finally:
        (native.directory / "release").touch()
        if worker.is_alive():
            worker.kill()
        worker.join(timeout=3)

    # Wait for the bounded descendant to exit and release its inherited lock,
    # without signalling it or leaving a child mutating shared fixture state.
    with native.lock.open("rb") as probe:
        deadline = time.monotonic() + 4
        while True:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                assert time.monotonic() < deadline
                time.sleep(0.01)
    with native.transaction() as retry:
        assert native.pam.pam_acct_mgmt(retry, 0) == 0
        assert native.pam.pam_open_session(retry, 0) == 0


@pytest.mark.parametrize("user,service,expected", [
    ("private-account-canary", "sshd", False),
    ("private-account-canary", "gdm-autologin", False),
    ("private-account-canary", "systemd-user", True),
    ("ordinary-private-account", "gdm-password", True),
])
def test_real_pam_service_and_identity_scope(native, user, service, expected):
    with native.transaction(user=user, service=service) as handle:
        assert (native.pam.pam_acct_mgmt(handle, 0) == 0) == expected
        assert (native.pam.pam_open_session(handle, 0) == 0) == expected
    assert native.calls() == []
