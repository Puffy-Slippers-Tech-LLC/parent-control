"""Finite block-format inputs and bounded public semantic/text association."""

FORMATS = ('heading-1', 'heading-2', 'ordered', 'bulleted', 'quote', 'code')
LINES = ('Heading sample', 'Subheading sample', 'Number sample', 'Bullet sample',
         'Quote sample', 'Code sample', 'Plain sample')
BODY = '\n'.join(LINES)
RANGES = {kind: (sum(len(line) + 1 for line in LINES[:i]),
                 sum(len(line) + 1 for line in LINES[:i]) + len(LINES[i]))
          for i, kind in enumerate(FORMATS)}
OPERATIONS = frozenset({
    *(f'block-{kind}-{action}' for kind in FORMATS
      for action in ('focus', 'home', 'selected', 'read')),
    'block-before', 'block-close', 'block-wrong-entry', 'block-reopen',
})


def projection(kinds):
    return [{'format': kind, 'start': RANGES[kind][0], 'end': RANGES[kind][1],
             'text': LINES[FORMATS.index(kind)]} for kind in kinds]


def expected(operation):
    if operation == 'block-before':
        return []
    if operation == 'block-reopen':
        return projection(FORMATS)
    kind = operation.removeprefix('block-').removesuffix('-read')
    return projection(FORMATS[:FORMATS.index(kind) + 1])


def document_runs(root, require):
    """Read bounded public document runs; offsets are Quill UTF-16 units."""
    value = root.document()
    require(type(value) is dict and set(value) == {'ops'}
            and type(value['ops']) is list and len(value['ops']) <= 20000,
            'ui:editor-document')
    result, offset = [], 0
    for operation in value['ops']:
        require(type(operation) is dict and set(operation) <= {'insert', 'attributes'}
                and type(operation.get('insert')) is str
                and type(operation.get('attributes', {})) is dict, 'ui:editor-document')
        text = operation['insert']
        end = offset + len(text.encode('utf-16-le')) // 2
        require(end <= 100000, 'ui:editor-document')
        result.append((offset, end, text, operation.get('attributes', {})))
        offset = end
    return result


def read_blocks(root, require):
    """Associate public paragraph formats with their exact synthetic line."""
    runs = document_runs(root, require)
    text = ''.join(run[2] for run in runs)
    # This helper is also used to prove that an ordinary/empty draft has no
    # block formatting. Distinct fixtures remain validated by their caller.
    found = []
    newline_positions = []
    offset = 0
    for first, last, part, attributes in runs:
        for character in part:
            if character == '\n':
                newline_positions.append((offset, attributes))
            offset += len(character.encode('utf-16-le')) // 2
    for position, attributes in newline_positions:
        kinds = []
        if attributes.get('header') in (1, 2):
            kinds.append('heading-' + str(attributes['header']))
        if attributes.get('list') in ('ordered', 'bullet'):
            kinds.append('ordered' if attributes['list'] == 'ordered' else 'bulleted')
        if attributes.get('blockquote'):
            kinds.append('quote')
        if attributes.get('code-block'):
            kinds.append('code')
        require(len(kinds) <= 1, 'ui:block-format')
        if not kinds:
            continue
        kind = kinds[0]
        require(text == BODY + '\n' and position == RANGES[kind][1],
                'ui:block-association')
        found.append(kind)
    require(len(found) == len(set(found)), 'ui:block-duplicate')
    return projection([kind for kind in FORMATS if kind in found])
