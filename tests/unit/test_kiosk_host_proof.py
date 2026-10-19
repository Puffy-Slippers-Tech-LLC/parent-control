"""Compiled native, source-local host proof witnesses using private descriptors.

These fixtures substitute the named /usr directory after independently pinning
the original. They prove the lookup dispatch without requiring a host mount or
claiming composed PAM/manager admission or real mount-attachment acceptance.
Compiler and probe children are bounded and synchronously reaped. All mutable
paths belong to pytest's launcher-provided disk scratch.
"""
from pathlib import Path
import hashlib
import subprocess

import pytest
from tools import test_storage


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def host_probe(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-host-proof')
    source = directory / 'proof.c'
    binary = directory / 'proof'
    source.write_text(r'''
#define _GNU_SOURCE
#include <sys/types.h>
#include <unistd.h>
#include <stdint.h>
#include <time.h>
static int fixture_clock(clockid_t, struct timespec *);
static ssize_t fixture_pread(int, void *, size_t, off_t);
static int fixture_hash(int, off_t, char[65], void *, uint64_t);
#define KIOSK_HOST_PROOF_OWNER getuid()
#define KIOSK_HOST_PROOF_GROUP getgid()
#define KIOSK_HOST_CLOCK_GETTIME fixture_clock
#define pread fixture_pread
#include "host-proof.h"
#undef pread
#include <dirent.h>
static uint64_t fake_time, expiry;
static int clock_failure, budget_mode, fake_hashes;
static const char *during_read, *expected_digest;
static int fixture_clock(clockid_t clock, struct timespec *value) {
    if (clock_failure) { errno = EIO; return -1; }
    if (!fake_time) return clock_gettime(clock, value);
    value->tv_sec = (time_t) (fake_time / 1000000ULL);
    value->tv_nsec = (long) ((fake_time % 1000000ULL) * 1000ULL); return 0;
}
static void require(int value, const char *stage) {
    if (!value) { fprintf(stderr, "host-proof:%s:%s\n", stage, strerror(errno)); exit(1); }
}
static unsigned descriptors(void) {
    DIR *directory = opendir("/proc/self/fd"); require(directory != NULL, "descriptor-count");
    struct dirent *entry; unsigned count = 0;
    while ((entry = readdir(directory))) if (strcmp(entry->d_name, ".") && strcmp(entry->d_name, "..")) count++;
    closedir(directory); return count;
}
static void put(const char *path, const char *bytes) {
    int fd = open(path, O_CREAT | O_TRUNC | O_WRONLY | O_CLOEXEC, 0644);
    require(fd >= 0 && write(fd, bytes, strlen(bytes)) == (ssize_t) strlen(bytes), "private-write");
    require(close(fd) == 0, "write-close");
}
static ssize_t fixture_pread(int fd, void *data, size_t size, off_t offset) {
    if (during_read) {
        const char *fault = during_read; during_read = NULL;
        if (!strcmp(fault, "replace-file")) {
            require(rename("usr/bin/tool", "usr/bin/old-tool") == 0, "hash-file-barrier"); put("usr/bin/tool", "original");
        } else if (!strcmp(fault, "replace-ancestor")) {
            require(rename("usr/bin", "usr/old-bin") == 0 && mkdir("usr/bin", 0755) == 0, "hash-ancestor-barrier");
            put("usr/bin/tool", "original"); require(symlink("../../bin", "usr/bin/retreat") == 0, "hash-alias-copy");
        } else if (!strcmp(fault, "expire-hash")) fake_time = expiry;
    }
    return pread(fd, data, size, offset);
}
static int fixture_hash(int fd, off_t size, char hex[65], void *library, uint64_t deadline) {
    if (budget_mode && size > 1000000) {
        /* Only bulk accounting is doubled. Sparse source size, inode/trust,
         * canonical closure and the real 512 MiB limit remain production code. */
        fake_hashes++; strcpy(hex, expected_digest); return kiosk_host_before(deadline);
    }
    return kiosk_host_sha256_library_until(fd, size, hex, library, deadline);
}
static void content(int fd, const char *bytes) {
    char data[64] = {0}; require(fd >= 0, "content-fd");
    require(pread(fd, data, sizeof(data), 0) == (ssize_t) strlen(bytes) && !memcmp(data, bytes, strlen(bytes)), "independent-bytes");
}
int main(int argc, char **argv) {
    require(argc == 4 && chdir(argv[2]) == 0, "arguments");
    const char *mode = argv[1]; unsigned baseline = descriptors();
    expected_digest = argv[3];
    int root = open(".", O_PATH | O_DIRECTORY | O_CLOEXEC);
    int usr = open("usr", O_PATH | O_DIRECTORY | O_CLOEXEC);
    struct kiosk_host_roots roots;
    require(kiosk_host_roots_from_fds(&roots, root, usr) == 0, "root-pins");
    close(root); close(usr);
    require((fcntl(roots.root, F_GETFD) & FD_CLOEXEC) && (fcntl(roots.usr, F_GETFD) & FD_CLOEXEC), "roots-cloexec");
    struct kiosk_host_spec specs[] = {
        {.path="/usr/bin/tool", .kind=S_IFREG, .sha256=argv[3], .mode=0644},
        {.path="/bin/tool", .kind=S_IFREG, .sha256=argv[3]},
        {.path="/lex/tool", .kind=S_IFREG},
        {.path="/usr/bin/retreat/tool", .kind=S_IFREG},
        {.path="/etc/required", .kind=S_IFREG},
        {.path="/mask", .kind=S_IFLNK, .link="/dev/null", .terminal_link=1},
        {.path="/", .kind=S_IFDIR},
    };
    unsigned count = 6;
    int initial_refusal = 0;
    if (!strcmp(mode, "wrong-root-label")) { count = 7; specs[6].label = "unexpected_t"; initial_refusal = 1; }
    if (!strcmp(mode, "root-sha-field")) { count = 7; specs[6].sha256 = argv[3]; initial_refusal = 1; }
    if (!strcmp(mode, "root-link-field")) { count = 7; specs[6].link = "/usr"; initial_refusal = 1; }
    if (!strcmp(mode, "invalid-hash-syntax")) { specs[0].sha256 = "invalid"; initial_refusal = 1; }
    if (!strcmp(mode, "invalid-label-syntax")) { specs[0].label = "unsafe label"; initial_refusal = 1; }
    if (!strcmp(mode, "clock-unavailable")) { clock_failure = 1; initial_refusal = 1; }
    if (!strcmp(mode, "deadline-before-capture")) { fake_time = 100; initial_refusal = 1; }
    if (!strcmp(mode, "aggregate-limit") || !strcmp(mode, "aggregate-exact")) {
        budget_mode = 1;
        off_t size = (off_t) KIOSK_HOST_FILE_BYTES - (!strcmp(mode, "aggregate-exact") ? 8 : 0);
        require(truncate("usr/bin/tool", size) == 0, "sparse-budget-input");
        struct stat sparse; require(stat("usr/bin/tool", &sparse) == 0 && sparse.st_size == size &&
            sparse.st_blocks * 512 < 1000000, "independent-sparse-size");
        initial_refusal = !strcmp(mode, "aggregate-limit");
    }
    if (!strcmp(mode, "wrong-hash")) { specs[0].sha256 = "0000000000000000000000000000000000000000000000000000000000000000"; initial_refusal = 1; }
    if (!strcmp(mode, "wrong-label")) { specs[0].label = "unexpected_t"; initial_refusal = 1; }
    if (!strcmp(mode, "wrong-kind")) { specs[0].kind = S_IFDIR; specs[0].sha256 = NULL; initial_refusal = 1; }
    if (!strcmp(mode, "wrong-mode")) { specs[0].mode = 0600; initial_refusal = 1; }
    if (!strcmp(mode, "wrong-link")) { specs[5].link = "/other"; initial_refusal = 1; }
    if (!strcmp(mode, "unbounded-mask-target")) { specs[5].terminal_link = 0; initial_refusal = 1; }
    if (!strcmp(mode, "noncanonical-spec")) { specs[0].path = "/usr/bin/../bin/tool"; initial_refusal = 1; }
    if (!strcmp(mode, "unsafe-dotdot")) {
        require(chmod("usr/unsafe", 0777) == 0 && unlink("lex") == 0 && symlink("usr/unsafe/../bin", "lex") == 0, "unsafe-alias"); initial_refusal = 1;
    }
    if (!strcmp(mode, "alias-cycle")) {
        require(unlink("lex") == 0 && symlink("lex", "lex") == 0, "cyclic-alias"); initial_refusal = 1;
    }
    if (!strcmp(mode, "privileged-file")) { require(chmod("usr/bin/tool", 04755) == 0, "setid"); specs[0].mode = 0; initial_refusal = 1; }
    if (!strcmp(mode, "hardlink")) { require(link("usr/bin/tool", "extra-link") == 0, "hardlink"); initial_refusal = 1; }
    struct kiosk_host_proof proof;
    int captured = !strcmp(mode, "deadline-before-capture") ?
        kiosk_host_proof_capture_until(&proof, &roots, specs, count, 99) :
        kiosk_host_proof_capture(&proof, &roots, specs, count);
    kiosk_host_roots_close(&roots);
    if (initial_refusal) {
        require(captured != 0 && proof.rows == NULL && !proof.sealed, "initial-refusal");
        if (budget_mode) require(fake_hashes == 1, "aggregate-stops-before-second-file");
        require(descriptors() == baseline, "initial-fd-balance"); puts("refused"); return 0;
    }
    require(captured == 0 && proof.sealed && proof.count == 10, "finite-closure-captured");
    if (budget_mode) require(proof.measured == KIOSK_HOST_FILE_BYTES && fake_hashes == 1, "exact-aggregate-limit");
    require(kiosk_host_proof_recheck(&proof, specs, count) == 0, "baseline-recheck");
    int refused = 0;
    if (!strcmp(mode, "replace-during-hash")) { during_read = "replace-file"; refused = 1;
    } else if (!strcmp(mode, "replace-ancestor-during-hash")) { during_read = "replace-ancestor"; refused = 1;
    } else if (!strcmp(mode, "deadline-during-hash")) { expiry = proof.deadline; during_read = "expire-hash"; refused = 1;
    } else if (!strcmp(mode, "deadline-before-recheck")) { fake_time = proof.deadline; refused = 1;
    } else if (!strncmp(mode, "private-view", 12)) {
        struct stat before, named;
        int original = openat(proof.roots.usr, "bin/tool", O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
        require(original >= 0 && fstat(original, &before) == 0, "independent-original-inode");
        require(rename("usr", "original-usr") == 0 && rename("private", "usr") == 0, "private-view-substitution");
        int private_file = openat(proof.roots.root, "usr/bin/tool", O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
        require(private_file >= 0 && fstat(private_file, &named) == 0 && named.st_ino != before.st_ino, "root-only-crosses-private-view");
        content(original, "original"); content(private_file, "original");
        if (!strcmp(mode, "private-view-original-drift")) {
            put("original-usr/bin/tool", "changed!"); refused = 1;
            content(private_file, "original"); content(original, "changed!");
        } else if (!strcmp(mode, "private-view-private-drift")) {
            put("usr/bin/tool", "private!"); content(original, "original");
        } else if (!strcmp(mode, "private-view-alias-drift")) {
            require(unlink("bin") == 0 && symlink("/usr/unsafe", "bin") == 0, "absolute-alias-replaced"); refused = 1;
        }
        close(original); close(private_file);
    } else if (!strcmp(mode, "ambient-siblings")) {
        put("usr/bin/unrelated", "ambient");
        require(mkdir("usr/unrelated-dir", 0755) == 0 && rename("usr/unsafe", "usr/renamed-ambient") == 0,
                "ambient-sibling-changes");
    } else if (!strcmp(mode, "same-bytes-replaced")) {
        require(rename("usr/bin/tool", "usr/bin/old-tool") == 0, "required-replaced"); put("usr/bin/tool", "original"); refused = 1;
    } else if (!strcmp(mode, "file-write-restored")) {
        struct stat saved; require(stat("usr/bin/tool", &saved) == 0, "file-before");
        put("usr/bin/tool", "changed!"); put("usr/bin/tool", "original");
        struct timespec times[] = {saved.st_atim, saved.st_mtim};
        require(utimensat(AT_FDCWD, "usr/bin/tool", times, 0) == 0, "restore-mtime"); refused = 1;
    } else if (!strcmp(mode, "directory-replaced")) {
        require(rename("usr/bin", "usr/old-bin") == 0 && mkdir("usr/bin", 0755) == 0, "ancestor-replaced");
        put("usr/bin/tool", "original"); require(symlink("../../bin", "usr/bin/retreat") == 0, "same-alias"); refused = 1;
    } else if (!strcmp(mode, "directory-mode")) { require(chmod("usr/bin", 0700) == 0, "directory-trust-changed"); refused = 1;
    } else if (!strcmp(mode, "required-unlinked")) { require(unlink("usr/bin/tool") == 0, "required-unlinked"); refused = 1;
    } else if (!strcmp(mode, "outside-usr-drift")) { put("etc/required", "changed!"); refused = 1;
    } else if (!strcmp(mode, "closure-truncated")) { count--; refused = 1;
    } else if (!strcmp(mode, "closure-changed")) { specs[0].sha256 = NULL; refused = 1;
    }
    require((kiosk_host_proof_recheck(&proof, specs, count) != 0) == refused, "final-source-local-proof");
    kiosk_host_proof_close(&proof);
    require(descriptors() == baseline, "final-fd-balance"); puts(refused ? "refused" : "verified"); return 0;
}
''')
    # Hash substitution exercises aggregate accounting with large sparse files;
    # the clock and read barriers leave all native path/stat/hash guards intact.
    header = (ROOT / 'tools/kiosk_host_proof.h').read_text()
    (directory / 'host-proof.h').write_text(header.replace(
        'kiosk_host_sha256_library_until(readable,', 'fixture_hash(readable,'))
    result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT),
                             str(source), '-ldl', '-o', str(binary)],
                            capture_output=True, text=True, timeout=30,
                            pass_fds=test_storage.scratch_descriptors())
    if result.returncode:
        pytest.fail(result.stderr, pytrace=False)
    return binary


@pytest.fixture
def host_tree(tmp_path):
    root = tmp_path / 'host'
    root.mkdir()
    # Keep the allocation root private; fixture trust is explicit and does not
    # inherit the developer's umask (mkdir parents otherwise use mode 0777).
    for relative in ('usr', 'usr/bin', 'usr/unsafe', 'private', 'private/bin', 'etc'):
        (root / relative).mkdir(exist_ok=True)
    for directory in (root, root / 'usr', root / 'usr/bin', root / 'usr/unsafe',
                      root / 'private', root / 'private/bin', root / 'etc'):
        directory.chmod(0o755)
    for relative in ('usr/bin/tool', 'private/bin/tool', 'etc/required'):
        (root / relative).write_bytes(b'original')
        (root / relative).chmod(0o644)
    (root / 'bin').symlink_to('/usr/bin')
    (root / 'lex').symlink_to('usr/bin/../../usr/bin')
    (root / 'usr/bin/retreat').symlink_to('../../bin')
    (root / 'mask').symlink_to('/dev/null')
    return root


@pytest.mark.parametrize('mode', [
    'unchanged', 'ambient-siblings', 'private-view', 'private-view-private-drift', 'aggregate-exact',
])
def test_native_host_proof_uses_original_usr_and_allows_siblings(host_probe, host_tree, mode):
    result = subprocess.run([str(host_probe), mode, str(host_tree), hashlib.sha256(b'original').hexdigest()],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'verified\n'


@pytest.mark.parametrize('mode', [
    'private-view-original-drift', 'private-view-alias-drift', 'outside-usr-drift',
    'same-bytes-replaced', 'file-write-restored', 'directory-replaced', 'directory-mode',
    'required-unlinked', 'closure-truncated', 'closure-changed',
    'wrong-hash', 'wrong-label', 'wrong-kind', 'wrong-mode', 'wrong-link',
    'unbounded-mask-target', 'noncanonical-spec', 'unsafe-dotdot', 'alias-cycle',
    'privileged-file', 'hardlink',
    'wrong-root-label', 'root-sha-field', 'root-link-field', 'invalid-hash-syntax', 'invalid-label-syntax',
    'clock-unavailable', 'deadline-before-capture', 'deadline-before-recheck', 'deadline-during-hash',
    'aggregate-limit', 'replace-during-hash', 'replace-ancestor-during-hash',
])
def test_native_host_proof_refuses_drift_or_unclosed_alias(host_probe, host_tree, mode):
    result = subprocess.run([str(host_probe), mode, str(host_tree), hashlib.sha256(b'original').hexdigest()],
                            capture_output=True, text=True, timeout=10,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'refused\n'
