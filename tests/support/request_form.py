"""Shared launch and event readers for the request-form component fixture."""

from tests.support.events import read_events


def launch_request(launch_ui, tmp_path, *, overlay, scenario="normal", selections_path=None):
    path = tmp_path / f"request-{overlay}-{scenario}.jsonl"
    application, _log = launch_ui("request_component_preview", environment_overrides={
        "ONPC_REQUEST_COMPONENT_EVENTS_PATH": str(path),
        "ONPC_REQUEST_COMPONENT_OVERLAY": "1" if overlay else "0",
        "ONPC_REQUEST_COMPONENT_SCENARIO": scenario,
        "ONPC_REQUEST_COMPONENT_SELECTIONS_PATH": str(selections_path or ""),
    })
    return application, path


def calls(path, method):
    return [item for item in read_events(path)
            if item["event"] == "call" and item["method"] == method]


def events(path, event):
    return [item for item in read_events(path) if item["event"] == event]
