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


def read_blocks(root, require):
    """Read only the already ID/owner-validated editor; never select by role.

    Exact distinct line text binds every object to one declared range. Reject
    duplicate semantic objects, incomplete trees and containers spanning normal
    comparison text. Containers need not themselves implement Text.
    """
    count = 0

    def visit(node, depth):
        nonlocal count
        count += 1
        require(node is not None and depth <= 12 and count <= 128, 'ui:block-tree')
        attrs = node.get_attributes()
        role = node.get_role_name()
        require(type(attrs) is dict and type(role) is str, 'ui:block-tree')
        iface = node.get_text_iface()
        length = iface.get_character_count() if iface is not None else 0
        require(type(length) is int and 0 <= length <= len(BODY) + 8, 'ui:block-text')
        value = iface.get_text(0, length) if iface is not None else None
        require(value is None or (type(value) is str and len(value) <= len(BODY) + 8),
                'ui:block-text')
        size = node.get_child_count()
        require(type(size) is int and 0 <= size <= 32, 'ui:block-tree')
        children = [visit(node.get_child_at_index(i), depth + 1) for i in range(size)]
        kind = None
        if role == 'heading':
            require(attrs.get('level') in ('1', '2'), 'ui:block-level')
            kind = 'heading-' + attrs['level']
        elif role == 'list item':
            descriptions = {'numbered list item': 'ordered', 'bulleted list item': 'bulleted'}
            require(attrs.get('roledescription') in descriptions, 'ui:block-list-kind')
            kind = descriptions[attrs['roledescription']]
        elif attrs.get('xml-roles') in ('blockquote', 'code'):
            kind = {'blockquote': 'quote', 'code': 'code'}[attrs['xml-roles']]
        texts = ([value.rstrip('\n')] if value is not None else
                 [text for child in children for text in child[0]])
        found = [item for child in children for item in child[1]]
        if kind:
            target = LINES[FORMATS.index(kind)]
            # Public list Text includes its marker on some WebKit versions;
            # the text-bearing child must still provide the exact line.
            descendants = [text for child in children for text in child[2]]
            require(target in texts or target in descendants, 'ui:block-association')
            require(not any(line in text for text in texts + descendants
                            for line in LINES if line != target), 'ui:block-association')
            found.append(kind)
        return texts, found, texts + [text for child in children for text in child[2]]

    _, found, _ = visit(root, 0)
    require(len(found) == len(set(found)), 'ui:block-duplicate')
    return projection([kind for kind in FORMATS if kind in found])
