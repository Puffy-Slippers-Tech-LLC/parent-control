# Persistent and derived state

[System design overview](../System-Design.md)

Read this for data ownership, preference/configuration schemas, defaults,
and saved-data changes.

Implementation: [preferences.py](../../broker/oh_no_parent_control/preferences.py), [config.py](../../broker/oh_no_parent_control/config.py), [configuration example](../../config).

## Persistent and derived state

The single product preference source for child UID `N` is:

```text
/var/lib/oh-no-parent-control/preferences/N.json
```

The preference directory is root-only and each mode-`0600` record is validated
and atomically replaced. The current preference format is version 3 (`FORMAT_VERSION` in
`preferences.py`); its logical schema is:

```text
version
parent_control_enabled
daily_time_limit_minutes
apps[desktop-id] = {
    state, targets[], patterns[], user_saved_match_rule
}
request = {
    last_selected_duration, last_custom_minutes,
    allow_soft_blocked_apps, last_selected_approver_uid,
    kiosk_muted, child_muted
}
```

App states are `allowed`, `permanent` (hard blocked), and `conditional` (soft
blocked). Normalization omits an allowed entry unless it carries a saved match
rule that must survive later policy changes.

Machine configuration is separate at
`/etc/oh-no-parent-control/config.json`. It contains only its schema version,
the kiosk UID, and the minimum successful-request interval; it does not
duplicate child preferences.

The ownership of runtime state is deliberately split:

| State | Authority | Purpose |
| --- | --- | --- |
| Configured screen-time and app choices | Product preference record | Durable parent intent |
| `AppFilter` | AccountsService | Live launcher/Flatpak blocklist derived from preferences |
| `ActiveExtension` | AccountsService | Current one-time grant |
| Usage intervals and estimates | `malcontent-timerd` | Measured daily use |
| UID-scoped native deny rules | fapolicyd | Live execution policy derived from `AppFilter` and saved patterns |
| Extension payload | System GNOME data directory | Immutable package content discovered when Shell starts |
| Extension activation | Per-account GNOME settings | Derived enabled state for managed children |

No measured usage, grant expiry, or generated execution state is imported into
the preference record.

A missing child record loads validated defaults; a record is created on save.
Defaults disable screen-time control, set a zero daily limit, leave apps allowed,
and select a 30-minute request with soft apps blocked and both surfaces muted.
The current validator normalizes omitted optional request fields and an omitted
daily limit.

The machine configuration also currently uses version 3, independently of the
preference schema. Its example kiosk UID is not a fixed runtime identity;
installation generates the actual value.

## Related design

- For non-authoritative per-user selector state, read [Front ends](Frontends.md#request-selector-state).
- For projecting app preferences into live enforcement, read [filters and execution rules](Applications.md#live-filter-and-execution-rules).
- Before shipping incompatible readers or writers, follow [Data migration](Data-Migration.md#adding-a-preference-migration).
