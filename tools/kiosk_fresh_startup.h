/* Complete initial-manager transaction. Include after kiosk_confinement.h.
 * Every authority here is independently observed; helper records are intent.
 */
#ifndef ONPC_KIOSK_FRESH_STARTUP_H
#define ONPC_KIOSK_FRESH_STARTUP_H
#include "kiosk_preparation_channel.h"
#include "kiosk_preparation_child.h"
#include "kiosk_policy_authority.h"
#include "kiosk_native_realization.h"
#include "kiosk_view_publication.h"
#include <linux/capability.h>
#include <sys/random.h>

#ifndef KIOSK_FRESH_DLOPEN
#define KIOSK_FRESH_DLOPEN dlopen
#endif
#ifndef KIOSK_FRESH_DLSYM
#define KIOSK_FRESH_DLSYM dlsym
#endif
#ifndef KIOSK_FRESH_DLCLOSE
#define KIOSK_FRESH_DLCLOSE dlclose
#endif
#ifndef KIOSK_FRESH_CAPGET
#define KIOSK_FRESH_CAPGET(header, data) syscall(SYS_capget, (header), (data))
#endif
#ifndef KIOSK_FRESH_CAPSET
#define KIOSK_FRESH_CAPSET(header, data) syscall(SYS_capset, (header), (data))
#endif
#ifndef KIOSK_FRESH_AMBIENT_CLEAR
#define KIOSK_FRESH_AMBIENT_CLEAR() prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0)
#endif

#define KIOSK_FRESH_MARKER "/usr/share/oh-no-parent-control/confinement/retained-view"
#define KIOSK_FRESH_ACCOUNT "/var/lib/oh-no-parent-control/package-created-kiosk-uid"

struct kiosk_fresh_mac {
    void *library;
    int selinux, gate;
    int (*change_profile)(const char *), (*aa_getcon)(char **, char **);
    int (*enabled)(void), (*enforcing)(void);
    int (*setexec)(const char *), (*setcurrent)(const char *), (*getcurrent)(char **);
    int (*getexec)(char **);
    void (*freecon)(char *);
};

struct kiosk_fresh_startup {
    struct kiosk_preparation_child child;
    struct kiosk_preparation_response measurement, response;
    struct kiosk_host_roots roots;
    struct kiosk_host_proof host, account;
    struct kiosk_policy_authority policy;
    struct kiosk_material_authority authority;
    struct kiosk_preparation_plan plan;
    struct kiosk_native_realization realized;
    struct kiosk_source_pin pin;
    struct kiosk_publication publication;
    struct kiosk_view view;
    struct kiosk_fresh_mac mac;
    struct kiosk_failure failure, cleanup_failure;
    int runtime, skeleton, target_parent, marker, attempted, armed;
    int ticket_adopted, transferred_scratch, ready, recovered, closed;
    void *crypto;
    uint64_t deadline;
    uid_t uid;
    char *material_bytes, *config_bytes, *inventory_bytes;
    size_t material_size, config_size, inventory_size;
    char material[65], generation[65], inventory[65], acquisition[65], boot[37];
    char marker_bytes[256];
    size_t marker_size;
    struct stat marker_info;
    const char *stage;
};

static inline void kiosk_fresh_startup_init(struct kiosk_fresh_startup *s)
{
    memset(s, 0, sizeof(*s));
    kiosk_preparation_child_init(&s->child);
    kiosk_preparation_response_init(&s->measurement);
    kiosk_preparation_response_init(&s->response);
    s->roots.root = s->roots.usr = -1;
    s->host.roots.root = s->host.roots.usr = -1;
    s->account.roots.root = s->account.roots.usr = -1;
    s->policy.host.roots.root = s->policy.host.roots.usr = -1;
    s->pin.fd = s->pin.parent = s->pin.worker = -1;
    s->publication.root = s->publication.parent = -1;
    s->realized.root = s->view.root = -1;
    s->runtime = s->skeleton = s->target_parent = s->marker = -1;
}

/* Resolve every final-transition symbol while original host /usr is visible. */
static inline int kiosk_fresh_mac_preload(struct kiosk_fresh_mac *m, const char *backend)
{
    memset(m, 0, sizeof(*m)); m->selinux = !strcmp(backend, "selinux");
    m->library = KIOSK_FRESH_DLOPEN(m->selinux ? "libselinux.so.1" : "libapparmor.so.1", RTLD_NOW | RTLD_LOCAL);
    if (!m->library) return -1;
    if (!m->selinux) {
        m->change_profile = (int (*)(const char *))KIOSK_FRESH_DLSYM(m->library, "aa_change_profile");
        m->aa_getcon = (int (*)(char **, char **))KIOSK_FRESH_DLSYM(m->library, "aa_getcon");
        return m->change_profile && m->aa_getcon ? 0 : -1;
    }
    m->enabled = (int (*)(void))KIOSK_FRESH_DLSYM(m->library, "is_selinux_enabled");
    m->enforcing = (int (*)(void))KIOSK_FRESH_DLSYM(m->library, "security_getenforce");
    m->setexec = (int (*)(const char *))KIOSK_FRESH_DLSYM(m->library, "setexeccon_raw");
    m->setcurrent = (int (*)(const char *))KIOSK_FRESH_DLSYM(m->library, "setcon_raw");
    m->getcurrent = (int (*)(char **))KIOSK_FRESH_DLSYM(m->library, "getcon_raw");
    m->freecon = (void (*)(char *))KIOSK_FRESH_DLSYM(m->library, "freecon");
    return m->enabled && m->enforcing && m->setexec && m->setcurrent && m->getcurrent && m->freecon ? 0 : -1;
}

static inline int kiosk_gate_mac_preload(struct kiosk_fresh_mac *m, const char *backend)
{
    if (kiosk_fresh_mac_preload(m, backend)) return -1;
    m->gate = 1;
    if (m->selinux) {
        m->getexec = (int (*)(char **))KIOSK_FRESH_DLSYM(m->library, "getexeccon_raw");
        if (!m->getexec) return -1;
    }
    return 0;
}

static inline int kiosk_fresh_mac_apply(struct kiosk_fresh_mac *m)
{
    char *label = NULL, *mode = NULL; int result = -1;
    if (!m->library) return -1;
    if (!m->selinux) {
        const char *profile = m->gate ? "onpc-kiosk-gate" : "onpc-kiosk-manager";
        if (!m->change_profile(profile) && m->aa_getcon(&label, &mode) >= 0 &&
            label && mode && !strcmp(label, profile) && !strcmp(mode, "enforce")) result = 0;
        free(label);
    } else {
        const char *context = m->gate ? "system_u:system_r:onpc_kiosk_gate_t:s0" :
            "system_u:system_r:onpc_kiosk_manager_pam_t:s0";
        if (m->enabled() == 1 && m->enforcing() == 1 &&
            (m->gate ? m->getexec && !m->setexec(context) && !m->getexec(&label) :
                !m->setexec(NULL) && !m->setcurrent(context) && !m->getcurrent(&label)) &&
            label && !strcmp(label, context)) result = 0;
        if (label) m->freecon(label);
    }
    return result;
}

static inline int kiosk_fresh_locks(int lock, int lease)
{
    return lock != lease && !kiosk_lock_identity(lock, KIOSK_CONFINEMENT_LOCK, 0) &&
        !kiosk_admission_current(lease) ? 0 : -1;
}

/* pam_systemd can seed inheritable capabilities before this PAM callback.
 * Remove only inheritance and ambient authority from the actual caller task.
 * Its root effective/permitted sets still belong to the executor's remaining
 * credential/MAC setup; the bounding set is never changed here. */
static inline int kiosk_fresh_capabilities_until(uint64_t deadline)
{
    struct __user_cap_header_struct header = {.version = _LINUX_CAPABILITY_VERSION_3, .pid = 0};
    struct __user_cap_data_struct before[_LINUX_CAPABILITY_U32S_3] = {{0}},
        cleared[_LINUX_CAPABILITY_U32S_3], after[_LINUX_CAPABILITY_U32S_3] = {{0}};
    if (kiosk_pin_before(deadline) || KIOSK_FRESH_CAPGET(&header, before) ||
        header.version != _LINUX_CAPABILITY_VERSION_3 || header.pid || kiosk_pin_before(deadline)) return -1;
    memcpy(cleared, before, sizeof(cleared));
    for (unsigned i = 0; i < _LINUX_CAPABILITY_U32S_3; i++) cleared[i].inheritable = 0;
    if (KIOSK_FRESH_CAPSET(&header, cleared) || kiosk_pin_before(deadline) ||
        KIOSK_FRESH_AMBIENT_CLEAR() || kiosk_pin_before(deadline) ||
        KIOSK_FRESH_CAPGET(&header, after) || header.version != _LINUX_CAPABILITY_VERSION_3 ||
        header.pid || kiosk_pin_before(deadline)) return -1;
    for (unsigned i = 0; i < _LINUX_CAPABILITY_U32S_3; i++)
        if (after[i].inheritable || after[i].effective != before[i].effective ||
            after[i].permitted != before[i].permitted) return -1;
    return 0;
}

/* Namespace cloning gives inherited mounts new mount identities. Runtime
 * publication and mountinfo walks must use this caller's private namespace,
 * while retaining independently checked original host inode identities. This
 * is performed once before measurement/attachment; never refresh after overlay.
 */
static inline int kiosk_fresh_reanchor_until(struct kiosk_fresh_startup *s)
{
    struct kiosk_host_roots current = {.root = -1, .usr = -1};
    struct stat original, fresh;
    int runtime = -1, result = -1;
    if (kiosk_pin_before(s->deadline) || kiosk_host_roots_open(&current)) goto done;
    int old_fds[] = {s->roots.root, s->roots.usr};
    int new_fds[] = {current.root, current.usr};
    for (unsigned i = 0; i < 2; i++) {
        if (fstat(old_fds[i], &original) || fstat(new_fds[i], &fresh) ||
            !S_ISDIR(fresh.st_mode) || !kiosk_host_trust(&fresh) ||
            original.st_dev != fresh.st_dev || original.st_ino != fresh.st_ino ||
            original.st_mode != fresh.st_mode || original.st_uid != fresh.st_uid ||
            original.st_gid != fresh.st_gid) goto done;
    }
    runtime = open(KIOSK_CONFINEMENT_RUNTIME, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (runtime < 0 || fstat(s->runtime, &original) || fstat(runtime, &fresh) ||
        !kiosk_publication_private(&fresh, 1) || original.st_dev != fresh.st_dev ||
        original.st_ino != fresh.st_ino || original.st_mode != fresh.st_mode ||
        original.st_uid != fresh.st_uid || original.st_gid != fresh.st_gid ||
        kiosk_pin_before(s->deadline)) goto done;
    kiosk_host_roots_close(&s->roots); s->roots = current;
    current.root = current.usr = -1;
    close(s->runtime); s->runtime = runtime; runtime = -1;
    result = 0;
done:
    kiosk_host_roots_close(&current);
    if (runtime >= 0) close(runtime);
    return result;
}

static inline int kiosk_fresh_account_until(struct kiosk_fresh_startup *s)
{
    char *record = NULL, digest[65];
    size_t size = 0; struct stat before;
    if (kiosk_policy_read(&s->roots, KIOSK_FRESH_ACCOUNT, s->deadline,
            &record, &size, &before, 1)) return -1;
    /* The single bounded preparation child owns the NSS/account comparison.
     * Native independently pins its canonical nonzero UID marker. Do not add
     * an unbounded NSS lookup to the PAM executor's original deadline. */
    size_t digits = size && record[size - 1] == '\n' ? size - 1 : size;
    uint64_t uid = 0;
    int valid = digits > 0 && digits <= 10 && record[0] >= '1' && record[0] <= '9';
    for (size_t i = 0; valid && i < digits; i++) {
        if (record[i] < '0' || record[i] > '9') valid = 0;
        else uid = uid * 10 + (unsigned)(record[i] - '0');
    }
    valid = valid && uid && (uint64_t)(uid_t)uid == uid &&
        !kiosk_material_sha256(record, size, s->crypto, s->deadline, digest);
    /* The broker owns root-only state with the platform's administrative group
     * (wheel on Fedora). Bind that exact verified group without relaxing the
     * root-group requirement for executables or any ancestor/alias source. */
    struct kiosk_host_spec spec = {.path = KIOSK_FRESH_ACCOUNT, .kind = S_IFREG, .mode = 0600,
        .sha256 = digest, .private_state_group = 1, .group = before.st_gid};
    if (valid) valid = !kiosk_host_proof_capture_until(&s->account, &s->roots, &spec, 1, s->deadline);
    if (valid) {
        const struct kiosk_host_row *row = kiosk_material_host_row(&s->account, KIOSK_FRESH_ACCOUNT);
        valid = row && kiosk_host_same(&row->info, &before);
    }
    if (valid) s->uid = (uid_t)uid;
    free(record); return valid ? 0 : -1;
}

static inline int kiosk_fresh_hex(const char *hex, unsigned char out[32])
{
    const char *digits = "0123456789abcdef";
    if (!kiosk_receipt_hex(hex)) return -1;
    for (unsigned i = 0; i < 32; i++) {
        const char *high = strchr(digits, hex[2 * i]);
        const char *low = strchr(digits, hex[2 * i + 1]);
        if (!high || !low) return -1;
        out[i] = (unsigned char)((high - digits) * 16 + (low - digits));
    }
    return 0;
}

/* This authority permits cleanup only. It is intentionally independent of a
 * valid semantic plan: a refused plan can still transfer exact owned scratch.
 * A malformed/ambiguous ticket retains the received descriptors for recovery;
 * neither an inode guess nor a directory sweep can substitute for the ticket.
 */
static inline int kiosk_fresh_adopt_ticket_until(struct kiosk_fresh_startup *s, uint64_t deadline)
{
    struct kiosk_material_json json = {0};
    struct kiosk_publication_member *members = NULL;
    struct stat parent, root; uint64_t identity[2], format;
    int result = -1;
    if (!s->failure.stage) s->stage = "ticket-json";
    if (!s->transferred_scratch || !s->child.reaped || s->ticket_adopted || s->response.count != 2 ||
        kiosk_preparation_json_fd(&json, s->response.fds[0], deadline)) goto done;
    unsigned ticket = kiosk_material_get(&json, 1, "ticket");
    const char *name = kiosk_material_property(&json, ticket, "name");
    unsigned set = kiosk_material_get(&json, ticket, "members");
    if (!s->failure.stage) s->stage = "ticket-root";
    if (!name || strlen(name) != 41 || strncmp(name, ".runtime-", 9) ||
        strspn(name + 9, "0123456789abcdef") != 32 ||
        kiosk_material_schema(&json, ticket, "format|name|root|parent|members", 5) ||
        kiosk_material_number(&json, ticket, "format", &format) || format != 1 ||
        !set || json.nodes[set].type != '{' || !json.nodes[set].count ||
        json.nodes[set].count > KIOSK_VIEW_ROWS - 4 || fstat(s->runtime, &parent) ||
        fstat(s->response.fds[1], &root) ||
        kiosk_preparation_array(&json, kiosk_material_get(&json, ticket, "parent"), identity, 2) ||
        identity[0] != (uint64_t)parent.st_dev || identity[1] != (uint64_t)parent.st_ino ||
        kiosk_preparation_array(&json, kiosk_material_get(&json, ticket, "root"), identity, 2) ||
        identity[0] != (uint64_t)root.st_dev || identity[1] != (uint64_t)root.st_ino) goto done;
    members = calloc(json.nodes[set].count, sizeof(*members)); if (!members) goto done;
    unsigned count = 0;
    if (!s->failure.stage) s->stage = "ticket-members";
    for (unsigned n = json.nodes[set].child; n; n = json.nodes[n].next) {
        const char *member = json.nodes[n].key;
        const char *number = !strncmp(member, "native-", 7) ? member + 7 : member;
        if (strcmp(member, "runtime.json") && (!*number || strspn(number, "0123456789") != strlen(number))) goto done;
        if (kiosk_receipt_before(deadline) || kiosk_preparation_array(&json, n, identity, 2) ||
            fstatat(s->response.fds[1], member, &members[count].info, AT_SYMLINK_NOFOLLOW) ||
            identity[0] != (uint64_t)members[count].info.st_dev || identity[1] != (uint64_t)members[count].info.st_ino) goto done;
        members[count++].name = (char *)member;
    }
    if (!s->failure.stage) s->stage = "ticket-publication";
    if (kiosk_publication_open_until(&s->publication, s->runtime, s->response.fds[1], name,
            members, count, deadline)) goto done;
    if (!s->failure.stage) s->stage = "ticket-membership";
    if (kiosk_publication_members(&s->publication)) {
        kiosk_publication_close(&s->publication); goto done;
    }
    s->ticket_adopted = 1; result = 0;
done:
    free(members); free(json.storage); free(json.nodes); return result;
}

static inline int kiosk_fresh_boot_until(struct kiosk_fresh_startup *s)
{
    char bytes[38] = {0}; int fd = open("/proc/sys/kernel/random/boot_id", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    ssize_t n = fd < 0 ? -1 : pread(fd, bytes, sizeof(bytes), 0);
    if (fd >= 0) close(fd);
    if (n != 37 || bytes[36] != '\n' || strspn(bytes, "0123456789abcdef-") != 36 ||
        bytes[8] != '-' || bytes[13] != '-' || bytes[18] != '-' || bytes[23] != '-' ||
        kiosk_pin_before(s->deadline)) return -1;
    for (unsigned i = 0; i < 36; i++)
        if (i != 8 && i != 13 && i != 18 && i != 23 && bytes[i] == '-') return -1;
    memcpy(s->boot, bytes, 36); s->boot[36] = 0; return 0;
}

static inline int kiosk_fresh_marker_until(struct kiosk_fresh_startup *s)
{
    int parent = -1; char name[PATH_MAX];
    int length = snprintf(s->marker_bytes, sizeof(s->marker_bytes), "ONPC-KIOSK-VIEW\t1\t%s\t%s\t%s\n",
        s->authority.backend, s->authority.digest, s->realized.receipt.digest);
    if (length <= 0 || length >= (int)sizeof(s->marker_bytes)) return -1;
    s->marker_size = (size_t)length;
    parent = kiosk_parent(s->realized.root, KIOSK_FRESH_MARKER + 5, name);
    if (parent < 0) return -1;
    s->marker = openat(parent, name, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    struct stat opened, named;
    unsigned long long parent_mount, marker_mount;
    int owned = s->marker >= 0 && !fstat(s->marker, &opened) && S_ISREG(opened.st_mode) &&
        opened.st_nlink == 1 && !fstatat(parent, name, &named, AT_SYMLINK_NOFOLLOW) &&
        S_ISREG(named.st_mode) && named.st_nlink == 1 && kiosk_pin_same_stat(&opened, &named) &&
        !kiosk_pin_fd_mount(parent, &parent_mount) &&
        !kiosk_pin_fd_mount(s->marker, &marker_mount) && parent_mount == marker_mount;
    close(parent);
    if (!owned) return -1;
    if (s->realized.selinux) {
        const char context[] = "system_u:object_r:onpc_kiosk_runtime_t:s0";
        if (fsetxattr(s->marker, "security.selinux", context, sizeof(context), 0)) return -1;
    }
    size_t offset = 0;
    while (offset < s->marker_size) {
        if (kiosk_pin_before(s->deadline)) return -1;
        ssize_t n = write(s->marker, s->marker_bytes + offset, s->marker_size - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        offset += (size_t)n;
    }
    return !kiosk_private_initialize(s->marker, 0444, 1) && !fstat(s->marker, &s->marker_info) &&
        !kiosk_realization_marker_until(&s->realized, KIOSK_FRESH_MARKER, s->marker,
            s->marker_bytes, s->marker_size, s->deadline, &s->failure) ? 0 : -1;
}

static inline int kiosk_fresh_marker_check(struct kiosk_fresh_startup *s)
{
    struct stat actual; char bytes[256];
    int fd = kiosk_pin_open(s->pin.fd, KIOSK_FRESH_MARKER + 5);
    if (fd < 0) return -1;
    int valid = !fstat(fd, &actual) && kiosk_pin_same_stat(&actual, &s->marker_info);
    close(fd);
    fd = openat(s->pin.fd, KIOSK_FRESH_MARKER + 5, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    valid = valid && fd >= 0 && pread(fd, bytes, s->marker_size, 0) == (ssize_t)s->marker_size &&
        !memcmp(bytes, s->marker_bytes, s->marker_size) && !fstat(fd, &actual) &&
        kiosk_pin_same_stat(&actual, &s->marker_info) && !kiosk_pin_before(s->deadline);
    if (fd >= 0) close(fd);
    return valid ? 0 : -1;
}

static inline int kiosk_fresh_record_check(struct kiosk_fresh_startup *s, const char *name,
    const void *expected, size_t expected_size)
{
    char *actual = NULL; size_t size = 0;
    int fd = openat(s->publication.root, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    int result = fd >= 0 && !kiosk_publication_read(fd, &actual, &size, s->deadline) &&
        size == expected_size && !memcmp(actual, expected, size) ? 0 : -1;
    if (fd >= 0) close(fd);
    free(actual); return result;
}

static inline int kiosk_fresh_runtime_current(struct kiosk_fresh_startup *s)
{
    struct stat opened, named; unsigned long long original_mount, named_mount;
    int fd = open(KIOSK_CONFINEMENT_RUNTIME, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int valid = s->runtime >= 0 && fd >= 0 && !fstat(s->runtime, &opened) &&
        !fstat(fd, &named) && kiosk_publication_private(&named, 1) &&
        opened.st_dev == named.st_dev && opened.st_ino == named.st_ino &&
        !kiosk_pin_fd_mount(s->runtime, &original_mount) && !kiosk_pin_fd_mount(fd, &named_mount) &&
        original_mount == named_mount;
    if (fd >= 0) close(fd);
    return valid ? 0 : -1;
}

static inline int kiosk_fresh_final_proofs(struct kiosk_fresh_startup *s, int lock, int lease)
{
    return !kiosk_fresh_runtime_current(s) &&
        !kiosk_host_proof_recheck(&s->account, s->account.specs, s->account.requested) &&
        !kiosk_material_verify_host_until(&s->authority, &s->host) &&
        !kiosk_material_verify_routes_until(&s->authority, &s->host) &&
        !kiosk_policy_recheck_until(&s->policy, s->deadline) &&
        !kiosk_fresh_marker_check(s) &&
        !kiosk_realization_verify_source_until(s->pin.fd, &s->realized.receipt, &s->authority,
            KIOSK_FRESH_MARKER, s->realized.entries, s->realized.entry_count, NULL, s->crypto,
            s->deadline, &s->failure) &&
        !kiosk_fresh_marker_check(s) && !kiosk_publication_members(&s->publication) &&
        !kiosk_fresh_record_check(s, "material.json", s->material_bytes, s->material_size) &&
        !kiosk_fresh_record_check(s, "view", s->realized.bytes, s->realized.size) &&
        !kiosk_fresh_record_check(s, "pins", s->inventory_bytes, s->inventory_size) &&
        !kiosk_fresh_locks(lock, lease) && !kiosk_pin_before(s->deadline) ? 0 : -1;
}

/* Free only descriptors whose owned work has ended. Lock/lease are borrowed
 * from the PAM owner and deliberately never closed or unlocked here. */
static inline void kiosk_fresh_descriptors_close(struct kiosk_fresh_startup *s)
{
    kiosk_preparation_response_close(&s->measurement);
    kiosk_preparation_response_close(&s->response);
    kiosk_host_proof_close(&s->host); kiosk_host_proof_close(&s->account);
    kiosk_policy_close(&s->policy); kiosk_host_roots_close(&s->roots);
    kiosk_publication_close(&s->publication);
    if (s->runtime >= 0) close(s->runtime);
    if (s->skeleton >= 0) close(s->skeleton);
    if (s->target_parent >= 0) close(s->target_parent);
    if (s->marker >= 0) close(s->marker);
    s->runtime = s->skeleton = s->target_parent = s->marker = -1;
    if (s->realized.root >= 0) { close(s->realized.root); s->realized.root = -1; }
    if (s->view.root >= 0) { close(s->view.root); s->view.root = -1; }
    if (s->crypto) { dlclose(s->crypto); s->crypto = NULL; }
}

/* Explicit failed-attempt recovery may have its own budget. It never changes
 * s->deadline, retries admission, accepts an unfinished child or removes ready.
 * Retain the owner state when a child, identity or mount cannot be resolved.
 */
static inline int kiosk_fresh_recover_until(struct kiosk_fresh_startup *s, uint64_t recovery_deadline)
{
    uint64_t ns;
    /* A failed ambient bind undo owns a cleanup witness even when subsequent
     * recovery succeeds. Keep it before any early recovery/deadline refusal. */
    if (s && s->realized.cleanup_failure.stage)
        kiosk_failure(&s->cleanup_failure, s->realized.cleanup_failure.stage,
            s->realized.cleanup_failure.reason, s->realized.cleanup_failure.error);
    if (s && s->recovered) return 0;
    if (!s || s->armed || kiosk_preparation_deadline_ns(recovery_deadline, &ns)) return -1;
    if (s->child.started && !s->child.reaped && kiosk_preparation_cancel_until(&s->child, ns)) return -1;
    if (s->transferred_scratch && !s->ticket_adopted &&
        kiosk_fresh_adopt_ticket_until(s, recovery_deadline)) return -1;
    if (kiosk_pin_before(recovery_deadline) || kiosk_pin_release(&s->pin, 0, &s->cleanup_failure)) return -1;
    for (unsigned i = s->realized.stage_count; i > 0; i--) {
        struct kiosk_owned_mount *stage = &s->realized.stages[i - 1];
        if (kiosk_pin_before(recovery_deadline)) return -1;
        if (stage->live) {
            if (!stage->id || kiosk_detach_owned(stage->path, stage->id, &s->cleanup_failure)) return -1;
            stage->live = 0;
        }
    }
    int view_cleanup = cleanup_kiosk_view(&s->view, 0);
    /* The view owner can fail after setup FDs have closed. Preserve its first
     * exact cleanup cause before the caller adds a generic recovery failure or
     * projects the transaction's diagnostic back into the view. */
    if (s->view.cleanup_failure.stage)
        kiosk_failure(&s->cleanup_failure, s->view.cleanup_failure.stage,
            s->view.cleanup_failure.reason, s->view.cleanup_failure.error);
    if (view_cleanup) return -1;
    if (s->ticket_adopted && !s->ready && kiosk_publication_abort_until(&s->publication, recovery_deadline)) return -1;
    s->transferred_scratch = 0; s->ticket_adopted = 0;
    kiosk_fresh_descriptors_close(s); s->recovered = 1; return 0;
}

/* Closing cannot drop an unreaped child or discard unresolved scratch/mount
 * ownership. Call recovery explicitly first after a refused transaction. */
static inline int kiosk_fresh_close(struct kiosk_fresh_startup *s)
{
    if (!s || s->closed) return s ? 0 : -1;
    if ((s->child.started && !s->child.reaped) || s->transferred_scratch ||
        s->pin.attached || s->pin.worker >= 0 || s->view.mounted || (!s->armed && s->view.cloned)) return -1;
    for (unsigned i = 0; i < s->realized.stage_count; i++) if (s->realized.stages[i].live) return -1;
    kiosk_fresh_descriptors_close(s);
    kiosk_preparation_plan_free(&s->plan); kiosk_material_free(&s->authority);
    kiosk_realization_close(&s->realized);
    for (unsigned i = 0; i < s->view.count; i++) free(s->view.mounts[i].path);
    free(s->view.mounts); s->view.mounts = NULL; s->view.count = 0;
    free(s->material_bytes); free(s->config_bytes); free(s->inventory_bytes);
    s->material_bytes = s->config_bytes = s->inventory_bytes = NULL;
    if (s->mac.library) { KIOSK_FRESH_DLCLOSE(s->mac.library); s->mac.library = NULL; }
    s->closed = 1; return 0;
}

/* One production composition, callable by the maintained native/PAM fixture.
 * The caller starts the deadline once and retains preparation ownership through
 * return. There is no retained-manager acquisition or fallback in this route.
 */
static inline int kiosk_fresh_startup_until(struct kiosk_fresh_startup *s, pam_handle_t *pamh,
    int lock, int lease, uint64_t deadline)
{
    unsigned char material[32], zero[32] = {0}, random[32];
    struct stat runtime, named, target, parent;
    struct kiosk_pin_target destination;
    struct kiosk_owned_mount *stages = NULL;
    int result = -1, runtime_parent = -1;
    if (!s || s->attempted || s->closed || s->recovered) return -1;
    s->attempted = 1; s->deadline = deadline; s->stage = "identity";
    const char *username = NULL, *service = NULL;
    uint64_t now;
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || !username || strcmp(username, KIOSK_ACCOUNT_NAME) ||
        pam_get_item(pamh, PAM_SERVICE, (const void **)&service) != PAM_SUCCESS ||
        !service || strcmp(service, "systemd-user") || kiosk_private_fsuid() ||
        kiosk_pin_now(&now) || deadline <= now || deadline - now > 60000000ULL ||
        kiosk_preparation_deadline_ns(deadline, &s->child.deadline_ns) || lock == lease ||
        kiosk_admission_current(lease) || flock(lease, LOCK_SH | LOCK_NB) ||
        kiosk_lock_identity(lock, KIOSK_CONFINEMENT_LOCK, 0) || flock(lock, LOCK_EX | LOCK_NB) ||
        kiosk_fresh_locks(lock, lease)) goto done;
    s->stage = "host";
    if (kiosk_host_roots_open(&s->roots) ||
        !(s->crypto = dlopen("libcrypto.so.3", RTLD_NOW | RTLD_LOCAL))) goto done;
    s->stage = "runtime";
    /* Pin trusted /run before mkdir. Its root-owned, non-writable namespace
     * plus the preparation lock excludes peer creation/rename; a privileged
     * administrator replacing it is outside the kiosk threat boundary. A new
     * runtime must still be on this exact parent mount before any mutation. */
    struct stat runtime_parent_info;
    unsigned long long runtime_parent_mount;
    runtime_parent = open("/run", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (runtime_parent < 0 || fstat(runtime_parent, &runtime_parent_info) ||
        !S_ISDIR(runtime_parent_info.st_mode) || !kiosk_host_trust(&runtime_parent_info) ||
        kiosk_pin_fd_mount(runtime_parent, &runtime_parent_mount)) goto done;
    int created = !mkdir(KIOSK_CONFINEMENT_RUNTIME, 0700);
    if ((!created && errno != EEXIST) ||
        (s->runtime = open(KIOSK_CONFINEMENT_RUNTIME, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
        fstat(s->runtime, &runtime) || !S_ISDIR(runtime.st_mode) ||
        lstat(KIOSK_CONFINEMENT_RUNTIME, &named) || !kiosk_pin_same_stat(&runtime, &named)) goto done;
    /* mkdir success is the creation authority. Existing runtime roots never
     * receive ownership or mode repair, including after an EEXIST race. */
    if (created) {
        unsigned long long opened_mount, named_mount;
        int named_fd = open(KIOSK_CONFINEMENT_RUNTIME, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        int owned = named_fd >= 0 && !fstat(named_fd, &named) && kiosk_pin_same_stat(&runtime, &named) &&
            !kiosk_pin_fd_mount(s->runtime, &opened_mount) && !kiosk_pin_fd_mount(named_fd, &named_mount) &&
            opened_mount == named_mount && opened_mount == runtime_parent_mount && !kiosk_pin_before(deadline);
        if (named_fd >= 0) close(named_fd);
        if (!owned) goto done;
    }
    if ((created && kiosk_private_initialize(s->runtime, 0700, 1)) ||
        fstat(s->runtime, &runtime) || !kiosk_publication_private(&runtime, 1) ||
        lstat(KIOSK_CONFINEMENT_RUNTIME, &named) || !kiosk_pin_same_stat(&runtime, &named) ||
        setup_kiosk_view(&s->view)) goto done;
    close(runtime_parent); runtime_parent = -1;
    s->stage = "host-anchor";
    if (kiosk_fresh_reanchor_until(s) || kiosk_fresh_account_until(s)) goto done;
    s->stage = "helper-launch";
    if (kiosk_fresh_locks(lock, lease) || kiosk_preparation_launch(&s->child, "manager", lock, lease, deadline)) goto done;
    s->stage = "measurement";
    if (kiosk_preparation_child_measurement(&s->child, 1, &s->measurement)) {
        if (s->child.refusal) kiosk_failure(&s->failure, "measurement",
            kiosk_preparation_refusal_reason(s->child.refusal), -1);
        goto done;
    }
    if (s->child.account.uid != s->uid ||
        kiosk_publication_read(s->measurement.fds[0], &s->material_bytes, &s->material_size, deadline) ||
        kiosk_publication_read(s->measurement.fds[1], &s->config_bytes, &s->config_size, deadline)) goto done;
    s->stage = "authority";
    if (kiosk_policy_acquire_until(&s->policy, &s->roots, s->config_bytes, s->config_size, s->crypto, deadline) ||
        kiosk_material_decode_until(&s->authority, s->material_bytes, s->material_size,
            s->policy.config, s->policy.config_size, s->policy.policy, s->policy.policy_size, s->crypto, deadline) ||
        strcmp(s->policy.backend, s->authority.backend) ||
        s->child.backend != (!strcmp(s->authority.backend, "apparmor") ? 1U : 2U) ||
        kiosk_fresh_hex(s->authority.digest, material) || memcmp(material, s->child.material, 32) ||
        kiosk_host_proof_capture_until(&s->host, &s->roots, s->authority.host_specs, s->authority.host_count, deadline) ||
        kiosk_material_verify_host_until(&s->authority, &s->host) || kiosk_material_verify_routes_until(&s->authority, &s->host) ||
        kiosk_fresh_mac_preload(&s->mac, s->authority.backend) ||
        s->view.selinux != !strcmp(s->authority.backend, "selinux")) goto done;
    memcpy(s->material, s->authority.digest, sizeof(s->material));
    s->stage = "selection";
    int selection[] = {s->view.root};
    if (kiosk_fresh_locks(lock, lease) || kiosk_preparation_child_select(&s->child, 1, s->child.backend,
            material, zero, selection, 1)) goto done;
    /* A send may have succeeded at the helper even when native rejects its
     * response. Record that ambiguity before receiving; never silently forget
     * potentially transferred scratch on a bad packet or helper identity. */
    s->transferred_scratch = 1;
    if (kiosk_preparation_child_result(&s->child, 1, s->child.backend, material, zero, &s->response)) goto done;
    s->stage = "reap";
    if (kiosk_preparation_finish(&s->child)) goto done;
    s->stage = "copy-ticket";
    if (kiosk_fresh_locks(lock, lease) || kiosk_fresh_adopt_ticket_until(s, deadline)) goto done;
    s->stage = "copy-plan";
    if (kiosk_preparation_plan_verify_until(&s->plan, s->response.fds[0], s->response.fds[1],
            &s->authority, &s->host, NULL, -1, s->crypto, deadline)) goto done;
    s->stage = "copy-parent";
    if ((uint64_t)runtime.st_dev != s->plan.ticket_parent[0] ||
        (uint64_t)runtime.st_ino != s->plan.ticket_parent[1]) goto done;
    s->stage = "realization";
    size_t random_used = 0;
    while (random_used < sizeof(random)) {
        if (kiosk_pin_before(deadline)) goto done;
        ssize_t n = getrandom(random + random_used, sizeof(random) - random_used, GRND_NONBLOCK);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) goto done;
        random_used += (size_t)n;
    }
    for (unsigned i = 0; i < sizeof(random); i++) snprintf(s->acquisition + i * 2, 3, "%02x", random[i]);
    s->skeleton = openat(s->view.root, "tree", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (s->skeleton < 0 || kiosk_realization_bind_until(&s->realized, s->skeleton, &s->plan, &s->authority,
            &s->roots, -1, s->response.fds[1], NULL, s->acquisition, s->crypto, deadline, &s->failure) ||
        kiosk_fresh_marker_until(s) || kiosk_fresh_boot_until(s) ||
        kiosk_publication_inventory_encode(s->realized.entries, s->realized.entry_count,
            &s->inventory_bytes, &s->inventory_size, deadline) ||
        kiosk_material_sha256(s->inventory_bytes, s->inventory_size, s->crypto, deadline, s->inventory)) goto done;
    strcpy(s->generation, s->realized.receipt.digest);
    s->stage = "attachment";
    s->target_parent = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int target_fd = s->target_parent < 0 ? -1 : openat(s->target_parent, "usr", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    unsigned long long parent_mount, target_mount;
    int valid = target_fd >= 0 && !fstat(s->target_parent, &parent) && !fstat(target_fd, &target) &&
        !kiosk_pin_fd_mount(s->target_parent, &parent_mount) && !kiosk_pin_fd_mount(target_fd, &target_mount);
    if (target_fd >= 0) close(target_fd);
    if (!valid) goto done;
    destination = (struct kiosk_pin_target){.parent_device = parent.st_dev, .parent_inode = parent.st_ino,
        .device = target.st_dev, .inode = target.st_ino, .parent_mount = parent_mount, .mount = target_mount};
    if (kiosk_realization_attach_until(&s->realized, &s->pin, s->target_parent, "usr", &destination, deadline, &s->failure)) goto done;
    s->stage = "staging";
    if (s->realized.stage_count >= KIOSK_VIEW_ROWS ||
        !(stages = calloc(s->realized.stage_count + 1, sizeof(*stages)))) goto done;
    stages[0] = (struct kiosk_owned_mount){.path = (char *)KIOSK_CONFINEMENT_VIEW, .id = s->view.root_id, .live = s->view.mounted};
    for (unsigned i = 0; i < s->realized.stage_count; i++) stages[i + 1] = s->realized.stages[i];
    int finished = kiosk_pin_finish_until(&s->pin, stages, s->realized.stage_count + 1,
        s->realized.entries, s->realized.entry_count, deadline, &s->failure);
    s->view.mounted = stages[0].live;
    for (unsigned i = 0; i < s->realized.stage_count; i++) s->realized.stages[i].live = stages[i + 1].live;
    free(stages); stages = NULL;
    if (finished) goto done;
    s->stage = "publication";
    if (kiosk_publication_write(&s->publication, "material.json", s->material_bytes, s->material_size, s->realized.selinux) ||
        kiosk_publication_write(&s->publication, "view", s->realized.bytes, s->realized.size, s->realized.selinux) ||
        kiosk_publication_write(&s->publication, "pins", s->inventory_bytes, s->inventory_size, s->realized.selinux) ||
        kiosk_fresh_final_proofs(s, lock, lease) ||
        kiosk_publication_rename_until(&s->publication, s->generation) ||
        kiosk_publication_ready_until(&s->publication, &s->pin, s->material, s->generation,
            s->inventory, s->boot, &s->marker_info, s->realized.selinux)) goto done;
    s->ready = 1; s->pin.published = 1;
    s->stage = "final-proof";
    if (kiosk_fresh_final_proofs(s, lock, lease)) goto done;
    s->stage = "environment";
    if (pam_putenv(pamh, "SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:") != PAM_SUCCESS) goto done;
    s->stage = "ambient";
    if (kiosk_fresh_capabilities_until(deadline)) goto done;
    s->stage = "closure";
    /* Transfer only the actual attachment's cleanup identity before closing
     * setup FDs. A final MAC refusal still detaches that exact private mount. */
    s->view.cloned = 1; s->view.clone_id = s->pin.attached_id;
    if (kiosk_pin_release(&s->pin, 1, &s->cleanup_failure)) goto done;
    s->pin.attached = 0;
    s->transferred_scratch = 0;
    kiosk_fresh_descriptors_close(s);
    s->stage = "lock";
    if (kiosk_fresh_locks(lock, lease) || kiosk_pin_before(deadline)) goto done;
    s->stage = "mac";
    if (kiosk_fresh_mac_apply(&s->mac) || kiosk_pin_before(deadline)) goto done;
    s->armed = 1; s->stage = "armed"; result = 0;
done:
    if (runtime_parent >= 0) close(runtime_parent);
    free(stages);
    if (s->publication.ready) s->ready = 1;
    if (result) {
        kiosk_failure(&s->failure, s->stage, "refused", -1);
        if (kiosk_fresh_recover_until(s, deadline)) kiosk_failure(&s->cleanup_failure, "recovery", "unresolved", -1);
    }
    return result;
}
#endif
