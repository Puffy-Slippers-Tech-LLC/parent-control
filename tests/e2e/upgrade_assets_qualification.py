"""300c's finite transfer/readback qualification, sharing product-free entry."""
from dataclasses import replace

from account_language import AccountLanguage, compare_desktop_entry
from asset_transfer import AssetTransfer
from private_artifacts import EvidenceError, require
from product_free_entry import PLAN as ENTRY_PLAN, ProductFreeEntryJourney, refuse_command
from watch_activity import operation

PLAN = replace(ENTRY_PLAN, stage_actions={
    'wrong-entry': 'upgrade-entry-refuse', 'desktop': 'upgrade-readback'})


def expected_refusal(action, code):
    try:
        action()
    except EvidenceError as error:
        require(str(error) == code, 'upgrade-assets:unexpected-refusal')
    else:
        require(False, 'upgrade-assets:missing-refusal')


def provisioning_refusals(verified, lease, guestfs, transfer):
    """No upload on a wrong attempt, consumed refusal, collision or replay."""
    with operation('Checking upgrade asset attempt, collision and replay refusal'):
        wrong = AssetTransfer(verified)
        expected_refusal(lambda: wrong.provision(None, guestfs), 'transfer:outside-provisioning')
        expected_refusal(lambda: wrong.provision(lease, guestfs), 'transfer:already-attempted')
        collision = AssetTransfer(verified)
        expected_refusal(lambda: collision.provision(lease, guestfs), 'transfer:destination-exists')
        expected_refusal(lambda: collision.provision(lease, guestfs), 'transfer:already-attempted')
        expected_refusal(lambda: transfer.provision(lease, guestfs), 'transfer:already-attempted')
    return {'wrong_attempt_refused': True, 'collision_refused': True, 'replay_refused': True}


def journey(context, progress):
    def entry(owner, guard):
        guard()
        refuse_command(owner, guard)
        owner.upgrade_preservation = AccountLanguage(owner.transport, owner.context.verified)
        first = owner.upgrade_preservation.read()
        require(owner.upgrade_preservation.read() == first, 'upgrade-assets:unstable-entry')
        owner.upgrade_entry = first
        guard()
        return {'wrong_entry_refused': True, 'product_free': True}

    def readback(owner, guard):
        with operation('Independently reading both upgrade packages and preserved guest state'):
            guard()
            transfer = owner.context.asset_transfer
            # A fresh transfer controller must refuse now that the guest runs.
            wrong = AssetTransfer(owner.context.verified)
            expected_refusal(lambda: wrong.provision(owner.context.lease, None),
                             'transfer:outside-provisioning')
            expected_refusal(lambda: wrong.provision(owner.context.lease, None),
                             'transfer:already-attempted')
            first, second = transfer.observe(owner.vm), transfer.observe(owner.vm)
            require(first == second and set(first['packages']) == {'current', 'previous'},
                    'upgrade-assets:independent-readback')
            before = owner.upgrade_preservation.read()
            compare_desktop_entry(owner.upgrade_entry, before)
            provider = owner.ui.observe('parent-desktop-provider')['provider']
            after = owner.upgrade_preservation.read()
            require(before == after, 'upgrade-assets:state-changed')
            require(owner.ui.observe('parent-desktop-provider')['provider'] == provider,
                    'upgrade-assets:observer-changed')
            guard()
            return {'packages': first['packages'], 'independent_readback': True,
                    'outside_provisioning_refused': True, 'accounts_and_locales_unchanged': True,
                    'desktop_session_unchanged': True, 'product_free': True}

    return ProductFreeEntryJourney(context, progress, PLAN, actions={
        'upgrade-entry-refuse': entry, 'upgrade-readback': readback})
