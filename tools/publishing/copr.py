"""COPR v3 submission and public repository verification for the Fedora channel."""
from __future__ import annotations

import base64
import configparser
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from . import source

BASE = 'https://copr.fedorainfracloud.org'
API = BASE + '/api_3'
OWNER = source.OWNER
PROJECT = source.PACKAGE
CHROOT = 'fedora-44-x86_64'
GIT_URL = source.ORIGIN.replace('git@github.com:', 'https://github.com/')
PENDING = {'pending', 'starting', 'importing', 'waiting', 'running', 'forked'}
FAILED = {'failed', 'canceled', 'cancelled', 'unknown', 'skipped'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # In particular, never forward the API token to a redirected endpoint.
        return None


def read(url, *, data=None, authorization=None):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.hostname not in ('copr.fedorainfracloud.org',
                                       'download.copr.fedorainfracloud.org',
                                       'copr-be.cloud.fedoraproject.org')):
        raise ValueError('unexpected COPR publication URL')
    if authorization and (parsed.netloc != 'copr.fedorainfracloud.org'
                          or parsed.path != '/api_3/build/create/scm'):
        raise ValueError('unexpected authenticated COPR endpoint')
    headers = {'Cache-Control': 'no-cache'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    if authorization:
        headers['Authorization'] = authorization
    request = Request(url, data=data, headers=headers)
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        return response.read()


def api(endpoint, **params):
    query = '?' + urlencode(params) if params else ''
    result = json.loads(read(API + endpoint + query))
    if not isinstance(result, dict) or 'error' in result:
        raise ValueError('COPR returned an invalid API result')
    return result


def project():
    result = api('/project', ownername=OWNER, projectname=PROJECT)
    if (result.get('ownername'), result.get('name')) != (OWNER, PROJECT):
        raise ValueError('COPR project identity mismatch')
    if set(result['chroot_repos']) != {CHROOT}:
        raise ValueError('COPR project must enable only fedora-44-x86_64')
    return result


def builds():
    # Include unidentified source builds: filtering by package name would hide
    # an in-flight source generation and could cause a duplicate submission.
    result, seen, offset = [], set(), 0
    while True:
        page = api('/build/list', ownername=OWNER, projectname=PROJECT,
                   limit=100, offset=offset, order='id', order_type='DESC')['items']
        if not page:
            return result
        for item in page:
            if item['id'] in seen:
                raise ValueError('COPR build listing changed during pagination; retry status')
            seen.add(item['id'])
            result.append(item)
        offset += len(page)


def credentials():
    path = Path.home() / '.config/copr'
    # Open without following a link; check the opened file rather than a prior
    # pathname stat. Secrets are never passed through command arguments/logs.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise ValueError('COPR credentials must be caller-owned and private; chmod 600 ~/.config/copr')
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read_file(stream)
            values = config['copr-cli']
            if values.get('copr_url', BASE).rstrip('/') != BASE:
                raise ValueError('COPR credentials must select the public Fedora COPR service')
            login, token = values['login'].strip(), values['token'].strip()
            if not login or not token or ':' in login or any(c in login + token for c in '\r\n'):
                raise ValueError('COPR credentials are incomplete')
        except (configparser.Error, KeyError):
            raise ValueError('invalid COPR credential configuration') from None
    return 'Basic ' + base64.b64encode((login + ':' + token).encode()).decode()


def submit(revision, authorization):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('COPR source must be pinned to an exact Git commit')
    data = dict(ownername=OWNER, projectname=PROJECT, clone_url=GIT_URL, committish=revision,
        subdirectory='', spec='rpm/oh-no-parent-control.spec.in', scm_type='git',
        source_build_method='make_srpm', chroots=[CHROOT], enable_net=False)
    return json.loads(read(API + '/build/create/scm', data=json.dumps(data).encode(),
                           authorization=authorization))


def indexed_package(product, build, repository):
    """Require the selected build's RPM in repodata and verify its download."""
    repository = repository.rstrip('/') + '/'
    repomd = ET.fromstring(read(repository + 'repodata/repomd.xml'))
    ns = {'r': 'http://linux.duke.edu/metadata/repo'}
    primary = repomd.find("r:data[@type='primary']", ns)
    if primary is None:
        raise ValueError('COPR repository has no primary metadata')
    location = primary.find('r:location', ns).attrib['href']
    packed = read(urljoin(repository, location))
    checksum = primary.find('r:checksum', ns)
    if checksum.attrib['type'] != 'sha256' or hashlib.sha256(packed).hexdigest() != checksum.text:
        raise ValueError('COPR primary metadata checksum mismatch')
    metadata = ET.fromstring(gzip.decompress(packed) if location.endswith('.gz') else packed)
    ns = {'p': 'http://linux.duke.edu/metadata/common'}
    for package in metadata.findall('p:package', ns):
        version = package.find('p:version', ns).attrib
        if (package.findtext('p:name', namespaces=ns), version['ver'],
                package.findtext('p:arch', namespaces=ns)) != (source.PACKAGE, product, 'x86_64'):
            continue
        href = package.find('p:location', ns).attrib['href']
        # COPR's result directory includes the numeric build ID (zero padded on
        # some backends). Do not accept another build of the same product.
        if not any(re.fullmatch(r'0*' + str(build['id']) + '-' + re.escape(source.PACKAGE),
                               part) for part in urlsplit(href).path.split('/')):
            continue
        payload = read(urljoin(repository, href))
        checksum = package.find('p:checksum', ns)
        size = int(package.find('p:size', ns).attrib['package'])
        if (checksum.attrib['type'] != 'sha256' or len(payload) != size
                or hashlib.sha256(payload).hexdigest() != checksum.text):
            raise ValueError('COPR RPM checksum mismatch')
        return True
    return False


def source_matches(build_id, revision):
    configuration = api('/build/source-build-config/' + str(build_id))
    scm = configuration.get('source_dict') or {}
    return (configuration.get('source_type') == 'scm'
            and scm.get('type') == 'git' and scm.get('clone_url') == GIT_URL
            and scm.get('committish') == revision and scm.get('subdirectory') == ''
            and scm.get('spec') == 'rpm/oh-no-parent-control.spec.in'
            and scm.get('srpm_build_method') == 'make_srpm')


def status(product, record):
    configuration = project()
    candidates = []
    listed = builds()
    unresolved = set(record.get('unidentified_ids', []))
    for build in listed:
        if (build['ownername'], build['projectname']) != (OWNER, PROJECT):
            raise ValueError('COPR build identity mismatch')
        package = build.get('source_package') or {}
        name, version = package.get('name'), package.get('version')
        matches_product = name == source.PACKAGE and version and version.split('-')[0] == product
        if name and version:
            unresolved.discard(build['id'])
        if (record.get('revision') and not record.get('build_id')
                and (matches_product or (not version and name in (None, source.PACKAGE)))):
            # A lost POST response can still be reconciled before RPM metadata
            # exists, including a source-generation failure. Bind exact inputs.
            if source_matches(build['id'], record['revision']):
                record['build_id'] = build['id']
            unresolved.discard(build['id'])
            if not matches_product and build['id'] != record.get('build_id'):
                continue
        if build['id'] == record.get('build_id'):
            if name not in (None, source.PACKAGE) or (version and version.split('-')[0] != product):
                raise ValueError('recorded COPR build has a different package or version')
            candidates.append(build)
        elif matches_product:
            candidates.append(build)
        elif build['state'] not in FAILED | {'succeeded'} and (not name or (name == source.PACKAGE and not version)):
            unresolved.add(build['id'])
    record['unidentified_ids'] = sorted(unresolved)
    successful = {}
    # A published product wins over a later pending/failed rebuild. Until that
    # is proven, keep following the retained submission rather than retarget it.
    for build in sorted(candidates, key=lambda item: item['id'], reverse=True):
        if build['state'] != 'succeeded' or set(build['chroots']) != {CHROOT}:
            continue
        packages = api('/build/built-packages/' + str(build['id'])).get(CHROOT, {}).get('packages', [])
        if not any((item['name'], item['version'], item['arch']) ==
                   (source.PACKAGE, product, 'x86_64') for item in packages):
            successful[build['id']] = 'COPR build has no matching product RPM'
            continue
        try:
            if indexed_package(product, build, configuration['chroot_repos'][CHROOT]):
                record['published_build_id'] = build['id']
                return 'published', 'repository metadata and RPM checksum verified'
        except HTTPError as error:
            if error.code != 404:
                raise
            error.close()
        successful[build['id']] = None
    recorded = next((item for item in candidates if item['id'] == record.get('build_id')), None)
    if record.get('phase') == 'rejected':
        raise ValueError(f'COPR rejected the submission (HTTP {record["http_status"]}); inspect credentials/project before retrying')
    if record.get('build_id') and recorded is None:
        return 'uncertain', 'recorded COPR build is missing; submission blocked'
    if record.get('revision') and not record.get('build_id'):
        return 'uncertain', 'recorded COPR source is not listed; monitoring without resubmitting'
    if candidates:
        build = recorded or max(candidates, key=lambda item: item['id'])
        record['build_id'] = build['id']
        if set(build['chroots']) != {CHROOT}:
            raise ValueError('COPR candidate must target only fedora-44-x86_64')
        if build['state'] in FAILED:
            raise ValueError(f'COPR build {build["id"]} failed; inspect the project before retrying')
        if build['state'] == 'succeeded':
            if successful[build['id']]:
                raise ValueError(successful[build['id']])
            return 'pending', 'build succeeded; waiting for repository publication'
        if build['state'] not in PENDING:
            raise ValueError('unrecognized COPR build state; inspect the project')
        return 'pending', f'build {build["id"]} is {build["state"]}'
    if unresolved:
        return 'uncertain', 'an unidentified COPR source build is in progress; submission blocked'
    if record.get('phase') in ('upload-started', 'submitted', 'published'):
        return 'uncertain', 'recorded submission is not listed; monitoring without resubmitting'
    return 'absent', 'no submission for this product version'
