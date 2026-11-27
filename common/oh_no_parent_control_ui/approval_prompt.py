"""Shared localized PolicyKit request content for the broker and previews."""

import gettext

from . import messages as m


def format_requested_duration(duration_seconds: int, translations=None) -> str:
    """Render validated request seconds using the child's private context."""
    if translations is None:
        translations = gettext.NullTranslations()
    if duration_seconds == 0:
        return m.REST_OF_DAY.render(translations)
    hours, remainder = divmod(duration_seconds, 60 * 60)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    for value, message in ((hours, m.hour_count), (minutes, m.minute_count),
                           (seconds, m.second_count)):
        if value:
            parts.append(message(value).render(translations))
    return m.DURATION_LIST_SEPARATOR.render(translations).join(parts)


def format_approval_message(duration_seconds, allow_soft_blocked_apps, translations, *, deferred=False):
    template = (m.POLKIT_GRANT_SOFT_APPS if allow_soft_blocked_apps
                else m.POLKIT_GRANT)
    mode = m.POLKIT_APPROVE_LATER if deferred else m.POLKIT_APPROVE_NOW
    # Polkit expands details once, after translation. Account labels stay in
    # their own detail so literal $(...) in user data is never reinterpreted.
    request = (template % {
        'target': '$(target-account)',
        'duration': format_requested_duration(duration_seconds, translations),
    }).render(translations)
    return f"{request}\n\n{mode.render(translations)}"
