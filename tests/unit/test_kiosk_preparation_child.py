"""Real native exec, descriptor isolation and exact-child deadline witnesses.

Pytest-private binaries/files and anonymous sockets only. No PAM, service,
namespace, installed helper or host path is changed. Each compiler/driver and
its atomically identified helper finish before scratch teardown.
"""
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools import test_storage

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def preparation_driver(tmp_path_factory):
    directory = tmp_path_factory.mktemp('kiosk-preparation-child')
    helper = directory / 'helper'
    source = directory / 'helper.c'
    source.write_text(r'''
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/mman.h>
#include <unistd.h>
#include "kiosk_preparation_channel.h"
struct report { uint64_t deadline, lock, lease; int isolated, explicit; };
int main(int argc, char **argv) {
    if (argc != 5 || strcmp(argv[1], "--native-channel") || strcmp(argv[3], "3")) return 90;
    struct stat locked, admitted;
    struct report r = {.deadline = strtoull(argv[4], NULL, 10), .isolated = 1, .explicit = 1};
    if (fstat(4, &locked) || fstat(5, &admitted)) return 91;
    r.lock = locked.st_ino; r.lease = admitted.st_ino;
    for (int fd = 0; fd < 3; fd++) {
        struct stat info;
        if (fstat(fd, &info) || !S_ISCHR(info.st_mode) || info.st_rdev != makedev(1, 3)) r.isolated = 0;
    }
    for (int fd = 3; fd <= 5; fd++) if (fcntl(fd, F_GETFD) != 0) r.explicit = 0;
    for (int fd = 6; fd < 1024; fd++) if (fcntl(fd, F_GETFD) >= 0) r.isolated = 0;
    if (send(3, &r, sizeof(r), MSG_NOSIGNAL) != sizeof(r)) return 92;
    char command;
    if (recv(3, &command, 1, 0) != 1) return 93;
    if (command == 'H') for (;;) pause();
    if (command == 'R') {
        unsigned char refusal[32] = {0}; memcpy(refusal, "ONPCERR1", 8);
        refusal[8] = !strcmp(argv[2], "manager") ? 1 : 2; refusal[9] = 1; refusal[11] = 9;
        kiosk_preparation_u64(refusal + 16, r.deadline);
        return send(3, refusal, sizeof(refusal), MSG_NOSIGNAL) == sizeof(refusal) ? 17 : 97;
    }
    if (command == 'P' || command == 'M') {
        int writer = memfd_create("account", MFD_CLOEXEC | MFD_ALLOW_SEALING);
        const char account[] = "ONPC-KIOSK-ACCOUNT\t1\t1000\t1000\t2\n1000\n1001\n";
        if (writer < 0 || write(writer, account, sizeof(account) - 1) != sizeof(account) - 1 ||
            fcntl(writer, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)) return 94;
        char name[64]; snprintf(name, sizeof(name), "/proc/self/fd/%d", writer);
        int fds[] = {open("/proc/self/fd/4", O_RDONLY | O_CLOEXEC),
                     open("/proc/self/fd/5", O_RDONLY | O_CLOEXEC),
                     open(name, O_RDONLY | O_CLOEXEC)};
        close(writer);
        unsigned char material[32] = {1}, view[32] = {0};
        struct kiosk_preparation_input measurement;
        if (kiosk_preparation_capture_phase(&measurement, 1, 1, 1, material, view, fds, 3, r.deadline) ||
            kiosk_preparation_send_phase(3, &measurement, fds, r.deadline)) return 94;
        struct kiosk_preparation_response selection; kiosk_preparation_response_init(&selection);
        if (kiosk_preparation_receive_phase(3, 2, 1, 1, material, view, r.deadline, &selection))
            return command == 'M' ? 0 : 95;
        int result[] = {fds[0], selection.fds[0]};
        struct kiosk_preparation_input intended;
        if (kiosk_preparation_capture_phase(&intended, 3, 1, 1, material, view, result, 2, r.deadline) ||
            kiosk_preparation_send_phase(3, &intended, result, r.deadline)) return 96;
        kiosk_preparation_response_close(&selection);
        close(fds[0]); close(fds[1]); close(fds[2]);
    }
    return strcmp(argv[2], "gate") == 0 ? 13 : 0;
}
''', encoding='utf-8')
    source.chmod(0o644)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-I', str(ROOT / 'tools'), str(source),
                    '-o', str(helper)], check=True, timeout=30, capture_output=True,
                   pass_fds=test_storage.scratch_descriptors())
    helper.chmod(0o755)
    driver_source = directory / 'driver.c'
    driver_source.write_text(
        '#define _GNU_SOURCE\n#define KIOSK_CONFINEMENT_PREPARE ' + json.dumps(str(helper)) + '\n' + r'''
#define KIOSK_PREPARATION_LOCK_OWNER getuid()
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include "kiosk_preparation_channel.h"
#include "kiosk_preparation_child.h"
struct report { uint64_t deadline, lock, lease; int isolated, explicit; };
static uint64_t now(void) {
    struct timespec t; if (clock_gettime(CLOCK_MONOTONIC, &t)) exit(89);
    return (uint64_t) t.tv_sec * 1000000000ULL + t.tv_nsec;
}
static int descriptors(void) {
    DIR *d = opendir("/proc/self/fd"); if (!d) return -1;
    int n = 0; while (readdir(d)) n++; closedir(d); return n;
}
int main(int argc, char **argv) {
    if (argc != 4) return 90;
    int lock = open(argv[1], O_RDWR | O_CLOEXEC), lease = open(argv[2], O_RDWR | O_CLOEXEC);
    if (lock < 0 || lease < 0) return 91;
    int stray = open(argv[1], O_RDONLY); if (stray < 0) return 92;
    int output = STDOUT_FILENO;
    if (!strcmp(argv[3], "closed-stdio")) {
        output = fcntl(STDOUT_FILENO, F_DUPFD_CLOEXEC, 100);
        if (output < 0) return 88;
        for (int fd = 0; fd < 3; fd++) close(fd);
        for (int fd = 0; fd < 3; fd++) if (open(argv[1], O_RDONLY) != fd) return 87;
    }
    int before = descriptors();
    struct kiosk_preparation_child child; kiosk_preparation_child_init(&child);
    uint64_t start = now(), deadline = start / 1000U + 2000000U;
    if (!strcmp(argv[3], "expired")) deadline = start / 1000U - 1;
    if (!strcmp(argv[3], "overflow")) deadline = UINT64_MAX;
    if (!strcmp(argv[3], "too-long")) deadline = start / 1000U + 61000000U;
    if (!strcmp(argv[3], "timeout")) deadline = start / 1000U + 250000U;
    const char *role = !strcmp(argv[3], "bad-exit") || !strcmp(argv[3], "refusal-gate") ? "gate" :
        !strcmp(argv[3], "bad-role") ? "outside" : "manager";
    if (!strcmp(argv[3], "same-lock")) { close(lease); lease = dup(lock); fcntl(lease, F_SETFD, FD_CLOEXEC); }
    if (!strcmp(argv[3], "writable-lock")) fchmod(lock, 0660);
    int launched = kiosk_preparation_launch(&child, role, lock, lease, deadline);
    if (launched) {
        if (child.started || child.pidfd >= 0 || child.channel >= 0 || descriptors() != before) return 93;
        printf("refused %d\n", errno); return 0;
    }
    if (kiosk_preparation_launch(&child, role, lock, lease, deadline) == 0) return 94;
    struct pollfd ready = {.fd = child.channel, .events = POLLIN};
    if (poll(&ready, 1, 1500) != 1) return 95;
    struct report report;
    if (recv(child.channel, &report, sizeof(report), MSG_DONTWAIT) != sizeof(report)) return 96;
    struct stat locked, admitted;
    if (fstat(lock, &locked) || fstat(lease, &admitted) || !report.isolated || !report.explicit ||
        report.lock != locked.st_ino || report.lease != admitted.st_ino || report.deadline != deadline * 1000U) return 97;
    int protocol = !strcmp(argv[3], "protocol") || !strcmp(argv[3], "protocol-material");
    int refusal = !strncmp(argv[3], "refusal-", 8);
    char command = refusal ? 'R' : !strcmp(argv[3], "timeout") ? 'H' : protocol ?
        (!strcmp(argv[3], "protocol-material") ? 'M' : 'P') : 'E';
    if (send(child.channel, &command, 1, MSG_NOSIGNAL) != 1) return 98;
    if (refusal) {
        struct kiosk_preparation_response response; kiosk_preparation_response_init(&response);
        if (kiosk_preparation_child_measurement(&child, child.role, &response) == 0 ||
            response.count || response.refusal != 9 || child.refusal != 9 || child.phase ||
            strcmp(kiosk_preparation_refusal_reason(child.refusal), "unexpected-preserved-executable") ||
            kiosk_preparation_child_measurement(&child, child.role, &response) == 0) return 107;
        kiosk_preparation_response_close(&response);
        if (kiosk_preparation_cancel_until(&child, now() + 2000000000ULL) ||
            !child.reaped || child.pidfd >= 0 || child.channel >= 0 || descriptors() != before) return 108;
        puts("refusal isolated no-leak"); close(stray); close(lock); close(lease); return 0;
    }
    if (protocol) {
        struct kiosk_preparation_response response; kiosk_preparation_response_init(&response);
        unsigned char material[32] = {1}, view[32] = {0};
        if (kiosk_preparation_child_result(&child, 1, 1, material, view, &response) == 0 ||
            kiosk_preparation_child_measurement(&child, 1, &response) || response.count != 3 ||
            child.account.uid != 1000 || child.account.gid != 1000 || child.account.count != 2 ||
            child.account.groups[0] != 1000 || child.account.groups[1] != 1001 ||
            kiosk_preparation_child_measurement(&child, 1, &response) == 0) return 102;
        kiosk_preparation_response_close(&response);
        char *directory = strdup(argv[1]); if (!directory) return 103;
        char *slash = strrchr(directory, '/'); if (!slash) return 103;
        *slash = 0;
        int target = open(directory, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
        free(directory);
        if (target < 0) return 103;
        if (command == 'M') material[0]++;
        int selected = kiosk_preparation_child_select(&child, 1, 1, material, view, &target, 1);
        close(target);
        if (command == 'M') {
            if (selected == 0 || child.phase != 0 ||
                kiosk_preparation_child_select(&child, 1, 1, material, view, &target, 1) == 0) return 104;
            if (kiosk_preparation_cancel_until(&child, now() + 2000000000ULL) ||
                child.pidfd >= 0 || child.channel >= 0 || descriptors() != before) return 105;
            puts("poisoned no-leak"); close(stray); close(lock); close(lease); return 0;
        }
        if (selected || kiosk_preparation_child_result(&child, 1, 1, material, view, &response) ||
            response.count != 2 || child.phase != 4 ||
            kiosk_preparation_child_result(&child, 1, 1, material, view, &response) == 0) return 106;
        kiosk_preparation_response_close(&response);
    }
    int finished = kiosk_preparation_finish(&child), retained = child.pidfd >= 0;
    if (!strcmp(argv[3], "timeout") && (finished == 0 || now() < deadline * 1000U)) return 99;
    if (kiosk_preparation_cancel_until(&child, now() + 2000000000ULL) ||
        !child.reaped || child.pidfd >= 0 || child.channel >= 0 || descriptors() != before ||
        fstat(lock, &locked) || fstat(lease, &admitted)) return 100;
    if (kiosk_preparation_finish(&child) == 0) return 101;
    dprintf(output, "finished %d retained %d isolated %d elapsed %llu\n", finished, retained,
        report.isolated, (unsigned long long) ((now() - start) / 1000000U));
    close(stray); close(lock); close(lease); return 0;
}
''', encoding='utf-8')
    driver = directory / 'driver'
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-function', '-I', str(ROOT / 'tools'),
                    str(driver_source), '-o', str(driver)], check=True, timeout=30,
                   capture_output=True, pass_fds=test_storage.scratch_descriptors())
    driver.chmod(0o755)
    return driver


@pytest.mark.parametrize('mode', ['healthy', 'closed-stdio', 'protocol', 'protocol-material',
                                'bad-exit', 'timeout', 'expired', 'overflow', 'too-long',
                                'bad-role', 'same-lock', 'writable-lock', 'refusal-manager', 'refusal-gate'])
def test_native_helper_owns_one_child_and_no_other_setup_descriptors(preparation_driver, tmp_path, mode):
    paths = [tmp_path / 'lock', tmp_path / 'lease']
    for path in paths:
        path.write_bytes(b'private-owned-lock')
        path.chmod(0o600)
    original = [path.stat().st_ino for path in paths]
    result = subprocess.run([str(preparation_driver), *(str(path) for path in paths), mode],
                            timeout=6, capture_output=True, text=True,
                            pass_fds=test_storage.scratch_descriptors())
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    if mode.startswith('refusal-'):
        assert result.stdout == 'refusal isolated no-leak\n'
    elif mode == 'protocol-material':
        assert result.stdout == 'poisoned no-leak\n'
    elif mode in ('healthy', 'closed-stdio', 'protocol', 'bad-exit', 'timeout'):
        assert result.stdout.startswith('finished ' + ('0' if mode in ('healthy', 'closed-stdio', 'protocol') else '-1'))
        assert 'isolated 1' in result.stdout
        if mode == 'timeout':
            assert 'retained 1' in result.stdout
            assert int(result.stdout.rsplit(' ', 1)[-1]) < 1500
    else:
        assert result.stdout.startswith('refused ')
    assert [path.stat().st_ino for path in paths] == original
    assert all(path.read_bytes() == b'private-owned-lock' for path in paths)
