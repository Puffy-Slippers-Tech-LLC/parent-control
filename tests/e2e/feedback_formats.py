"""Finite all-format composition and public inline/link readback; never Send."""
if __package__:
    from . import block_semantics as blocks
else:
    import block_semantics as blocks

INLINE = ('bold', 'italic', 'underline', 'strike')
LINK = 'https://example.com/feedback'
START = len(blocks.BODY) - len(blocks.LINES[-1])
END = START + 5
KINDS = (*INLINE, 'link', 'clear')
OPERATIONS = frozenset({
    *(f'formats-{kind}-{action}' for kind in KINDS
      for action in ('focus', 'home', 'selected', 'read')),
    'formats-before', 'formats-link-target', 'formats-link-save',
    *(f'formats-{state}-{action}' for state in ('kept', 'cleared')
      for action in ('close', 'wrong-entry', 'reopen')),
})


def expected(operation):
    linked = operation.startswith('linked-')
    operation = operation.replace('linked-', 'formats-', 1) if linked else operation
    clear = operation in ('formats-before', 'formats-clear-read', 'formats-cleared-reopen')
    kind = operation.removeprefix('formats-').removesuffix('-read')
    applied = () if clear else INLINE[:INLINE.index(kind) + 1] if kind in INLINE else INLINE
    return {'blocks': [] if clear or linked else blocks.projection(blocks.FORMATS),
            'inline': list(applied),
            'link': LINK if kind == 'link' or operation == 'formats-kept-reopen' else None,
            'normal_comparison': True, 'text_exact': True}


def read_links(root, require, *, details=False):
    """Read public Hyperlink URI and exact Text beneath the ID-resolved editor."""
    seen, links = set(), []

    def visit(node, depth):
        require(node is not None and depth <= 12 and node not in seen
                and len(seen) < 128, 'ui:formats-link-tree')
        seen.add(node)
        if node.get_role_name() == 'link':
            text = node.get_text_iface()
            link = node.get_hyperlink()
            require(text is not None and text.get_character_count() == END - START
                    and text.get_text(0, END - START) == blocks.BODY[START:END],
                    'ui:formats-link-text')
            require(link is not None and link.get_n_anchors() == 1 and link.is_valid(),
                    'ui:formats-link-interface')
            uri = link.get_uri(0)
            require(uri == LINK, 'ui:formats-link-uri')
            # WebKit's Hyperlink indices describe an embedded object in its
            # local container, not editor-global flattened character indices.
            # Associate by unique synthetic text; use only the public width.
            first, last = link.get_start_index(), link.get_end_index()
            require(type(first) is int and type(last) is int and first >= 0
                    and last - first == 1, 'ui:formats-link-extent')
            value = text.get_text(0, END - START)
            require(blocks.BODY.count(value) == 1 and blocks.BODY.index(value) == START,
                    'ui:formats-link-association')
            links.append({'uri': uri, 'text': text, 'start': START, 'end': END,
                          'width': last - first})
        count = node.get_child_count()
        require(type(count) is int and 0 <= count <= 32, 'ui:formats-link-tree')
        for index in range(count):
            visit(node.get_child_at_index(index), depth + 1)

    visit(root, 0)
    require(len(links) <= 1, 'ui:formats-link-duplicate')
    return links if details else links[0]['uri'] if links else None


def attribute_range(text, start, end, values, require):
    """Require a public run covering the whole declared uniform range."""
    attrs, first, last = text.get_attribute_run((start + end) // 2, True)
    require(type(attrs) is dict and type(first) is int and type(last) is int
            and 0 <= first <= start < end <= last <= text.get_character_count(),
            'ui:formats-inline-range')
    require(all(attrs.get(key) == value for key, value in values.items()),
            'ui:formats-inline-result')


def root_offset(offset, links, require):
    """Map a flattened boundary outside links using their observed widths."""
    require(not any(item['start'] < offset < item['end'] for item in links),
            'ui:formats-inline-overlap')
    return offset - sum(item['end'] - item['start'] - item['width']
                        for item in links if item['end'] <= offset)


def read(ui, require, operation):
    ui.read_synthetic_text('body-blocks')
    root = ui.text_recipient('feedback-editor-input')
    text = root.get_text_iface()
    result = blocks.read_blocks(root, require)
    wanted = expected(operation)
    links = read_links(root, require, details=True)
    link = links[0]['uri'] if links else None
    require(link == wanted['link'], 'ui:formats-result')
    normal = {'weight': '400', 'style': 'normal', 'underline': 'none', 'strikethrough': 'false'}
    styled = dict(normal)
    for kind, key, value in (('bold', 'weight', '700'), ('italic', 'style', 'italic'),
                             ('underline', 'underline', 'single'), ('strike', 'strikethrough', 'true')):
        if kind in wanted['inline']:
            styled[key] = value
    ranges = [(START, END, styled), (END, len(blocks.BODY), normal)]
    if not wanted['blocks']:
        ranges += [(start, end, normal) for start, end in blocks.RANGES.values()]
    for start, end, values in ranges:
        contained = [item for item in links if (start, end) == (item['start'], item['end'])]
        if contained:
            attribute_range(contained[0]['text'], 0, end - start, values, require)
        else:
            require(not any(start < item['end'] and end > item['start'] for item in links),
                    'ui:formats-inline-overlap')
            # Derive the root attribute coordinates from the complete public
            # link inventory and unique text association. Never apply the local
            # Hyperlink start index as an editor offset or assume a fixed delta.
            attribute_range(text, root_offset(start, links, require),
                            root_offset(end, links, require), values, require)
    require(result == wanted['blocks'] and link == wanted['link'], 'ui:formats-result')
    return wanted


def operate(ui, operation, require, error_type):
    require(operation in OPERATIONS, 'ui:formats-operation')
    original = operation
    operation = operation.replace('linked-', 'formats-', 1)
    if operation.endswith('-wrong-entry'):
        require(ui.absent_id('feedback-dialog', within='parent-window'), 'ui:formats-entry')
        try:
            read(ui, require, 'formats-kept-reopen')
        except error_type as error:
            require(str(error) == 'ui:text-entry', 'ui:formats-refusal')
        else:
            raise error_type('ui:formats-refusal-missing')
        return
    if operation.endswith('-reopen'):
        ui.activate_id('parent-feedback-button')
        ui.wait(lambda: ui.id_target('feedback-editor-input', sensitive=True), 'formats-editor')
    ui.read_synthetic_text('body-blocks')
    if operation.endswith('-close'):
        read(ui, require, original.replace('-close', '-reopen'))
        ui.activate_id('feedback-close')
        ui.wait(lambda: ui.absent_id('feedback-dialog', within='parent-window'), 'feedback-closed')
        ui.parent()
    elif operation == 'formats-link-target':
        # Quill offers the selected editor text as the initial link destination
        # and selects it for replacement. Prove both before ordinary typing.
        ui.read_synthetic_text('link-initial')
        target = ui.text_recipient('feedback-link-target', focused=True).get_text_iface()
        require(target is not None and ui.api.Text.get_n_selections(target) == 1,
                'ui:formats-link-selection')
        selection = ui.api.Text.get_selection(target, 0)
        require((selection.start_offset, selection.end_offset) == (0, END - START),
                'ui:formats-link-selection')
    elif operation == 'formats-link-save':
        ui.text_recipient('feedback-link-target', focused=True)
        ui.read_synthetic_text('link-target')
        ui.activate_id('feedback-link-save')
    elif operation.endswith('-focus'):
        ui.focus_text('feedback-editor-input')
    elif operation.endswith(('-home', '-selected')):
        text = ui.text_recipient('feedback-editor-input', focused=True).get_text_iface()
        if operation.endswith('-home'):
            require(ui.api.Text.get_caret_offset(text) == 0, 'ui:formats-caret')
        else:
            kind = operation.removeprefix('formats-').removesuffix('-selected')
            require(ui.api.Text.get_n_selections(text) == 1, 'ui:formats-selection')
            selection = ui.api.Text.get_selection(text, 0)
            expected_end = END
            if kind == 'clear':
                links = read_links(ui.text_recipient('feedback-editor-input'), require, details=True)
                expected_end = root_offset(len(blocks.BODY), links, require)
            require((selection.start_offset, selection.end_offset) ==
                    ((0, expected_end) if kind == 'clear' else (START, END)),
                    f'ui:formats-selection:{selection.start_offset}:{selection.end_offset}')
            ui.activate_id('feedback-format-' + kind)
    else:
        return read(ui, require, original)


def format_stages(kind):
    return (f'formats-{kind}-focus', f'formats-{kind}-home', f'formats-{kind}-selected',
            *(('formats-link-target', 'formats-link-save') if kind == 'link' else ()),
            f'formats-{kind}-read')


def all_formats(prefix=''):
    """Independent callers bind unique invocations to the same public operations."""
    stages = (*(f'block-{kind}-{action}' for kind in blocks.FORMATS
                for action in ('focus', 'home', 'selected', 'read')),
              *(stage for kind in (*INLINE, 'link') for stage in format_stages(kind)))
    return {prefix + stage: 'ui:' + stage for stage in stages}


STAGES = ('feedback-open', 'text-body-blocks-focus', 'text-body-blocks-selected',
          'text-body-blocks-read', 'formats-before',
          *(f'block-{kind}-{action}' for kind in blocks.FORMATS
            for action in ('focus', 'home', 'selected', 'read')),
          *(stage for kind in (*INLINE, 'link') for stage in format_stages(kind)),
          'formats-kept-close', 'formats-kept-wrong-entry', 'formats-kept-reopen',
          *format_stages('clear'),
          'formats-cleared-close', 'formats-cleared-wrong-entry', 'formats-cleared-reopen')

LINK_STAGES = (*STAGES[:4], 'linked-before',
               *(stage.replace('formats-', 'linked-', 1)
                 for kind in (*INLINE, 'link') for stage in format_stages(kind)),
               'linked-kept-close', 'linked-kept-wrong-entry', 'linked-kept-reopen')
OPERATIONS |= frozenset(stage for stage in LINK_STAGES if stage.startswith('linked-'))
