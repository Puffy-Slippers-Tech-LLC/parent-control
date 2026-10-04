"""DESK13 single-use account binding, transport and independent confirmation."""
import copy
import json
from pathlib import Path

from private_artifacts import require
from watch_activity import operation
from account_language_guest import LOCALE, ROLE
from session_control import ACCOUNTS, local_graphical


def compare_desktop_entry(before, after):
    """Preserve languages across login, accounting for its departed greeter.

    GNOME 50 removes its temporary NSS gdm-greeter account at sign-in. Only
    that exact account, bound to the independently read old graphical greeter
    session, may disappear. Mutation confirmation still compares all accounts
    and sessions exactly against the fresh desktop snapshot.
    """
    expected = copy.deepcopy(before)
    for identity, session in before['sessions'].items():
        uid = session['User']
        if (local_graphical(session) and session['Class'] == 'greeter'
                and identity not in after['sessions'] and uid != before['target_uid']
                and before['accounts'].get(uid, {}).get('name') == 'gdm-greeter'
                and uid not in after['accounts']
                and not any(item['User'] == uid for item in after['sessions'].values())):
            del expected['accounts'][uid]
    require({key: value for key, value in expected.items() if key != 'sessions'} ==
            {key: value for key, value in after.items() if key != 'sessions'},
            'account-language:entry-preservation')


def guest_source():
    session = Path(__file__).with_name('session_control.py').read_text()
    return ('import sys, types\nsession_control = types.ModuleType("session_control")\n'
            'sys.modules["session_control"] = session_control\n'
            f'exec({session!r}, session_control.__dict__)\n').encode() + (
                Path(__file__).with_name('account_language_guest.py').read_bytes())


class AccountLanguage:
    def __init__(self, transport, verified, *, product_free=True):
        require(type(product_free) is bool, 'account-language:product-binding')
        self.product_free = product_free
        self.transport, self.verified = transport, verified
        self.identity = copy.deepcopy(transport.config)
        self.attempted = False
        self.failed = False

    def command(self, action):
        require(self.transport.config == self.identity, 'account-language:wrong-attempt')
        self.transport.guard(self.identity)
        self.verified.recheck()
        raw = self.transport.call(['/usr/bin/python3', '-I', '-', action, ROLE, LOCALE],
                                  input=guest_source(), timeout=90)
        self.transport.guard(self.identity)
        self.verified.recheck()
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'account-language:response-bound')
        result = json.loads(raw)
        require(type(result) is dict and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                'account-language:response-schema')
        return result

    def read(self):
        with operation('Reading system account languages and preservation witnesses'):
            value = self.command('read' if self.product_free else 'read-installed')
        require(set(value) == {'accounts', 'sessions', 'system_locale', 'observer_locale',
                              'product_free', 'target_uid'}
                and value['product_free'] is self.product_free and type(value['accounts']) is dict
                and 0 < len(value['accounts']) <= 128 and value['target_uid'] in value['accounts']
                and all(type(uid) is str and uid.isdecimal() and type(item) is dict
                        and set(item) == {'name', 'language'}
                        and type(item['name']) is str and len(item['name']) <= 128
                        and type(item['language']) is str and len(item['language']) <= 128
                        for uid, item in value['accounts'].items())
                and value['accounts'][value['target_uid']]['name'] == ACCOUNTS[ROLE]
                and type(value['sessions']) is dict and len(value['sessions']) <= 32
                and type(value['system_locale']) is list
                and type(value['observer_locale']) is dict, 'account-language:read-schema')
        return value

    def refuse(self):
        require(not self.attempted and not self.failed, 'account-language:replay')
        before = self.read()
        with operation('Refusing child desktop-language input at the greeter'):
            require(self.command('refuse') == {'wrong_entry_refused': True},
                    'account-language:wrong-refusal')
        require(self.read() == before, 'account-language:refusal-mutated-state')
        return before

    def submit(self, role, language, identity):
        require(role == ROLE, 'account-language:target-binding')
        require(language == LOCALE, 'account-language:locale-binding')
        require(identity == self.identity, 'account-language:wrong-attempt')
        require(not self.attempted and not self.failed, 'account-language:replay')
        self.attempted = self.failed = True
        with operation('Setting the declared child desktop language through AccountsService'):
            require(self.command('set') == {'accepted': True}, 'account-language:submission')
        self.failed = False

    def confirm(self, before):
        require(self.attempted and not self.failed, 'account-language:unconfirmed-submission')
        self.failed = True
        first, second = self.read(), self.read()
        require(first == second, 'account-language:independent-readback')
        language = first['accounts'][first['target_uid']]['language']
        # Ubuntu AccountsService's language-validate strips the encoding suffix.
        # Accept only these two representations of the one declared binding;
        # report the actual API value, never infer confirmation from submission.
        require(language in (LOCALE, 'zh_CN'), 'account-language:confirmed-language')
        expected = copy.deepcopy(before)
        expected['accounts'][expected['target_uid']]['language'] = language
        require(first == expected, 'account-language:preservation-or-setting')
        self.failed = False
        return {'confirmed_language': language, 'requested_locale': LOCALE,
                'session_renewal_required': True,
                'independent_readback': True, 'other_accounts_unchanged': True,
                'observer_and_system_locale_unchanged': True, 'session_unchanged': True,
                'product_free': self.product_free}
