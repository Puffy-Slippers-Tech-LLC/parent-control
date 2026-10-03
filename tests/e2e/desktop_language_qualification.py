"""300b finite DESK13 setting and preservation slice on the fresh admin envelope."""
from dataclasses import replace

from account_language import AccountLanguage, LOCALE, ROLE, compare_desktop_entry
from native_fixtures import fixture_actions
from private_artifacts import require
from product_free_entry import PLAN as ENTRY_PLAN, ProductFreeEntryJourney

PLAN = replace(ENTRY_PLAN, stage_actions={
    'wrong-entry': 'language-refuse', 'desktop': 'language-qualify'})


def journey(context, progress):
    chinese = fixture_actions(profile='chinese', include_refusal=False)

    def refuse(owner, guard):
        guard()
        owner.account_language = AccountLanguage(owner.transport, owner.context.verified)
        owner.language_entry = owner.account_language.refuse()
        guard()
        return {'wrong_entry_refused': True, 'unchanged_state': True}

    def qualify(owner, guard):
        guard()
        assets = chinese['native-verify'](owner, guard)
        controller = owner.account_language
        before = controller.read()
        compare_desktop_entry(owner.language_entry, before)
        provider = owner.ui.observe('parent-desktop-provider')['provider']
        require(provider['locale'] == 'en_US.UTF-8', 'account-language:observer-language')
        require(controller.command('reject-inputs') == {
            'wrong_account_refused': True, 'undeclared_locale_refused': True},
            'account-language:input-refusals')
        require(controller.read() == before, 'account-language:invalid-input-mutated-state')
        guard()
        controller.submit(ROLE, LOCALE, controller.identity)
        guard()
        result = controller.confirm(before)
        require(owner.ui.observe('parent-desktop-provider')['provider'] == provider,
                'account-language:observer-changed')
        guard()
        return {**result, 'chinese_assets_verified': assets['independent_readback'],
                'wrong_account_refused': True, 'undeclared_locale_refused': True}

    return ProductFreeEntryJourney(context, progress, PLAN,
        actions={'language-refuse': refuse, 'language-qualify': qualify})
