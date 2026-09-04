"""User-local request selector defaults; never an account authority."""

import json
import logging
import os
from pathlib import Path
import tempfile

LOG = logging.getLogger(__name__)


class SelectionStore:
    def __init__(self, path, *, child_overlay=False):
        self.path = Path(path)
        self.child_overlay = child_overlay
        self.values = {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("invalid selector state")
            self.values = {key: uid for key, uid in value.items()
                           if key in ("child_uid", "approver_uid")
                           and type(uid) is int and 0 < uid < 2**32}
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            LOG.warning("local request selections could not be loaded")

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
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent, delete=False) as stream:
                temporary = stream.name
                json.dump(self.values, stream)
            os.replace(temporary, self.path)
            temporary = None
            LOG.info("local request selection saved selector=%s", key)
        except OSError:
            LOG.warning("local request selection could not be saved selector=%s", key)
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
