"""Controller-owned fixture secrets; never accept worker variables from a CLI.

os-autoinst filters these names on secret-filtered saves, but its initial vars
and backend captures remain private. No credential is put in argv/environment.
"""

import json
import os

from private_artifacts import EvidenceError, _directory, require


PASSWORD_VARIABLES = {
    'parent': '_SECRET_ONPC_PARENT_PASSWORD',
    'child': '_SECRET_ONPC_CHILD_PASSWORD',
    'other-parent': '_SECRET_ONPC_OTHER_PARENT_PASSWORD',
    'other-child': '_SECRET_ONPC_OTHER_CHILD_PASSWORD',
}


class SecretVariables:
    """Freeze a bounded mapping, registering every value before any capture.

    ASCII printable fixtures avoid keyboard layout/control-character ambiguity.
    Actual fixture acquisition and live prompt qualification belong to the
    trusted controller, not this storage helper. repr never contains values.
    """

    def __init__(self, passwords=None):
        passwords = {} if passwords is None else passwords
        require(type(passwords) is dict, 'secret:variables')
        require(all(type(role) is str and role in PASSWORD_VARIABLES
                    and type(value) is str and 1 <= len(value) <= 256
                    and all(32 <= ord(char) <= 126 for char in value)
                    for role, value in passwords.items()), 'secret:variables')
        self.__values = {PASSWORD_VARIABLES[role]: value for role, value in passwords.items()}

    def __repr__(self):
        return '<SecretVariables [redacted]>'

    @property
    def registered_secrets(self):
        return tuple(self.__values.values())

    def stage(self, directory, public_variables):
        """Exclusive 0600 write relative to a pinned 0700 directory descriptor.

        Refuse caller-supplied secret names even if empty or apparently safe.
        Partial writes are retained privately on failure, never retried/spawned.
        """
        require(type(public_variables) is dict and all(
            type(key) is str and not key.startswith('_SECRET_') and '_PASSWORD' not in key
            for key in public_variables), 'secret:variable-collision')
        data = json.dumps({**public_variables, **self.__values}, allow_nan=False).encode('utf-8')
        self._stage_file(directory, 'vars.json', data)

    def stage_password_files(self, directory):
        """Fixed role filenames for virt-customize's supported file selectors."""
        paths = {}
        for role, variable in PASSWORD_VARIABLES.items():
            require(variable in self.__values, 'secret:fixture-roles')
            name = role + '.password'
            self._stage_file(directory, name, self.__values[variable].encode('ascii'))
            paths[role] = directory / name
        return paths

    @staticmethod
    def _stage_file(directory, name, data):
        fd = _directory(directory)
        try:
            output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
            with os.fdopen(output, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(fd)
            current = _directory(directory)
            try:
                old, new = os.fstat(fd), os.fstat(current)
                require((old.st_dev, old.st_ino) == (new.st_dev, new.st_ino),
                        'secret:directory-replaced')
            finally:
                os.close(current)
        except OSError:
            raise EvidenceError('secret:stage-failed') from None
        finally:
            os.close(fd)
