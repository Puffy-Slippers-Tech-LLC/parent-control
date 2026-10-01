"""Immutable presentation messages, rendered in the owning surface's context.

Messages retain their source and operands until rendering. Late worker results
and already-open controls therefore use the current personal language. Ordinary
strings (user data, paths, protocol values and diagnostics) are never translated.
"""

class Message(str):
    def __new__(cls, source, values=None, *, plural=None, count=None, context=None):
        fallback = plural if plural is not None and count != 1 else source
        obj = super().__new__(cls, fallback % values if values is not None else fallback)
        obj.source, obj.values = source, values
        obj.plural, obj.count = plural, count
        obj.context = context
        return obj

    def __mod__(self, values):
        if not isinstance(values, dict):
            raise TypeError("presentation messages require named operands")
        return Message(self.source, values, plural=self.plural, count=self.count,
                       context=self.context)

    def render(self, translations):
        if self.context is not None:
            source = (translations.npgettext(self.context, self.source, self.plural, self.count)
                      if self.plural is not None else translations.pgettext(self.context, self.source))
        else:
            source = (translations.ngettext(self.source, self.plural, self.count)
                      if self.plural is not None else translations.gettext(self.source))
        if self.values is None:
            return source
        values = {key: render(value, translations) for key, value in self.values.items()}
        return source % values

    def __add__(self, other):
        return JoinedMessage((self, other))

    def __radd__(self, other):
        return JoinedMessage((other, self))


class JoinedMessage(str):
    """Independent paragraphs/units; never join translated sentence fragments."""

    def __new__(cls, parts):
        obj = super().__new__(cls, ''.join(map(str, parts)))
        obj.parts = parts
        return obj

    def render(self, translations):
        return ''.join(render(part, translations) for part in self.parts)

    def __add__(self, other):
        return JoinedMessage((*self.parts, other))


def gettext(source):
    """Extraction marker; defer lookup until a presentation destination exists."""
    return Message(source)


def ngettext(singular, plural, count):
    return Message(singular, plural=plural, count=count)


def pgettext(context, source):
    return Message(source, context=context)


def render(value, translations):
    return value.render(translations) if isinstance(value, (Message, JoinedMessage)) else value


def source_message(value):
    """Recover a reviewed validation message after an exception string boundary."""
    from . import messages
    return messages.BY_SOURCE.get(value, value)
