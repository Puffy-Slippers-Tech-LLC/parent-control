/* Native observations for one retained-manager admission. Include after the
 * confinement failure and namespace types. This owner never signals a manager,
 * refreshes a selected identity, runs a process, or authorizes a receipt. */
#ifndef ONPC_KIOSK_MANAGER_ADMISSION_H
#define ONPC_KIOSK_MANAGER_ADMISSION_H
#include <stdint.h>
#include <inttypes.h>
#include <poll.h>
#include <sys/syscall.h>
#include <sys/statfs.h>
#include <dlfcn.h>

#define KIOSK_MANAGER_TASKS 256U
#define KIOSK_MANAGER_GROUPS 128U
#define KIOSK_MANAGER_MARKER "share/oh-no-parent-control/confinement/retained-view"

/* Opaque ABI types avoid requiring systemd development headers or a new link
 * dependency. All calls below use the public sd-bus API. */
struct sd_bus;
struct sd_bus_message;
struct kiosk_manager_bus {
    void *library;
    struct sd_bus *bus;
    int (*new_bus)(struct sd_bus **);
    int (*set_address)(struct sd_bus *, const char *);
    int (*set_client)(struct sd_bus *, int);
    int (*start)(struct sd_bus *);
    int (*get_fd)(struct sd_bus *);
    struct sd_bus *(*unref)(struct sd_bus *);
    int (*new_call)(struct sd_bus *, struct sd_bus_message **, const char *, const char *, const char *, const char *);
    int (*append)(struct sd_bus_message *, const char *, ...);
    int (*call)(struct sd_bus *, struct sd_bus_message *, uint64_t, void *, struct sd_bus_message **);
    int (*enter)(struct sd_bus_message *, char, const char *);
    int (*exit)(struct sd_bus_message *);
    int (*read)(struct sd_bus_message *, const char *, ...);
    int (*array)(struct sd_bus_message *, char, const void **, size_t *);
    int (*at_end)(struct sd_bus_message *, int);
    struct sd_bus_message *(*message_unref)(struct sd_bus_message *);
};
struct kiosk_manager_unit {
    uint32_t pid;
    unsigned char invocation[16];
    char cgroup[PATH_MAX];
};
struct kiosk_manager_task {
    int fd;
    pid_t tid;
    unsigned long long start;
    struct stat proc;
};
struct kiosk_manager_proof {
    int proc, pidfd, root, usr, executable, marker, selected, acquired, failed;
    struct kiosk_pin_namespace mount_namespace;
    struct stat root_info, usr_info, executable_info, marker_info;
    struct stat host_mount, user_namespace, pid_namespace;
    struct kiosk_manager_bus connection;
    struct kiosk_manager_unit unit;
    struct kiosk_manager_task tasks[KIOSK_MANAGER_TASKS];
    unsigned count, group_count;
    uid_t uid;
    gid_t gid, groups[KIOSK_MANAGER_GROUPS];
    int selinux;
    uint64_t deadline;
    char boot[64], cgroup[PATH_MAX], material[65], view[65];
};

static uint64_t
kiosk_manager_now(void)
{
    struct timespec time;
    return clock_gettime(CLOCK_MONOTONIC, &time) == 0 ?
        (uint64_t) time.tv_sec * 1000000U + (uint64_t) time.tv_nsec / 1000U : 0;
}

static int
kiosk_manager_denied(struct kiosk_failure *failure, const char *reason)
{
    kiosk_failure(failure, "manager", reason, 0);
    return -1;
}

static int
kiosk_manager_refuse(struct kiosk_manager_proof *proof, struct kiosk_failure *failure, const char *reason)
{
    proof->failed = 1;
    return kiosk_manager_denied(failure, reason);
}

static int
kiosk_manager_same(const struct stat *a, const struct stat *b)
{
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino;
}

static int
kiosk_manager_file_same(const struct stat *a, const struct stat *b)
{
    return kiosk_manager_same(a, b) && a->st_mode == b->st_mode &&
        a->st_uid == b->st_uid && a->st_gid == b->st_gid && a->st_size == b->st_size &&
        a->st_nlink == b->st_nlink && a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
        a->st_mtim.tv_nsec == b->st_mtim.tv_nsec && a->st_ctim.tv_sec == b->st_ctim.tv_sec &&
        a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}

/* proc records are finite regular pseudo-files. Read EOF, not a truncated
 * prefix. A task FD remains pinned even when its numeric TID is reused. */
static int
kiosk_manager_text(int parent, const char *path, char *text, size_t capacity)
{
    int fd = openat(parent, path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
    struct stat info;
    size_t count = 0;
    int result = -1;
    if (fd < 0) return -1;
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode)) goto done;
    while (count < capacity - 1) {
        ssize_t size = read(fd, text + count, capacity - count - 1);
        if (size < 0) goto done;
        if (size == 0) { text[count] = 0; result = (int) count; goto done; }
        count += (size_t) size;
    }
done:
    close(fd);
    return result;
}

static int
kiosk_manager_bus_open(struct kiosk_manager_bus *bus)
{
    bus->library = dlopen("libsystemd.so.0", RTLD_NOW | RTLD_LOCAL);
    if (bus->library == NULL) return -1;
#define KIOSK_BUS_SYMBOL(field, name) do { \
    *(void **) (&bus->field) = dlsym(bus->library, name); \
    if (bus->field == NULL) return -1; \
} while (0)
    KIOSK_BUS_SYMBOL(new_bus, "sd_bus_new");
    KIOSK_BUS_SYMBOL(set_address, "sd_bus_set_address");
    KIOSK_BUS_SYMBOL(set_client, "sd_bus_set_bus_client");
    KIOSK_BUS_SYMBOL(start, "sd_bus_start");
    KIOSK_BUS_SYMBOL(get_fd, "sd_bus_get_fd");
    KIOSK_BUS_SYMBOL(unref, "sd_bus_unref");
    KIOSK_BUS_SYMBOL(new_call, "sd_bus_message_new_method_call");
    KIOSK_BUS_SYMBOL(append, "sd_bus_message_append");
    KIOSK_BUS_SYMBOL(call, "sd_bus_call");
    KIOSK_BUS_SYMBOL(enter, "sd_bus_message_enter_container");
    KIOSK_BUS_SYMBOL(exit, "sd_bus_message_exit_container");
    KIOSK_BUS_SYMBOL(read, "sd_bus_message_read");
    KIOSK_BUS_SYMBOL(array, "sd_bus_message_read_array");
    KIOSK_BUS_SYMBOL(at_end, "sd_bus_message_at_end");
    KIOSK_BUS_SYMBOL(message_unref, "sd_bus_message_unref");
#undef KIOSK_BUS_SYMBOL
    /* No environment-selected bus, address, shell or helper. sd_bus_start queues
     * asynchronous authentication; sd_bus_call below bounds its completion. */
    return bus->new_bus(&bus->bus) >= 0 &&
        bus->set_address(bus->bus, "unix:path=/run/dbus/system_bus_socket") >= 0 &&
        bus->set_client(bus->bus, 1) >= 0 && bus->start(bus->bus) >= 0 ? 0 : -1;
}

static int
kiosk_manager_property(struct kiosk_manager_bus *bus, const char *path,
                       const char *interface, const char *property, const char *type,
                       void *value, size_t capacity, uint64_t deadline)
{
    struct sd_bus_message *request = NULL, *reply = NULL;
    uint64_t now;
    int result = -1;
    if (bus->new_call(bus->bus, &request, "org.freedesktop.systemd1", path,
                      "org.freedesktop.DBus.Properties", "Get") < 0 ||
        bus->append(request, "ss", interface, property) < 0 ||
        !(now = kiosk_manager_now()) || now >= deadline ||
        bus->call(bus->bus, request, deadline - now, NULL, &reply) < 0 ||
        bus->enter(reply, 'v', type) <= 0) goto done;
    if (strcmp(type, "s") == 0) {
        const char *text;
        if (bus->read(reply, "s", &text) <= 0 || text == NULL || strlen(text) >= capacity) goto done;
        strcpy(value, text);
    } else if (strcmp(type, "ay") == 0) {
        const void *bytes;
        size_t size;
        if (bus->array(reply, 'y', &bytes, &size) <= 0 || size != capacity) goto done;
        memcpy(value, bytes, size);
    } else if (bus->read(reply, "u", value) <= 0) goto done;
    if (bus->at_end(reply, 0) <= 0 || bus->exit(reply) < 0 || bus->at_end(reply, 1) <= 0)
        goto done;
    now = kiosk_manager_now();
    if (now && now < deadline) result = 0;
done:
    if (request) bus->message_unref(request);
    if (reply) bus->message_unref(reply);
    return result;
}

static int
kiosk_manager_unit_read(struct kiosk_manager_proof *proof, struct kiosk_manager_unit *unit)
{
    char path[128], state[32];
    uint64_t now = kiosk_manager_now(), deadline = now + 5000000U;
    if (!now || now >= proof->deadline) return -1;
    if (deadline > proof->deadline) deadline = proof->deadline;
    snprintf(path, sizeof(path), "/org/freedesktop/systemd1/unit/user_40%lu_2eservice", (unsigned long) proof->uid);
    memset(unit, 0, sizeof(*unit));
    if (kiosk_manager_property(&proof->connection, path, "org.freedesktop.systemd1.Service", "MainPID", "u",
                               &unit->pid, sizeof(unit->pid), deadline) != 0 ||
        kiosk_manager_property(&proof->connection, path, "org.freedesktop.systemd1.Unit", "InvocationID", "ay",
                               unit->invocation, sizeof(unit->invocation), deadline) != 0 ||
        kiosk_manager_property(&proof->connection, path, "org.freedesktop.systemd1.Service", "ControlGroup", "s",
                               unit->cgroup, sizeof(unit->cgroup), deadline) != 0 ||
        kiosk_manager_property(&proof->connection, path, "org.freedesktop.systemd1.Unit", "ActiveState", "s",
                               state, sizeof(state), deadline) != 0 ||
        (strcmp(state, "active") && strcmp(state, "reloading")) || unit->pid <= 1 ||
        unit->pid > INT_MAX || !kiosk_path(unit->cgroup, 1) || !strcmp(unit->cgroup, "/")) return -1;
    unsigned nonzero = 0;
    for (unsigned i = 0; i < sizeof(unit->invocation); i++) nonzero |= unit->invocation[i];
    int bus_fd = proof->connection.get_fd(proof->connection.bus);
    int flags = bus_fd < 0 ? -1 : fcntl(bus_fd, F_GETFD);
    return nonzero && flags >= 0 && (flags & FD_CLOEXEC) ? 0 : -1;
}

static int
kiosk_manager_live(struct kiosk_manager_proof *proof)
{
    struct pollfd lifetime = {.fd = proof->pidfd, .events = POLLIN};
    uint64_t now = kiosk_manager_now();
    return now && now < proof->deadline && proof->pidfd >= 0 &&
        poll(&lifetime, 1, 0) == 0 && lifetime.revents == 0 ? 0 : -1;
}

static int
kiosk_manager_start(int task, pid_t tid, unsigned long long *start)
{
    char text[8192], *end, *part;
    if (kiosk_manager_text(task, "stat", text, sizeof(text)) <= 0) return -1;
    errno = 0;
    long id = strtol(text, &end, 10);
    if (errno || id != tid || *end != ' ' || end[1] != '(' || !(part = strrchr(end, ')')) || part[1] != ' ')
        return -1;
    part += 2;
    for (unsigned field = 3; field < 22; field++) {
        end = strchr(part, ' ');
        if (end == NULL || end == part) return -1;
        part = end + 1;
    }
    errno = 0;
    *start = strtoull(part, &end, 10);
    return !errno && *start && end != part && *end == ' ' ? 0 : -1;
}

static int
kiosk_manager_numbers(const char *text, unsigned long long *values, unsigned capacity, unsigned *count, int base)
{
    *count = 0;
    for (;;) {
        while (*text == ' ' || *text == '\t') text++;
        if (!*text) return 0;
        if (*count == capacity || *text == '-' || *text == '+') return -1;
        char *end;
        errno = 0;
        unsigned long long value = strtoull(text, &end, base);
        if (errno || end == text || (*end && *end != ' ' && *end != '\t')) return -1;
        values[(*count)++] = value;
        text = end;
    }
}

static int
kiosk_manager_credentials(struct kiosk_manager_proof *proof, int task, pid_t tid)
{
    char text[32768], *save, *line;
    unsigned seen = 0;
    if (kiosk_manager_text(task, "status", text, sizeof(text)) <= 0) return -1;
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        const char *names[] = {"Uid:", "Gid:", "Groups:", "CapInh:", "CapPrm:", "CapEff:", "CapAmb:", "Pid:", "Tgid:"};
        for (unsigned field = 0; field < 9; field++) {
            size_t n = strlen(names[field]);
            if (strncmp(line, names[field], n)) continue;
            unsigned long long values[KIOSK_MANAGER_GROUPS]; unsigned count;
            if ((seen & (1U << field)) ||
                kiosk_manager_numbers(line + n, values, KIOSK_MANAGER_GROUPS, &count,
                                      field >= 3 && field <= 6 ? 16 : 10) != 0) return -1;
            seen |= 1U << field;
            if (field < 2) {
                if (count != 4) return -1;
                for (unsigned j = 0; j < 4; j++)
                    if (values[j] != (field ? (unsigned long long) proof->gid : proof->uid)) return -1;
            } else if (field == 2) {
                if (count != proof->group_count) return -1;
                for (unsigned j = 0; j < count; j++) {
                    unsigned found = 0;
                    for (unsigned k = 0; k < count; k++) found += values[j] == proof->groups[k];
                    if (found != 1) return -1;
                    for (unsigned k = 0; k < j; k++) if (values[k] == values[j]) return -1;
                }
            } else if (count != 1 || values[0] != (field == 7 ? (unsigned long long) tid :
                       field == 8 ? (unsigned long long) proof->unit.pid : 0)) return -1;
        }
    }
    return seen == 511 ? 0 : -1;
}

static int
kiosk_manager_object(int proc, const char *path, const struct stat *expected)
{
    struct stat info;
    int fd = openat(proc, path, O_PATH | O_CLOEXEC);
    int valid = fd >= 0 && fstat(fd, &info) == 0 && kiosk_manager_same(&info, expected);
    if (fd >= 0) close(fd);
    return valid ? 0 : -1;
}

static int
kiosk_manager_label(struct kiosk_manager_proof *proof, int task)
{
    char text[256];
    int n = kiosk_manager_text(task, proof->selinux ? "attr/current" : "attr/apparmor/current", text, sizeof(text));
    if (n <= 0) return -1;
    while (n && (text[n - 1] == '\n' || text[n - 1] == 0)) text[--n] = 0;
    return strcmp(text, proof->selinux ? "system_u:system_r:onpc_kiosk_manager_t:s0" :
                  "onpc-kiosk-manager (enforce)") == 0 ? 0 : -1;
}

/* cgroup v2 is the supported system-manager layout; init.scope is admitted
 * beneath the exact unit component, never an adjacent prefix. */
static int
kiosk_manager_cgroup(struct kiosk_manager_proof *proof, int task, int initial)
{
    char text[PATH_MAX + 16];
    int n = kiosk_manager_text(task, "cgroup", text, sizeof(text));
    if (n < 5 || strncmp(text, "0::", 3) || text[n - 1] != '\n') return -1;
    text[n - 1] = 0;
    if (strchr(text + 3, '\n') || !kiosk_path(text + 3, 1)) return -1;
    size_t length = strlen(proof->unit.cgroup);
    if (strncmp(text + 3, proof->unit.cgroup, length) ||
        (text[3 + length] && text[3 + length] != '/')) return -1;
    if (initial) strcpy(proof->cgroup, text + 3);
    return strcmp(text + 3, proof->cgroup) == 0 ? 0 : -1;
}

static int
kiosk_manager_marker_read(struct kiosk_manager_proof *proof, int task)
{
    char path[PATH_MAX], text[256], expected[256];
    struct stat info;
    snprintf(path, sizeof(path), "root/usr/%s", KIOSK_MANAGER_MARKER);
    int fd = openat(task, path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    ssize_t n = pread(fd, text, sizeof(text), 0);
    int length = snprintf(expected, sizeof(expected), "ONPC-KIOSK-VIEW\t1\t%s\t%s\t%s\n",
                          proof->selinux ? "selinux" : "apparmor", proof->material, proof->view);
    int valid = fstat(fd, &info) == 0 && kiosk_manager_file_same(&info, &proof->marker_info) &&
        n == length && length > 0 && (size_t) length < sizeof(text) && !memcmp(text, expected, (size_t) length);
    close(fd);
    return valid ? 0 : -1;
}

static int
kiosk_manager_task_check(struct kiosk_manager_proof *proof, struct kiosk_manager_task *task)
{
    unsigned long long before, after;
    struct stat info;
    if (kiosk_manager_live(proof) != 0 || fstat(task->fd, &info) != 0 ||
        !kiosk_manager_same(&task->proc, &info) ||
        kiosk_manager_start(task->fd, task->tid, &before) != 0 || before != task->start ||
        kiosk_manager_credentials(proof, task->fd, task->tid) != 0 || kiosk_manager_label(proof, task->fd) != 0 ||
        kiosk_manager_cgroup(proof, task->fd, 0) != 0 ||
        kiosk_manager_object(task->fd, "root", &proof->root_info) != 0 ||
        kiosk_manager_object(task->fd, "root/usr", &proof->usr_info) != 0 ||
        kiosk_manager_object(task->fd, "ns/mnt", &(struct stat) {.st_dev = proof->mount_namespace.device,
                              .st_ino = proof->mount_namespace.inode}) != 0 ||
        kiosk_manager_object(task->fd, "ns/user", &proof->user_namespace) != 0 ||
        kiosk_manager_object(task->fd, "ns/pid", &proof->pid_namespace) != 0) return -1;
    int executable = openat(task->fd, "exe", O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    int same = executable >= 0 && fstat(executable, &info) == 0 &&
        kiosk_manager_file_same(&info, &proof->executable_info);
    if (executable >= 0) close(executable);
    if (!same || (proof->selected && kiosk_manager_marker_read(proof, task->fd) != 0)) return -1;
    return kiosk_manager_start(task->fd, task->tid, &after) == 0 && before == after ? 0 : -1;
}

static int
kiosk_manager_tid_compare(const void *a, const void *b)
{
    pid_t left = *(const pid_t *) a, right = *(const pid_t *) b;
    return (left > right) - (left < right);
}

static int
kiosk_manager_census(struct kiosk_manager_proof *proof, pid_t tids[KIOSK_MANAGER_TASKS], unsigned *count)
{
    int fd = openat(proof->proc, "task", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    DIR *directory = fd < 0 ? NULL : fdopendir(fd);
    if (!directory) { if (fd >= 0) close(fd); return -1; }
    struct dirent *entry;
    *count = 0;
    errno = 0;
    while ((entry = readdir(directory)) != NULL) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char *end; errno = 0;
        unsigned long tid = strtoul(entry->d_name, &end, 10);
        if (errno || !tid || tid > INT_MAX || *end || *count >= KIOSK_MANAGER_TASKS) { closedir(directory); return -1; }
        tids[(*count)++] = (pid_t) tid;
        errno = 0;
    }
    int error = errno;
    closedir(directory);
    if (error || !*count) return -1;
    qsort(tids, *count, sizeof(*tids), kiosk_manager_tid_compare);
    for (unsigned i = 1; i < *count; i++) if (tids[i] == tids[i - 1]) return -1;
    return 0;
}

static int
kiosk_manager_check(struct kiosk_manager_proof *proof, struct kiosk_failure *failure)
{
    pid_t tids[KIOSK_MANAGER_TASKS]; unsigned count;
    struct kiosk_manager_unit unit;
    char boot[64];
    if (!proof->acquired || proof->failed || kiosk_manager_live(proof) != 0 ||
        kiosk_manager_unit_read(proof, &unit) != 0 || memcmp(&unit, &proof->unit, sizeof(unit)) ||
        kiosk_manager_text(AT_FDCWD, "/proc/sys/kernel/random/boot_id", boot, sizeof(boot)) <= 0 ||
        strcmp(boot, proof->boot)) return kiosk_manager_refuse(proof, failure, "unit-identity");
    if (kiosk_manager_census(proof, tids, &count) != 0 || count != proof->count)
        return kiosk_manager_refuse(proof, failure, "task-membership");
    for (unsigned i = 0; i < count; i++)
        if (tids[i] != proof->tasks[i].tid || kiosk_manager_task_check(proof, &proof->tasks[i]) != 0)
            return kiosk_manager_refuse(proof, failure, "task-identity");
    if (kiosk_manager_census(proof, tids, &count) != 0 || count != proof->count)
        return kiosk_manager_refuse(proof, failure, "task-membership");
    for (unsigned i = 0; i < count; i++) {
        char path[64]; struct stat current; unsigned long long start;
        snprintf(path, sizeof(path), "task/%ld", (long) tids[i]);
        int fd = openat(proof->proc, path, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        int valid = tids[i] == proof->tasks[i].tid && fd >= 0 && fstat(fd, &current) == 0 &&
            kiosk_manager_same(&current, &proof->tasks[i].proc) &&
            kiosk_manager_start(fd, tids[i], &start) == 0 && start == proof->tasks[i].start;
        if (fd >= 0) close(fd);
        if (!valid) return kiosk_manager_refuse(proof, failure, "task-membership");
    }
    if (kiosk_manager_live(proof) != 0 || kiosk_manager_unit_read(proof, &unit) != 0 ||
        memcmp(&unit, &proof->unit, sizeof(unit))) return kiosk_manager_refuse(proof, failure, "unit-identity");
    return 0;
}

static void
kiosk_manager_release(struct kiosk_manager_proof *proof)
{
    int *fds[] = {&proof->proc, &proof->pidfd, &proof->root, &proof->usr,
                  &proof->executable, &proof->marker, &proof->mount_namespace.fd};
    for (unsigned i = 0; i < sizeof(fds) / sizeof(fds[0]); i++) {
        if (*fds[i] >= 0) close(*fds[i]);
        *fds[i] = -1;
    }
    for (unsigned i = 0; i < proof->count; i++) {
        if (proof->tasks[i].fd >= 0) close(proof->tasks[i].fd);
        proof->tasks[i].fd = -1;
    }
    if (proof->connection.bus && proof->connection.unref) proof->connection.unref(proof->connection.bus);
    if (proof->connection.library) dlclose(proof->connection.library);
    proof->connection.bus = NULL; proof->connection.library = NULL;
    proof->acquired = proof->selected = 0;
}

static int
kiosk_manager_pin_object(int proc, const char *path, int flags, struct stat *info)
{
    int fd = openat(proc, path, flags | O_CLOEXEC);
    if (fd >= 0 && fstat(fd, info) == 0) return fd;
    if (fd >= 0) close(fd);
    return -1;
}

static int
kiosk_manager_acquire_until(struct kiosk_manager_proof *proof, uid_t uid, gid_t gid,
                            const gid_t *groups, unsigned count, int selinux,
                            uint64_t transaction_deadline, struct kiosk_failure *failure)
{
    struct stat mount_namespace, host_root;
    pid_t tids[KIOSK_MANAGER_TASKS]; unsigned tasks;
    char path[128], map[128];
    const char *reason = "acquisition-inputs";
    memset(proof, 0, sizeof(*proof));
    proof->proc = proof->pidfd = proof->root = proof->usr = proof->executable = proof->marker = -1;
    proof->mount_namespace.fd = -1;
    for (unsigned i = 0; i < KIOSK_MANAGER_TASKS; i++) proof->tasks[i].fd = -1;
    proof->deadline = kiosk_manager_now();
    if (!uid || !gid || count > KIOSK_MANAGER_GROUPS || (count && !groups) || !proof->deadline)
        goto refused;
    proof->deadline += 60000000U;
    if (transaction_deadline && transaction_deadline < proof->deadline)
        proof->deadline = transaction_deadline;
    if (kiosk_manager_now() >= proof->deadline) goto refused;
    proof->uid = uid; proof->gid = gid; proof->selinux = selinux;
    proof->group_count = count;
    for (unsigned i = 0; i < count; i++) {
        if (groups[i] == 0) goto refused;
        for (unsigned j = 0; j < i; j++) if (groups[i] == groups[j]) goto refused;
        proof->groups[i] = groups[i];
    }
    reason = "acquisition-host";
    if (stat("/proc/self/ns/mnt", &proof->host_mount) != 0 || stat("/proc/1/ns/user", &proof->user_namespace) != 0 ||
        stat("/proc/1/ns/pid", &proof->pid_namespace) != 0 || stat("/proc/1/root", &host_root) != 0 ||
        kiosk_manager_text(AT_FDCWD, "/proc/sys/kernel/random/boot_id", proof->boot, sizeof(proof->boot)) <= 0)
        goto refused;
    const char *maps[] = {"/proc/1/uid_map", "/proc/1/gid_map"};
    reason = "acquisition-mapping";
    for (unsigned i = 0; i < 2; i++) {
        unsigned long long inside, outside, size; char extra;
        if (kiosk_manager_text(AT_FDCWD, maps[i], map, sizeof(map)) <= 0 ||
            sscanf(map, "%llu %llu %llu %c", &inside, &outside, &size, &extra) != 3 ||
            inside || outside || size != UINT32_MAX) goto refused;
    }
    reason = "acquisition-unit";
    if (kiosk_manager_bus_open(&proof->connection) != 0 || kiosk_manager_unit_read(proof, &proof->unit) != 0)
        goto refused;
    reason = "acquisition-proc";
    proof->pidfd = (int) syscall(SYS_pidfd_open, proof->unit.pid, 0);
    snprintf(path, sizeof(path), "/proc/%u", proof->unit.pid);
    proof->proc = open(path, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (proof->pidfd < 0 || proof->proc < 0 || kiosk_manager_live(proof) != 0) goto refused;
    struct statfs filesystem;
    if (fstatfs(proof->proc, &filesystem) != 0 || filesystem.f_type != 0x9fa0) goto refused;
    proof->root = kiosk_manager_pin_object(proof->proc, "root", O_PATH | O_DIRECTORY, &proof->root_info);
    proof->usr = kiosk_manager_pin_object(proof->root, "usr", O_PATH | O_DIRECTORY | O_NOFOLLOW, &proof->usr_info);
    proof->executable = kiosk_manager_pin_object(proof->proc, "exe", O_RDONLY | O_NONBLOCK, &proof->executable_info);
    proof->mount_namespace.fd = kiosk_manager_pin_object(proof->proc, "ns/mnt", O_RDONLY, &mount_namespace);
    reason = "acquisition-objects";
    if (proof->root < 0 || proof->usr < 0 || proof->executable < 0 || proof->mount_namespace.fd < 0 ||
        !kiosk_manager_same(&host_root, &proof->root_info) ||
        kiosk_manager_same(&mount_namespace, &proof->host_mount) ||
        !S_ISREG(proof->executable_info.st_mode) || proof->executable_info.st_uid != 0 ||
        (proof->executable_info.st_mode & 022) ||
        kiosk_manager_cgroup(proof, proof->proc, 1) != 0 || kiosk_manager_census(proof, tids, &tasks) != 0)
        goto refused;
    proof->mount_namespace.device = mount_namespace.st_dev;
    proof->mount_namespace.inode = mount_namespace.st_ino;
    reason = "acquisition-tasks";
    for (unsigned i = 0; i < tasks; i++) {
        struct kiosk_manager_task *task = &proof->tasks[i];
        snprintf(path, sizeof(path), "task/%ld", (long) tids[i]);
        task->tid = tids[i];
        task->fd = kiosk_manager_pin_object(proof->proc, path, O_PATH | O_DIRECTORY | O_NOFOLLOW, &task->proc);
        proof->count++;
        if (task->fd < 0 || kiosk_manager_start(task->fd, task->tid, &task->start) != 0) goto refused;
    }
    unsigned leader = 0;
    for (unsigned i = 0; i < proof->count; i++) leader += proof->tasks[i].tid == (pid_t) proof->unit.pid;
    if (leader != 1) goto refused;
    proof->acquired = 1;
    if (kiosk_manager_check(proof, failure) == 0) return 0;
refused:
    kiosk_manager_release(proof);
    return kiosk_manager_denied(failure, reason);
}

/* Standalone acquisitions retain the existing sixty-second ceiling. The PAM
 * coordinator uses acquire_until with its already-started transaction deadline
 * so acquisition, preparation, binding and the last observation share it. */
static inline int
kiosk_manager_acquire(struct kiosk_manager_proof *proof, uid_t uid, gid_t gid,
                      const gid_t *groups, unsigned count, int selinux, struct kiosk_failure *failure)
{
    return kiosk_manager_acquire_until(proof, uid, gid, groups, count, selinux, 0, failure);
}

static int
kiosk_manager_digest(const char *text)
{
    if (!text || strlen(text) != 64) return 0;
    for (unsigned i = 0; i < 64; i++)
        if (!(text[i] >= '0' && text[i] <= '9') && !(text[i] >= 'a' && text[i] <= 'f')) return 0;
    return 1;
}

/* The coordinator must independently verify expected_executable's bytes,
 * capabilities and role against its selected completed source receipt. These
 * descriptors may never be obtained from an untrusted helper's pathname. */
static int
kiosk_manager_select(struct kiosk_manager_proof *proof, int expected_executable, int expected_marker,
                     const char *material, const char *view, struct kiosk_failure *failure)
{
    struct stat executable, marker;
    if (!proof->acquired || proof->failed || proof->selected || !kiosk_manager_digest(material) || !kiosk_manager_digest(view) ||
        fstat(expected_executable, &executable) != 0 ||
        !kiosk_manager_file_same(&executable, &proof->executable_info) ||
        fstat(expected_marker, &marker) != 0 || !S_ISREG(marker.st_mode) || marker.st_uid != 0 ||
        (marker.st_mode & 022)) return kiosk_manager_refuse(proof, failure, "selected-source");
    if (proof->marker >= 0) return kiosk_manager_refuse(proof, failure, "selected-marker");
    proof->marker = kiosk_pin_open(proof->usr, KIOSK_MANAGER_MARKER);
    if (proof->marker < 0 || fstat(proof->marker, &proof->marker_info) != 0 ||
        !kiosk_manager_file_same(&marker, &proof->marker_info)) return kiosk_manager_refuse(proof, failure, "selected-marker");
    strcpy(proof->material, material); strcpy(proof->view, view);
    proof->selected = 1;
    return kiosk_manager_check(proof, failure);
}

static int
kiosk_manager_recheck(struct kiosk_manager_proof *proof, struct kiosk_failure *failure)
{
    if (!proof->selected) return kiosk_manager_refuse(proof, failure, "source-unselected");
    return kiosk_manager_check(proof, failure);
}
#endif
