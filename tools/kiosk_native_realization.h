#ifndef ONPC_KIOSK_NATIVE_REALIZATION_H
#define ONPC_KIOSK_NATIVE_REALIZATION_H
/* Actual native realization. Include after kiosk_confinement.h's pin owner.
 * A verified plan is an intention, never a receipt. This owner independently
 * reopens descriptor-relative sources, checks the fresh skeleton, observes
 * every bind and nested mount and serializes only those actual outcomes.
 * All descriptors/strings in the inputs are borrowed. No pathname fallback,
 * helper process, renewed deadline, ready publication or MAC is provided here.
 */
#include "kiosk_preparation_plan.h"
#include <stdarg.h>

struct kiosk_realized_node {
    const struct kiosk_preparation_row *plan;
    const char *kind;
    struct stat info;
    char sha[65], label[256];
    int mounted;
};
struct kiosk_realized_coverage {
    char *path;
    unsigned owner;
    struct stat info;
    uint64_t origin[2];
};
struct kiosk_native_realization {
    int root;
    uint64_t deadline, measured;
    struct kiosk_realized_node *nodes;
    unsigned count;
    struct kiosk_realized_coverage *coverage;
    unsigned coverage_count;
    struct kiosk_pin_entry *entries;
    unsigned entry_count;
    struct kiosk_owned_mount *stages;
    unsigned stage_count;
    char *bytes;
    size_t size;
    struct kiosk_receipt receipt;
    struct kiosk_failure cleanup_failure;
    const struct kiosk_receipt *source;
    int bound, marker_verified, selinux, source_check;
};

static inline const char *kiosk_realization_relative(const char *path)
{ return !strcmp(path, "/usr") ? "" : path + 5; }

static inline int kiosk_realization_assert(const struct stat *s, const uint64_t a[8])
{
    return a[0] == (uint64_t)s->st_dev && a[1] == (uint64_t)s->st_ino &&
        a[2] == (uint64_t)s->st_size && a[3] == (uint64_t)s->st_mtim.tv_sec * 1000000000ULL + s->st_mtim.tv_nsec &&
        a[4] == (uint64_t)s->st_ctim.tv_sec * 1000000000ULL + s->st_ctim.tv_nsec &&
        a[5] == (uint64_t)s->st_mode && a[6] == s->st_uid && a[7] == s->st_gid;
}

static inline int kiosk_realization_local_error(void)
{ return errno == ENOENT || errno == EACCES || errno == EPERM || errno == EIO || errno == ESTALE; }

static inline int kiosk_realization_find(const struct kiosk_native_realization *r, const char *path)
{
    unsigned lo = 0, hi = r->count;
    while (lo < hi) { unsigned m = lo + (hi - lo) / 2;
        if (strcmp(r->nodes[m].plan->path, path) < 0) lo = m + 1; else hi = m; }
    return lo < r->count && !strcmp(r->nodes[lo].plan->path, path) ? (int)lo : -1;
}

/* Enumerate only private tree parents. Shallow source directories must start
 * empty and remain opaque after binding. A symlink is inspected, never walked.
 * Every entry must have exactly one plan row; masks and absences stay explicit.
 */
static inline int kiosk_realization_structure(struct kiosk_native_realization *r, unsigned index,
                                             int before, const char *marker)
{
    if (kiosk_pin_before(r->deadline) != 0) return -1;
    const struct kiosk_preparation_row *p = r->nodes[index].plan;
    unsigned depth = 0;
    for (const char *part = p->path; *part; part++) depth += *part == '/';
    if (depth > 128) return -1;
    int fd = kiosk_pin_open(r->root, kiosk_realization_relative(p->path));
    struct stat info; unsigned long long mount_id, root_id;
    if (fd < 0 || fstat(fd, &info) != 0 || !kiosk_trusted_stat(&info, S_IFDIR) ||
        (info.st_mode & 07777) != 0755 || kiosk_pin_fd_mount(fd, &mount_id) != 0 ||
        kiosk_pin_fd_mount(r->root, &root_id) != 0 || mount_id != root_id ||
        kiosk_label(fd, NULL, 0, r->selinux) != 0) {
        if (fd >= 0) close(fd);
        return -1;
    }
    int readable = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    close(fd); DIR *dir = readable < 0 ? NULL : fdopendir(readable);
    if (!dir) { if (readable >= 0) close(readable); return -1; }
    unsigned seen = 0; int result = -1; struct dirent *entry;
    errno = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char path[PATH_MAX];
        if (kiosk_pin_before(r->deadline) != 0 ||
            snprintf(path, sizeof(path), "%s/%s", p->path, entry->d_name) >= PATH_MAX) goto done;
        if (marker && !strcmp(path, marker)) continue; /* Checked separately. */
        int child = kiosk_realization_find(r, path);
        if (child < 0) goto done;
        struct kiosk_realized_node *node = &r->nodes[child];
        const char *kind = before ? node->plan->kind : node->kind;
        if (!strcmp(kind, "absent")) goto done;
        struct stat s;
        int ambient = r->source_check && !node->plan->required && !strcmp(node->plan->source_class, "ambient");
        if (fstatat(dirfd(dir), entry->d_name, &s, AT_SYMLINK_NOFOLLOW) != 0 || (!ambient && !kiosk_trusted_stat(&s, 0))) goto done;
        if (!strcmp(kind, "link")) {
            char link[PATH_MAX]; ssize_t n = readlinkat(dirfd(dir), entry->d_name, link, sizeof(link));
            if (!S_ISLNK(s.st_mode) || n <= 0 || n >= PATH_MAX) goto done;
            link[n] = 0;
            if (!node->plan->link || strcmp(link, node->plan->link)) goto done;
        } else {
            int directory = strcmp(kind, "file") != 0;
            if ((directory ? !S_ISDIR(s.st_mode) : !S_ISREG(s.st_mode)) ||
                (before && !directory && (s.st_size || s.st_nlink != 1)) ||
                (!node->mounted && (s.st_mode & 07777) != (directory ? 0755 : 0644))) goto done;
            if (directory && (before || !strcmp(kind, "tree") || !strcmp(kind, "empty-directory"))) {
                if (kiosk_realization_structure(r, (unsigned)child, before, marker) != 0) goto done;
            }
        }
        seen++; errno = 0;
    }
    if (errno) goto done;
    unsigned expected = 0;
    for (unsigned i = index + 1; i < r->count; i++) {
        const char *path = r->nodes[i].plan->path;
        if (!kiosk_below(path, p->path)) break;
        const char *rest = path + strlen(p->path) + 1;
        const char *kind = before ? r->nodes[i].plan->kind : r->nodes[i].kind;
        if (!strchr(rest, '/') && strcmp(kind, "absent")) expected++;
    }
    if (seen == expected && kiosk_pin_before(r->deadline) == 0) result = 0;
done:
    closedir(dir); return result;
}

/* Reopen a canonical source only beneath the already pinned root. Copies are
 * exact named children of the independently verified scratch directory. */
static inline int kiosk_realization_source(const struct kiosk_preparation_row *p,
                                          const struct kiosk_host_roots *host, int clone, int copies,
                                          int *parent, char name[PATH_MAX])
{
    *parent = -1;
    if (p->copied) {
        if (!p->copy_name || !kiosk_path(p->copy_name, 0) || strchr(p->copy_name, '/')) return -1;
        strcpy(name, p->copy_name); *parent = fcntl(copies, F_DUPFD_CLOEXEC, 3);
    } else {
        const char *path = p->source_path;
        if (!path || !kiosk_path(path, 1) || !strcmp(path, "/")) return -1;
        int root = clone >= 0 ? clone : !strncmp(path, "/usr/", 5) ? host->usr : host->root;
        const char *relative = clone >= 0 || root == host->usr ? path + 5 : path + 1;
        if (clone >= 0 && strncmp(path, "/usr/", 5)) return -1;
        *parent = kiosk_parent(root, relative, name);
    }
    return *parent < 0 ? -1 : openat(*parent, name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
}

/* Foreign inode/topology is never eligible narrowing. A same-origin ambient
 * object that became untrusted or unavailable may only shrink the fresh view.
 */
static inline int kiosk_realization_measure(struct kiosk_native_realization *r, struct kiosk_realized_node *n,
                                          int fd, int retained, void *crypto)
{
    const struct kiosk_preparation_row *p = n->plan;
    struct stat after;
    int ambient = !strcmp(p->source_class, "ambient") && !p->required;
    if (kiosk_pin_before(r->deadline) != 0) return -1;
    if (fstat(fd, &n->info) != 0) return ambient && kiosk_realization_local_error() ? 1 : -1;
    const uint64_t *assertion = p->copied ? p->copy_identity : p->assertion;
    if ((uint64_t)n->info.st_dev != assertion[0] || (uint64_t)n->info.st_ino != assertion[1] ||
        (n->info.st_mode & S_IFMT) != (mode_t)(assertion[5] & S_IFMT)) return ambient && !retained ? 1 : -1;
    if (!kiosk_trusted_stat(&n->info, 0) || (S_ISREG(n->info.st_mode) && n->info.st_nlink > 1)) return ambient ? 1 : -1;
    if (!kiosk_realization_assert(&n->info, assertion)) return ambient && !retained ? 1 : -1;
    if (S_ISLNK(n->info.st_mode)) {
        char link[PATH_MAX]; ssize_t length = readlinkat(fd, "", link, sizeof(link));
        if (length <= 0 || length >= PATH_MAX) return -1;
        link[length] = 0;
        return p->link && !strcmp(link, p->link) ? 0 : -1;
    }
    if (!S_ISREG(n->info.st_mode) && !S_ISDIR(n->info.st_mode)) return -1;
    if (S_ISREG(n->info.st_mode) && !ambient &&
        (n->info.st_nlink != 1 && !(retained && !strcmp(p->source_class, "vendor") && n->info.st_nlink == 0))) return -1;
    char path[64]; snprintf(path, sizeof(path), "/proc/self/fd/%d", fd);
    int readable = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (readable < 0) return ambient && kiosk_realization_local_error() ? 1 : -1;
    int result = -1;
    if (fstat(readable, &after) != 0 || !kiosk_pin_same_stat(&after, &n->info)) goto done;
    if (S_ISREG(n->info.st_mode)) {
        ssize_t capability = fgetxattr(readable, "security.capability", NULL, 0);
        if (capability >= 0 || errno != ENODATA) { result = ambient && capability >= 0 ? 1 : -1; goto done; }
        if ((n->info.st_mode & 06000) && !(p->spec && p->spec->privileged)) { result = ambient ? 1 : -1; goto done; }
        if (!ambient) {
            if (!p->spec || n->info.st_size < 0 || (uint64_t)n->info.st_size != p->spec->size ||
                (uint64_t)n->info.st_size > KIOSK_HOST_FILE_BYTES - r->measured) goto done;
            r->measured += (uint64_t)n->info.st_size;
            if (kiosk_host_sha256_library_until(readable, n->info.st_size, n->sha, crypto, r->deadline) != 0 ||
                strcmp(n->sha, p->spec->sha256)) goto done;
        }
    }
    if (kiosk_host_label(readable, n->label) != 0 ||
        (p->spec && p->spec->label && strcmp(p->spec->label, "-") && strcmp(n->label, p->spec->label)) ||
        fstat(readable, &after) != 0 || !kiosk_pin_same_stat(&after, &n->info) || kiosk_pin_before(r->deadline) != 0) goto done;
    result = 0;
done:
    close(readable); return result;
}

/* Initial sources have no V. Observe actual nested mounts in this namespace
 * solely to reject unsafe source authority by masking the whole ambient owner.
 * All lookup remains descriptor-relative; mountinfo paths are never opened.
 */
static inline int kiosk_realization_initial_nested(struct kiosk_native_realization *r, unsigned owner, int source)
{
    const struct kiosk_preparation_row *p = r->nodes[owner].plan;
    char descriptor[64], root_path[PATH_MAX];
    snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", source);
    ssize_t length = readlink(descriptor, root_path, sizeof(root_path) - 1);
    if (length <= 0 || length >= PATH_MAX - 1) return -1;
    root_path[length] = 0;
    if (!kiosk_path(root_path, 1)) return -1;
    FILE *stream = fopen("/proc/self/mountinfo", "re");
    if (!stream) return -1;
    char *line = NULL; size_t capacity = 0, total = 0; unsigned mounts = 0; int unsafe = 0, result = -1;
    while (getline(&line, &capacity, stream) >= 0) {
        char path[PATH_MAX];
        if (kiosk_pin_before(r->deadline) != 0 || ++mounts > KIOSK_VIEW_ROWS ||
            (total += strlen(line)) > KIOSK_VIEW_BYTES ||
            sscanf(line, "%*u %*u %*s %*s %4095s", path) != 1 || kiosk_pin_decode_mountpath(path) != 0) goto done;
        if (!kiosk_below(path, root_path)) continue;
        char relative[PATH_MAX]; strcpy(relative, path + strlen(root_path) + 1);
        int current = fcntl(source, F_DUPFD_CLOEXEC, 3); char *part = relative;
        if (current < 0) goto done;
        for (;;) {
            char *slash = strchr(part, '/'); if (slash) *slash = 0;
            unsigned long long parent_id, child_id; struct stat info;
            if (kiosk_pin_before(r->deadline) != 0 || kiosk_pin_fd_mount(current, &parent_id) != 0) { close(current); goto done; }
            int child = openat(current, part, O_PATH | O_NOFOLLOW | O_CLOEXEC | (slash ? O_DIRECTORY : 0));
            close(current); current = child;
            if (current < 0 || fstat(current, &info) != 0 || kiosk_pin_fd_mount(current, &child_id) != 0) {
                if (current >= 0) close(current);
                goto done;
            }
            if (!kiosk_trusted_stat(&info, 0) || (S_ISREG(info.st_mode) && info.st_nlink > 1)) unsafe = 1;
            if (!slash) {
                close(current);
                if (child_id == parent_id || (!S_ISDIR(info.st_mode) && !S_ISREG(info.st_mode))) goto done;
                break;
            }
            part = slash + 1;
        }
    }
    if (!ferror(stream) && kiosk_pin_before(r->deadline) == 0)
        result = unsafe ? (!p->required && !strcmp(p->source_class, "ambient") ? 1 : -1) : 0;
done:
    free(line); fclose(stream); return result;
}

/* V's independently acquired recursive witnesses must retain their source
 * inode/type/mount boundary even when metadata loss makes the ambient owner
 * ineligible. Check each intermediate directory too, without following links.
 */
static inline int kiosk_realization_nested(struct kiosk_native_realization *r, unsigned owner, int source)
{
    if (!r->source) return kiosk_realization_initial_nested(r, owner, source);
    const struct kiosk_preparation_row *p = r->nodes[owner].plan;
    int unsafe = 0;
    for (unsigned i = 0; i < r->source->nc; i++) {
        const struct kiosk_receipt_row *c = &r->source->coverage[i];
        if (c->number[KC_OWNER] != owner) continue;
        if (strcmp(p->kind, "directory") || !kiosk_below(c->v[KC_PATH], p->path)) return -1;
        char path[PATH_MAX]; strcpy(path, c->v[KC_PATH] + strlen(p->path) + 1);
        int current = fcntl(source, F_DUPFD_CLOEXEC, 3); char *part = path;
        if (current < 0) return -1;
        for (;;) {
            char *slash = strchr(part, '/'); if (slash) *slash = 0;
            unsigned long long parent_id, child_id; struct stat info;
            if (kiosk_pin_before(r->deadline) != 0 || kiosk_pin_fd_mount(current, &parent_id) != 0) { close(current); return -1; }
            int child = openat(current, part, O_PATH | O_NOFOLLOW | O_CLOEXEC | (slash ? O_DIRECTORY : 0));
            close(current); current = child;
            if (current < 0 || fstat(current, &info) != 0 || kiosk_pin_fd_mount(current, &child_id) != 0) {
                if (current >= 0) close(current);
                return -1;
            }
            if (!kiosk_trusted_stat(&info, 0) || (S_ISREG(info.st_mode) && info.st_nlink > 1)) unsafe = 1;
            if (!slash) {
                int valid = (uint64_t)info.st_dev == c->number[KC_DEV] && (uint64_t)info.st_ino == c->number[KC_INO] &&
                    (info.st_mode & S_IFMT) == (mode_t)(c->number[KC_MODE] & S_IFMT) && child_id != parent_id;
                close(current); if (!valid) return -1; break;
            }
            part = slash + 1;
        }
    }
    return unsafe ? (!p->required && !strcmp(p->source_class, "ambient") ? 1 : -1) : 0;
}

static inline int kiosk_realization_parent_same(const struct kiosk_preparation_row *p,
                                               const struct kiosk_host_roots *host, int clone, int copies,
                                               const struct stat *expected)
{
    int parent = -1; char name[PATH_MAX]; struct stat observed;
    int fd = kiosk_realization_source(p, host, clone, copies, &parent, name);
    if (fd >= 0) close(fd);
    int valid = parent >= 0 && fstat(parent, &observed) == 0 && kiosk_trusted_stat(&observed, S_IFDIR) &&
        kiosk_host_same(expected, &observed);
    if (parent >= 0) close(parent);
    return valid ? 0 : -1;
}

static inline int kiosk_realization_named_state(const struct kiosk_realized_node *n, int parent,
                                               const char *name, int retained)
{
    struct stat named;
    const struct kiosk_preparation_row *p = n->plan;
    int ambient = !p->required && !strcmp(p->source_class, "ambient");
    if (fstatat(parent, name, &named, AT_SYMLINK_NOFOLLOW) != 0)
        return ambient && kiosk_realization_local_error() ? 1 : -1;
    if (named.st_dev != n->info.st_dev || named.st_ino != n->info.st_ino ||
        (named.st_mode & S_IFMT) != (n->info.st_mode & S_IFMT)) return ambient && !retained ? 1 : -1;
    if (!kiosk_trusted_stat(&named, 0) || (S_ISREG(named.st_mode) && named.st_nlink > 1)) return ambient ? 1 : -1;
    if (!kiosk_pin_same_stat(&named, &n->info)) return ambient && !retained ? 1 : -1;
    return 0;
}

static inline int kiosk_realization_bind(struct kiosk_native_realization *r, unsigned i,
                                       const struct kiosk_host_roots *host, int clone, int copies, void *crypto)
{
    struct kiosk_realized_node *n = &r->nodes[i];
    const struct kiosk_preparation_row *p = n->plan;
    if (!p->has_source) return 0;
    int parent = -1, target_parent = -1, source = -1, target = -1, observed = -1, result = -1;
    char name[PATH_MAX], target_name[PATH_MAX], from[64], to[64], path[PATH_MAX + 64];
    struct stat named, placeholder, parent_info;
    source = kiosk_realization_source(p, host, clone, copies, &parent, name);
    int ambient = !p->required && !strcmp(p->source_class, "ambient");
    int state = source < 0 ? (ambient && parent >= 0 && kiosk_realization_local_error() ? 1 : -1) :
        kiosk_realization_measure(r, n, source, clone >= 0, crypto);
    if (state < 0 || parent < 0 || fstat(parent, &parent_info) != 0 || !kiosk_trusted_stat(&parent_info, S_IFDIR) ||
        kiosk_pin_before(r->deadline) != 0) goto done;
    if (source >= 0 && !strcmp(p->kind, "directory")) {
        int nested = kiosk_realization_nested(r, i, source);
        if (nested < 0) goto done;
        if (nested) state = 1;
    }
    target_parent = kiosk_parent(r->root, kiosk_realization_relative(p->path), target_name);
    if (target_parent < 0 || (target = openat(target_parent, target_name, O_PATH | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
        fstat(target, &placeholder) != 0) goto done;
    if (state == 0) state = kiosk_realization_named_state(n, parent, name, clone >= 0);
    if (state < 0) goto done;
omit:
    if (state == 1) {
        if (!ambient || kiosk_realization_parent_same(p, host, clone, copies, &parent_info) != 0) goto done;
        if (!strcmp(p->kind, "directory")) {
            /* Keep the already verified empty private directory, including its
             * runtime label and original owned inode. Never modify the source. */
            n->kind = "empty-directory";
        } else {
            if (unlinkat(target_parent, target_name, 0) != 0) goto done;
            n->kind = "absent";
        }
        memset(&n->info, 0, sizeof(n->info)); result = 0; goto done;
    }
    if (!strcmp(p->kind, "tree") || !strcmp(p->kind, "link")) {
        result = kiosk_realization_parent_same(p, host, clone, copies, &parent_info); goto done;
    }
    if (r->stage_count >= KIOSK_VIEW_ROWS ||
        snprintf(path, sizeof(path), "/proc/self/fd/%d/%s", target_parent, target_name) >= (int)sizeof(path)) goto done;
    /* Cleanup paths must outlive the parent descriptor; use the kernel's actual
     * path of the independently opened fresh root, never a helper path. */
    char root_path[PATH_MAX], descriptor[64]; snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", r->root);
    ssize_t length = readlink(descriptor, root_path, sizeof(root_path) - 1);
    if (length <= 0 || length >= PATH_MAX - 1) goto done;
    root_path[length] = 0;
    if (!kiosk_path(root_path, 1) || snprintf(path, sizeof(path), "%s/%s", root_path,
        kiosk_realization_relative(p->path)) >= (int)sizeof(path)) goto done;
    struct kiosk_owned_mount *stage = &r->stages[r->stage_count];
    if (!(stage->path = strdup(path))) goto done;
    r->stage_count++;
    snprintf(from, sizeof(from), "/proc/self/fd/%d", source); snprintf(to, sizeof(to), "/proc/self/fd/%d", target);
    if (kiosk_pin_before(r->deadline) != 0 || mount(from, to, NULL, MS_BIND | MS_REC, NULL) != 0) goto done;
    stage->live = 1; n->mounted = 1;
    observed = openat(target_parent, target_name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
    unsigned long long previous;
    if (observed < 0 || kiosk_pin_fd_mount(target, &previous) != 0 || kiosk_pin_fd_mount(observed, &stage->id) != 0 ||
        stage->id == previous || fstat(observed, &named) != 0 || named.st_dev != n->info.st_dev || named.st_ino != n->info.st_ino ||
        (named.st_mode & S_IFMT) != (n->info.st_mode & S_IFMT) ||
        kiosk_realization_parent_same(p, host, clone, copies, &parent_info) != 0 ||
        kiosk_pin_before(r->deadline) != 0) goto done;
    state = kiosk_realization_named_state(n, parent, name, clone >= 0);
    if (state < 0) goto done;
    if (!strcmp(p->kind, "directory")) {
        int nested = kiosk_realization_nested(r, i, source);
        if (nested < 0) goto done;
        if (nested) state = 1;
    }
    if (state == 1) {
        if (kiosk_detach_owned(stage->path, stage->id, &r->cleanup_failure) != 0) goto done;
        stage->live = 0; n->mounted = 0;
        goto omit;
    }
    result = 0;
done:
    if (source >= 0) close(source);
    if (parent >= 0) close(parent);
    if (target >= 0) close(target);
    if (target_parent >= 0) close(target_parent);
    if (observed >= 0) close(observed);
    return result;
}

static inline int kiosk_realization_entry_compare(const void *a, const void *b)
{ return strcmp(((const struct kiosk_pin_entry *)a)->relative, ((const struct kiosk_pin_entry *)b)->relative); }

static inline int kiosk_realization_add_entry(struct kiosk_native_realization *r, const char *relative)
{
    unsigned depth = 0;
    for (const char *p = relative; *p; p++) depth += *p == '/';
    if (depth > 128) return -1;
    for (unsigned i = 0; i < r->entry_count; i++) if (!strcmp(r->entries[i].relative, relative)) return 0;
    if (r->entry_count >= KIOSK_VIEW_ROWS || kiosk_pin_before(r->deadline) != 0) return -1;
    int fd = kiosk_pin_open(r->root, relative); struct stat s;
    unsigned long long id, parent_id;
    if (fd < 0 || fstat(fd, &s) != 0 || !kiosk_trusted_stat(&s, 0) ||
        (!S_ISREG(s.st_mode) && !S_ISDIR(s.st_mode)) || kiosk_pin_fd_mount(fd, &id) != 0) {
        if (fd >= 0) close(fd);
        return -1;
    }
    close(fd);
    int mounted = !*relative;
    if (*relative) {
        char parent[PATH_MAX]; strcpy(parent, relative); char *slash = strrchr(parent, '/');
        if (slash) *slash = 0; else parent[0] = 0;
        if (kiosk_realization_add_entry(r, parent) != 0) return -1;
        fd = kiosk_pin_open(r->root, parent);
        int valid = fd >= 0 && kiosk_pin_fd_mount(fd, &parent_id) == 0;
        if (fd >= 0) close(fd);
        if (!valid) return -1;
        mounted = id != parent_id;
    }
    struct kiosk_pin_entry *e = &r->entries[r->entry_count++];
    *e = (struct kiosk_pin_entry){.relative = strdup(relative), .device = s.st_dev, .inode = s.st_ino,
        .mode = s.st_mode, .uid = s.st_uid, .gid = s.st_gid, .mountpoint = mounted};
    return e->relative ? 0 : -1;
}

/* The kernel mount table supplies independent actual recursive coverage. A
 * retained coverage row must match its acquired V inode, not just its pathname.
 * Stack-hidden, duplicate and unowned mounts fail later strict topology checks.
 */
static inline int kiosk_realization_inventory(struct kiosk_native_realization *r, const struct kiosk_receipt *v)
{
    char descriptor[64], root_path[PATH_MAX];
    snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", r->root);
    ssize_t n = readlink(descriptor, root_path, sizeof(root_path) - 1);
    if (n <= 0 || n >= PATH_MAX - 1) return -1;
    root_path[n] = 0;
    if (!kiosk_path(root_path, 1)) return -1;
    for (unsigned i = 0; i < r->count; i++) {
        struct kiosk_realized_node *node = &r->nodes[i];
        if (strcmp(node->kind, "link") && strcmp(node->kind, "absent") &&
            kiosk_realization_add_entry(r, kiosk_realization_relative(node->plan->path)) != 0) return -1;
    }
    FILE *stream = fopen("/proc/self/mountinfo", "re");
    if (!stream) return -1;
    char *line = NULL; size_t cap = 0, total = 0; int result = -1;
    while (getline(&line, &cap, stream) >= 0) {
        char encoded[PATH_MAX];
        if (kiosk_pin_before(r->deadline) != 0 || (total += strlen(line)) > KIOSK_VIEW_BYTES ||
            sscanf(line, "%*u %*u %*s %*s %4095s", encoded) != 1 || kiosk_pin_decode_mountpath(encoded) != 0) goto done;
        if (!kiosk_below(encoded, root_path)) continue;
        const char *relative = encoded + strlen(root_path) + 1;
        char path[PATH_MAX]; if (snprintf(path, sizeof(path), "/usr/%s", relative) >= PATH_MAX) goto done;
        if (kiosk_realization_find(r, path) >= 0) continue;
        int owner = -1;
        for (unsigned i = 0; i < r->count; i++) if (!strcmp(r->nodes[i].kind, "directory") &&
            r->nodes[i].mounted && kiosk_below(path, r->nodes[i].plan->path)) { owner = (int)i; break; }
        if (owner < 0 || r->coverage_count >= KIOSK_VIEW_ROWS || kiosk_realization_add_entry(r, relative) != 0) goto done;
        struct kiosk_realized_coverage *c = &r->coverage[r->coverage_count++];
        c->path = strdup(path); c->owner = (unsigned)owner;
        int fd = kiosk_pin_open(r->root, relative);
        int valid = c->path && fd >= 0 && fstat(fd, &c->info) == 0;
        if (fd >= 0) close(fd);
        if (!valid) goto done;
        c->origin[0] = c->info.st_dev; c->origin[1] = c->info.st_ino;
        if (v) {
            const struct kiosk_receipt_row *found = NULL;
            for (unsigned j = 0; j < v->nc; j++) if (!strcmp(v->coverage[j].v[KC_PATH], path)) { found = &v->coverage[j]; break; }
            if (!found || found->number[KC_OWNER] != (unsigned)owner || found->number[KC_DEV] != (uint64_t)c->info.st_dev ||
                found->number[KC_INO] != (uint64_t)c->info.st_ino) goto done;
            c->origin[0] = found->number[KC_ORIGIN_DEV]; c->origin[1] = found->number[KC_ORIGIN_INO];
        }
    }
    if (ferror(stream)) goto done;
    /* A missing recursive mount is not an ambient omission. Only omission of
     * its entire eligible shallow owner can remove a V coverage witness. */
    if (v) for (unsigned i = 0; i < v->nc; i++) {
        unsigned owner = (unsigned)v->coverage[i].number[KC_OWNER];
        if (owner >= r->count) goto done;
        if (!strcmp(r->nodes[owner].kind, "empty-directory")) continue;
        unsigned found = 0;
        for (unsigned j = 0; j < r->coverage_count; j++) found += !strcmp(v->coverage[i].v[KC_PATH], r->coverage[j].path);
        if (found != 1) goto done;
    }
    qsort(r->entries, r->entry_count, sizeof(*r->entries), kiosk_realization_entry_compare);
    for (unsigned i = 1; i < r->entry_count; i++) {
        char parent[PATH_MAX]; strcpy(parent, r->entries[i].relative); char *slash = strrchr(parent, '/');
        if (slash) *slash = 0; else parent[0] = 0;
        unsigned j = 0; while (j < i && strcmp(parent, r->entries[j].relative)) j++;
        if (j == i) goto done;
        r->entries[i].parent = j;
    }
    struct kiosk_failure failure = {0};
    result = kiosk_pin_coverage_policy_until(r->root, r->entries, r->entry_count, NULL, 0, r->deadline, &failure);
done:
    free(line); fclose(stream); return result;
}

struct kiosk_realization_buffer { char *bytes; size_t used, allocated; };
static inline int kiosk_realization_append(struct kiosk_realization_buffer *b, const char *format, ...)
{
    va_list ap, copy; va_start(ap, format); va_copy(copy, ap);
    int n = vsnprintf(NULL, 0, format, copy); va_end(copy);
    if (n < 0 || (size_t)n > KIOSK_RECEIPT_BYTES - b->used) { va_end(ap); return -1; }
    size_t need = b->used + (size_t)n + 1;
    if (need > b->allocated) {
        size_t allocated = need > b->allocated * 2 ? need : b->allocated * 2;
        if (allocated > KIOSK_RECEIPT_BYTES + 1) allocated = KIOSK_RECEIPT_BYTES + 1;
        char *bytes = realloc(b->bytes, allocated);
        if (!bytes) { va_end(ap); return -1; } b->bytes = bytes; b->allocated = allocated;
    }
    vsnprintf(b->bytes + b->used, b->allocated - b->used, format, ap); va_end(ap); b->used += (size_t)n; return 0;
}

static inline int kiosk_realization_coverage_compare(const void *a, const void *b)
{ return strcmp(((const struct kiosk_realized_coverage *)a)->path, ((const struct kiosk_realized_coverage *)b)->path); }

static inline int kiosk_realization_serialize(struct kiosk_native_realization *r, const struct kiosk_material_authority *a,
                                             const struct kiosk_receipt *v, const char *acquisition, void *crypto)
{
    struct kiosk_realization_buffer b = {0}; int result = -1;
    if (!kiosk_receipt_hex(acquisition) || kiosk_realization_append(&b,
        "ONPC-KIOSK-RECEIPT\t2\t%s\t%s\t%s\t%s\t%s\t%s\n", v ? "I" : "V", a->backend,
        v ? "gate" : "manager", a->digest, v ? v->digest : "-", acquisition) != 0) goto done;
    for (unsigned i = 0; i < r->count; i++) {
        struct kiosk_realized_node *n = &r->nodes[i]; const struct kiosk_preparation_row *p = n->plan;
        int omitted = !strcmp(n->kind, "absent") || !strcmp(n->kind, "empty-directory");
        if (!omitted) {
            int fd = kiosk_pin_open(r->root, kiosk_realization_relative(p->path)); struct stat actual;
            if (fd < 0 || fstat(fd, &actual) != 0) { if (fd >= 0) close(fd); goto done; }
            close(fd);
            if (n->mounted && !kiosk_pin_same_stat(&actual, &n->info)) goto done;
            n->info = actual;
        }
        struct stat zero = {0}; const struct stat *s = omitted ? &zero : &n->info;
        uint64_t origin_dev = p->origin[0], origin_ino = p->origin[1];
        if (!origin_ino && !omitted) { origin_dev = s->st_dev; origin_ino = s->st_ino; }
        if (kiosk_pin_before(r->deadline) != 0 || kiosk_realization_append(&b,
            "N\t%s\t%s\t%d\t%s\t%s\t%s\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%s\t%s\t%s\t%d\n",
            p->path, n->kind, p->required, p->source_class, omitted ? "none" : v ? "retained" : "initial", p->role,
            (unsigned long long)p->slot, (unsigned long long)origin_dev, (unsigned long long)origin_ino,
            (unsigned long long)s->st_dev, (unsigned long long)s->st_ino, (unsigned long long)s->st_size,
            (unsigned long long)s->st_mtim.tv_sec * 1000000000ULL + s->st_mtim.tv_nsec,
            (unsigned long long)s->st_ctim.tv_sec * 1000000000ULL + s->st_ctim.tv_nsec,
            (unsigned long long)s->st_mode, (unsigned long long)s->st_uid, (unsigned long long)s->st_gid,
            (unsigned long long)s->st_nlink, n->sha[0] && !omitted ? n->sha : "-",
            n->label[0] && !omitted ? n->label : "-", !strcmp(n->kind, "link") ? p->link : "-",
            !strcmp(n->kind, "tree") && !i ? 1 : n->mounted) != 0) goto done;
    }
    qsort(r->coverage, r->coverage_count, sizeof(*r->coverage), kiosk_realization_coverage_compare);
    for (unsigned i = 0; i < r->coverage_count; i++) {
        const struct kiosk_realized_coverage *c = &r->coverage[i]; const struct stat *s = &c->info;
        if (kiosk_pin_before(r->deadline) != 0 || kiosk_realization_append(&b,
            "C\t%u\t%s\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\n", c->owner, c->path,
            (unsigned long long)c->origin[0], (unsigned long long)c->origin[1], (unsigned long long)s->st_dev,
            (unsigned long long)s->st_ino, (unsigned long long)s->st_size,
            (unsigned long long)s->st_mtim.tv_sec * 1000000000ULL + s->st_mtim.tv_nsec,
            (unsigned long long)s->st_ctim.tv_sec * 1000000000ULL + s->st_ctim.tv_nsec,
            (unsigned long long)s->st_mode, (unsigned long long)s->st_uid, (unsigned long long)s->st_gid) != 0) goto done;
    }
    if (kiosk_receipt_parse(&r->receipt, b.bytes, b.used, crypto, r->deadline) != 0 ||
        (v && kiosk_receipt_derivation(v, &r->receipt, r->deadline) != 0)) goto done;
    r->bytes = b.bytes; r->size = b.used; b.bytes = NULL; result = 0;
done:
    free(b.bytes); return result;
}

/* Caller must establish fresh target ownership/private mount namespace first.
 * Failure retains explicit stage inventory for identity-owned cleanup. */
static inline int kiosk_realization_bind_until(struct kiosk_native_realization *r, int skeleton,
                                              const struct kiosk_preparation_plan *plan,
                                              const struct kiosk_material_authority *authority,
                                              const struct kiosk_host_roots *host, int clone, int copies,
                                              const struct kiosk_receipt *source, const char *acquisition,
                                              void *crypto, uint64_t deadline, struct kiosk_failure *failure)
{
    memset(r, 0, sizeof(*r)); r->root = -1; r->deadline = deadline; r->source = source;
    if (!plan || !plan->verified || plan->deadline != deadline || authority->deadline != deadline ||
        !plan->count || plan->count > KIOSK_VIEW_ROWS || (source != NULL) != (clone >= 0) ||
        kiosk_pin_before(deadline) != 0 || (r->root = fcntl(skeleton, F_DUPFD_CLOEXEC, 3)) < 0 ||
        !(r->nodes = calloc(plan->count, sizeof(*r->nodes))) ||
        !(r->coverage = calloc(KIOSK_VIEW_ROWS, sizeof(*r->coverage))) ||
        !(r->entries = calloc(KIOSK_VIEW_ROWS, sizeof(*r->entries))) ||
        !(r->stages = calloc(KIOSK_VIEW_ROWS, sizeof(*r->stages)))) goto denied;
    r->selinux = !strcmp(authority->backend, "selinux");
    r->count = plan->count;
    for (unsigned i = 0; i < r->count; i++) { r->nodes[i].plan = &plan->rows[i]; r->nodes[i].kind = plan->rows[i].kind; }
    if (strcmp(r->nodes[0].plan->path, "/usr") || strcmp(r->nodes[0].kind, "tree") ||
        kiosk_realization_structure(r, 0, 1, NULL) != 0) goto denied;
    for (unsigned i = 1; i < r->count; i++) if (kiosk_realization_bind(r, i, host, clone, copies, crypto) != 0) goto denied;
    if (kiosk_realization_structure(r, 0, 0, NULL) != 0 || kiosk_realization_inventory(r, source) != 0 ||
        kiosk_realization_serialize(r, authority, source, acquisition, crypto) != 0) goto denied;
    r->bound = 1; return 0;
denied:
    kiosk_failure(failure, "realization", "identity", -1); return -1;
}

/* Receipt hashes deliberately exclude the private marker. The coordinator
 * creates this exact native-owned inode from the completed digest, then this
 * call independently checks bytes/identity and adds it to strict mount coverage.
 * The marker cannot add a mount or hide any plan row. */
static inline int kiosk_realization_marker_until(struct kiosk_native_realization *r, const char *path,
                                                int expected, const void *bytes, size_t size,
                                                uint64_t deadline, struct kiosk_failure *failure)
{
    struct stat s, e, after; unsigned long long id, root_id; char buffer[4096]; int fd = -1, result = -1;
    if (!r->bound || r->marker_verified || deadline != r->deadline || !kiosk_receipt_path(path) ||
        kiosk_realization_find(r, path) >= 0 || !bytes || !size || size >= sizeof(buffer) ||
        kiosk_pin_before(deadline) != 0 || fstat(expected, &e) != 0 || !kiosk_trusted_stat(&e, S_IFREG) || e.st_nlink != 1 ||
        (e.st_mode & 07777) != 0444 || e.st_size != (off_t)size) goto done;
    fd = kiosk_pin_open(r->root, kiosk_realization_relative(path));
    if (fd < 0 || fstat(fd, &s) != 0 || !kiosk_pin_same_stat(&s, &e) || kiosk_pin_fd_mount(fd, &id) != 0 ||
        kiosk_pin_fd_mount(r->root, &root_id) != 0 || id != root_id) goto done;
    close(fd); fd = openat(r->root, kiosk_realization_relative(path), O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0 || pread(fd, buffer, size, 0) != (ssize_t)size || memcmp(buffer, bytes, size) ||
        pread(fd, buffer, 1, size) != 0 || fstat(fd, &after) != 0 || !kiosk_pin_same_stat(&e, &after) ||
        kiosk_realization_structure(r, 0, 0, path) != 0 || kiosk_realization_add_entry(r, kiosk_realization_relative(path)) != 0 ||
        kiosk_pin_before(deadline) != 0) goto done;
    /* Re-sort/re-parent after adding the marker. */
    qsort(r->entries, r->entry_count, sizeof(*r->entries), kiosk_realization_entry_compare);
    for (unsigned i = 1; i < r->entry_count; i++) {
        char parent[PATH_MAX]; strcpy(parent, r->entries[i].relative); char *slash = strrchr(parent, '/');
        if (slash) *slash = 0; else parent[0] = 0;
        unsigned j = 0; while (j < i && strcmp(parent, r->entries[j].relative)) j++;
        if (j == i) goto done;
        r->entries[i].parent = j;
    }
    r->marker_verified = 1; result = 0;
done:
    if (fd >= 0) close(fd);
    if (result) kiosk_failure(failure, "realization", "marker", -1);
    return result;
}

/* Clone only the actual checked skeleton, recursively seal it, then use the
 * established strict attachment/topology owner. Caller supplies combined owned
 * staging inventory to kiosk_pin_finish_until() before ready publication. */
static inline int kiosk_realization_attach_until(struct kiosk_native_realization *r, struct kiosk_source_pin *pin,
                                                int parent, const char *name, const struct kiosk_pin_target *target,
                                                uint64_t deadline, struct kiosk_failure *failure)
{
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
    if (!r->bound || !r->marker_verified || deadline != r->deadline || pin->fd != -1 || pin->parent != -1 ||
        pin->worker != -1 || pin->attached || kiosk_pin_before(deadline) != 0 ||
        kiosk_pin_coverage_policy_until(r->root, r->entries, r->entry_count, NULL, 0, deadline, failure) != 0 ||
        (pin->fd = open_tree(r->root, "", AT_EMPTY_PATH | AT_RECURSIVE | OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC)) < 0 ||
        kiosk_pin_before(deadline) != 0 ||
        mount_setattr(pin->fd, "", AT_EMPTY_PATH | AT_RECURSIVE, &readonly, sizeof(readonly)) != 0 ||
        kiosk_pin_attach_until(pin, parent, name, target, r->entries, r->entry_count, deadline, failure) != 0) {
        kiosk_failure(failure, "realization", "attach", -1); return -1;
    }
    return 0;
}

/* Complete retained-tree closure/content check in addition to pin topology.
 * The coordinator independently binds V and the native marker to the live
 * manager. This function never derives required authority from V's flag: every
 * material member and its tree ancestors are mandatory. Ambient provenance may
 * be unsafe now, but its original inode/type must survive for local narrowing.
 * Marker bytes/inode are verified by the coordinator before and after this
 * call; the one excluded path cannot shadow any receipt node.
 */
static inline int kiosk_realization_verify_source_until(int root, const struct kiosk_receipt *v,
                                                       struct kiosk_material_authority *a,
                                                       const char *marker,
                                                       const struct kiosk_pin_entry *entries, unsigned count,
                                                       const unsigned char *ambient, void *crypto,
                                                       uint64_t deadline, struct kiosk_failure *failure)
{
    struct kiosk_native_realization r = {.root = root, .deadline = deadline, .source_check = 1};
    struct kiosk_preparation_row *rows = NULL;
    int result = -1;
    if (!v || kiosk_preparation_view_authority_until(v, a, deadline) != 0 ||
        strcmp(v->kind, "V") || strcmp(v->material, a->digest) || strcmp(v->backend, a->backend) ||
        !marker || !kiosk_receipt_path(marker) || kiosk_receipt_find(v, marker) ||
        a->deadline != deadline || !v->nn || v->nn > KIOSK_VIEW_ROWS ||
        !(rows = calloc(v->nn, sizeof(*rows))) || !(r.nodes = calloc(v->nn, sizeof(*r.nodes))) ||
        kiosk_pin_coverage_policy_until(root, entries, count, ambient, 1, deadline, failure) != 0) goto done;
    r.count = v->nn; r.selinux = !strcmp(a->backend, "selinux");
    for (unsigned i = 0; i < r.count; i++) {
        const struct kiosk_receipt_row *n = &v->nodes[i];
        rows[i] = (struct kiosk_preparation_row){.path = n->v[KR_PATH], .kind = n->v[KR_KIND],
            .link = n->v[KR_LINK], .required = (int)n->number[KR_REQUIRED],
            .source_class = n->v[KR_CLASS], .role = n->v[KR_ROLE]};
        r.nodes[i].plan = &rows[i]; r.nodes[i].kind = rows[i].kind;
        r.nodes[i].mounted = (int)n->number[KR_MOUNT];
        for (unsigned j = 0; j < a->count; j++) if (!strcmp(a->specs[j].path, rows[i].path)) rows[i].spec = &a->specs[j];
        /* Material membership and every explicit ancestor cannot be forged as
         * ambient, an absence or a shallow directory by the saved receipt. */
        int mandatory = rows[i].spec != NULL;
        for (unsigned j = 0; j < a->count && !mandatory; j++) mandatory = kiosk_below(a->specs[j].path, rows[i].path);
        if (mandatory && !rows[i].required) goto done;
        if (rows[i].spec && (strcmp(rows[i].source_class, rows[i].spec->source_class) ||
            strcmp(rows[i].role, rows[i].spec->role) || strcmp(rows[i].kind, rows[i].spec->kind))) goto done;
        int fd = kiosk_pin_provenance_open(root, kiosk_realization_relative(rows[i].path));
        if (!strcmp(rows[i].kind, "absent")) {
            if (fd >= 0) { close(fd); goto done; }
            if (errno != ENOENT) goto done;
            continue;
        }
        struct stat s, after;
        if (fd < 0 || fstat(fd, &s) != 0) { if (fd >= 0) close(fd); goto done; }
        if (!strcmp(rows[i].kind, "empty-directory")) {
            int valid = kiosk_trusted_stat(&s, S_IFDIR) && (s.st_mode & 07777) == 0755;
            close(fd); if (!valid) goto done; continue;
        }
        if ((uint64_t)s.st_dev != n->number[KR_DEV] || (uint64_t)s.st_ino != n->number[KR_INO] ||
            (s.st_mode & S_IFMT) != (mode_t)(n->number[KR_MODE] & S_IFMT)) { close(fd); goto done; }
        int is_ambient = !strcmp(rows[i].source_class, "ambient") && !mandatory;
        if (!is_ambient && (!kiosk_trusted_stat(&s, 0) || s.st_mode != (mode_t)n->number[KR_MODE] ||
            s.st_uid != n->number[KR_UID] || s.st_gid != n->number[KR_GID])) { close(fd); goto done; }
        if (S_ISLNK(s.st_mode)) {
            char text[PATH_MAX]; ssize_t length = readlinkat(fd, "", text, sizeof(text));
            close(fd);
            if (length <= 0 || length >= PATH_MAX) goto done;
            text[length] = 0; if (strcmp(text, rows[i].link)) goto done;
            continue;
        }
        if (!is_ambient && S_ISREG(s.st_mode)) {
            char descriptor[64], sha[65], label[256]; snprintf(descriptor, sizeof(descriptor), "/proc/self/fd/%d", fd);
            int readable = open(descriptor, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
            int vendor = !strcmp(rows[i].source_class, "vendor");
            int valid = readable >= 0 && (s.st_nlink == 1 || (vendor && s.st_nlink == 0)) &&
                (uint64_t)s.st_size == n->number[KR_SIZE] && rows[i].spec &&
                (uint64_t)s.st_size <= KIOSK_HOST_FILE_BYTES - r.measured;
            if (valid) {
                r.measured += (uint64_t)s.st_size;
                ssize_t capability = fgetxattr(readable, "security.capability", NULL, 0);
                valid = capability < 0 && errno == ENODATA;
                valid = valid && kiosk_host_sha256_library_until(readable, s.st_size, sha, crypto, deadline) == 0 &&
                    !strcmp(sha, rows[i].spec->sha256) && !strcmp(sha, n->v[KR_SHA]) &&
                    kiosk_host_label(readable, label) == 0 && !strcmp(label[0] ? label : "-", n->v[KR_LABEL]) &&
                    fstat(readable, &after) == 0 && kiosk_pin_same_stat(&s, &after);
            }
            if (readable >= 0) close(readable);
            close(fd); if (!valid) goto done;
        } else close(fd);
    }
    for (unsigned j = 0; j < a->count; j++) if (!kiosk_receipt_find(v, a->specs[j].path)) goto done;
    if (kiosk_realization_structure(&r, 0, 0, marker) != 0 || kiosk_pin_before(deadline) != 0) goto done;
    result = 0;
done:
    free(rows); free(r.nodes);
    if (result) kiosk_failure(failure, "realization", "source-closure", -1);
    return result;
}

/* Never detaches stages implicitly or recovers a refused owner. The coordinator
 * owns serial cleanup and must finish it before freeing this inventory. */
static inline void kiosk_realization_close(struct kiosk_native_realization *r)
{
    if (r->root >= 0) close(r->root);
    for (unsigned i = 0; i < r->coverage_count; i++) free(r->coverage[i].path);
    for (unsigned i = 0; i < r->entry_count; i++) free((void *)r->entries[i].relative);
    for (unsigned i = 0; i < r->stage_count; i++) free(r->stages[i].path);
    free(r->nodes); free(r->coverage); free(r->entries); free(r->stages); free(r->bytes); kiosk_receipt_free(&r->receipt);
    memset(r, 0, sizeof(*r)); r->root = -1;
}
#endif
