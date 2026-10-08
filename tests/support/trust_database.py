"""Private LMDB writer for trust-reader concurrency regressions."""

import ctypes as c
from contextlib import contextmanager
from pathlib import Path
import select
import subprocess
import sys


class Value(c.Structure):
    _fields_ = [('size', c.c_size_t), ('data', c.c_void_p)]


def check(result):
    if result:
        raise RuntimeError(f'private LMDB writer failed: {result}')


@contextmanager
def writer_environment(directory):
    """Keep a private daemon-like environment alive until its caller finishes."""
    directory = Path(directory)
    directory.mkdir(exist_ok=True)
    try:
        lib = c.CDLL('liblmdb.so.0')
    except OSError:
        lib = c.CDLL('liblmdb.so.0.0.0')
    pointer, uint = c.c_void_p, c.c_uint
    signatures = {
        'mdb_env_create': [c.POINTER(pointer)],
        'mdb_env_set_maxdbs': [pointer, uint],
        'mdb_env_set_mapsize': [pointer, c.c_size_t],
        'mdb_env_open': [pointer, c.c_char_p, uint, uint],
        'mdb_txn_begin': [pointer, pointer, uint, c.POINTER(pointer)],
        'mdb_dbi_open': [pointer, c.c_char_p, uint, c.POINTER(uint)],
        'mdb_drop': [pointer, uint, c.c_int],
        'mdb_put': [pointer, uint, c.POINTER(Value), c.POINTER(Value), uint],
        'mdb_txn_commit': [pointer],
        'mdb_txn_abort': [pointer],
        'mdb_env_close': [pointer],
    }
    for name, arguments in signatures.items():
        function = getattr(lib, name)
        function.argtypes = arguments
        function.restype = None if name in ('mdb_txn_abort', 'mdb_env_close') else c.c_int

    env = pointer()
    try:
        check(lib.mdb_env_create(c.byref(env)))
        check(lib.mdb_env_set_maxdbs(env, 4))
        check(lib.mdb_env_set_mapsize(env, 16 * 1024 * 1024))
        # Match the daemon's WRITEMAP | NOSYNC | MAPASYNC flags.
        check(lib.mdb_env_open(env, str(directory).encode(), 0x80000 | 0x10000 | 0x100000, 0o600))
        yield lib, env
    finally:
        if env:
            lib.mdb_env_close(env)


@contextmanager
def live_database(directory):
    """Hold a writer in a bounded, waited child, separate from reader environments."""
    command = [sys.executable, '-c',
               'import sys; from tests.support.trust_database import writer_environment; '
               'exec("with writer_environment(sys.argv[1]):\\n '
               'print(\'ready\', flush=True); sys.stdin.read(1)")', str(directory)]
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=Path(__file__).resolve().parents[2])
    try:
        if not select.select([child.stdout], [], [], 15)[0] or child.stdout.readline() != b'ready\n':
            raise RuntimeError('private LMDB writer did not become ready')
        yield
    finally:
        try:
            _, error = child.communicate(b'\n', timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            raise
        if child.returncode:
            raise RuntimeError(f'private LMDB writer failed: {error.decode()}')


def replace_records(directory, records, repeats=1, *, database_name='trust.db', metadata=None,
                    after_refresh=None):
    """Commit empty/refilled generations, like fapolicyd's database rebuild."""
    pointer, uint = c.c_void_p, c.c_uint
    txn, dbi = pointer(), uint()
    with writer_environment(directory) as (lib, env):
        try:
            for _ in range(repeats):
                for rows in ([], records):
                    check(lib.mdb_txn_begin(env, None, 0, c.byref(txn)))
                    check(lib.mdb_dbi_open(txn, database_name.encode(), 0x40000 | 0x04, c.byref(dbi)))
                    check(lib.mdb_drop(txn, dbi, 0))
                    for path, source, size, digest in rows:
                        key_bytes = path.encode()
                        data_bytes = f'{source} {size} {digest}'.encode()
                        key = Value(len(key_bytes), c.cast(c.c_char_p(key_bytes), pointer))
                        data = Value(len(data_bytes), c.cast(c.c_char_p(data_bytes), pointer))
                        check(lib.mdb_put(txn, dbi, c.byref(key), c.byref(data), 0))
                    if metadata is not None:
                        meta_dbi = uint()
                        check(lib.mdb_dbi_open(txn, b'trust.meta', 0x40000, c.byref(meta_dbi)))
                        key = Value(7, c.cast(c.c_char_p(b'current'), pointer))
                        data = Value(len(metadata), c.cast(c.c_char_p(metadata), pointer))
                        check(lib.mdb_put(txn, meta_dbi, c.byref(key), c.byref(data), 0))
                    result = lib.mdb_txn_commit(txn)
                    txn = pointer()
                    check(result)
                if after_refresh is not None:
                    after_refresh()
        finally:
            if txn:
                lib.mdb_txn_abort(txn)
