#ifndef ONPC_KIOSK_POLICY_AUTHORITY_H
#define ONPC_KIOSK_POLICY_AUTHORITY_H
/* Native attestation and loaded-enforcement observations. The preparation
 * helper still owns the complete PAM-stack audit. This owner never executes a
 * program, loads policy, repairs a record or renews the transaction deadline.
 * Acquire before /usr attachment; final reads use the original host anchors.
 */
#include "kiosk_material_authority.h"

#define KIOSK_POLICY_STATE "/var/lib/oh-no-parent-control/kiosk-confinement.json"
#define KIOSK_POLICY_CONFIG "/usr/share/oh-no-parent-control/confinement/config.json"
#define KIOSK_POLICY_PROFILES "/sys/kernel/security/apparmor/profiles"
#ifndef KIOSK_POLICY_DLOPEN
#define KIOSK_POLICY_DLOPEN dlopen
#endif
#ifndef KIOSK_POLICY_DLSYM
#define KIOSK_POLICY_DLSYM dlsym
#endif
#ifndef KIOSK_POLICY_DLCLOSE
#define KIOSK_POLICY_DLCLOSE dlclose
#endif

struct kiosk_policy_authority {
    struct kiosk_host_proof host;
    struct kiosk_material_json configuration;
    char *config, *policy;
    size_t config_size, policy_size;
    const char *backend;
    void *selinux;
    uint64_t deadline;
    int initialized, acquired, failed;
};

static inline void kiosk_policy_close(struct kiosk_policy_authority *p)
{
    if (!p) return;
    if (p->initialized) kiosk_host_proof_close(&p->host);
    free(p->configuration.storage); free(p->configuration.nodes);
    free(p->config); free(p->policy);
    if (p->selinux) KIOSK_POLICY_DLCLOSE(p->selinux);
    memset(p, 0, sizeof(*p)); p->host.roots.root = p->host.roots.usr = -1;
}

/* These three package paths have no lexical aliases. Never follow even a
 * root-owned link here: Python's payload/state safe() has the same rule. */
static inline int kiosk_policy_open(const struct kiosk_host_roots *roots, const char *path)
{
    char name[PATH_MAX]; struct stat info;
    int fd = -1, child = -1;
    if (!roots || !path || !kiosk_material_path(path) || strlen(path) >= sizeof(name)) return -1;
    strcpy(name, path + 1);
    char *part = name;
    if (!strncmp(path, "/usr/", 5)) { fd = fcntl(roots->usr, F_DUPFD_CLOEXEC, 3); part += 4; }
    else fd = fcntl(roots->root, F_DUPFD_CLOEXEC, 3);
    if (fd < 0 || fstat(fd, &info) || !S_ISDIR(info.st_mode) || !kiosk_host_trust(&info)) goto failed;
    for (;;) {
        char *slash = strchr(part, '/');
        if (slash) *slash = 0;
        child = openat(fd, part, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC | (slash ? O_DIRECTORY : 0));
        if (child < 0 || fstat(child, &info) || !kiosk_host_trust(&info) ||
            (slash ? !S_ISDIR(info.st_mode) : !S_ISREG(info.st_mode))) goto failed;
        close(fd); fd = child; child = -1;
        if (!slash) return fd;
        part = slash + 1;
    }
failed:
    if (child >= 0) close(child);
    if (fd >= 0) close(fd);
    return -1;
}

static inline int kiosk_policy_read(const struct kiosk_host_roots *roots, const char *path,
    uint64_t deadline, char **bytes, size_t *size, struct stat *identity, int state)
{
    struct stat after; char *data = NULL; int result = -1;
    int fd = kiosk_policy_open(roots, path);
    if (fd < 0 || kiosk_host_before(deadline) || fstat(fd, identity) || identity->st_nlink != 1 ||
        (identity->st_mode & 06000) || (state && (identity->st_mode & 07777) != 0600) ||
        identity->st_size <= 0 || (uint64_t)identity->st_size > KIOSK_RECEIPT_BYTES) goto done;
    size_t length = (size_t)identity->st_size;
    data = malloc(length + 1); if (!data) goto done;
    size_t offset = 0;
    while (offset < length) {
        if (kiosk_host_before(deadline)) goto done;
        ssize_t n = pread(fd, data + offset, length - offset, (off_t)offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) goto done;
        offset += (size_t)n;
    }
    char extra;
    if (pread(fd, &extra, 1, (off_t)length) != 0 || fstat(fd, &after) ||
        !kiosk_host_same(identity, &after) || kiosk_host_before(deadline)) goto done;
    data[length] = 0; *bytes = data; *size = length; data = NULL; result = 0;
done:
    free(data); if (fd >= 0) close(fd); return result;
}

static inline int kiosk_policy_apparmor(struct kiosk_policy_authority *p)
{
    struct kiosk_material_json *j = &p->configuration;
    unsigned profiles = kiosk_material_get(j, 1, "apparmor_profiles");
    if (!profiles || j->nodes[profiles].type != '[' || !j->nodes[profiles].count) return -1;
    int fd = kiosk_policy_open(&p->host.roots, KIOSK_POLICY_PROFILES);
    char *bytes = NULL; size_t size = 0, capacity = 0; int result = -1;
    if (fd < 0) goto done;
    for (;;) {
        if (kiosk_host_before(p->deadline) || size == KIOSK_RECEIPT_BYTES) goto done;
        if (capacity - size < 4096) {
            size_t next = capacity ? capacity * 2 : 4096;
            if (next > KIOSK_RECEIPT_BYTES + 1ULL) next = KIOSK_RECEIPT_BYTES + 1ULL;
            void *allocation = realloc(bytes, next); if (!allocation) goto done;
            bytes = allocation; capacity = next;
        }
        ssize_t n = read(fd, bytes + size, capacity - size - 1);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) goto done;
        if (!n) break;
        size += (size_t)n;
    }
    if (!bytes || memchr(bytes, 0, size)) goto done;
    bytes[size] = 0;
    for (unsigned n = j->nodes[profiles].child; n; n = j->nodes[n].next) {
        const char *profile = kiosk_material_text(j, n); int found = 0;
        if (!profile || !kiosk_receipt_text(profile) || !profile[0]) goto done;
        size_t length = strlen(profile);
        for (const char *line = bytes; *line;) {
            if (kiosk_host_before(p->deadline)) goto done;
            const char *end = strchr(line, '\n'); size_t count = end ? (size_t)(end - line) : strlen(line);
            if (count == length + 10 && !memcmp(line, profile, length) && !memcmp(line + length, " (enforce)", 10)) found = 1;
            line += count; if (*line) line++;
        }
        if (!found) goto done;
    }
    result = kiosk_host_before(p->deadline);
done:
    free(bytes); if (fd >= 0) close(fd); return result;
}

struct kiosk_policy_decision {
    uint32_t allowed, decided, auditallow, auditdeny, seqno, flags;
};

static inline int kiosk_policy_selinux(struct kiosk_policy_authority *p)
{
    int (*enabled)(void) = (int (*)(void))KIOSK_POLICY_DLSYM(p->selinux, "is_selinux_enabled");
    int (*enforcing)(void) = (int (*)(void))KIOSK_POLICY_DLSYM(p->selinux, "security_getenforce");
    unsigned short (*class_of)(const char *) = (unsigned short (*)(const char *))KIOSK_POLICY_DLSYM(p->selinux, "string_to_security_class");
    uint32_t (*permission)(unsigned short, const char *) = (uint32_t (*)(unsigned short, const char *))KIOSK_POLICY_DLSYM(p->selinux, "string_to_av_perm");
    int (*compute)(const char *, const char *, unsigned short, uint32_t, struct kiosk_policy_decision *) =
        (int (*)(const char *, const char *, unsigned short, uint32_t, struct kiosk_policy_decision *))
        KIOSK_POLICY_DLSYM(p->selinux, "security_compute_av_flags_raw");
    if (!enabled || !enforcing || !class_of || !permission || !compute ||
        kiosk_host_before(p->deadline) || enabled() != 1 || enforcing() != 1) return -1;
    unsigned short cls = class_of("process"); uint32_t perm = cls ? permission(cls, "ptrace") : 0;
    if (!cls || !perm) return -1;
    struct kiosk_material_json *j = &p->configuration;
    unsigned domains = kiosk_material_get(j, 1, "domains");
    unsigned preserved = kiosk_material_get(j, 1, "preserved_executables");
    if (!domains || j->nodes[domains].type != '[' || !j->nodes[domains].count ||
        !preserved || j->nodes[preserved].type != '[') return -1;
    for (unsigned n = j->nodes[domains].child, vendor = !!j->nodes[preserved].count; n || vendor;) {
        char context[256];
        if (n) {
            const char *domain = kiosk_material_text(j, n);
            if (!domain || !*domain || strlen(domain) > 128) return -1;
            for (const char *s = domain; *s; s++) if ((*s < 'a' || *s > 'z') && *s != '-') return -1;
            int length = snprintf(context, sizeof(context), "system_u:system_r:onpc_kiosk_%s_t:s0", domain);
            if (length <= 0 || length >= (int)sizeof(context)) return -1;
            for (char *s = context; *s; s++) if (*s == '-') *s = '_';
            n = j->nodes[n].next;
        } else { strcpy(context, "system_u:system_r:policykit_auth_t:s0"); vendor = 0; }
        struct kiosk_policy_decision decision = {0};
        if (kiosk_host_before(p->deadline) || compute(context, context, cls, perm, &decision) ||
            (decision.flags & 1U)) return -1;
    }
    return kiosk_host_before(p->deadline);
}

static inline int kiosk_policy_enforcing(struct kiosk_policy_authority *p)
{
    return !strcmp(p->backend, "apparmor") ? kiosk_policy_apparmor(p) : kiosk_policy_selinux(p);
}

/* Config is the measurement descriptor's exact bytes, independently matched
 * against the original package input. crypto must be preloaded by the caller.
 * admission_protocol/prelease_upgrade_boot_id belong to removal migration:
 * Python verify does not turn them into an admission or boot freshness gate.
 */
static inline int kiosk_policy_acquire_until(struct kiosk_policy_authority *p,
    const struct kiosk_host_roots *roots, const void *expected_config, size_t expected_size,
    void *crypto, uint64_t deadline)
{
    struct kiosk_material_json state = {0}; char *record = NULL; size_t record_size = 0;
    struct stat identities[3]; char hashes[3][65]; const char *paths[3] = {KIOSK_POLICY_STATE, KIOSK_POLICY_CONFIG, NULL};
    memset(p, 0, sizeof(*p)); p->host.roots.root = p->host.roots.usr = -1; p->deadline = deadline; p->initialized = 1;
    if (!expected_config || !expected_size || !crypto || kiosk_host_before(deadline) ||
        kiosk_policy_read(roots, paths[0], deadline, &record, &record_size, identities, 1) ||
        kiosk_material_json_parse(&state, record, record_size, deadline)) goto failed;
    uint64_t schema; unsigned pam = kiosk_material_get(&state, 1, "pam");
    if (kiosk_material_number(&state, 1, "schema", &schema) || schema != 1 ||
        kiosk_material_schema(&state, pam, "gdm-password|systemd-user", 2)) goto failed;
    const char *backend = kiosk_material_property(&state, 1, "backend");
    if (!backend || (strcmp(backend, "apparmor") && strcmp(backend, "selinux"))) goto failed;
    paths[2] = !strcmp(backend, "apparmor") ? "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor" :
        "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.cil";
    if (kiosk_policy_read(roots, paths[1], deadline, &p->config, &p->config_size, identities + 1, 0) ||
        p->config_size != expected_size || memcmp(p->config, expected_config, expected_size) ||
        kiosk_policy_read(roots, paths[2], deadline, &p->policy, &p->policy_size, identities + 2, 0) ||
        record_size > KIOSK_RECEIPT_BYTES - p->config_size ||
        p->policy_size > KIOSK_RECEIPT_BYTES - record_size - p->config_size ||
        kiosk_material_json_parse(&p->configuration, p->config, p->config_size, deadline)) goto failed;
    p->backend = kiosk_material_property(&p->configuration, 1, "backend");
    if (!p->backend || strcmp(p->backend, backend) ||
        kiosk_material_sha256(record, record_size, crypto, deadline, hashes[0]) ||
        kiosk_material_sha256(p->config, p->config_size, crypto, deadline, hashes[1]) ||
        kiosk_material_sha256(p->policy, p->policy_size, crypto, deadline, hashes[2]) ||
        !kiosk_material_equal(kiosk_material_property(&state, 1, "loaded_config_sha256"), hashes[1]) ||
        !kiosk_material_equal(kiosk_material_property(&state, 1, "loaded_policy_sha256"), hashes[2])) goto failed;
    struct kiosk_host_spec specs[3]; memset(specs, 0, sizeof(specs));
    for (unsigned i = 0; i < 3; i++) { specs[i].path = paths[i]; specs[i].kind = S_IFREG; specs[i].sha256 = hashes[i]; }
    specs[0].mode = 0600;
    if (kiosk_host_proof_capture_until(&p->host, roots, specs, 3, deadline)) goto failed;
    for (unsigned i = 0; i < 3; i++) {
        const struct kiosk_host_row *row = kiosk_material_host_row(&p->host, paths[i]);
        if (!row || !kiosk_host_same(&row->info, identities + i)) goto failed;
    }
    if (!strcmp(p->backend, "selinux")) {
        p->selinux = KIOSK_POLICY_DLOPEN("libselinux.so.1", RTLD_NOW | RTLD_LOCAL);
        if (!p->selinux) goto failed;
    }
    if (kiosk_policy_enforcing(p)) goto failed;
    p->acquired = 1;
    free(record); free(state.storage); free(state.nodes); return 0;
failed:
    free(record); free(state.storage); free(state.nodes); kiosk_policy_close(p); p->failed = 1; return -1;
}

static inline int kiosk_policy_recheck_until(struct kiosk_policy_authority *p, uint64_t deadline)
{
    if (!p || !p->acquired || p->failed || deadline != p->deadline || kiosk_host_before(deadline) ||
        kiosk_host_proof_recheck(&p->host, p->host.specs, p->host.requested) || kiosk_policy_enforcing(p)) {
        if (p) p->failed = 1;
        return -1;
    }
    return 0;
}
#endif
