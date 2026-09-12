"""Synthetic system information shared by diagnostic attachment tests."""


def sample_info():
    return {"schema": 1, "app_version": "1.2", "os": {"id": "ubuntu", "version": "26.04"},
            "kernel": "6.17.0", "architecture": "x86_64", "session_type": "wayland",
            "timezone": {"name": "America/Los_Angeles", "utc_offset_seconds": -25200},
            "accounts": {"administrators": 2, "non_administrators": 3, "status": "complete"},
            "dependencies": {"status": "complete", "packages": [
                {"name": "python3", "version": "3.14.2", "architecture": "amd64", "status": "installed"},
            ]}}
