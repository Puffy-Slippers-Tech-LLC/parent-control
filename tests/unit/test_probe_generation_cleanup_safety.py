"""Fresh witness ownership, mutation refusal and bounded filesystem cleanup."""

import hashlib
import os
from pathlib import Path
import stat

import pytest

from oh_no_parent_control import probe_generation as generation


@pytest.fixture
def prepared_paths(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    source = tmp_path / "packaged-witness"
    source.write_bytes(b"test witness payload")
    source.chmod(0o755)
    monkeypatch.setattr(generation, "RUNTIME_ROOT", str(root))
    monkeypatch.setattr(generation, "WITNESS_SOURCE", str(source))
    return root, source


@pytest.fixture
def owner(prepared_paths):
    adapter = generation.ProbeGeneration()
    yield adapter
    assert adapter.close(settled=True), "owned generation cleanup incomplete"
    assert adapter.cleanup_complete


def test_fresh_copy_is_pinned_read_only_and_retained_until_settlement(owner, prepared_paths):
    root, source = prepared_paths
    first = owner.prepare()
    assert first == owner.verify() == owner.identity
    assert first.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first.size == len(source.read_bytes())
    target = Path(first.witness)
    assert (first.device, first.inode) == (target.stat().st_dev, target.stat().st_ino)
    assert target.stat().st_ino != source.stat().st_ino
    assert stat.S_IMODE(target.stat().st_mode) == 0o500
    assert stat.S_IMODE(Path(first.directory).stat().st_mode) == 0o700
    assert owner._writer is None
    with pytest.raises(OSError):
        os.write(owner._witness, b"mutation")
    descriptors = [owner._root, owner._directory, owner._witness]
    assert not owner.close(settled=False) and not owner.cleanup_complete
    assert target.exists() and owner.verify() == first
    other = generation.ProbeGeneration()
    try:
        second = other.prepare()
        assert second.token != first.token and second.inode != first.inode
        assert second.sha256 == first.sha256
    finally:
        assert other.close(settled=True)
    assert owner.close(settled=True) and owner.close(settled=True)
    assert owner.identity == first and not list(root.iterdir())
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    with pytest.raises(RuntimeError):
        owner.prepare()


@pytest.mark.parametrize("kind", ["symlink", "fifo", "empty", "oversize", "writable",
                                  "no-exec", "setuid"])
def test_unsafe_source_refuses_without_creating_generation(owner, prepared_paths, kind):
    root, source = prepared_paths
    if kind == "symlink":
        source.rename(source.with_suffix(".real"))
        source.symlink_to(source.with_suffix(".real"))
    elif kind == "fifo":
        source.unlink()
        os.mkfifo(source, 0o700)
    elif kind in {"empty", "oversize"}:
        source.write_bytes(b"" if kind == "empty" else b"x" * (generation.MAX_WITNESS_BYTES + 1))
    else:
        source.chmod({"writable": 0o777, "no-exec": 0o644, "setuid": 0o4755}[kind])
    with pytest.raises((OSError, generation.GenerationRefused)):
        owner.prepare()
    assert not list(root.iterdir()) and owner.identity is None


@pytest.mark.parametrize("kind", ["mode", "symlink", "collision"])
def test_unsafe_root_or_existing_generation_is_never_adopted(owner, prepared_paths, monkeypatch, kind):
    root, source = prepared_paths
    if kind == "mode":
        root.chmod(0o755)
    elif kind == "symlink":
        root.rename(root.with_suffix(".real"))
        root.symlink_to(root.with_suffix(".real"))
    else:
        monkeypatch.setattr(generation.secrets, "token_hex", lambda _: "1" * 32)
        collision = root / ("1" * 32)
        collision.mkdir(mode=0o700)
        (collision / "foreign").write_bytes(b"preserve")
    with pytest.raises((OSError, generation.GenerationRefused)):
        owner.prepare()
    assert owner.close(settled=True)
    assert root.exists() and source.exists()
    if kind == "collision":
        assert (collision / "foreign").read_bytes() == b"preserve"


@pytest.mark.parametrize("stage", ["write", "chmod", "read-open"])
@pytest.mark.parametrize("error", [OSError, KeyboardInterrupt])
def test_partial_creation_retains_owned_cleanup_for_retry(owner, prepared_paths, monkeypatch, stage, error):
    real_open = generation.os.open
    def interrupted(*args, **kwargs):
        raise error("private source path")
    with monkeypatch.context() as patch:
        if stage == "read-open":
            def open_read(*args, **kwargs):
                if args[0] == "witness" and args[1] == generation.READ_FLAGS:
                    interrupted()
                return real_open(*args, **kwargs)
            patch.setattr(generation.os, "open", open_read)
        else:
            patch.setattr(generation.os, "write" if stage == "write" else "fchmod", interrupted)
        with pytest.raises(error):
            owner.prepare()
    assert owner.failure == "prepare-refused" and not owner.cleanup_complete
    assert owner.close(settled=True)
    assert not list(prepared_paths[0].iterdir())


@pytest.mark.parametrize("kind", ["root", "directory", "witness", "missing-directory", "missing-witness"])
def test_replacement_or_rename_never_adopts_foreign_paths(owner, prepared_paths, kind):
    identity = owner.prepare()
    path = {"root": prepared_paths[0], "directory": Path(identity.directory),
            "witness": Path(identity.witness), "missing-directory": Path(identity.directory),
            "missing-witness": Path(identity.witness)}[kind]
    moved = path.with_name(path.name + "-original")
    path.rename(moved)
    if kind in {"root", "directory"}:
        path.mkdir(mode=0o700)
        (path / "foreign").write_bytes(b"preserve")
    elif kind == "witness":
        path.write_bytes(b"foreign")
        path.chmod(0o500)
    with pytest.raises((OSError, generation.GenerationRefused)):
        owner.verify()
    if kind == "root":
        # Cleanup stays relative to the pinned old root; no global path adoption.
        assert owner.close(settled=True)
        assert (path / "foreign").read_bytes() == b"preserve"
        assert not list(moved.iterdir())
    else:
        assert not owner.close(settled=True)
        if kind == "directory":
            assert (path / "foreign").read_bytes() == b"preserve"
            (path / "foreign").unlink()
            path.rmdir()
        elif kind == "witness":
            assert path.read_bytes() == b"foreign"
            path.unlink()
        moved.rename(path)
        with pytest.raises(generation.GenerationRefused):
            owner.verify()  # Restoration permits cleanup, never positive promotion.
        assert owner.close(settled=True)


@pytest.mark.parametrize("kind", ["content", "mode", "hardlink", "directory-mode"])
def test_observed_mutation_permanently_invalidates_generation(owner, kind):
    identity = owner.prepare()
    target = Path(identity.witness)
    if kind == "content":
        target.chmod(0o700)
        target.write_bytes(b"x" * identity.size)
        target.chmod(0o500)
    elif kind == "mode":
        target.chmod(0o700)
    elif kind == "directory-mode":
        Path(identity.directory).chmod(0o755)
    else:
        os.link(target, target.with_name("duplicate"))
    with pytest.raises(generation.GenerationRefused):
        owner.verify()
    if kind == "hardlink":
        assert not owner.close(settled=True)
        target.with_name("duplicate").unlink()
    assert owner.close(settled=True)


@pytest.mark.parametrize("operation", ["unlink", "rmdir"])
def test_cleanup_error_preserves_descriptors_and_retries_exact_identity(owner, monkeypatch, operation):
    identity = owner.prepare()
    with monkeypatch.context() as patch:
        def denied(*args, **kwargs):
            raise PermissionError("private filesystem detail")
        patch.setattr(generation.os, operation, denied)
        assert not owner.close(settled=True)
    assert not owner.cleanup_complete
    for descriptor in (owner._root, owner._directory, owner._witness):
        os.fstat(descriptor)
    assert owner.close(settled=True)
    assert not Path(identity.directory).exists()


def test_unknown_directory_identity_never_adopts_current_path(prepared_paths, monkeypatch):
    adapter = generation.ProbeGeneration()
    real_fstat = generation.os.fstat
    try:
        def uncertain(descriptor):
            if descriptor == adapter._directory:
                raise OSError("identity unavailable")
            return real_fstat(descriptor)
        with monkeypatch.context() as patch:
            patch.setattr(generation.os, "fstat", uncertain)
            with pytest.raises(OSError):
                adapter.prepare()
        assert not adapter.close(settled=True)
        assert adapter._directory_identity is None
        assert (prepared_paths[0] / adapter._token).is_dir()
    finally:
        # Fixture owns this empty directory. The adapter must not adopt it.
        (prepared_paths[0] / adapter._token).rmdir()
        os.close(adapter._directory)
        os.close(adapter._root)


def test_concurrent_operations_do_not_change_owner(owner):
    identity = owner.prepare()
    with owner._lock:
        for operation in (owner.prepare, owner.verify, lambda: owner.close(settled=True)):
            with pytest.raises(RuntimeError, match="already running"):
                operation()
    assert owner.failure is None and owner.verify() == identity


def test_partial_write_pins_original_inode_until_cleanup(owner, monkeypatch):
    original_write = generation.os.write
    written = []
    def partial(descriptor, payload):
        if written:
            raise OSError("write interrupted")
        written.append(original_write(descriptor, payload[:3]))
        return written[-1]
    with monkeypatch.context() as patch:
        patch.setattr(generation.os, "write", partial)
        with pytest.raises(OSError):
            owner.prepare()
    pinned = owner._writer
    original_unlink = generation.os.unlink
    def unlink(name, **kwargs):
        assert generation._identity(os.fstat(pinned)) == owner._witness_identity
        original_unlink(name, **kwargs)
    monkeypatch.setattr(generation.os, "unlink", unlink)
    assert owner.close(settled=True)
    with pytest.raises(OSError):
        os.fstat(pinned)


def test_changed_source_during_read_refuses_without_publication(owner, prepared_paths, monkeypatch):
    original_read = generation.os.read
    changed = False
    def read(descriptor, count):
        nonlocal changed
        data = original_read(descriptor, count)
        if not changed:
            changed = True
            prepared_paths[1].write_bytes(b"replacement payload")
        return data
    monkeypatch.setattr(generation.os, "read", read)
    with pytest.raises(generation.GenerationRefused, match="source-changed"):
        owner.prepare()
    assert owner.identity is None and not list(prepared_paths[0].iterdir())


def test_unrelated_child_prevents_directory_removal_and_is_preserved(owner):
    identity = owner.prepare()
    foreign = Path(identity.directory) / "foreign"
    foreign.write_bytes(b"preserve")
    assert not owner.close(settled=True)
    assert foreign.read_bytes() == b"preserve"
    assert not owner.cleanup_complete
    foreign.unlink()
    assert owner.close(settled=True)


def test_diagnostics_exclude_paths_contents_and_exception_details(owner, prepared_paths, monkeypatch, caplog):
    def denied(*args, **kwargs):
        raise OSError("private filesystem detail")
    monkeypatch.setattr(owner, "_source_bytes", denied)
    with pytest.raises(OSError):
        owner.prepare()
    assert owner.failure == "prepare-refused"
    assert "private filesystem detail" not in caplog.text
    assert str(prepared_paths[0]) not in caplog.text
    assert "test witness payload" not in caplog.text
