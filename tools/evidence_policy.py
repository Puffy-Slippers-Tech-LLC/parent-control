"""Pure proportional policy over existing, authenticated reference results.

The caller supplies the independently trusted owning consumer contract and owns
retaining bindings. This module neither reads evidence nor grants acceptance.
"""
from dataclasses import asdict, dataclass, fields, replace
from enum import Enum
import errno
import hashlib
import re

if __package__:
    from . import evidence_identity as identity
else:
    import evidence_identity as identity


class Condition(str, Enum):
    PROTECTED = 'protected'
    DENIED = 'denied'
    INTEGRITY = 'integrity'
    IDENTITY = 'identity'
    CONFLICT = 'conflict'
    PENDING = 'pending'
    BUSY = 'busy'
    STALE = 'stale'
    CAPACITY = 'capacity'
    MISSING = 'missing'
    FRAGMENT = 'fragment'


class Severity(str, Enum):
    BLOCK = 'block'
    ADVISORY = 'advisory'


# This order prevents presentation/unavailability from hiding authority failures.
_PRECEDENCE = tuple(Condition)
RECOVERY_ACTIONS = {
    Condition.PROTECTED: 'resume_owned_reconciliation',
    Condition.DENIED: 'restore_authorized_access_without_authentication_retry',
    Condition.INTEGRITY: 'preserve_evidence_and_inspect_exact_publication',
    Condition.IDENTITY: 'select_exact_declared_proof',
    Condition.CONFLICT: 'reconcile_with_owning_contract',
    Condition.PENDING: 'resume_owned_publication_recovery',
    Condition.BUSY: 'wait_for_recorded_owner',
    Condition.STALE: 'refresh_exact_selection',
    Condition.CAPACITY: 'use_owned_retention_recovery',
    Condition.MISSING: 'renew_affected_acceptance_evidence',
    Condition.FRAGMENT: 'repair_declared_document_anchor',
}


class DeclarationError(ValueError):
    """A declaration cannot be justified by its trusted owning contract."""


@dataclass(frozen=True)
class ReferenceBinding:
    consumer_id: str
    reference_sha256: str
    claim_sha256: str
    consumer_sha256: str
    contract_sha256: str
    role: str
    active: bool

    def payload(self):
        return asdict(self)

    @classmethod
    def from_payload(cls, value):
        if not isinstance(value, dict) or set(value) != {item.name for item in fields(cls)}:
            raise DeclarationError('reference policy: invalid retained binding')
        for key in ('consumer_id', 'reference_sha256', 'claim_sha256', 'consumer_sha256', 'contract_sha256'):
            identity._hex(value[key])
        identity._choice(value['role'], {'required_evidence', 'required_instruction', 'optional_presentation',
                                        'historical_information', 'example', 'operational_path'})
        if type(value['active']) is not bool:
            raise DeclarationError('reference policy: invalid retained relevance')
        return cls(**value)


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    condition: Condition
    document: str
    line: int
    expected: str | None
    actual: str | None
    recovery: str

    def payload(self):
        return dict(severity=self.severity.value, condition=self.condition.value,
                    document=self.document, line=self.line, expected=self.expected,
                    actual=self.actual, recovery=self.recovery)


@dataclass(frozen=True)
class Decision:
    diagnostic: Diagnostic | None
    binding: ReferenceBinding | None

    @property
    def blocked(self):
        return self.diagnostic is not None and self.diagnostic.severity == Severity.BLOCK

    @property
    def advisory(self):
        return self.diagnostic is not None and self.diagnostic.severity == Severity.ADVISORY


def bind_reference(reference, claim, consumer, contract, *, active):
    """Bind exact source bytes and complete declaration to a trusted contract.

    ``claim`` is the literal containing claim with its destination excluded.
    Capture a prior binding before mutation, never to bless a newly broken link.
    Contract trust comes from the caller's independent owner, not this function.
    """
    try:
        identity.validate_consumer(consumer)
        identity.validate_consumer(contract)
    except (ValueError, TypeError, KeyError) as error:
        raise DeclarationError('reference policy: invalid owning declaration') from error
    if consumer != contract:
        raise DeclarationError('reference policy: conflicting owning declaration')
    if (not isinstance(reference, str) or not reference or len(reference) > 8 * 1024 * 1024
            or not isinstance(claim, bytes) or len(claim) > 8 * 1024 * 1024
            or type(active) is not bool):
        raise DeclarationError('reference policy: invalid reference binding')
    try:
        reference_bytes = reference.encode('utf-8')
    except UnicodeError as error:
        raise DeclarationError('reference policy: invalid reference binding') from error
    return ReferenceBinding(consumer['consumer_id'], hashlib.sha256(reference_bytes).hexdigest(),
                            hashlib.sha256(claim).hexdigest(),
                            identity.digest(consumer), identity.digest(contract),
                            consumer['role'], active)


def _opaque(value):
    if value is None:
        return None
    if isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value):
        return value
    try:
        return identity.digest(value)
    except (ValueError, TypeError):
        return None


def assess_reference(conditions, *, document, line, reference, claim, consumer,
                     contract, active, retained=None, expected=None, actual=None):
    """Return one bounded refusal/advisory; availability never means a pass.

    An empty condition set means the existing verifier found no defect. The
    returned binding is state for the owning caller, not verification evidence.
    """
    if isinstance(conditions, (Condition, str)):
        conditions = (conditions,)
    failures = {Condition(item) for item in conditions}
    try:
        binding = bind_reference(reference, claim, consumer, contract, active=active)
    except DeclarationError:
        binding = None
        failures.add(Condition.CONFLICT)
    if retained is not None and not isinstance(retained, ReferenceBinding):
        failures.add(Condition.CONFLICT)
    elif binding is not None and retained is not None and retained.role != binding.role:
        failures.add(Condition.CONFLICT)
    if not failures:
        return Decision(None, binding)
    condition = next(item for item in _PRECEDENCE if item in failures)
    severity = Severity.BLOCK
    if binding is not None:
        if (condition == Condition.MISSING and not active
                and binding.role == 'historical_information'
                and isinstance(retained, ReferenceBinding)
                and replace(retained, active=binding.active) == binding):
            severity = Severity.ADVISORY
        elif (condition in (Condition.MISSING, Condition.FRAGMENT)
              and binding.role == 'optional_presentation'
              and all(ref['kind'] == 'document' for ref in consumer['references'])):
            severity = Severity.ADVISORY
    # Never put exception strings, source claims or unbounded identifiers in output.
    if (not isinstance(document, str) or len(document) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in document)):
        document = '<document>'
    if type(line) is not int or line < 1 or line > 2 ** 31 - 1:
        line = 1
    diagnostic = Diagnostic(severity, condition, document, line, _opaque(expected),
                            _opaque(actual), RECOVERY_ACTIONS[condition])
    return Decision(diagnostic, binding)


def condition_for_exception(error):
    """Classify typed resolver/OS failures without inspecting their prose.

    Existing generic ValueError refusals remain strict integrity failures. Owners
    that know a pending transaction or stale selection supply that condition.
    """
    if __package__:
        from . import test_retention as retention
    else:
        import test_retention as retention
    if isinstance(error, retention.OwnerBusy):
        return Condition.BUSY
    if isinstance(error, retention.PublicationPending):
        return Condition.PENDING
    if isinstance(error, retention.CapacityExceeded):
        return Condition.CAPACITY
    if isinstance(error, PermissionError):
        return Condition.DENIED
    if isinstance(error, identity.EvidenceContextError):
        return Condition.IDENTITY
    if isinstance(error, (identity.EvidenceIntegrityError, identity.MalformedEvidence)):
        return Condition.INTEGRITY
    if isinstance(error, FileNotFoundError):
        return Condition.MISSING
    if isinstance(error, BlockingIOError):
        return Condition.BUSY
    if isinstance(error, OSError):
        if error.errno in (errno.EACCES, errno.EPERM):
            return Condition.DENIED
        if error.errno in (errno.EBUSY, errno.EAGAIN):
            return Condition.BUSY
        if error.errno in (errno.ENOSPC, errno.EDQUOT):
            return Condition.CAPACITY
    return Condition.INTEGRITY
