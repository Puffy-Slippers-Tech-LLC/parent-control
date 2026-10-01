"""Scripted language storage for GUI tests; no product backend or OS calls."""

import os
from pathlib import Path
import time


class LanguageFixture:
    def __init__(self, record):
        self.record = record
        self.language = os.environ.get('ONPC_LANGUAGE_INITIAL', '')
        self.load_failures = int(os.environ.get('ONPC_LANGUAGE_LOAD_FAILURES', '0'))
        self.save_failures = int(os.environ.get('ONPC_LANGUAGE_SAVE_FAILURES', '0'))
        release = os.environ.get('ONPC_LANGUAGE_SAVE_RELEASE')
        self.release = Path(release) if release else None

    def read(self):
        self.record('language-read')
        if self.load_failures:
            self.load_failures -= 1
            self.record('language-read-failed')
            raise RuntimeError('synthetic language read failure')
        return self.language

    def released(self):
        return self.release is None or self.release.is_file()

    def commit(self, language):
        if self.save_failures:
            self.save_failures -= 1
            self.record('language-save-failed', language=language)
            raise RuntimeError('synthetic language save failure')
        self.language = language
        self.record('language-committed', language=language)
        return language

    def save(self, language):
        self.record('language-save-started', language=language)
        deadline = time.monotonic() + 60
        while not self.released():
            if time.monotonic() >= deadline:
                raise TimeoutError('language save fixture was not released')
            time.sleep(.02)
        return self.commit(language)
