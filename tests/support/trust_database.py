"""Private LMDB writer for trust-reader concurrency regressions."""

import ctypes as c
from pathlib import Path


class Value(c.Structure):
    _fields_ = [('size', c.c_size_t), ('data', c.c_void_p)]


def replace_records(directory, records, repeats=1):
    """Commit empty/refilled generations, like fapolicyd's database rebuild."""
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

    def check(result):
        if result:
            raise RuntimeError(f'private LMDB writer failed: {result}')

    env, txn, dbi = pointer(), pointer(), uint()
    try:
        check(lib.mdb_env_create(c.byref(env)))
        check(lib.mdb_env_set_maxdbs(env, 2))
        check(lib.mdb_env_set_mapsize(env, 16 * 1024 * 1024))
        # Match the daemon's WRITEMAP | NOSYNC | MAPASYNC flags.
        check(lib.mdb_env_open(env, str(directory).encode(), 0x80000 | 0x10000 | 0x100000, 0o600))
        for _ in range(repeats):
            for rows in ([], records):
                check(lib.mdb_txn_begin(env, None, 0, c.byref(txn)))
                check(lib.mdb_dbi_open(txn, b'trust.db', 0x40000 | 0x04, c.byref(dbi)))
                check(lib.mdb_drop(txn, dbi, 0))
                for path, source, size, digest in rows:
                    key_bytes = path.encode()
                    data_bytes = f'{source} {size} {digest}'.encode()
                    key = Value(len(key_bytes), c.cast(c.c_char_p(key_bytes), pointer))
                    data = Value(len(data_bytes), c.cast(c.c_char_p(data_bytes), pointer))
                    check(lib.mdb_put(txn, dbi, c.byref(key), c.byref(data), 0))
                result = lib.mdb_txn_commit(txn)
                txn = pointer()
                check(result)
    finally:
        if txn:
            lib.mdb_txn_abort(txn)
        if env:
            lib.mdb_env_close(env)
