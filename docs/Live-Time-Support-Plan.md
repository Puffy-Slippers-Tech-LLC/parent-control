# Retired live-time support proposal

Status: retired; no implementation or native package work is scheduled here.

The [optional-extension goal](SystemDesign/Optional-Child-Extension.md#destination-and-release-boundaries)
removes core dependencies on the extension while retaining it for desktop
reminders, the in-session overlay and the precise countdown. Those convenience
features may keep reading `Main.timeLimitsManager`; an external equivalent is
not a prerequisite for core independence.

The earlier native-support and independent-reader proposals are unnecessary for
that goal. Their retirement grants no source, installed timing or enforcement
acceptance. Native recording and Malcontent storage remain authoritative; no
upstream changes, package replacement or second activity ledger is proposed.
Current reader behavior belongs to [Screen time](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement).
Remaining core enforcement qualification belongs to the
[expiry plan](Broker-Expiry-Plan.md) and optional-extension design.
