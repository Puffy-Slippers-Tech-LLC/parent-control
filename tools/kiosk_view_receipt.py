"""Closed retained-view records; these helpers confer no descriptor authority.

Native constructs/compares the expected inventory and independently observes
sources, links and mount topology. A helper's mutually consistent records are
never acquisition or publication evidence. Missing/unsafe ambient inputs are
represented explicitly, preserving their original source index and provenance.
"""
import hashlib
import json
import stat

MAX_ROWS = 32768
MAX_BYTES = 64 * 1024 * 1024
MAX_PATH = 4096
MAX_INTEGER = (1 << 63) - 1
CLASSES = ('skeleton', 'native', 'runtime', 'payload', 'vendor', 'alias', 'ambient')
ROLES = ('manager', 'executor', 'gate', 'session-start', 'leader', 'service',
         'pipewire', 'app-start', 'notifications-start', 'notification-client-start',
         'wellbeing-start', 'audio-start', 'packages-start', 'audio', 'rpm', 'locale',
         'python', 'gjs', 'polkit', 'bwrap', 'bwrap-native', 'glycin', 'webkit',
         'scanner', 'blocked', 'library', 'data', 'skeleton', 'ambient', 'vendor')
KINDS = ('tree', 'directory', 'empty-directory', 'file', 'link', 'absent')
NODE_FIELDS = ('path', 'kind', 'required', 'source_class', 'acquisition', 'role',
               'source_index', 'origin_device', 'origin_inode', 'device', 'inode',
               'size', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'gid', 'nlink',
               'sha256', 'label', 'link', 'mountpoint')
COVERAGE_FIELDS = ('owner', 'path', 'origin_device', 'origin_inode', 'device',
                   'inode', 'size', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'gid')


def _text(value):
    if (not isinstance(value, str) or not value or
            any(ord(c) < 32 or ord(c) == 127 for c in value) or
            len(value.encode('utf-8')) >= MAX_PATH):
        raise ValueError('receipt-text')
    return value


def _path(value):
    _text(value)
    if (value != '/usr' and not value.startswith('/usr/')) or any(
            part in ('', '.', '..') for part in value.split('/')[1:]):
        raise ValueError('receipt-path')
    return value


def _integer(value):
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise ValueError('receipt-integer')
    return value


def _digest(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('receipt-digest')
    return value


def material_canonical(record):
    """Exactly the pre-existing material_digest encoding, without inode data."""
    data = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')
    if len(data) > MAX_BYTES:
        raise ValueError('material-limit')
    return data


def _hash(domain, data):
    if len(data) > MAX_BYTES:
        raise ValueError('receipt-limit')
    return hashlib.sha256(domain + b'\0' + len(data).to_bytes(8, 'big') + data).hexdigest()


def material_digest(record):
    return _hash(b'ONPC-KIOSK-MATERIAL', material_canonical(record))


def validate_receipt(record):
    if (not isinstance(record, dict) or set(record) != {
            'format', 'kind', 'backend', 'role', 'material', 'source', 'acquisition', 'nodes', 'coverage'} or
            type(record['format']) is not int or record['format'] != 2 or
            record['kind'] not in ('V', 'I') or record['backend'] not in ('apparmor', 'selinux') or
            record['role'] != ('manager' if record['kind'] == 'V' else 'gate')):
        raise ValueError('receipt-header')
    _digest(record['material'])
    _digest(record['acquisition'])
    if record['kind'] == 'V':
        if record['source'] != '-':
            raise ValueError('receipt-self-reference')
    else:
        _digest(record['source'])
    nodes, coverage = record['nodes'], record['coverage']
    if (not isinstance(nodes, list) or not isinstance(coverage, list) or not nodes or
            len(nodes) + len(coverage) > MAX_ROWS):
        raise ValueError('receipt-limit')
    previous, by_path, previous_index = '', {}, -1
    for node in nodes:
        if not isinstance(node, dict) or set(node) != set(NODE_FIELDS):
            raise ValueError('receipt-node')
        path, kind = _path(node['path']), node['kind']
        if path <= previous or kind not in KINDS:
            raise ValueError('receipt-order')
        previous = path
        if node['required'] not in (0, 1) or type(node['required']) is not int:
            raise ValueError('receipt-required')
        if (node['source_class'] not in CLASSES or node['role'] not in ROLES or
                node['acquisition'] not in ('initial', 'retained', 'none')):
            raise ValueError('receipt-class')
        for key in NODE_FIELDS[6:18]:
            _integer(node[key])
        if node['source_index'] <= previous_index:
            raise ValueError('receipt-source-index')
        previous_index = node['source_index']
        if type(node['mountpoint']) is not int or node['mountpoint'] not in (0, 1):
            raise ValueError('receipt-mountpoint')
        _text(node['label'])
        _text(node['link'])
        no_source = kind in ('empty-directory', 'absent')
        if no_source:
            if (node['required'] or node['source_class'] != 'ambient' or node['role'] != 'ambient' or
                    node['acquisition'] != 'none' or node['mountpoint'] or node['sha256'] != '-' or
                    node['label'] != '-' or node['link'] != '-' or any(node[key] for key in NODE_FIELDS[9:18])):
                raise ValueError('receipt-omission')
        else:
            if (not node['inode'] or not node['origin_inode'] or node['acquisition'] !=
                    ('initial' if record['kind'] == 'V' else 'retained')):
                raise ValueError('receipt-provenance')
            expected_type = stat.S_IFREG if kind == 'file' else stat.S_IFLNK if kind == 'link' else stat.S_IFDIR
            if stat.S_IFMT(node['mode']) != expected_type:
                raise ValueError('receipt-kind')
            if kind == 'file' and node['source_class'] != 'ambient':
                _digest(node['sha256'])
            elif node['sha256'] != '-':
                raise ValueError('receipt-digest')
            if kind != 'link' and node['link'] != '-':
                raise ValueError('receipt-link')
            if kind == 'link' and (node['link'] == '-' or node['mountpoint']):
                raise ValueError('receipt-link')
            if kind == 'tree':
                if node['source_class'] != 'skeleton' or node['role'] != 'skeleton':
                    raise ValueError('receipt-class')
            elif node['source_class'] == 'skeleton':
                raise ValueError('receipt-class')
            if node['source_class'] == 'ambient':
                if node['required'] or node['role'] != 'ambient':
                    raise ValueError('receipt-class')
            elif node['source_class'] != 'skeleton' and not node['required']:
                raise ValueError('receipt-required')
            if node['source_class'] in ('native', 'runtime', 'payload', 'vendor') and kind != 'file' and not (
                    node['source_class'] == 'runtime' and kind == 'link'):
                raise ValueError('receipt-class')
            if node['source_class'] in ('runtime', 'payload') and node['role'] != 'data':
                raise ValueError('receipt-role')
            if node['source_class'] == 'vendor' and node['role'] != 'vendor':
                raise ValueError('receipt-role')
            if node['source_class'] == 'alias' and (kind != 'link' or node['role'] != 'data'):
                raise ValueError('receipt-role')
            if node['source_class'] in ('native', 'runtime', 'payload', 'vendor') and kind == 'file':
                allowed_links = ((0, 1) if node['source_class'] == 'vendor' and
                                 record['kind'] == 'I' else (1,))
                if node['nlink'] not in allowed_links:
                    raise ValueError('receipt-links')
        if path != '/usr' and by_path.get(path.rsplit('/', 1)[0], {}).get('kind') != 'tree':
            raise ValueError('receipt-parent')
        by_path[path] = node
    if nodes[0]['path'] != '/usr' or nodes[0]['kind'] != 'tree' or not nodes[0]['required'] or not nodes[0]['mountpoint']:
        raise ValueError('receipt-root')
    previous = ''
    for witness in coverage:
        if not isinstance(witness, dict) or set(witness) != set(COVERAGE_FIELDS):
            raise ValueError('receipt-coverage')
        path = _path(witness['path'])
        for key in COVERAGE_FIELDS:
            if key != 'path':
                _integer(witness[key])
        owner = witness['owner']
        if owner >= len(nodes):
            raise ValueError('receipt-coverage')
        parent = nodes[owner]
        if (path <= previous or path in by_path or parent['kind'] != 'directory' or
                not path.startswith(parent['path'] + '/') or not witness['origin_inode'] or
                not witness['inode'] or stat.S_IFMT(witness['mode']) not in (stat.S_IFREG, stat.S_IFDIR)):
            raise ValueError('receipt-coverage')
        previous = path
    return record


def encode_receipt(record):
    validate_receipt(record)
    lines = ['\t'.join(('ONPC-KIOSK-RECEIPT', '2', record['kind'], record['backend'],
                       record['role'], record['material'], record['source'], record['acquisition']))]
    for node in record['nodes']:
        lines.append('\t'.join(('N', *(str(node[key]) for key in NODE_FIELDS))))
    for witness in record['coverage']:
        lines.append('\t'.join(('C', *(str(witness[key]) for key in COVERAGE_FIELDS))))
    data = ('\n'.join(lines) + '\n').encode('utf-8')
    if len(data) > MAX_BYTES:
        raise ValueError('receipt-limit')
    return data


def receipt_digest(record):
    return _hash(b'ONPC-KIOSK-VIEW' if record['kind'] == 'V' else b'ONPC-KIOSK-INVOCATION',
                 encode_receipt(record))


def check_derivation(source, invocation):
    """Check narrowing only; actual mounted-source checks remain native-owned."""
    validate_receipt(source)
    validate_receipt(invocation)
    if (source['kind'] != 'V' or invocation['kind'] != 'I' or
            source['backend'] != invocation['backend'] or source['material'] != invocation['material'] or
            invocation['source'] != receipt_digest(source) or len(source['nodes']) != len(invocation['nodes'])):
        raise ValueError('receipt-derivation')
    invariant = ('path', 'required', 'source_class', 'role', 'source_index', 'origin_device', 'origin_inode')
    for old, new in zip(source['nodes'], invocation['nodes']):
        if any(old[key] != new[key] for key in invariant):
            raise ValueError('receipt-derivation')
        if old['kind'] != new['kind']:
            allowed = ('empty-directory',) if old['kind'] == 'directory' else ('absent',) if old['kind'] in ('file', 'link') else ()
            if old['required'] or new['kind'] not in allowed:
                raise ValueError('receipt-derivation')
        elif old['kind'] not in ('tree', 'empty-directory', 'absent'):
            identity = () if old['kind'] == 'link' else ('device', 'inode')
            if any(old[key] != new[key] for key in (*identity, 'sha256', 'label', 'link', 'mountpoint')):
                raise ValueError('receipt-derivation')
            if old['source_class'] in ('native', 'runtime', 'payload', 'vendor') and any(
                    old[key] != new[key] for key in ('size', 'mode', 'uid', 'gid')):
                raise ValueError('receipt-derivation')
    wanted = [item for item in source['coverage'] if invocation['nodes'][item['owner']]['kind'] == 'directory']
    if len(wanted) != len(invocation['coverage']):
        raise ValueError('receipt-derivation')
    for old, new in zip(wanted, invocation['coverage']):
        if any(old[key] != new[key] for key in ('owner', 'path', 'origin_device', 'origin_inode', 'device', 'inode')):
            raise ValueError('receipt-derivation')
    return invocation
