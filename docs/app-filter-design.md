
• Recommended design: no daemon. Use one custom polkit “meta-action” that implies both existing Malcontent actions, then make the two existing D-
  Bus calls non-interactively.

  This is the cleanest option because the extension process is already running as the restricted child user and is already the correct polkit
  subject for both operations. Adding a daemon introduces the problem of RequestExtension caller identity:
  org.freedesktop.MalcontentTimer1.Child.RequestExtension identifies the request by the system-bus sender. A separate privileged daemon would
  either need to run as that child user or use a different parent/admin API.

  ## Recommended flow

  GNOME Shell extension
     │
     │ 1. CheckAuthorization(custom meta-action, interactive)
     ▼
  One parent authentication prompt
     │ authorization for meta-action is granted
     │ because it implies the two real actions
     ▼
  Extension performs, without interactive auth:
     - org.freedesktop.MalcontentTimer1.Child.RequestExtension
     - com.endlessm.ParentalControls.AppFilter.AppFilter set

  ## Polkit action

  Add one system policy file for the extension:

  <action id="org.gnome.shell.extensions.request-more-time.ApproveTimeAndApps">
    <description>Extend screen time and update app restrictions</description>
    <message>Authentication is required to extend screen time and update app restrictions.</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.imply">
      org.freedesktop.Malcontent.SessionLimits.Extend
      com.endlessm.ParentalControls.AppFilter.ChangeOwn
    </annotate>
  </action>

  Use auth_admin, not auth_admin_keep, because the existing SessionLimits.Extend action deliberately does not use _keep to prevent trivial
  repeated extension requests.

  ## Extension implementation

  Before requesting anything:

  1. Acquire the custom action once using PolkitPermission, Gio.DBus CheckAuthorization, or Polkit.Authority.
  2. Allow interactive authentication only for that single check.

  After that authorization succeeds:

  - Call RequestExtension with Gio.DBusCallFlags.NONE, not ALLOW_INTERACTIVE_AUTHORIZATION.
  - Write AppFilter with Properties.Set using Gio.DBusCallFlags.NONE.

  Both backend checks will be authorized by implication from the meta-action, assuming they happen while the temporary authorization is valid.

  The app filter write should still be:

  AppFilter = (false, [blocked app targets])

  because the requested semantics are blocklist semantics:

  - checkbox checked → []
  - checkbox unchecked → configured app targets

  Other apps remain allowed automatically.

  ## Why this meets your goals

  - One prompt: only the custom meta-action prompts. The two backend actions are implied.
  - Official/current APIs: public D-Bus interfaces and the documented polkit org.freedesktop.policykit.imply mechanism.
  - Reliable: the time grant still uses the official MalcontentTimer1.Child.RequestExtension flow. App filtering uses the official
    AccountsService vendor extension.

  - Not overly complicated: no new daemon, no direct manipulation of ActiveExtension, and no need to call private GNOME Shell APIs for
    authorization.

  The existing polkitAgentChooser.js should be updated to intercept the new custom action instead of only
  org.freedesktop.Malcontent.SessionLimits.Extend, so the single prompt uses the custom administrator chooser.

  One packaging note: the polkit action file is a system-level policy file, so it must be installed under /usr/share/polkit-1/actions/ rather
  than being bundled only as a user extension. That is the only system-level addition needed.