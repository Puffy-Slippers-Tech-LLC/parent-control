"""Clear runner outcomes shared by one execution and its repair sessions.

Each case has one atomic record. Missing records mean pending work; process
claims, source revisions and agent statements never supply completion credit.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile

VARIABLE = 'ONPC_TEST_RESULT_DIRECTORY'
REPAIR_QUEUE = 'ONPC_TEST_REPAIR_QUEUE'
PENDING_STATUS = 76


def classic_profile(options):
    return isinstance(options, (list, tuple)) and (
        '--subcategory=gnome-classic' in options
        or ('--subcategory', 'gnome-classic') in zip(options, options[1:]))


def same_desktop_profile(category, saved, requested):
    return category != 'e2e' or classic_profile(saved) == classic_profile(requested)


def result_key(record):
    key = [record['category'], record['family'], record['case'], record.get('work')]
    if not same_desktop_profile(record['category'], record.get('options', []), ()):
        key.append('gnome-classic')
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


class ResultStore:
    def __init__(self, directory=None):
        if directory is None:
            directory = os.environ.get(VARIABLE)
        self.directory = Path(directory) if directory else None
        self.path = None
        if self.directory is None:
            return
        from test_retention import ensure_directory
        ensure_directory(self.directory)
        self.path = self.directory / 'cases'
        ensure_directory(self.path)

    def load(self):
        if self.path is None:
            return []
        records = []
        for path in sorted(self.path.glob('*.json')):
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(descriptor) as stream:
                    from test_retention import private
                    info = os.fstat(stream.fileno())
                    private(info, regular=True)
                    if info.st_size > 128 * 1024:
                        continue
                    value = json.load(stream)
                if (isinstance(value, dict)
                        and all(isinstance(value.get(key), str) for key in ('category', 'family', 'case'))
                        and type(value.get('status')) is int
                        and value['status'] >= 0 and value['status'] not in (130, 75, PENDING_STATUS)):
                    records.append(value)
            except (OSError, ValueError):
                continue
        return records

    def begin(self):
        """The next outcome belongs only to the invocation about to start."""
        (self.directory / 'failure.json').unlink(missing_ok=True)

    def failure(self):
        try:
            value = json.loads((self.directory / 'failure.json').read_text())
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def select_failure(self, category, family, cases, options, *, vms=()):
        """Discovery may return a selected known failure without reproducing it."""
        if not os.environ.get(REPAIR_QUEUE):
            return None
        for record in self.failures():
            saved = record.get('work')
            case = record['case'] or (saved.get('case') if isinstance(saved, dict) else '')
            if (record['category'] == category and record['family'] in (family, 'command')
                    and same_desktop_profile(category, record.get('options', []), options)
                    and (case in cases if case else record.get('options') == options)):
                vm = record.get('vm') if record.get('vm') in vms else next(iter(vms), '')
                failure = dict(record, options=options, vm=vm)
                if isinstance(saved, dict):
                    failure['work'] = dict(saved, category=category, options=options)
                self._save(self.directory / 'failure.json', failure)
                return failure
        return None

    def failures(self):
        return [record for record in self.load() if record['status']]

    def passed(self, category, family, *, options=()):
        return {record['case'] for record in self.load()
                if record['category'] == category and record['family'] == family and not record['status']
                and same_desktop_profile(category, record.get('options', []), options)
                and record['case']}

    def complete(self, category, family, options):
        return any(record['category'] == category and record['family'] == family
                   and not record['case'] and not record['status'] and record.get('complete') is True
                   and not record.get('work')
                   and record.get('options') == options for record in self.load())

    def finish_command(self, category, options, *, family=None, work=None):
        """Resolve the enclosing operation that actually completed."""
        for record in self.failures():
            saved = record.get('work')
            matching = (not saved and record.get('options') == options if work is None else
                        isinstance(saved, dict) and all(saved.get(key) == work.get(key)
                                                       for key in ('case', 'area')))
            if (record['category'] == category and not record['case']
                    and (family is None or record['family'] in (family, 'command'))
                    and same_desktop_profile(category, record.get('options', []), options) and matching):
                context = {key: value for key, value in record.items()
                           if key not in ('category', 'family', 'case', 'status', 'complete')}
                self.record(category, record['family'], '', 0, complete=True, **context)

    def reconcile(self, category, family, cases, *, options=None):
        """Forget vanished cases; replacements receive no completion credit."""
        if cases is None:
            return
        selected = set(cases)
        for record in self.load():
            if (record['category'] == category and record['family'] == family
                    and (options is None or record.get('options', []) == options)
                    and record['case'] and record['case'] not in selected):
                (self.path / (result_key(record) + '.json')).unlink(missing_ok=True)

    def record(self, category, family, case, status, **context):
        if self.path is None:
            return
        if (not all(isinstance(value, str) for value in (category, family, case))
                or type(status) is not int):
            raise ValueError('invalid runner outcome')
        if status < 0 or status in (130, 75, PENDING_STATUS):
            return
        record = dict(context, category=category, family=family, case=case, status=status)
        record.setdefault('vm', '')
        record.setdefault('options', [])
        for field in ('detail', 'output', 'output_tail'):
            if field in record:
                record[field] = str(record[field])[-16000:]
        self._save(self.path / (result_key(record) + '.json'), record)
        if status and os.environ.get(REPAIR_QUEUE):
            self._save(self.directory / 'failure.json', record)
        return record

    @staticmethod
    def _save(path, record):
        encoded = json.dumps(record, ensure_ascii=True)
        if len(encoded) > 128 * 1024:
            record = {key: value for key, value in record.items()
                      if key in ('category', 'family', 'case', 'status', 'vm', 'options',
                                 'complete', 'work', 'invocation')}
            encoded = json.dumps(record, ensure_ascii=True)
        fd, temporary = tempfile.mkstemp(prefix='result-', dir=path.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
