/* Original-host assertions for the native admission transaction.  This owner
 * never follows a kernel symlink: canonical entry into /usr always selects the
 * separately pinned original /usr, even after the caller attaches its view.
 * A capture is preparatory evidence, not authority to admit a retained view. */
#ifndef ONPC_KIOSK_HOST_PROOF_H
#define ONPC_KIOSK_HOST_PROOF_H
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <time.h>
#include <unistd.h>

#ifndef KIOSK_HOST_PROOF_OWNER
#define KIOSK_HOST_PROOF_OWNER 0
#endif
#ifndef KIOSK_HOST_PROOF_GROUP
#define KIOSK_HOST_PROOF_GROUP 0
#endif
#define KIOSK_HOST_PROOF_ROWS 32768U
#define KIOSK_HOST_PROOF_BYTES (64U * 1024U * 1024U)
#define KIOSK_HOST_FILE_BYTES (512ULL * 1024ULL * 1024ULL)
#ifndef KIOSK_HOST_CLOCK_GETTIME
#define KIOSK_HOST_CLOCK_GETTIME clock_gettime
#endif

struct kiosk_host_roots { int root, usr; };
struct kiosk_host_spec {
    const char *path;
    mode_t kind;                  /* S_IFDIR, S_IFREG or S_IFLNK. */
    const char *link, *sha256, *label;
    mode_t mode;                  /* Zero means no extra permission assertion. */
    int privileged, terminal_link; /* Only explicit masks stop at link text. */
};
struct kiosk_host_row {
    char *path, *link;
    struct stat info;
    char sha256[65], label[256];
    unsigned epoch;
};
struct kiosk_host_proof {
    struct kiosk_host_roots roots;
    struct kiosk_host_row *rows;
    unsigned count;
    struct kiosk_host_spec *specs;
    unsigned requested;
    size_t bytes;
    int sealed;
    unsigned epoch;
    void *crypto;
    uint64_t deadline, measured;
};

/* One absolute deadline belongs to the admission transaction, not each pass. */
static inline int kiosk_host_now(uint64_t *now)
{
    struct timespec value;
    if (KIOSK_HOST_CLOCK_GETTIME(CLOCK_MONOTONIC, &value) != 0 || value.tv_sec < 0 ||
        (uint64_t) value.tv_sec > (UINT64_MAX - 999999ULL) / 1000000ULL) return -1;
    *now = (uint64_t) value.tv_sec * 1000000ULL + (uint64_t) value.tv_nsec / 1000ULL;
    return 0;
}

static inline int kiosk_host_before(uint64_t deadline)
{
    uint64_t now;
    return deadline && kiosk_host_now(&now) == 0 && now < deadline ? 0 : -1;
}

static inline int kiosk_host_trust(const struct stat *info)
{
    return info->st_uid == KIOSK_HOST_PROOF_OWNER &&
        (S_ISLNK(info->st_mode) || !(info->st_mode & 022)) &&
        (S_ISDIR(info->st_mode) || S_ISREG(info->st_mode) || S_ISLNK(info->st_mode));
}

/* Directories are identity/trust boundaries, not a digest of ambient siblings.
 * Measured files retain all eight source-local fields, plus link count. */
static inline int kiosk_host_same(const struct stat *a, const struct stat *b)
{
    if (a->st_dev != b->st_dev || a->st_ino != b->st_ino ||
        a->st_mode != b->st_mode || a->st_uid != b->st_uid || a->st_gid != b->st_gid)
        return 0;
    return S_ISDIR(a->st_mode) ||
        (a->st_size == b->st_size && a->st_nlink == b->st_nlink &&
         a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
         a->st_ctim.tv_sec == b->st_ctim.tv_sec && a->st_ctim.tv_nsec == b->st_ctim.tv_nsec);
}

static inline void kiosk_host_roots_close(struct kiosk_host_roots *roots)
{
    if (roots->root >= 0) close(roots->root);
    if (roots->usr >= 0) close(roots->usr);
    roots->root = roots->usr = -1;
}

/* Also supports independently opened descriptor fixtures. Never adopts caller
 * descriptors; every owned duplicate is close-on-exec. */
static inline int kiosk_host_roots_from_fds(struct kiosk_host_roots *roots, int root, int usr)
{
    struct stat info;
    roots->root = roots->usr = -1;
    roots->root = fcntl(root, F_DUPFD_CLOEXEC, 3);
    roots->usr = fcntl(usr, F_DUPFD_CLOEXEC, 3);
    if (roots->root < 0 || roots->usr < 0 ||
        fstat(roots->root, &info) != 0 || !S_ISDIR(info.st_mode) || !kiosk_host_trust(&info) ||
        fstat(roots->usr, &info) != 0 || !S_ISDIR(info.st_mode) || !kiosk_host_trust(&info)) {
        kiosk_host_roots_close(roots); return -1;
    }
    return 0;
}

static inline int kiosk_host_roots_open(struct kiosk_host_roots *roots)
{
    int root = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int usr = root < 0 ? -1 : openat(root, "usr", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int result = kiosk_host_roots_from_fds(roots, root, usr);
    if (root >= 0) close(root);
    if (usr >= 0) close(usr);
    return result;
}

/* Native final checks cannot start a hash subprocess after /usr attachment.
 * Use the distribution's already trusted libcrypto through its public EVP API.
 * No link-time dependency or crypto structure layout is assumed. */
static inline int kiosk_host_sha256_library_until(int fd, off_t size, char hex[65], void *library, uint64_t deadline)
{
    void *context = NULL;
    int result = -1;
    if (!library || size < 0 || (uint64_t) size > KIOSK_HOST_FILE_BYTES || kiosk_host_before(deadline) != 0) goto done;
    void *(*ctx_new)(void) = (void *(*)(void)) dlsym(library, "EVP_MD_CTX_new");
    void (*ctx_free)(void *) = (void (*)(void *)) dlsym(library, "EVP_MD_CTX_free");
    const void *(*sha256)(void) = (const void *(*)(void)) dlsym(library, "EVP_sha256");
    int (*init)(void *, const void *, void *) = (int (*)(void *, const void *, void *)) dlsym(library, "EVP_DigestInit_ex");
    int (*update)(void *, const void *, size_t) = (int (*)(void *, const void *, size_t)) dlsym(library, "EVP_DigestUpdate");
    int (*final)(void *, unsigned char *, unsigned *) = (int (*)(void *, unsigned char *, unsigned *)) dlsym(library, "EVP_DigestFinal_ex");
    if (!ctx_new || !ctx_free || !sha256 || !init || !update || !final) goto done;
    context = ctx_new();
    if (context && init(context, sha256(), NULL) == 1) {
        unsigned char buffer[65536], digest[32];
        off_t offset = 0;
        while (offset < size) {
            if (kiosk_host_before(deadline) != 0) goto free_context;
            size_t wanted = (uint64_t) (size - offset) > sizeof(buffer) ? sizeof(buffer) : (size_t) (size - offset);
            ssize_t n = pread(fd, buffer, wanted, offset);
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0 || update(context, buffer, (size_t) n) != 1) goto free_context;
            offset += n;
        }
        unsigned length = 0;
        if (kiosk_host_before(deadline) == 0 && pread(fd, buffer, 1, size) == 0 &&
            final(context, digest, &length) == 1 && length == 32) {
            static const char digits[] = "0123456789abcdef";
            for (unsigned i = 0; i < 32; i++) {
                hex[i * 2] = digits[digest[i] >> 4]; hex[i * 2 + 1] = digits[digest[i] & 15];
            }
            hex[64] = '\0'; result = 0;
        }
    }
free_context:
    if (context) ctx_free(context);
done:
    return result;
}

static inline int kiosk_host_sha256(int fd, off_t size, char hex[65])
{
    uint64_t now;
    if (kiosk_host_now(&now) != 0 || now > UINT64_MAX - 60000000ULL) return -1;
    void *library = dlopen("libcrypto.so.3", RTLD_NOW | RTLD_LOCAL);
    int result = kiosk_host_sha256_library_until(fd, size, hex, library, now + 60000000ULL);
    if (library) dlclose(library);
    return result;
}

static inline int kiosk_host_label(int fd, char label[256])
{
    ssize_t n = fgetxattr(fd, "security.selinux", label, 255);
    if (n < 0) return errno == ENODATA ? (label[0] = '\0', 0) : -1;
    while (n && label[n - 1] == '\0') n--;
    if (!n || memchr(label, '\0', (size_t) n)) return -1;
    label[n] = '\0'; return 0;
}

static inline void kiosk_host_proof_close(struct kiosk_host_proof *proof)
{
    for (unsigned i = 0; i < proof->count; i++) { free(proof->rows[i].path); free(proof->rows[i].link); }
    for (unsigned i = 0; i < proof->requested; i++) {
        free((void *) proof->specs[i].path); free((void *) proof->specs[i].link);
        free((void *) proof->specs[i].sha256); free((void *) proof->specs[i].label);
    }
    free(proof->specs);
    free(proof->rows);
    if (proof->crypto) dlclose(proof->crypto);
    kiosk_host_roots_close(&proof->roots);
    memset(proof, 0, sizeof(*proof)); proof->roots.root = proof->roots.usr = -1;
}

/* Sorted bounded closure: duplicate ancestors must match their first observed
 * assertion even during capture. Rechecking cannot introduce another object. */
static inline int kiosk_host_observe(struct kiosk_host_proof *proof, const char *path, int fd,
                                   const struct stat *info, int capture, struct kiosk_host_row **out)
{
    unsigned low = 0, high = proof->count;
    struct kiosk_host_row observed = {.info = *info};
    char link[PATH_MAX];
    if (!kiosk_host_trust(info) || kiosk_host_before(proof->deadline) != 0) return -1;
    while (low < high) {
        unsigned middle = low + (high - low) / 2;
        if (strcmp(proof->rows[middle].path, path) < 0) low = middle + 1; else high = middle;
    }
    int exists = low < proof->count && !strcmp(proof->rows[low].path, path);
    if (!exists && (!capture || proof->count >= KIOSK_HOST_PROOF_ROWS)) return -1;
    /* Several lexical aliases may reach the same canonical file. Full eight
     * fields must still match on every visit; hash each inode once per pass. */
    if (exists && S_ISREG(info->st_mode) && proof->rows[low].epoch == proof->epoch) {
        if (!kiosk_host_same(&proof->rows[low].info, info)) return -1;
        *out = &proof->rows[low]; return 0;
    }
    if (S_ISLNK(info->st_mode)) {
        ssize_t n = readlinkat(fd, "", link, sizeof(link));
        if (n <= 0 || n >= PATH_MAX) return -1;
        link[n] = '\0'; observed.link = link;
    } else if (S_ISREG(info->st_mode) || S_ISDIR(info->st_mode)) {
        if (S_ISREG(info->st_mode) && (info->st_nlink != 1 || info->st_gid != KIOSK_HOST_PROOF_GROUP)) return -1;
        char descriptor[64]; struct stat before, after;
        snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", fd);
        int readable = open(descriptor, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (readable < 0) return -1;
        int measured = S_ISREG(info->st_mode), capability_absent = 1;
        if (measured) {
            if (info->st_size < 0 || (uint64_t) info->st_size > KIOSK_HOST_FILE_BYTES - proof->measured) {
                close(readable); return -1;
            }
            proof->measured += (uint64_t) info->st_size;
            ssize_t capability = fgetxattr(readable, "security.capability", NULL, 0);
            capability_absent = capability < 0 && errno == ENODATA;
        }
        int valid = fstat(readable, &before) == 0 && kiosk_host_same(info, &before) &&
            capability_absent && (!measured || kiosk_host_sha256_library_until(readable, info->st_size, observed.sha256, proof->crypto, proof->deadline) == 0) &&
            kiosk_host_label(readable, observed.label) == 0 && fstat(readable, &after) == 0 &&
            kiosk_host_same(info, &after);
        close(readable);
        if (!valid) return -1;
    }
    struct stat final;
    if (fstat(fd, &final) != 0 || !kiosk_host_same(info, &final)) return -1;
    if (exists) {
        struct kiosk_host_row *row = &proof->rows[low];
        if (!kiosk_host_same(&row->info, info) || strcmp(row->sha256, observed.sha256) ||
            strcmp(row->label, observed.label) ||
            (row->link ? !observed.link || strcmp(row->link, observed.link) : observed.link != NULL)) return -1;
    } else {
        size_t used = strlen(path) + 1 + (observed.link ? strlen(observed.link) + 1 : 0);
        if (used > KIOSK_HOST_PROOF_BYTES - proof->bytes) return -1;
        observed.path = strdup(path);
        observed.link = observed.link ? strdup(observed.link) : NULL;
        if (!observed.path || (S_ISLNK(info->st_mode) && !observed.link)) {
            free(observed.path); free(observed.link); return -1;
        }
        memmove(proof->rows + low + 1, proof->rows + low, (proof->count - low) * sizeof(*proof->rows));
        proof->rows[low] = observed; proof->count++; proof->bytes += used;
    }
    proof->rows[low].epoch = proof->epoch;
    *out = &proof->rows[low]; return 0;
}

/* Retain the directory stack in userspace. In particular, never open kernel
 * '..' from the pinned /usr and then re-enter a newly attached /usr. */
static inline int kiosk_host_walk(struct kiosk_host_proof *proof, const struct kiosk_host_spec *spec,
                                 int capture, char resolved[PATH_MAX])
{
    int stack[PATH_MAX / 2 + 1], child = -1, result = -1;
    unsigned depth = 0, links = 0, steps = 0;
    char pending[PATH_MAX], traversed[PATH_MAX] = "/";
    struct stat info; struct kiosk_host_row *row;
    size_t length = spec->path ? strlen(spec->path) : 0;
    if (!length || length >= PATH_MAX || spec->path[0] != '/' ||
        (spec->kind != S_IFDIR && spec->kind != S_IFREG && spec->kind != S_IFLNK) ||
        (spec->terminal_link && (spec->kind != S_IFLNK || !spec->link)) ||
        (spec->link && spec->kind != S_IFLNK) || (spec->sha256 && spec->kind != S_IFREG) ||
        (spec->label && spec->kind == S_IFLNK) || (spec->mode & ~07777U) ||
        kiosk_host_before(proof->deadline) != 0) return -1;
    if (spec->sha256 && (strlen(spec->sha256) != 64 || strspn(spec->sha256, "0123456789abcdef") != 64)) return -1;
    if (spec->link && (!spec->link[0] || strlen(spec->link) >= PATH_MAX)) return -1;
    if (spec->label) {
        if (strlen(spec->label) >= sizeof(row->label)) return -1;
        for (const unsigned char *p = (const unsigned char *) spec->label; *p; p++) if (*p <= 32 || *p >= 127) return -1;
    }
    /* Requests are canonical lexical names; only alias text may introduce dot
     * components, which the walk checks before consuming '..'. */
    if (length > 1) {
        for (const char *p = spec->path + 1; *p;) {
            const char *end = strchr(p, '/'); size_t n = end ? (size_t) (end - p) : strlen(p);
            if (!n || (n == 1 && p[0] == '.') || (n == 2 && p[0] == '.' && p[1] == '.') || (end && !end[1])) return -1;
            p = end ? end + 1 : p + n;
        }
    }
    stack[0] = fcntl(proof->roots.root, F_DUPFD_CLOEXEC, 3);
    if (stack[0] < 0) return -1;
    if (fstat(stack[0], &info) != 0 || !S_ISDIR(info.st_mode) ||
        kiosk_host_observe(proof, "/", stack[0], &info, capture, &row) != 0) goto done;
    strcpy(pending, spec->path + 1);
    int endpoint_checked = 0;
    if (!pending[0]) {
        if (spec->kind != S_IFDIR || (spec->mode && (info.st_mode & 07777) != spec->mode) ||
            (spec->label && strcmp(spec->label, row->label))) goto done;
        endpoint_checked = 1;
    }
    while (pending[0]) {
        char part[PATH_MAX], next[PATH_MAX], expanded[PATH_MAX];
        char *slash = strchr(pending, '/');
        size_t n = slash ? (size_t) (slash - pending) : strlen(pending);
        memcpy(part, pending, n); part[n] = '\0';
        memmove(pending, slash ? slash + 1 : pending + n, strlen(slash ? slash + 1 : pending + n) + 1);
        if (++steps > KIOSK_HOST_PROOF_ROWS || kiosk_host_before(proof->deadline) != 0) goto done;
        if (!part[0] || !strcmp(part, ".")) continue;
        if (!strcmp(part, "..")) {
            if (depth) { close(stack[depth--]); char *last = strrchr(traversed, '/'); if (last == traversed) last[1] = '\0'; else *last = '\0'; }
            continue;
        }
        int used = snprintf(next, sizeof(next), "%s%s%s", traversed, depth ? "/" : "", part);
        if (used < 0 || used >= PATH_MAX || depth >= PATH_MAX / 2) goto done;
        child = !strcmp(next, "/usr") ? fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3) :
            openat(stack[depth], part, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (child < 0 || fstat(child, &info) != 0 ||
            kiosk_host_observe(proof, next, child, &info, capture, &row) != 0) goto done;
        /* Hashing reads the pin; separately prove that its original named edge
         * still selects it. The explicit /usr anchor is the sole dispatch. */
        int named = !strcmp(next, "/usr") ? fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3) :
            openat(stack[depth], part, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        struct stat named_info;
        int same_edge = named >= 0 && fstat(named, &named_info) == 0 && kiosk_host_same(&info, &named_info);
        if (named >= 0) close(named);
        if (!same_edge) goto done;
        if (S_ISREG(info.st_mode) && !spec->privileged && (info.st_mode & 06000)) goto done;
        if (!pending[0] && !endpoint_checked) {
            if ((info.st_mode & S_IFMT) != spec->kind ||
                (spec->mode && (info.st_mode & 07777) != spec->mode) ||
                (spec->link && (!row->link || strcmp(spec->link, row->link))) ||
                (spec->sha256 && strcmp(spec->sha256, row->sha256)) ||
                (spec->label && strcmp(spec->label, row->label)) ||
                (!spec->privileged && S_ISREG(info.st_mode) && (info.st_mode & 06000))) goto done;
            endpoint_checked = 1;
            if (spec->terminal_link) { strcpy(traversed, next); close(child); child = -1; break; }
        }
        if (S_ISLNK(info.st_mode)) {
            if (++links > 40 || !row->link) goto done;
            int absolute = row->link[0] == '/';
            used = snprintf(expanded, sizeof(expanded), "%s%s%s", row->link + absolute, pending[0] ? "/" : "", pending);
            if (used < 0 || used >= PATH_MAX) goto done;
            close(child); child = -1;
            if (absolute) { while (depth) close(stack[depth--]); strcpy(traversed, "/"); }
            strcpy(pending, expanded); continue;
        }
        if (pending[0] && !S_ISDIR(info.st_mode)) goto done;
        stack[++depth] = child; child = -1; strcpy(traversed, next);
    }
    if (!endpoint_checked) goto done;
    if (resolved) strcpy(resolved, traversed);
    result = 0;
done:
    if (child >= 0) close(child);
    do { close(stack[depth]); } while (depth--);
    return result;
}

/* Reopen every canonical edge from the original anchors after measurements.
 * A renamed ancestor cannot hide behind its still-readable old descriptor. */
static inline int kiosk_host_edges(struct kiosk_host_proof *proof)
{
    for (unsigned i = 0; i < proof->count; i++) {
        char path[PATH_MAX] = "/", pending[PATH_MAX];
        strcpy(pending, proof->rows[i].path + 1);
        int current = fcntl(proof->roots.root, F_DUPFD_CLOEXEC, 3), result = -1;
        struct stat info; struct kiosk_host_row *row;
        if (current < 0) return -1;
        if (fstat(current, &info) != 0 || kiosk_host_observe(proof, "/", current, &info, 0, &row) != 0) goto edge_done;
        for (char *part = pending; *part;) {
            char *next = strchr(part, '/'); if (next) *next++ = '\0';
            size_t used = strlen(path);
            if (used + strlen(part) + 1 >= sizeof(path) || kiosk_host_before(proof->deadline) != 0) goto edge_done;
            if (used > 1) strcat(path, "/");
            strcat(path, part);
            int child = !strcmp(path, "/usr") ? fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3) :
                openat(current, part, O_PATH | O_NOFOLLOW | O_CLOEXEC);
            if (child < 0) goto edge_done;
            close(current); current = child;
            if (fstat(current, &info) != 0 || (next && !S_ISDIR(info.st_mode)) ||
                kiosk_host_observe(proof, path, current, &info, 0, &row) != 0) goto edge_done;
            if (!next) break;
            part = next;
        }
        result = 0;
edge_done:
        close(current);
        if (result != 0) return -1;
    }
    return kiosk_host_before(proof->deadline);
}

static inline int kiosk_host_proof_capture_until(struct kiosk_host_proof *proof, const struct kiosk_host_roots *roots,
                                               const struct kiosk_host_spec *specs, unsigned count, uint64_t deadline)
{
    memset(proof, 0, sizeof(*proof)); proof->roots.root = proof->roots.usr = -1;
    proof->deadline = deadline;
    if (!roots || !specs || !count || count > KIOSK_HOST_PROOF_ROWS ||
        kiosk_host_before(deadline) != 0 || kiosk_host_roots_from_fds(&proof->roots, roots->root, roots->usr) != 0) return -1;
    proof->rows = calloc(KIOSK_HOST_PROOF_ROWS, sizeof(*proof->rows));
    proof->specs = calloc(count, sizeof(*proof->specs));
    proof->crypto = dlopen("libcrypto.so.3", RTLD_NOW | RTLD_LOCAL);
    if (!proof->rows || !proof->specs || !proof->crypto) goto failed;
    proof->epoch = 1;
    for (unsigned i = 0; i < count; i++) {
        const char *strings[] = {specs[i].path, specs[i].link, specs[i].sha256, specs[i].label};
        const char **copies[] = {&proof->specs[i].path, &proof->specs[i].link, &proof->specs[i].sha256, &proof->specs[i].label};
        proof->specs[i] = specs[i];
        /* Clear borrowed strings before a partial copy can fail. */
        for (unsigned j = 0; j < 4; j++) *copies[j] = NULL;
        proof->requested++;
        for (unsigned j = 0; j < 4; j++) if (strings[j]) {
            size_t used = strnlen(strings[j], PATH_MAX) + 1;
            if (used > PATH_MAX || used > KIOSK_HOST_PROOF_BYTES - proof->bytes ||
                !(*copies[j] = strdup(strings[j]))) goto failed;
            proof->bytes += used;
        }
        if (kiosk_host_walk(proof, proof->specs + i, 1, NULL) != 0) goto failed;
    }
    if (kiosk_host_edges(proof) != 0) goto failed;
    proof->sealed = 1; return 0;
failed:
    kiosk_host_proof_close(proof); return -1;
}

/* Preparatory convenience only. Composed admission must supply its already
 * running transaction deadline to capture_until, never renew it here. */
static inline int kiosk_host_proof_capture(struct kiosk_host_proof *proof, const struct kiosk_host_roots *roots,
                                         const struct kiosk_host_spec *specs, unsigned count)
{
    uint64_t now;
    if (kiosk_host_now(&now) != 0 || now > UINT64_MAX - 60000000ULL) {
        memset(proof, 0, sizeof(*proof)); proof->roots.root = proof->roots.usr = -1; return -1;
    }
    return kiosk_host_proof_capture_until(proof, roots, specs, count, now + 60000000ULL);
}

/* The caller retains the same explicit required specs for the transaction.
 * The sealed closure cannot authorize newly discovered objects at final proof. */
static inline int kiosk_host_proof_recheck(struct kiosk_host_proof *proof,
                                         const struct kiosk_host_spec *specs, unsigned count)
{
    if (!proof->sealed || !specs || !count || count != proof->requested) return -1;
    if (++proof->epoch == 0) return -1;
    proof->measured = 0;
    for (unsigned i = 0; i < count; i++) {
        const struct kiosk_host_spec *saved = proof->specs + i;
        const char *a[] = {specs[i].path, specs[i].link, specs[i].sha256, specs[i].label};
        const char *b[] = {saved->path, saved->link, saved->sha256, saved->label};
        if (specs[i].kind != saved->kind || specs[i].mode != saved->mode ||
            specs[i].privileged != saved->privileged || specs[i].terminal_link != saved->terminal_link) return -1;
        for (unsigned j = 0; j < 4; j++)
            if (a[j] ? !b[j] || strcmp(a[j], b[j]) : b[j] != NULL) return -1;
        if (kiosk_host_walk(proof, saved, 0, NULL) != 0) return -1;
    }
    return kiosk_host_edges(proof);
}
#endif
