"""Availability debt cannot weaken exact claims, ownership or required proof."""
import copy
import errno
import stat

import pytest

import evidence_identity as identity
import evidence_policy as policy


def consumer(role='historical_information', *, evidence=False):
    repository = dict(root='/checkout', device=1, inode=2, uid=1000)
    owner = dict(repository_sha256=identity.digest(repository),
                 caller=dict(uid=1000, gid=1000), journal='/checkout/journal',
                 identity=dict(device=1, inode=3, mode=stat.S_IFDIR | 0o700,
                               uid=1000, gid=1000))
    context = dict(repository=repository, workflow='docs/Plan.md', owner=owner,
                   run='1' * 32, task='E10', check='check_exact', attempt='2' * 32,
                   target='ubuntu', inputs_sha256='3' * 64, sources_sha256='4' * 64)
    reference = (dict(kind='evidence', record_id='5' * 64, member_id='6' * 64,
                      closure_sha256='7' * 64) if evidence else
                 dict(kind='document', destination='../Proof.md', fragment='proof'))
    return dict(schema='onpc-evidence-consumer', version=1, consumer_id='8' * 64,
                owner=owner, revision_sha256='9' * 64, role=role,
                expected_context=context if evidence else None,
                references=[reference], state='accepted')


def arguments(value=None, **changes):
    value = consumer() if value is None else value
    result = dict(document='docs/History.md', line=17, reference='../Proof.md#proof',
                  claim=b'[Ubuntu passed](../Proof.md#proof)\n', consumer=value,
                  contract=copy.deepcopy(value), active=False)
    result.update(changes)
    return result


def binding(args):
    return policy.bind_reference(args['reference'], args['claim'], args['consumer'],
                                 args['contract'], active=args['active'])


def test_historical_loss_is_nonpassing_and_requires_unchanged_retained_binding():
    args = arguments()
    before = binding(args)
    decision = policy.assess_reference(policy.Condition.MISSING, retained=before, **args)
    assert decision.advisory and not decision.blocked
    assert decision.binding == before
    assert decision.diagnostic.condition == policy.Condition.MISSING
    assert policy.assess_reference(policy.Condition.MISSING, **args).blocked
    assert policy.assess_reference(policy.Condition.MISSING, retained=before,
                                   **dict(args, active=True)).blocked
    # It remains an availability diagnostic; no pass/completion field is emitted.
    assert set(decision.diagnostic.payload()) == {
        'severity', 'condition', 'document', 'line', 'expected', 'actual', 'recovery'}


@pytest.mark.parametrize('change', ['claim', 'reference', 'revision', 'context', 'role'])
def test_changed_claim_or_declaration_cannot_inherit_debt(change):
    args = arguments(consumer(evidence=True))
    before = binding(args)
    if change == 'claim':
        args['claim'] = b'[Both targets passed](../Proof.md#proof)\n'
    elif change == 'reference':
        args['reference'] = '../archive/../Proof.md#proof'
    else:
        args['consumer'] = copy.deepcopy(args['consumer'])
        if change == 'revision':
            args['consumer']['revision_sha256'] = 'a' * 64
        elif change == 'context':
            args['consumer']['expected_context']['target'] = 'fedora'
        else:
            args['consumer']['role'] = 'optional_presentation'
        args['contract'] = copy.deepcopy(args['consumer'])
    assert policy.assess_reference(policy.Condition.MISSING, retained=before, **args).blocked


@pytest.mark.parametrize('condition', list(policy.Condition))
def test_refusals_take_precedence_over_historical_availability(condition):
    args = arguments()
    decision = policy.assess_reference([policy.Condition.MISSING, condition],
                                       retained=binding(args), **args)
    if condition == policy.Condition.MISSING or condition == policy.Condition.FRAGMENT:
        assert decision.advisory
    else:
        assert decision.blocked
        assert decision.diagnostic.condition == condition


@pytest.mark.parametrize('role', ['required_instruction', 'required_evidence',
                                  'historical_information', 'optional_presentation'])
@pytest.mark.parametrize('unavailable', [policy.Condition.MISSING, policy.Condition.FRAGMENT])
def test_only_declared_optional_document_fragment_is_advisory(role, unavailable):
    args = arguments(consumer(role, evidence=role == 'required_evidence'))
    decision = policy.assess_reference(unavailable, **args)
    assert decision.advisory == (role == 'optional_presentation')
    if role == 'optional_presentation':
        assert policy.assess_reference(unavailable,
                                       **arguments(consumer(role, evidence=True))).blocked
        for condition in (policy.Condition.INTEGRITY, policy.Condition.IDENTITY,
                          policy.Condition.PROTECTED):
            assert policy.assess_reference([unavailable, condition], **args).blocked


def test_absent_conflicting_and_downgraded_declarations_block():
    args = arguments(consumer('required_instruction'))
    for contract in (None, {}, consumer('optional_presentation')):
        decision = policy.assess_reference(policy.Condition.FRAGMENT,
                                           **dict(args, contract=contract))
        assert decision.blocked
        assert decision.diagnostic.condition == policy.Condition.CONFLICT
    before = binding(args)
    downgraded = arguments(consumer('optional_presentation'))
    decision = policy.assess_reference(policy.Condition.FRAGMENT, retained=before, **downgraded)
    assert decision.blocked and decision.diagnostic.condition == policy.Condition.CONFLICT


def test_complete_reference_can_exceed_parser_destination_limit():
    # The caller passes the complete Markdown occurrence, not just its destination.
    reference = '[proof](' + 'x' * 8192 + ')'
    args = arguments(reference=reference, claim=b'[proof]()\n')
    decision = policy.assess_reference([], **args)
    assert not decision.blocked and decision.binding is not None


@pytest.mark.parametrize('error,condition', [
    (FileNotFoundError('secret missing'), policy.Condition.MISSING),
    (PermissionError('secret denied'), policy.Condition.DENIED),
    (BlockingIOError('secret busy'), policy.Condition.BUSY),
    (OSError(errno.ENOSPC, 'secret capacity'), policy.Condition.CAPACITY),
    (identity.EvidenceContextError('secret identity'), policy.Condition.IDENTITY),
    (identity.EvidenceIntegrityError('secret digest'), policy.Condition.INTEGRITY),
    (ValueError('secret expired'), policy.Condition.INTEGRITY),
])
def test_typed_diagnostics_are_bounded_without_exception_or_claim_prose(error, condition):
    assert policy.condition_for_exception(error) == condition
    decision = policy.assess_reference(condition, expected={'task': 'secret expected'},
                                       actual='secret actual', **arguments())
    payload = decision.diagnostic.payload()
    assert 'secret' not in str(payload) and 'Ubuntu' not in str(payload)
    assert payload['document'] == 'docs/History.md' and payload['line'] == 17
    assert len(payload['expected']) == len(payload['actual']) == 64
    assert payload['recovery']


def test_success_binding_is_detached_from_mutable_contract():
    args = arguments()
    decision = policy.assess_reference([], **args)
    assert not decision.blocked and not decision.advisory and decision.diagnostic is None
    before = decision.binding
    args['contract']['revision_sha256'] = 'a' * 64
    assert decision.binding == before
    assert policy.assess_reference([], **args).blocked


def test_binding_roundtrip_and_owner_refusals_keep_machine_readable_classes():
    import test_retention as retention
    saved = binding(arguments())
    assert policy.ReferenceBinding.from_payload(saved.payload()) == saved
    for error, condition in ((retention.OwnerBusy('private'), policy.Condition.BUSY),
                             (retention.PublicationPending('private'), policy.Condition.PENDING),
                             (retention.CapacityExceeded('private'), policy.Condition.CAPACITY)):
        assert policy.condition_for_exception(error) == condition
