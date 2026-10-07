"""Release eligibility and private persistence; no live services or UI."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest import mock

import pytest

from oh_no_parent_control.config import validate
from oh_no_parent_control.core import AccessDenied, BackendFailure, Broker, InvalidRequest
from oh_no_parent_control.data_migration import MigrationError, migrate_all_state
from oh_no_parent_control.preferences import PreferenceStore, PreferencesError, default_preferences
from oh_no_parent_control.whats_new import (
    METADATA_PATH, WhatsNewCatalog, WhatsNewError, read_document, read_metadata,
    read_history, validate_metadata, version_key,
)
from tests.support.broker import Accounts, Authorizer
from tests.support.configuration import valid_config


def note(version="1.4", **extra):
    return {"ProductVersion": version,
            "Content": "# New features\n\n- **Bold** and [a link](https://example.com)\n\n```\ncode\n```\n",
            **extra}


def catalog(current="1.5", first="1.3", records=None):
    # Test catalogues declare their source directly, without author-facing ShowIn.
    records = records if records is not None else [note("1.4"), note("1.5")]
    return WhatsNewCatalog(current, first, tuple(
        dict(record, record_id=record.get("record_id", record["ProductVersion"] + ":" + component))
        for record in records for component in ("Parent", "Child")
        if "record_id" not in record or record["record_id"].endswith(":" + component)))


def make_backend(tmp_path, notes=None):
    accounts = Accounts()
    store = PreferenceStore(tmp_path / "preferences")
    broker = Broker(lambda: validate(valid_config()), Authorizer(), accounts, store,
                    whats_new_loader=lambda: notes or catalog())
    return broker, store, accounts


def test_metadata_preserves_markdown_and_derives_child_identity():
    original = note(SeeMore="https://example.com/release?v=1.4#notes")
    parsed, = validate_metadata({"version": 1, "records": [original]})
    assert parsed["record_id"] == "1.4:Child"
    assert "ShowIn" not in parsed
    assert parsed["Content"] == original["Content"]
    assert parsed["SeeMore"] == original["SeeMore"]
    assert "SeeMore" not in validate_metadata({"version": 1, "records": [note()]})[0]


def test_separate_sources_preserve_literal_markdown_for_both_audiences(tmp_path):
    metadata = tmp_path / METADATA_PATH.name
    metadata.write_text("""# Author comments are allowed.
version = 1

[[records]]
ProductVersion = "1.4"
SeeMore = "https://example.com/releases/1.4"
Content = '''
## What's new — nouveautés

- **Quoted:** "Hello" and 'welcome'.
  Indented Markdown with a literal \\n and \\path.

```text
code
```
'''
""", encoding="utf-8")
    product = tmp_path / "app.json"
    installation = tmp_path / "installation.json"
    write_json(product, {"version": "1.4"})
    write_json(installation, {"version": 1, "first_version": "1.3", "current_version": "1.4"})
    history = tmp_path / "VersionHistory.md"
    history.write_text("## v1.4 -\n### Parent changes\n- Parent only.\n\n## v1.3 — 2026-10-03\nOld notes\n")
    loaded = WhatsNewCatalog.load(metadata, product, installation, history)
    expected = ("## What's new — nouveautés\n\n"
                "- **Quoted:** \"Hello\" and 'welcome'.\n"
                "  Indented Markdown with a literal \\n and \\path.\n\n"
                "```text\ncode\n```\n")
    record, = loaded.available("Child", [])["records"]
    assert record["Content"] == expected
    assert record["SeeMore"] == "https://example.com/releases/1.4"
    assert record["record_id"] == "1.4:Child"
    assert record["auto_show"] is True
    parent, = loaded.available("Parent", [])["records"]
    assert parent["Content"] == "### Parent changes\n- Parent only.\n\n"
    assert parent["record_id"] == "1.4:Parent"
    assert "ShowIn" not in parent and "SeeMore" not in parent
    assert parent["auto_show"] is True


@pytest.mark.parametrize("contents", [
    b"version = 1\nversion = 1\nrecords = []\n",
    b"version = 1\n[[records]]\nContent = 'one'\nContent = 'two'\n",
    b"version = 1\n[[records]]\nContent = '''unterminated",
    b"\xff",
    b" " * (512 * 1024 + 1),
], ids=["duplicate-document-key", "duplicate-record-key", "unterminated", "invalid-utf8", "oversized"])
def test_toml_reader_rejects_duplicates_invalid_encoding_and_oversized_input(tmp_path, contents):
    path = tmp_path / "metadata.toml"
    path.write_bytes(contents)
    with pytest.raises(WhatsNewError):
        read_metadata(path)


def test_packaged_toml_catalogue_passes_release_validation():
    from tests.support.paths import ROOT

    validate_metadata(read_metadata(ROOT / "data" / METADATA_PATH.name))
    read_history(ROOT / "docs/VersionHistory.md")


def test_history_preserves_body_and_ignores_release_headings_in_fenced_code(tmp_path):
    history = tmp_path / "VersionHistory.md"
    body = "### Features\n\n```markdown\n## v99.0 -\n```\n- Literal notes.\n\n"
    history.write_text("## v1.10.0 -\n" + body + "## v1.9 — 2026-10-01\nOlder notes\n")
    records = read_history(history)
    assert records[-1] == dict(ProductVersion="1.10", Content=body, record_id="1.10:Parent")


@pytest.mark.parametrize("text", [
    "No releases", "## v1.4 -\n  \n", "## vbad -\nNotes\n",
    "## v1.4 -\nNotes\n## v1.4.0 -\nDuplicate\n",
])
def test_invalid_history_is_rejected(tmp_path, text):
    path = tmp_path / "VersionHistory.md"
    path.write_text(text)
    with pytest.raises(WhatsNewError):
        read_history(path)


def test_current_child_entry_is_optional_and_never_falls_back_to_parent_or_old_child(tmp_path):
    metadata, history = tmp_path / "child.toml", tmp_path / "VersionHistory.md"
    product, installation = tmp_path / "app.json", tmp_path / "installation.json"
    history.write_text("## v1.5 -\nParent notes\n")
    write_json(product, {"version": "1.5"})
    write_json(installation, {"version": 1, "first_version": "1.3", "current_version": "1.5"})
    for text in ("version = 1\nrecords = []\n",
                 "version = 1\n[[records]]\nProductVersion = '1.4'\nContent = 'Old child notes'\n"):
        metadata.write_text(text)
        loaded = WhatsNewCatalog.load(metadata, product, installation, history)
        assert loaded.available("Parent", [])["records"][0]["Content"] == "Parent notes\n"
        assert loaded.available("Child", [])["records"] == []
        with pytest.raises(WhatsNewError):
            loaded.acknowledgement("Child", "1.5")


@pytest.mark.parametrize("change", [
    {"ProductVersion": ""}, {"ProductVersion": "v1.4"}, {"ProductVersion": "1.4-1"},
    {"ProductVersion": "01.4"}, {"ProductVersion": True}, {"ShowIn": "Parent"},
    {"Content": " "}, {"Content": None},
    {"Content": "bad\x00text"}, {"Content": "\ud800"}, {"Content": "x" * 65537},
    {"SeeMore": "javascript:alert(1)"}, {"SeeMore": "file:///etc/passwd"},
    {"SeeMore": "https://user:secret@example.com"}, {"SeeMore": "https://"},
    {"SeeMore": "https://example.com:99999"}, {"SeeMore": "https://example.com\n"},
    {"SeeMore": "https://[::1]unexpected/path"}, {"SeeMore": "https://prefix[::1]/"},
    {"SeeMore": "https://example.com\\path"}, {"SeeMore": "https://%00.example.com/"},
    {"SeeMore": "https://example.com%2f.other/"},
    {"Unexpected": True},
])
def test_invalid_metadata_is_rejected(change):
    with pytest.raises(WhatsNewError):
        validate_metadata({"version": 1, "records": [note(**change)]})


@pytest.mark.parametrize("field", ["ProductVersion", "Content"])
def test_required_fields(field):
    value = note()
    del value[field]
    with pytest.raises(WhatsNewError):
        validate_metadata({"version": 1, "records": [value]})


@pytest.mark.parametrize("link", [
    "http://example.com/releases", "https://example.com:8443/a%20b?q=a%2Fb#notes",
    "https://[::1]:8443/releases", "https://127.0.0.1/releases",
])
def test_valid_see_more_links_are_preserved(link):
    record, = validate_metadata({"version": 1, "records": [note(SeeMore=link)]})
    assert record["SeeMore"] == link


def test_numeric_versions_duplicate_equivalence_and_read_guards(tmp_path):
    assert version_key("1.10") > version_key("1.9")
    assert version_key("1.4.0") == version_key("1.4")
    with pytest.raises(WhatsNewError):
        validate_metadata({"version": 1, "records": [note("1.4"), note("1.4.0")]})
    with pytest.raises(WhatsNewError):
        validate_metadata({"version": 2, "records": []})
    path = tmp_path / "metadata.json"
    for contents in ('{"version":1,"version":1,"records":[]}', "{", " " * (512 * 1024 + 1)):
        path.write_text(contents)
        with pytest.raises(WhatsNewError):
            read_document(path)


def test_record_identity_is_stable_when_content_changes():
    a = catalog(current="1.4", records=[note("1.4")])
    b = catalog(current="1.4", records=[note("1.4", Content="Updated **Markdown**")])
    assert a.retained_records == b.retained_records == {"1.4:Parent", "1.4:Child", "1.4:Child,Parent"}
    assert b.available("Child", list(a.retained_records))["records"][0]["auto_show"] is False


def test_upgrade_only_returns_current_release_even_when_user_skips_versions():
    notes = catalog(current="1.10", first="1.3", records=[
        note("1.2"), note("1.3"), note("1.4"), note("1.9"), note("1.10"), note("2.0")])
    available = notes.available("Parent", ["1.4:Child,Parent"])["records"]
    assert [(record["ProductVersion"], record["auto_show"]) for record in available] == [
        ("1.10", True)]
    assert notes.available("Parent", ["1.10:Child,Parent"])["records"][0]["auto_show"] is False
    fresh = catalog(current="1.5", first="1.5")
    assert all(not record["auto_show"] for record in fresh.available("Child", [])["records"])


def test_independent_users_and_versions_survive_broker_restart(tmp_path):
    broker, store, accounts = make_backend(tmp_path)
    broker._whats_new_loader = lambda: catalog(current="1.4")
    assert all(record["auto_show"] for record in broker.get_own_whats_new(1003)["records"])
    broker.acknowledge_own_whats_new(1003, "1.4")
    assert [record["auto_show"] for record in broker.get_own_whats_new(1003)["records"]] == [False]
    # Read/query is not acknowledgement, and seen records remain available to menus.
    assert all(record["auto_show"] for record in broker.get_own_whats_new(1001)["records"])
    restarted, _, _ = make_backend(tmp_path)
    assert restarted.get_own_whats_new(1003)["records"][0]["auto_show"] is True
    restarted.acknowledge_own_whats_new(1003, "1.5")
    assert all(not record["auto_show"] for record in restarted.get_own_whats_new(1003)["records"])
    saved = json.loads((store.directory / "1003.json").read_text())
    assert set(saved) == {"version", "personal"}
    assert saved["personal"]["whats_new_seen"] == ["1.4:Parent", "1.5:Parent"]
    assert (store.directory.stat().st_mode & 0o777) == 0o700
    assert ((store.directory / "1003.json").stat().st_mode & 0o777) == 0o600
    assert accounts.events == []


def test_kiosk_shares_selected_child_state_and_component_filtering(tmp_path):
    notes = catalog(records=[note("1.5")])
    broker, _, accounts = make_backend(tmp_path, notes)
    assert [r["ProductVersion"] for r in broker.get_own_whats_new(1003)["records"]] == ["1.5"]
    assert [r["ProductVersion"] for r in broker.get_child_whats_new(991, 1001)["records"]] == ["1.5"]
    broker.acknowledge_child_whats_new(991, 1001, "1.5")
    assert broker.get_own_whats_new(1001)["records"][0]["auto_show"] is False
    assert broker.get_own_whats_new(1002)["records"][0]["auto_show"] is True
    assert broker.get_own_whats_new(1003)["records"][0]["auto_show"] is True
    # A role change of the same UID still leaves the independent Parent record unseen.
    from dataclasses import replace
    accounts.users[1001] = replace(accounts.users[1001], is_admin=True)
    assert broker.get_own_whats_new(1001)["records"][0]["auto_show"] is True
    broker.acknowledge_own_whats_new(1001, "1.5")
    accounts.users[1001] = replace(accounts.users[1001], is_admin=False)
    assert broker.get_own_whats_new(1001)["records"][0]["auto_show"] is False
    for caller in (991, 1004, 1005, 900, True):
        with pytest.raises((AccessDenied, InvalidRequest)):
            broker.get_own_whats_new(caller)
    for caller, target in ((1003, 1001), (1001, 1002), (991, 1003), (991, 991)):
        with pytest.raises(AccessDenied):
            broker.get_child_whats_new(caller, target)
        with pytest.raises(AccessDenied):
            broker.acknowledge_child_whats_new(caller, target, "1.5")
    for caller, version in ((1003, "1.4"), (1001, "1.4"), (1001, "2.0"), (1001, "bad"), (1001, None)):
        with pytest.raises(InvalidRequest):
            broker.acknowledge_own_whats_new(caller, version)
    assert accounts.events == []


def test_gc_runs_on_acknowledgement_preserves_other_components_and_personal_policy(tmp_path):
    broker, store, _ = make_backend(tmp_path)
    policy = default_preferences()
    policy["parent_control_enabled"] = True
    policy["daily_time_limit_minutes"] = 60
    store.save(1001, policy)
    stale = store.load(1001)
    store.acknowledge_whats_new(1001, "1.4:Child", {"1.4:Child", "1.5:Parent"})
    store.acknowledge_whats_new(1001, "1.5:Parent", {"1.4:Child", "1.5:Parent"})
    store.update_language(1001, "fr")
    store.update_notifications(1001, {"show_in_fullscreen": False, "reminders": []})
    broker._whats_new_loader = lambda: catalog("2.0", records=[
        note("1.5", record_id="1.5:Parent"), note("2.0", record_id="2.0:Child")])
    broker.get_own_whats_new(1001)
    assert store.load(1001)["personal"]["whats_new_seen"] == ["1.4:Child", "1.5:Parent"]
    broker.acknowledge_own_whats_new(1001, "2.0")
    store.save(1001, stale)  # Also covers policy rollback with an obsolete snapshot.
    result = store.load(1001)
    assert result["personal"] == {"language": "fr", "notifications": {
        "show_in_fullscreen": False, "reminders": []}, "whats_new_seen": ["1.5:Parent", "2.0:Child"]}
    assert result["parent_control_enabled"] is True
    assert result["daily_time_limit_minutes"] == 60
    assert result["apps"] == policy["apps"]
    assert result["request"] == policy["request"]


def test_concurrent_acknowledgements_merge_without_losing_versions(tmp_path):
    _, store, _ = make_backend(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(store.acknowledge_whats_new, 1001, record_id, {"1.5:Parent", "1.5:Child"})
                   for record_id in ("1.5:Parent", "1.5:Child")]
        for future in futures:
            future.result(timeout=5)
    assert store.load(1001)["personal"]["whats_new_seen"] == ["1.5:Child", "1.5:Parent"]


def test_component_mismatch_metadata_failure_and_root_identity(tmp_path):
    broker, store, _ = make_backend(tmp_path, catalog(records=[note("1.5", record_id="1.5:Parent")]))
    assert broker.get_own_whats_new(1001)["records"] == []
    with pytest.raises(InvalidRequest):
        broker.acknowledge_own_whats_new(1001, "1.5")
    assert not store.directory.exists()
    broker.acknowledge_own_whats_new(0, "1.5")
    assert store.load(0)["personal"]["whats_new_seen"] == ["1.5:Parent"]
    broker._whats_new_loader = mock.Mock(side_effect=WhatsNewError("invalid metadata"))
    with pytest.raises(BackendFailure):
        broker.get_own_whats_new(1003)
    with pytest.raises(BackendFailure):
        broker.acknowledge_own_whats_new(1003, "1.5")
    assert not (store.directory / "1003.json").exists()


@pytest.mark.parametrize("seen", [None, {}, ["1.4"], ["1.4:Kiosk"],
                                     ["1.4:Parent", "1.4.0:Parent"], ["1.4:Parent"] * 257])
def test_invalid_saved_acknowledgements_are_preserved(tmp_path, seen):
    broker, store, _ = make_backend(tmp_path)
    store.update_language(1001, "fr")
    path = store.directory / "1001.json"
    document = json.loads(path.read_text())
    document["personal"]["whats_new_seen"] = seen
    path.write_text(json.dumps(document))
    before = path.read_bytes()
    with pytest.raises(BackendFailure):
        broker.acknowledge_own_whats_new(1001, "1.5")
    assert path.read_bytes() == before


def test_invalid_or_failed_storage_never_reports_acknowledged(tmp_path):
    broker, store, _ = make_backend(tmp_path)
    store.update_language(1001, "fr")
    path = store.directory / "1001.json"
    before = path.read_bytes()
    with mock.patch("oh_no_parent_control.preferences.os.replace", side_effect=OSError):
        with pytest.raises(BackendFailure):
            broker.acknowledge_own_whats_new(1001, "1.5")
    assert path.read_bytes() == before
    path.write_text('{"version":99,"personal":{"language":"fr"}}')
    corrupt = path.read_bytes()
    with pytest.raises(BackendFailure):
        broker.acknowledge_own_whats_new(1001, "1.5")
    assert path.read_bytes() == corrupt
    with pytest.raises(PreferencesError):
        store.acknowledge_whats_new(1001, "9.0:Child", {"1.4:Child"})


def write_json(path, document, mode=0o600):
    path.write_text(json.dumps(document))
    path.chmod(mode)


def test_package_configuration_tracks_origin_upgrade_and_idempotent_retry(tmp_path):
    product = tmp_path / "app.json"
    state = tmp_path / "state"
    write_json(product, {"version": "1.3"})
    assert migrate_all_state(state, product_path=product) == 1
    path = state / "whats-new-installation.json"
    before = path.read_bytes()
    assert migrate_all_state(state, product_path=product) == 0
    assert path.read_bytes() == before
    write_json(product, {"version": "2.0"})
    assert migrate_all_state(state, product_path=product) == 1
    assert json.loads(path.read_text()) == {"version": 1, "first_version": "1.3", "current_version": "2.0"}
    write_json(product, {"version": "1.5"})
    upgraded = path.read_bytes()
    with pytest.raises(MigrationError):
        migrate_all_state(state, product_path=product)
    assert path.read_bytes() == upgraded


def test_upgrade_from_payload_without_feature_and_catalog_loading(tmp_path):
    product, metadata = tmp_path / "app.json", tmp_path / "whats-new-child.toml"
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    write_json(state / "previous-product.json", {"version": "1.3"})
    write_json(product, {"version": "1.5"})
    metadata.write_text("version = 1\n[[records]]\nProductVersion = '1.5'\n"
                        "Content = '''\n" + note("1.5")["Content"] + "'''\n",
                        encoding="utf-8")
    migrate_all_state(state, product_path=product)
    assert not (state / "previous-product.json").exists()
    history = tmp_path / "VersionHistory.md"
    history.write_text("## v1.5 -\n" + note("1.5")["Content"])
    loaded = WhatsNewCatalog.load(metadata, product, state / "whats-new-installation.json", history)
    assert loaded.available("Parent", [])["records"][0]["auto_show"] is True
    migrate_all_state(state, product_path=product)
    assert json.loads((state / "whats-new-installation.json").read_text())["first_version"] == "1.3"
    write_json(product, {"version": "1.6"})
    with pytest.raises(WhatsNewError):
        WhatsNewCatalog.load(metadata, product, state / "whats-new-installation.json", history)


@pytest.mark.parametrize("failure", ["future", "permissions", "symlink", "interruption"])
def test_installation_history_refuses_unsafe_state_and_retries_atomic_failure(tmp_path, failure):
    product, state = tmp_path / "app.json", tmp_path / "state"
    state.mkdir(mode=0o700)
    write_json(product, {"version": "1.5"})
    history = state / "whats-new-installation.json"
    if failure == "interruption":
        pending = state / "previous-product.json"
        write_json(pending, {"version": "1.3"})
        with mock.patch("oh_no_parent_control.data_migration._atomic_write", side_effect=MigrationError):
            with pytest.raises(MigrationError):
                migrate_all_state(state, product_path=product)
        assert pending.exists() and not history.exists()
        migrate_all_state(state, product_path=product)
        assert json.loads(history.read_text())["first_version"] == "1.3"
    else:
        value = {"version": 2 if failure == "future" else 1, "first_version": "1.3", "current_version": "1.4"}
        write_json(history, value, mode=0o644 if failure == "permissions" else 0o600)
        if failure == "symlink":
            target = state / "foreign.json"
            history.rename(target)
            history.symlink_to(target)
        before = history.read_bytes()
        with pytest.raises(MigrationError):
            migrate_all_state(state, product_path=product)
        assert history.read_bytes() == before
