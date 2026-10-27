"""Independent product-version gates and monitoring for DEB and RPM releases."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError

from . import copr


def load(path):
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    if not isinstance(result, dict):
        raise ValueError('invalid channel publication journal; preserve it for recovery')
    return result


def deb_status(product, record, p):
    entries = [item for item in p.sources() if item['distro_series_link'] == p.SERIES
               and re.fullmatch(re.escape(product) + r'\+ppa[1-9][0-9]*~ubuntu26\.04\.1',
                                item['source_package_version'])]
    if entries:
        versions = sorted({item['source_package_version'] for item in entries},
                          key=p.publication_version_key, reverse=True)
        observations = {}
        # An indexed product remains published even if a later rebuild failed.
        for version in versions:
            progress = {}
            try:
                binary = p.published_binary(version, progress=progress)
            except ValueError as error:
                observations[version] = error
            else:
                if binary:
                    record['published_version'] = version
                    record.setdefault('version', version)
                    return 'published', 'source, build, binary, index and checksum verified'
                observations[version] = progress['detail']
        attempted = record.get('phase') in ('upload-started', 'published', 'complete')
        version = record['version'] if attempted else versions[0]
        if version not in observations:
            return 'uncertain', 'recorded DEB revision is not listed; monitoring without resubmitting'
        record.update(version=version, phase='upload-started')
        detail = observations[version]
        if isinstance(detail, ValueError):
            raise detail
        return 'pending', detail
    if record.get('phase') in ('upload-started', 'published', 'complete'):
        return 'uncertain', 'recorded upload is not listed; monitoring without resubmitting'
    return 'absent', 'no submission for this product version'


def check(channel, product, record, p):
    try:
        state, detail = (deb_status(product, record, p) if channel == 'deb'
                         else copr.status(product, record))
        return state, detail
    except (URLError, TimeoutError, ConnectionError) as error:
        # Unknown status is never permission to submit. Do not echo remote
        # response bodies, URLs containing credentials, or private exceptions.
        reason = f'HTTP {error.code}' if isinstance(error, HTTPError) else type(error).__name__
        if isinstance(error, HTTPError):
            error.close()
            if error.code not in (408, 429, 500, 502, 503, 504):
                return 'failed', f'status unavailable ({reason}); inspect the service configuration'
        return 'uncertain', f'status unavailable ({reason}); submission blocked'
    except (ValueError, KeyError, TypeError, ParseError) as error:
        if isinstance(error, ValueError):
            return 'failed', str(error)
        return 'failed', 'invalid service response; submission blocked'


def pin_source(root, directory, product, p):
    """Authenticate the shared product tag independently of DEB upload state."""
    tag = 'v' + product
    refs = p.command('git', 'ls-remote', p.PUBLIC_GIT, 'refs/tags/' + tag + '^{}', cwd=root)
    lines = refs.splitlines()
    if len(lines) != 1 or not re.fullmatch(r'[0-9a-f]{40}\s+refs/tags/' + re.escape(tag) + r'\^\{\}', lines[0]):
        raise ValueError('RPM publication requires the public signed product tag; resume source publication first')
    revision = lines[0].split()[0]
    checkout = directory / ('rpm-source-v' + product)
    if not checkout.exists():
        checkout.mkdir(mode=0o700)
        p.command('git', 'init', '--bare', str(checkout), cwd=root)
    p.command('git', 'fetch', p.PUBLIC_GIT, 'refs/tags/' + tag + ':refs/tags/' + tag, cwd=checkout)
    signature = p.command('git', '-c', 'gpg.program=/usr/bin/gpg', 'verify-tag', '--raw', tag, cwd=checkout)
    signatures = [line.split() for line in signature.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
    if not signatures or any(p.release.KEY not in (line[2], line[-1]) for line in signatures):
        raise ValueError('COPR source tag is not signed by the configured publisher')
    if p.command('git', 'rev-parse', tag + '^{}', cwd=checkout) != revision:
        raise ValueError('COPR source tag changed during verification')
    metadata = json.loads(p.command('git', 'show', revision + ':data/app.json', cwd=checkout))
    if metadata['version'] != product:
        raise ValueError('COPR source tag has a different product version')
    recipe = p.command('git', 'show', revision + ':.copr/Makefile', cwd=checkout)
    if '--release 1' not in recipe:
        raise ValueError('signed source lacks the official COPR release recipe; do not publish a development RPM')
    return revision


def merge_deb_journal(root, record, p, product):
    journal = load(p.journal_directory(root) / 'state.json')
    if journal and journal.get('product') == product:
        attempted = ('upload-started', 'published', 'complete')
        if journal['phase'] in attempted or record.get('phase') not in attempted:
            record.update({key: journal[key] for key in ('phase', 'version')})
    return journal


def announce(product, channel, state, detail, p):
    destination = 'Launchpad PPA' if channel == 'deb' else 'COPR'
    if state == 'published':
        p.say(f'v{product} {channel} is already published to {destination}', success=True)
    else:
        p.say(f'v{product} {channel} / {destination}: {detail}', error=state == 'failed')


def monitor(product, records, p, *, persist=None):
    """Poll both channels together; a terminal failure cannot hide the other."""
    deadline = time.monotonic() + p.WAIT_SECONDS
    finished, failures = set(), {}
    previous = {}
    while True:
        for channel in ('deb', 'rpm'):
            if channel in finished:
                continue
            state, detail = check(channel, product, records[channel], p)
            if state == 'absent':
                state, detail = 'failed', 'this version has not been submitted'
            if previous.get(channel) != (state, detail):
                announce(product, channel, state, detail, p)
                previous[channel] = state, detail
            if state in ('published', 'failed'):
                finished.add(channel)
                if state == 'failed':
                    failures[channel] = detail
                else:
                    records[channel]['phase'] = 'published'
            if persist:
                persist()
        if len(finished) == 2:
            break
        if time.monotonic() >= deadline:
            raise ValueError('channel publication not confirmed within 24 hours; rerun to monitor without resubmitting')
        time.sleep(p.POLL_SECONDS)
    if failures:
        raise ValueError('publication failed for ' + ', '.join(failures) + '; see channel status above')


def monitor_status(root, p):
    directory = p.journal_directory(root)
    reference = load(directory / 'channels-monitor.json')
    state = load(Path(reference['journal'])) if reference else load(directory / 'channels.json')
    if reference and (state is None or state.get('product') != reference['product']):
        state = reference
    if state is None:
        # Retain compatibility with Launchpad-only historical journals and main
        # handoffs, without changing them or choosing an unrelated RPM version.
        version = p.publication_status(root, wait=False)
        product = '.'.join(str(part) for part in p.publication_version_key(version)[:2])
        state = {'product': product, 'deb': {'version': version, 'phase': 'upload-started'}, 'rpm': {}}
    p.parse_product_version(state['product'])
    monitor(state['product'], {key: dict(state[key]) for key in ('deb', 'rpm')}, p)


def run(root, p, *, status=False):
    if status or p.command('git', 'branch', '--show-current', cwd=root) == 'main':
        return monitor_status(root, p)
    branch = p.publishing_branch(root)
    with p.locked(root, attach=True, name='channels.lock') as legacy_path:
        if legacy_path is None:
            return monitor_status(root, p)
        current = json.loads((root / 'data/app.json').read_text())['version']
        product, _ = p.history_entry((root / p.HISTORY).read_text(), current)
        p.publishing_branch(root, product)
        path = legacy_path.with_name('channels.json')
        state = load(path)
        if state and state.get('product') != product:
            if any(state[key].get('phase') != 'published' for key in ('deb', 'rpm')):
                raise ValueError('unfinished channel publication belongs to a different version; preserve its journal')
            state = None
        if state is None:
            state = {'product': product, 'branch': branch, 'deb': {}, 'rpm': {}}
        if state.get('branch') != branch:
            raise ValueError('channel publication belongs to a different release branch')

        def persist():
            p.save(path, state)

        merge_deb_journal(root, state['deb'], p, product)
        # Both gates run before any commit, signing, build, push or upload.
        gates = {channel: check(channel, product, state[channel], p) for channel in ('deb', 'rpm')}
        for channel, (outcome, detail) in gates.items():
            announce(product, channel, outcome, detail, p)
        persist()
        errors, recovery_errors = {}, {}
        # The existing DEB workflow owns common signed release source and the
        # main handoff. Stop it before waiting, so COPR gets its turn promptly.
        if gates['deb'][0] == 'absent':
            try:
                p.publish(root, wait=False)
            except (ValueError, OSError) as error:
                if str(error) == 'publication cancelled before updating main':
                    raise
                errors['deb'] = str(error)
                p.say(str(error), error=True)
            finally:
                merge_deb_journal(root, state['deb'], p, product)
                persist()
            if state['deb'].get('phase') in ('upload-started', 'published') and 'deb' in errors:
                recovery_errors['deb'] = errors.pop('deb')
        # Public status never depends on archived .changes/.dsc/tar files or
        # auto-commits local edits. Only an unfinished Git handoff is resumed.
        journal = load(legacy_path)
        if ('deb' not in recovery_errors and journal and journal.get('product') == product
                and journal.get('phase') in ('upload-started', 'published')):
            try:
                with p.locked(root) as delivery_path:
                    p.resume_delivery(root, journal, delivery_path)
            except (ValueError, OSError) as error:
                if str(error) == 'publication cancelled before updating main':
                    raise
                recovery_errors['deb'] = str(error)
                p.say(f'local DEB release recovery incomplete: {error}', error=True)
        if gates['rpm'][0] == 'absent':
            try:
                revision = pin_source(root, path.parent, product, p)
                authorization = copr.credentials()
                # Reconcile immediately before the write as another client may
                # have submitted while source preparation was running.
                outcome, detail = check('rpm', product, state['rpm'], p)
                if outcome == 'absent':
                    state['rpm'].update(phase='upload-started', revision=revision)
                    persist()  # A lost response must never trigger a second POST.
                    try:
                        result = copr.submit(revision, authorization)
                        if (type(result.get('id')) is not int or result['id'] <= 0
                                or (result.get('ownername'), result.get('projectname')) != (copr.OWNER, copr.PROJECT)):
                            raise ValueError('COPR returned an invalid submission identity')
                        state['rpm'].update(phase='submitted', build_id=result['id'])
                        persist()
                    except HTTPError as error:
                        if error.code in (400, 401, 403, 404, 422):
                            state['rpm'].update(phase='rejected', http_status=error.code)
                            persist()
                            p.say(f'COPR rejected the submission (HTTP {error.code}); no retry attempted', error=True)
                        else:
                            p.say('COPR submission result uncertain; monitoring without resubmitting', error=True)
                        error.close()
                    except (ValueError, URLError, TimeoutError, ConnectionError):
                        p.say('COPR submission result uncertain; monitoring without resubmitting', error=True)
                else:
                    announce(product, 'rpm', outcome, detail, p)
            except (ValueError, OSError) as error:
                # Never print credential parser errors or raw HTTP response data.
                errors['rpm'] = str(error) if isinstance(error, ValueError) else 'COPR preparation failed; check source and credentials'
                p.say(errors['rpm'], error=True)
        persist()
        # Hand main an independent channel reference even when only one service
        # needed a submission. Preserve a newer release's monitoring selection.
        journal = load(legacy_path)
        if journal and journal.get('product') == product and journal.get('main_update', {}).get('phase') == 'complete':
            try:
                p.reconcile_main_monitor(journal, legacy_path)
            except (ValueError, OSError) as error:
                recovery_errors['monitor'] = str(error)
                p.say(f'local monitoring handoff incomplete: {error}', error=True)
        monitor_error = None
        try:
            monitor(product, state, p, persist=persist)
        except ValueError as error:
            monitor_error = error
        # Complete legacy checkout synchronization after DEB publication. A
        # failed RPM must not prevent an independently successful DEB close-out.
        journal = load(legacy_path)
        if ('deb' not in recovery_errors and state['deb'].get('phase') == 'published' and journal
                and journal.get('product') == product
                and journal.get('phase') in ('upload-started', 'published')):
            try:
                if state['deb'].get('published_version') != journal['version']:
                    raise ValueError('published DEB revision differs from the recorded submission; reconcile the release journal')
                with p.locked(root) as delivery_path:
                    p.resume_delivery(root, journal, delivery_path, published=True)
                recovery_errors.pop('deb', None)
                errors.pop('deb', None)
            except (ValueError, OSError) as error:
                recovery_errors['deb'] = str(error)
                p.say(f'DEB publication confirmed; local release recovery incomplete: {error}', error=True)
        if errors:
            raise ValueError('channel preparation failed for ' + ', '.join(errors) + '; see errors above')
        if monitor_error:
            raise monitor_error
        if recovery_errors:
            raise ValueError('publication confirmed; local release recovery incomplete; see errors above')
