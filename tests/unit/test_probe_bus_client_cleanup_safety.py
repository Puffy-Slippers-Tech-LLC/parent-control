"""Deterministic late Gio completion and cancellation ownership tests."""

from concurrent.futures import ThreadPoolExecutor

from gi.repository import Gio, GLib
import pytest

from oh_no_parent_control import execution_probe as probe

ADDRESS = "unix:path=/test-address"


class Lifecycle:
    def __init__(self):
        self.now = 0.0
        self.sources = []
        self.open_callback = None
        self.close_callback = None
        self.context = None
        self.open_cancel = None
        self.close_cancel = None
        self.open_error = False
        self.close_error = False
        self.closed = False
        self.auto_open = True
        self.auto_close = True
        self.opens = 0
        self.closes = 0
        self.exit_on_close = True
        self.hook = lambda: None
        self.create_callback = None
        self.creates = 0
        self.create_error = None

    def call(self, owner, path, interface, method, parameters, reply_type,
             flags, timeout, cancellable, callback, data):
        assert owner == ":1.50" and path == probe.SYSTEMD_PATH
        assert interface == probe.SYSTEMD_MANAGER_INTERFACE and method == "StartTransientUnit"
        assert parameters.unpack()[1] == "fail"
        assert timeout == GLib.MAXINT and cancellable is None
        assert flags == Gio.DBusCallFlags.NONE
        assert reply_type.dup_string() == "(o)"
        self.creates += 1
        self.create_callback = lambda: callback(self, self, data)

    def call_finish(self, result):
        assert result is self
        if self.create_error:
            raise Gio.DBusError.new_for_dbus_error(self.create_error, "secret payload")
        return GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/42",))

    def schedule(self, callback):
        source = GLib.idle_source_new()
        source.set_callback(lambda: (callback(), False)[1])
        source.attach(self.context)
        self.sources.append(source)

    def sleep(self, seconds):
        self.now += seconds
        self.hook()

    def new(self, address, flags, observer, cancellable, callback, data):
        assert address == ADDRESS and observer is None
        assert flags == (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                         Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
        self.opens += 1
        self.context = GLib.MainContext.get_thread_default()
        self.open_cancel = cancellable
        self.open_callback = lambda: callback(None, self, data)
        if self.auto_open:
            self.schedule(self.open_callback)

    def finish(self, result):
        assert result is self
        if self.open_error:
            raise Gio.DBusError.new_for_dbus_error("org.test.Error", "secret payload")
        return self

    def set_exit_on_close(self, value):
        self.exit_on_close = value

    def is_closed(self):
        return self.closed

    def close(self, cancellable, callback, data):
        self.closes += 1
        self.close_cancel = cancellable
        self.close_callback = lambda: callback(self, self, data)
        if self.auto_close:
            self.schedule(self.close_callback)

    def close_finish(self, result):
        assert result is self
        if self.close_error:
            raise Gio.DBusError.new_for_dbus_error("org.test.Error", "secret payload")
        self.closed = True
        return True


@pytest.fixture
def lifecycle(monkeypatch):
    backend = Lifecycle()
    monkeypatch.setattr(probe.time, "monotonic", lambda: backend.now)
    monkeypatch.setattr(probe.time, "sleep", backend.sleep)
    monkeypatch.setattr(Gio.DBusConnection, "new_for_address", backend.new)
    monkeypatch.setattr(Gio.DBusConnection, "new_for_address_finish", backend.finish)
    yield backend
    for source in backend.sources:
        source.destroy()


def test_single_owned_client_closes_without_reopening(lifecycle):
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS) and client.connection is lifecycle
    assert not lifecycle.exit_on_close and not client.cleanup_complete
    assert client.close() and client.cleanup_complete and client.connection is None
    assert client.close() and lifecycle.closes == lifecycle.opens == 1
    with pytest.raises(RuntimeError, match="single-use"):
        client.open(ADDRESS)


@pytest.mark.parametrize("reply", [None, probe.UNIT_EXISTS, "org.test.Error"])
def test_late_create_reply_survives_deadline_without_disconnect_or_replay(lifecycle, caplog, reply):
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS)
    client.start_create(":1.50", "onpc-test.service", "ONPC test")
    assert client.poll_create() is None
    assert not client.close() and client.connection is lifecycle
    assert not client.cleanup_complete and lifecycle.closes == 0
    assert client.poll_create() is None
    with pytest.raises(RuntimeError, match="already submitted"):
        client.start_create(":1.50", "onpc-test.service", "ONPC test")
    lifecycle.create_error = reply
    lifecycle.schedule(lifecycle.create_callback)
    with caplog.at_level("INFO"):
        result = client.poll_create()
    assert result.outcome == ("replied" if reply is None else
                              "collision" if reply == probe.UNIT_EXISTS else "uncertain")
    assert bool(result.job) == (reply is None)
    assert client.poll_create() is result and lifecycle.creates == 1
    assert "secret payload" not in caplog.text
    assert lifecycle.now <= 2 * probe.CLEANUP_SECONDS + probe.POLL_SECONDS
    assert client.close() and client.cleanup_complete


@pytest.mark.parametrize("phase", ["dispatch", "poll"])
def test_interrupted_create_keeps_reply_and_sender_owned(lifecycle, monkeypatch, phase):
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS)
    previous = GLib.MainContext.get_thread_default()

    def interrupt():
        raise KeyboardInterrupt

    if phase == "dispatch":
        original = lifecycle.call

        def interrupted(*args):
            original(*args)
            interrupt()

        monkeypatch.setattr(lifecycle, "call", interrupted)
        operation = lambda: client.start_create(":1.50", "onpc-test.service", "ONPC test")
    else:
        client.start_create(":1.50", "onpc-test.service", "ONPC test")
        lifecycle.hook = interrupt
        operation = client.poll_create
    with pytest.raises(KeyboardInterrupt):
        operation()
    assert GLib.MainContext.get_thread_default() == previous
    assert not client.close() and client.connection is lifecycle
    lifecycle.hook = lambda: None
    lifecycle.schedule(lifecycle.create_callback)
    assert client.poll_create().job == "/org/freedesktop/systemd1/job/42"
    assert client.close() and lifecycle.creates == 1


def test_create_poll_refuses_overlap_and_does_not_dispatch_default_context(lifecycle):
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS)
    client.start_create(":1.50", "onpc-test.service", "ONPC test")
    callbacks = []
    source = GLib.idle_source_new()
    source.set_callback(lambda: (callbacks.append(True), False)[1])
    source.attach(GLib.MainContext.default())
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            def hook():
                lifecycle.hook = lambda: None
                for operation in (client.poll_create, client.close):
                    with pytest.raises(RuntimeError, match="already running"):
                        executor.submit(operation).result(timeout=2)
                lifecycle.schedule(lifecycle.create_callback)
            lifecycle.hook = hook
            assert client.poll_create().outcome == "replied"
        assert not callbacks and client.close()
    finally:
        source.destroy()


@pytest.mark.parametrize("arrival", ["before-close", "during-close", "after-close-timeout"])
def test_late_success_after_cancel_is_retained_and_closed(lifecycle, arrival):
    lifecycle.auto_open = False
    client = probe.ProbeBusClient()
    assert not client.open(ADDRESS)
    assert lifecycle.open_cancel.is_cancelled()
    assert not client.cleanup_complete and client.connection is None
    if arrival == "after-close-timeout":
        assert not client.close()
    if arrival == "during-close":
        def hook():
            lifecycle.hook = lambda: None
            lifecycle.schedule(lifecycle.open_callback)
        lifecycle.hook = hook
    else:
        lifecycle.schedule(lifecycle.open_callback)
    assert client.close() and lifecycle.closed and client.connection is None
    assert lifecycle.opens == lifecycle.closes == 1
    assert lifecycle.now <= 3 * probe.CLEANUP_SECONDS + probe.POLL_SECONDS


def test_never_completed_open_stays_owned_without_blocking_or_replay(lifecycle):
    lifecycle.auto_open = False
    client = probe.ProbeBusClient()
    assert not client.open(ADDRESS)
    assert not client.close() and not client.cleanup_complete
    with pytest.raises(RuntimeError, match="single-use"):
        client.open(ADDRESS)
    assert lifecycle.opens == 1 and lifecycle.closes == 0
    assert lifecycle.now <= 2 * probe.CLEANUP_SECONDS + probe.POLL_SECONDS


def test_late_constructor_error_is_collected_without_a_connection(lifecycle, caplog):
    lifecycle.auto_open = False
    lifecycle.open_error = True
    client = probe.ProbeBusClient()
    with caplog.at_level("INFO"):
        assert not client.open(ADDRESS)
        lifecycle.schedule(lifecycle.open_callback)
        assert client.close() and client.cleanup_complete
    assert lifecycle.closes == 0 and "secret payload" not in caplog.text


def test_close_timeout_does_not_drop_pending_callback_or_replay_close(lifecycle):
    lifecycle.auto_close = False
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS)
    assert not client.close() and lifecycle.close_cancel.is_cancelled()
    assert not client.close() and lifecycle.closes == 1
    # is_closed alone cannot retire an unfinished finish callback.
    lifecycle.closed = True
    assert not client.cleanup_complete
    lifecycle.schedule(lifecycle.close_callback)
    assert client.close() and lifecycle.closes == 1


def test_failed_close_retries_only_the_same_owned_connection(lifecycle, caplog):
    client = probe.ProbeBusClient()
    assert client.open(ADDRESS)
    lifecycle.close_error = True
    with caplog.at_level("INFO"):
        assert not client.close() and not client.cleanup_complete
    assert "secret payload" not in caplog.text
    lifecycle.close_error = False
    assert client.close() and lifecycle.closes == 2 and lifecycle.opens == 1


@pytest.mark.parametrize("phase", ["open", "close"])
def test_interrupt_retains_operation_and_restores_thread_context(lifecycle, phase):
    client = probe.ProbeBusClient()
    previous = GLib.MainContext.get_thread_default()
    if phase == "close":
        assert client.open(ADDRESS)
        lifecycle.auto_close = False
    else:
        lifecycle.auto_open = False

    def interrupt():
        raise KeyboardInterrupt

    lifecycle.hook = interrupt
    with pytest.raises(KeyboardInterrupt):
        client.open(ADDRESS) if phase == "open" else client.close()
    assert GLib.MainContext.get_thread_default() == previous
    assert not client.cleanup_complete
    pending = lifecycle.open_cancel if phase == "open" else lifecycle.close_cancel
    assert pending.is_cancelled()
    lifecycle.hook = lambda: None
    lifecycle.schedule(lifecycle.open_callback if phase == "open" else lifecycle.close_callback)
    assert client.close()


def test_overlapping_lifecycle_operations_refuse_without_context_dispatch(lifecycle):
    client = probe.ProbeBusClient()
    lifecycle.auto_open = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        def hook():
            lifecycle.hook = lambda: None
            for operation in (lambda: client.open(ADDRESS), client.close):
                with pytest.raises(RuntimeError, match="already running"):
                    executor.submit(operation).result(timeout=2)
            lifecycle.schedule(lifecycle.open_callback)
        lifecycle.hook = hook
        assert client.open(ADDRESS)
    assert client.close() and lifecycle.opens == 1


def test_close_before_open_permanently_disarms_client(lifecycle):
    client = probe.ProbeBusClient()
    assert client.close() and client.cleanup_complete
    with pytest.raises(RuntimeError, match="single-use"):
        client.open(ADDRESS)
    assert lifecycle.opens == lifecycle.closes == 0


@pytest.mark.parametrize("phase", ["open", "close"])
def test_interrupt_during_dispatch_retains_possible_callback(lifecycle, monkeypatch, phase):
    client = probe.ProbeBusClient()
    if phase == "open":
        dispatch = lifecycle.new

        def interrupted(*args):
            dispatch(*args)
            raise KeyboardInterrupt

        monkeypatch.setattr(Gio.DBusConnection, "new_for_address", interrupted)
    else:
        assert client.open(ADDRESS)
        dispatch = lifecycle.close

        def interrupted(*args):
            dispatch(*args)
            raise KeyboardInterrupt

        monkeypatch.setattr(lifecycle, "close", interrupted)
    with pytest.raises(KeyboardInterrupt):
        client.open(ADDRESS) if phase == "open" else client.close()
    assert client.connection is None and not client.cleanup_complete
    assert client.close() and lifecycle.closed
    assert lifecycle.opens == lifecycle.closes == 1


@pytest.mark.parametrize("address", ["autolaunch:", "tcp:host=localhost",
                                     "unix:path=/a;autolaunch:", None])
def test_unowned_transport_is_rejected_before_dispatch(lifecycle, address):
    client = probe.ProbeBusClient()
    with pytest.raises(ValueError, match="one Unix bus address"):
        client.open(address)
    assert client.close() and lifecycle.opens == lifecycle.closes == 0


def test_lifecycle_does_not_dispatch_broker_default_context(lifecycle):
    callbacks = []
    source = GLib.idle_source_new()
    source.set_callback(lambda: (callbacks.append(True), False)[1])
    source.attach(GLib.MainContext.default())
    client = probe.ProbeBusClient()
    try:
        assert client.open(ADDRESS) and client.close()
        assert callbacks == []
    finally:
        source.destroy()
