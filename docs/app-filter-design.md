# Single authorization for time and app access

The child extension is an untrusted front end. It sends the selected approver UID, duration, and conditional-app choice to the root broker through `RequestOwnAccess`; it does not invoke Polkit or write AccountsService properties. The broker derives the target UID from the live system-bus caller, loads the canonical app policy, and validates the selected local administrator.

The broker then checks the dedicated `tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access` Polkit action for the child's unique system-bus subject. Because the broker is the trusted mechanism, it can supply the validated target, approver, duration, and app-relaxation details. The action uses `auth_admin`, has no implied AccountsService permissions, and retains no authorization in the child session.

After approval, the broker revalidates the caller, both accounts, and the preference snapshot. It calculates the complete desired state, writes `AppFilter` and `ActiveExtension` as one verified root-owned transaction, and rolls back the prior state if any write or read-back fails. Only a verified commit is reported as approved.

## App-filter semantics

The app filter remains a blocklist, represented as:

    AppFilter = (false, [blocked app targets])

When “Allow soft blocked apps” is checked, soft blocked targets are omitted while hard blocked targets remain. When it is unchecked, both soft blocked and hard blocked targets remain blocked. Other apps are allowed by the blocklist automatically.

After an approved unchecked request, the broker first verifies that complete blocklist, then terminates matching native and Flatpak applications owned only by the approved child's UID, and writes `ActiveExtension` last. An approved checked request performs no process termination at all. Native PID signalling uses pidfds after verifying all reported process UIDs; Flatpak enumeration and instance-specific termination run with the approved child's identity and runtime directory, so an identical application owned by another account is out of scope.

Parent revocation always restores and verifies the complete hard-and-soft blocklist, terminates matching applications with the same selected-child UID isolation, and clears `ActiveExtension` last. If termination may have started and the revocation cannot finish, the broker retains the strict filter, restores the prior grant, and reports failure; it never attempts to affect another user's process.

The request action is installed under `/usr/share/polkit-1/actions/`, and its administrator-selection rule is installed under `/etc/polkit-1/rules.d/`.
