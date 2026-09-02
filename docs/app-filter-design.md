# Single authorization for time and app access

The child extension is an untrusted front end. It sends the selected approver
UID, duration, and conditional-app choice to the root broker through
`RequestOwnAccess`; it does not invoke Polkit or write AccountsService
properties. The broker derives the target UID from the live system-bus caller,
loads the canonical app policy, and validates the selected local administrator.

The broker then checks the dedicated
`tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access` Polkit action
for the child's unique system-bus subject. Because the broker is the trusted
mechanism, it can supply the validated target, approver, duration, and
app-relaxation details. The action uses `auth_admin`, has no implied
AccountsService permissions, and retains no authorization in the child
session.

After approval, the broker revalidates the caller, both accounts, and the
preference snapshot. It calculates the complete desired state, writes
`AppFilter` and `ActiveExtension` as one verified root-owned transaction, and
rolls back the prior state if any write or read-back fails. Only a verified
commit is reported as approved.

## App-filter semantics

The app filter remains a blocklist, represented as:

    AppFilter = (false, [blocked app targets])

When “Allow soft blocked apps” is checked, soft blocked targets are omitted
while hard blocked targets remain. When it is unchecked, both soft blocked and
hard blocked targets remain blocked. Other apps are allowed by the blocklist
automatically.

The request action is installed under `/usr/share/polkit-1/actions/`, and its
administrator-selection rule is installed under `/etc/polkit-1/rules.d/`.
