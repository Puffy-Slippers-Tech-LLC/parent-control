"""Opt-in fixed fault for the guarded runner's single allowed qualification case.

Uses pytest's public call wrapper so an assertion/skip exception propagates
unchanged; only a successfully completed real call receives the injected fault.
"""

import pytest

CASE = 'test_authorization.py::test_method_role_matrix[ListManagedUsers-parent1]'
FAILURE = 'harness:qualification-failure'


def pytest_addoption(parser):
    parser.addoption('--onpc-qualification-failure', action='store_true', default=False)


def pytest_collection_finish(session):
    if session.config.getoption('--onpc-qualification-failure'):
        if [item.nodeid for item in session.items] != [CASE]:
            pytest.exit('qualification:requires-allowlisted-case', returncode=4)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    result = yield
    if item.config.getoption('--onpc-qualification-failure') and item.nodeid == CASE:
        pytest.fail(FAILURE, pytrace=False)
    return result
