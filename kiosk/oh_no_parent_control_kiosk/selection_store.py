"""User-local request selector defaults; never an account authority."""

import json
import errno
from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code, os_error_code
import os
from pathlib import Path
import tempfile

LOG = get_logger("kiosk-selection-store")


class SelectionStore:
    def __init__(self, path, *, child_overlay=False):
        self.path = Path(path)
        self.child_overlay = child_overlay
        self.values = {}
        stage = 'read'
        try:
            encoded = self.path.read_text(encoding="utf-8")
            stage = 'decode'
            value = json.loads(encoded)
            if not isinstance(value, dict):
                raise ValueError("invalid selector state")
            self.values = {key: uid for key, uid in value.items()
                           if key in ("child_uid", "approver_uid")
                           and type(uid) is int and 0 < uid < 2**32}
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            LOG.warning("kiosk-selection-store.001")
            self._record_failure(error, stage)

    def preferred(self, key):
        if key == "child_uid" and self.child_overlay:
            return 0
        return self.values.get(key, 0)

    def remember(self, key, uid):
        if key == "child_uid" and self.child_overlay:
            return
        if self.values.get(key) == uid:
            return
        self.values[key] = uid
        temporary = None
        stage = 'directory'
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            stage = 'write'
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent, delete=False) as stream:
                temporary = stream.name
                json.dump(self.values, stream)
            stage = 'replace'
            os.replace(temporary, self.path)
            temporary = None
            LOG.info("kiosk-selection-store.002", selector={"child_uid": "child", "approver_uid": "approver"}.get(key, "other"))
        except OSError as error:
            LOG.warning("kiosk-selection-store.003", selector={"child_uid": "child", "approver_uid": "approver"}.get(key, "other"))
            self._record_failure(error, stage)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _record_failure(error, stage):
        try:
            LOG.warning('kiosk-selection-store.failure', stage=stage,
                        error_type=error_code(error), os_error={
                            errno.ENOTDIR: 'not-directory', errno.EISDIR: 'is-directory',
                            errno.EEXIST: 'already-exists',
                        }.get(getattr(error, 'errno', None), os_error_code(error)))
        except Exception:
            pass
