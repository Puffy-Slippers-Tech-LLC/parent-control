"""Associate saved wildcard choices with uniquely matching replacement launchers.

Pure matching shared by the Parent view and broker commit path. The caller
supplies one account's validated preferences and complete current catalogue.
"""

import fnmatch
import posixpath
from collections import Counter


def replacement_policy_ids(policies, applications):
    """Map a new desktop ID to one disappeared ID, without merging choices.

    Distinct current choices win; equivalent duplicate choices can consolidate.
    Missing/ambiguous matches and precise rules stay under their original IDs.
    A basename glob never crosses a directory.
    """
    catalogue = {app['id']: app for app in applications}
    candidates = {}
    for saved_id, policy in policies.items():
        if saved_id in catalogue or not policy.get('patterns'):
            continue
        matches = []
        for app_id, app in catalogue.items():
            current = policies.get(app_id)
            if current is not None and not _equivalent_choice(policy, current, app):
                continue
            if any(
                    target.startswith('/')
                    and posixpath.dirname(target) == posixpath.dirname(pattern)
                    and fnmatch.fnmatchcase(posixpath.basename(target), posixpath.basename(pattern))
                    for target in app['targets'] for pattern in policy['patterns']):
                matches.append(app_id)
        if len(matches) == 1:
            candidates[saved_id] = matches[0]
    counts = Counter(candidates.values())
    return {app_id: saved_id for saved_id, app_id in candidates.items() if counts[app_id] == 1}


def _equivalent_choice(previous, current, app):
    if (previous.get('state') != current.get('state') or
            previous.get('user_saved_match_rule', False) != current.get('user_saved_match_rule', False)):
        return False
    patterns = current.get('patterns', [])
    if not patterns and not current.get('user_saved_match_rule', False):
        # A default saved against the shared AppImageLauncher had no version
        # pattern. Once the payload is discovered, Parent uses its suggestion.
        patterns = app.get('suggested_patterns', [])
    return bool(patterns) and previous.get('patterns') == patterns
