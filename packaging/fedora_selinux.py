"""Use the Fedora SELinux module store without racing other policy writers."""

from contextlib import contextmanager
from ctypes import CDLL, POINTER, byref, c_char_p, c_int, c_size_t, c_uint16, c_void_p, string_at
from pathlib import Path


SEMANAGE_CONFIG = Path('/etc/selinux/semanage.conf')
STORE_ROOT = b'/var/lib/selinux'


def bind(library, signatures):
    for name, (result, *arguments) in signatures.items():
        function = getattr(library, name)
        function.restype = result
        function.argtypes = arguments
    return library


def check(result, operation):
    if result < 0:
        raise OSError(f'SELinux policy {operation} failed')


def uses_standard_module_store():
    try:
        contents = SEMANAGE_CONFIG.read_bytes()
    except FileNotFoundError:
        return True  # libsemanage supplies its built-in default.
    # Honor the configured connection as well as the root. An alternate root
    # can share the final policy files even if no live reload is requested.
    defaults = {b'store-root': STORE_ROOT, b'module-store': b'direct'}
    seen = set()
    for line in contents.split(b'\n'):
        setting, separator, value = line.partition(b'=')
        # The native scanner accepts a comment and newline between a key and
        # its '='. Refuse split or ambiguous selectors while ignoring tokens
        # in comments and values belonging to other directives.
        declaration = setting.partition(b'#')[0]
        if not any(key in declaration for key in defaults):
            continue
        key = setting.strip(b' \t')
        if key not in defaults or key in seen or not separator:
            return False
        default = defaults[key]
        # In the native scanner, trailing blanks after a quoted argument
        # make the unquoted token match longer and keep the literal quotes.
        if value.strip(b' \t') != default and value.lstrip(b' \t') != b'"' + default + b'"':
            return False
        seen.add(key)
    return True


def configured_store():
    if not uses_standard_module_store():
        return None
    lib = bind(CDLL('libselinux.so.1'), {'selinux_getpolicytype': (c_int, POINTER(c_void_p))})
    libc = bind(CDLL(None), {'free': (None, c_void_p)})
    value = c_void_p()
    check(lib.selinux_getpolicytype(byref(value)), 'type lookup')
    try:
        return string_at(value).decode('ascii')
    finally:
        libc.free(value)


def semanage():
    ptr, out = c_void_p, POINTER(c_void_p)
    return bind(CDLL('libsemanage.so.2'), {
        'semanage_handle_create': (ptr,),
        'semanage_handle_destroy': (None, ptr),
        'semanage_select_store': (None, ptr, c_char_p, c_int),
        'semanage_set_store_root': (None, ptr, c_char_p),
        'semanage_connect': (c_int, ptr),
        'semanage_disconnect': (c_int, ptr),
        'semanage_begin_transaction': (c_int, ptr),
        'semanage_commit': (c_int, ptr),
        'semanage_set_rebuild': (None, ptr, c_int),
        'semanage_set_reload': (None, ptr, c_int),
        'semanage_set_default_priority': (c_int, ptr, c_uint16),
        'semanage_module_list_all': (c_int, ptr, out, POINTER(c_int)),
        'semanage_module_list_nth': (ptr, ptr, c_int),
        'semanage_module_info_get_name': (c_int, ptr, ptr, out),
        'semanage_module_info_get_priority': (c_int, ptr, ptr, POINTER(c_uint16)),
        'semanage_module_info_get_lang_ext': (c_int, ptr, ptr, out),
        'semanage_module_info_get_enabled': (c_int, ptr, ptr, POINTER(c_int)),
        'semanage_module_info_destroy': (c_int, ptr, ptr),
        'semanage_module_key_create': (c_int, ptr, out),
        'semanage_module_key_set_name': (c_int, ptr, ptr, c_char_p),
        'semanage_module_key_set_priority': (c_int, ptr, ptr, c_uint16),
        'semanage_module_key_destroy': (c_int, ptr, ptr),
        'semanage_module_compute_checksum': (c_int, ptr, ptr, c_int, out, POINTER(c_size_t)),
        'semanage_module_install': (c_int, ptr, c_char_p, c_size_t, c_char_p, c_char_p),
        'semanage_module_remove': (c_int, ptr, c_char_p),
    })


class ModuleStore:
    def __init__(self, lib, handle, name, priority):
        self.lib = lib
        self.libc = bind(CDLL(None), {'free': (None, c_void_p)})
        self.handle = handle
        self.name = name
        self.priority = priority

    def checksum(self):
        lib, handle = self.lib, self.handle
        key, checksum, length = c_void_p(), c_void_p(), c_size_t()
        check(lib.semanage_module_key_create(handle, byref(key)), 'module key creation')
        try:
            check(lib.semanage_module_key_set_name(handle, key, self.name), 'module key name')
            check(lib.semanage_module_key_set_priority(handle, key, self.priority), 'module key priority')
            check(lib.semanage_module_compute_checksum(handle, key, 1, byref(checksum), byref(length)),
                  'module checksum')
            # Read the native C string. Some libsemanage versions include
            # the terminator in the reported checksum length.
            return string_at(checksum).decode('ascii')
        finally:
            self.libc.free(checksum)
            lib.semanage_module_key_destroy(handle, key)
            self.libc.free(key)

    def inventory(self):
        lib, handle = self.lib, self.handle
        modules, count = c_void_p(), c_int()
        check(lib.semanage_module_list_all(handle, byref(modules), byref(count)), 'module inventory')
        found = False
        conflict = False
        try:
            for index in range(count.value):
                info = lib.semanage_module_list_nth(modules, index)
                name, language, priority, enabled = c_void_p(), c_void_p(), c_uint16(), c_int()
                check(lib.semanage_module_info_get_name(handle, info, byref(name)), 'module name')
                if string_at(name) != self.name:
                    continue
                check(lib.semanage_module_info_get_priority(handle, info, byref(priority)), 'module priority')
                if priority.value != self.priority:
                    conflict = True
                    continue
                check(lib.semanage_module_info_get_lang_ext(handle, info, byref(language)), 'module language')
                if found or string_at(language) != b'cil':
                    raise ValueError('unrecognized SSH SELinux policy at the package priority')
                check(lib.semanage_module_info_get_enabled(handle, info, byref(enabled)), 'module status')
                found = True
                conflict |= not enabled.value
            return self.checksum() if found else None, conflict
        finally:
            for index in range(count.value):
                info = lib.semanage_module_list_nth(modules, index)
                lib.semanage_module_info_destroy(handle, info)
            self.libc.free(modules)

    def install(self, data):
        check(self.lib.semanage_module_install(self.handle, data, len(data), self.name, b'cil'), 'module install')

    def remove(self):
        check(self.lib.semanage_module_remove(self.handle, self.name), 'module removal')

    def commit(self):
        # The store may already have been published by an interrupted writer,
        # before the previous commit reached the active kernel policy.
        self.lib.semanage_set_rebuild(self.handle, 1)
        check(self.lib.semanage_commit(self.handle), 'commit')


@contextmanager
def module_store(store, name, priority, *, writable, reload):
    if not uses_standard_module_store():
        raise ValueError('SSH SELinux policy requires the default module store root and direct connection')
    lib = semanage()
    handle = lib.semanage_handle_create()
    if not handle:
        raise OSError('cannot create a SELinux policy handle')
    try:
        lib.semanage_select_store(handle, store.encode('ascii'), 1)  # SEMANAGE_CON_DIRECT
        lib.semanage_set_store_root(handle, STORE_ROOT)
        check(lib.semanage_connect(handle), f'{store} store connection')
        try:
            if writable:
                check(lib.semanage_begin_transaction(handle), 'transaction lock')
                check(lib.semanage_set_default_priority(handle, priority), 'set package priority')
                lib.semanage_set_reload(handle, int(reload))
            yield ModuleStore(lib, handle, name.encode('ascii'), priority)
        finally:
            lib.semanage_disconnect(handle)
    finally:
        lib.semanage_handle_destroy(handle)
