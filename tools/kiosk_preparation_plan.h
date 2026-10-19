#ifndef ONPC_KIOSK_PREPARATION_PLAN_H
#define ONPC_KIOSK_PREPARATION_PLAN_H
/* Preparation returns intent, never source authority. All input descriptors
 * are borrowed. Rows retain the complete original slot domain; no descriptor
 * per row is retained. The binder reopens checked names and repeats assertions.
 * Required sources and copies are independently checked here. Initial ambient
 * assertions are frozen intent only: the binder must independently reobserve
 * each source, narrow eligible changes and never adopt a replacement inode.
 * V must additionally have independent actual mount/clone coverage verification.
 * This module performs no binding, publication, cleanup or admission. */
#include "kiosk_material_authority.h"
#include <sys/syscall.h>
#include <linux/stat.h>

struct kiosk_preparation_row {
    const char *path, *kind, *original_kind, *link, *source_class, *role;
    const char *source_path, *copy_name;
    uint64_t slot, index, assertion[8], copy_identity[8], origin[2], source_identity[2];
    int required, has_source, copied;
    const struct kiosk_material_spec *spec;
};
struct kiosk_preparation_plan {
    struct kiosk_material_json json;
    struct kiosk_preparation_row *rows;
    unsigned count, ticket_members;
    const char *ticket_name;
    uint64_t ticket_root[2], ticket_parent[2], deadline;
    int verified;
};

static inline void kiosk_preparation_plan_free(struct kiosk_preparation_plan *p)
{
    free(p->json.storage); free(p->json.nodes); free(p->rows);
    memset(p, 0, sizeof(*p));
}
static inline struct kiosk_preparation_row *kiosk_preparation_plan_find(
    const struct kiosk_preparation_plan *p, const char *path)
{
    unsigned lo = 0, hi = p->count;
    while (lo < hi) { unsigned m = lo + (hi - lo) / 2;
        if (strcmp(p->rows[m].path, path) < 0) lo = m + 1; else hi = m; }
    return lo < p->count && !strcmp(p->rows[lo].path, path) ? p->rows + lo : NULL;
}
static inline void kiosk_preparation_assertion(const struct stat *s, uint64_t v[8])
{
    v[0] = s->st_dev; v[1] = s->st_ino; v[2] = s->st_size;
    v[3] = (uint64_t)s->st_mtim.tv_sec * 1000000000ULL + s->st_mtim.tv_nsec;
    v[4] = (uint64_t)s->st_ctim.tv_sec * 1000000000ULL + s->st_ctim.tv_nsec;
    v[5] = s->st_mode; v[6] = s->st_uid; v[7] = s->st_gid;
}
static inline int kiosk_preparation_same(const struct stat *s, const uint64_t v[8])
{ uint64_t actual[8]; kiosk_preparation_assertion(s, actual); return !memcmp(actual, v, sizeof(actual)); }
static inline int kiosk_preparation_kind(const struct stat *s, const char *kind)
{
    return !strcmp(kind, "file") ? S_ISREG(s->st_mode) : !strcmp(kind, "link") ? S_ISLNK(s->st_mode) :
        (!strcmp(kind, "tree") || !strcmp(kind, "directory")) && S_ISDIR(s->st_mode);
}
/* Initial scanning is exactly one level beneath native-derived covered trees.
 * A helper cannot invent a tree to grow the ambient source allowlist. */
static inline int kiosk_preparation_ambient_path(const struct kiosk_material_authority *a, const char *path)
{
    if (!kiosk_material_usr(path) || !strcmp(path, "/usr")) return 0;
    char parent[PATH_MAX]; strcpy(parent, path); *strrchr(parent, '/') = 0;
    const struct kiosk_material_spec *spec = kiosk_material_find(a, parent);
    if (!spec || strcmp(spec->kind, "tree")) return 0;
    size_t size = strlen(path);
    for (unsigned i = 0; i < a->count; i++) {
        if (kiosk_receipt_before(a->deadline)) return 0;
        if (!strncmp(a->specs[i].path, path, size) && a->specs[i].path[size] == '/') return 0;
    }
    return 1;
}
static inline int kiosk_preparation_array(const struct kiosk_material_json *j,
    unsigned n, uint64_t *v, unsigned size)
{
    if (!n || j->nodes[n].type != '[' || j->nodes[n].count != size) return -1;
    unsigned i = 0;
    for (unsigned c = j->nodes[n].child; c; c = j->nodes[c].next) {
        if (j->nodes[c].type != '#' || kiosk_receipt_before(j->deadline)) return -1;
        v[i++] = j->nodes[c].number;
    }
    return 0;
}
static inline int kiosk_preparation_equal(const struct kiosk_material_json *a, unsigned x,
    const struct kiosk_material_json *b, unsigned y, unsigned depth)
{
    if (!x || !y || depth > 64 || kiosk_receipt_before(a->deadline) ||
        a->nodes[x].type != b->nodes[y].type || a->nodes[x].count != b->nodes[y].count) return 0;
    char type = a->nodes[x].type;
    if (type == '"') return !strcmp(a->nodes[x].text, b->nodes[y].text);
    if (type == '#') return a->nodes[x].number == b->nodes[y].number;
    unsigned q = b->nodes[y].child;
    for (unsigned p = a->nodes[x].child; p; p = a->nodes[p].next) {
        unsigned match = type == '{' ? kiosk_material_get(b, y, a->nodes[p].key) : q;
        if (!kiosk_preparation_equal(a, p, b, match, depth + 1)) return 0;
        if (q) q = b->nodes[q].next;
    }
    return 1;
}
/* Bounded stable record read, canonical encoding and duplicate rejection. */
static inline int kiosk_preparation_json_fd(struct kiosk_material_json *j, int fd, uint64_t deadline)
{
    struct stat before, after; char *bytes = NULL; int result = -1;
    if (kiosk_receipt_before(deadline) || fstat(fd, &before) || !S_ISREG(before.st_mode) ||
        before.st_size <= 0 || (uint64_t)before.st_size > KIOSK_RECEIPT_BYTES) return -1;
    bytes = malloc((size_t)before.st_size);
    if (!bytes) return -1;
    for (size_t offset = 0; offset < (size_t)before.st_size;) {
        if (kiosk_receipt_before(deadline)) goto done;
        size_t count = (size_t)before.st_size - offset;
        if (count > 65536) count = 65536;
        ssize_t n = pread(fd, bytes + offset, count, (off_t)offset);
        if (n <= 0) goto done;
        offset += (size_t)n;
    }
    struct kiosk_receipt_json canonical = {bytes, bytes + before.st_size, deadline, 0};
    if (fstat(fd, &after) || !kiosk_host_same(&before, &after) ||
        kiosk_receipt_json_value(&canonical, 0) || canonical.p != canonical.end ||
        kiosk_material_json_parse(j, bytes, (size_t)before.st_size, deadline)) goto done;
    result = 0;
done:
    free(bytes); return result;
}
/* No kernel symlink traversal, including intermediate components. The root is
 * already the independently selected original /usr or acquired retained clone. */
static inline int kiosk_preparation_open(int usr, const char *path, int readable, uint64_t deadline)
{
    if (!kiosk_material_usr(path) || kiosk_receipt_before(deadline)) return -1;
    int current = fcntl(usr, F_DUPFD_CLOEXEC, 3);
    if (current < 0 || !strcmp(path, "/usr")) return current;
    char components[PATH_MAX]; strcpy(components, path + 5); char *part = components;
    for (;;) {
        char *slash = strchr(part, '/'); if (slash) *slash = 0;
        if (kiosk_receipt_before(deadline)) { close(current); return -1; }
        int next = openat(current, part, O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK |
            (slash ? O_PATH | O_DIRECTORY : readable ? O_RDONLY : O_PATH));
        close(current); if (next < 0) return -1;
        current = next; if (!slash) return current; part = slash + 1;
    }
}
static inline int kiosk_preparation_file(int fd, const struct kiosk_material_spec *s,
    const char *backend, void *crypto, uint64_t deadline, int copied, const uint64_t identity[8])
{
    struct stat before, after; char digest[65], label[256];
    if (kiosk_receipt_before(deadline) || fstat(fd, &before) || !S_ISREG(before.st_mode) ||
        !kiosk_preparation_same(&before, identity) || before.st_uid != KIOSK_HOST_PROOF_OWNER ||
        before.st_gid != KIOSK_HOST_PROOF_GROUP || (before.st_mode & 022) ||
        (before.st_nlink != 1 && !(s->privileged && !copied && before.st_nlink == 0)) ||
        (!s->privileged && (before.st_mode & 06000)) ||
        (uint64_t)before.st_size != s->size || (before.st_mode & 07777) != s->mode) return -1;
    errno = 0;
    if (fgetxattr(fd, "security.capability", NULL, 0) >= 0 || errno != ENODATA) return -1;
    if (!strcmp(backend, "selinux") && (kiosk_host_label(fd, label) || strcmp(label, s->label))) return -1;
    if (kiosk_host_sha256_library_until(fd, before.st_size, digest, crypto, deadline) ||
        strcmp(digest, s->sha256)) return -1;
    if (!strcmp(s->source_class, "native") || !strcmp(s->source_class, "vendor")) {
        unsigned char magic[4];
        if (pread(fd, magic, sizeof(magic), 0) != 4 || memcmp(magic, "\177ELF", 4)) return -1;
    }
    return fstat(fd, &after) || !kiosk_preparation_same(&after, identity) || kiosk_receipt_before(deadline) ? -1 : 0;
}

/* Semantic checks before clone acquisition. The receipt parser supplies closed
 * syntax only. Required membership/class/content/role here comes from native M.
 * Ambient flags are derived using material_find(), never trusted from V. */
static inline int kiosk_preparation_view_authority_until(const struct kiosk_receipt *v,
    struct kiosk_material_authority *a, uint64_t deadline)
{
    if (!v || !a || deadline != a->deadline || kiosk_receipt_before(deadline) ||
        !kiosk_material_equal(v->kind, "V") || !kiosk_material_equal(v->role, "manager") ||
        !kiosk_material_equal(v->backend, a->backend) || !kiosk_material_equal(v->material, a->digest) ||
        !v->nn || v->nn > KIOSK_RECEIPT_ROWS) return -1;
    unsigned required = 0;
    for (unsigned i = 0; i < v->nn; i++) {
        const struct kiosk_receipt_row *r = v->nodes + i;
        const struct kiosk_material_spec *s = kiosk_material_find(a, r->v[KR_PATH]);
        if (kiosk_receipt_before(deadline) || (i && strcmp(v->nodes[i - 1].v[KR_PATH], r->v[KR_PATH]) >= 0) ||
            (i && v->nodes[i - 1].number[KR_INDEX] >= r->number[KR_INDEX]) ||
            r->number[KR_REQUIRED] != (uint64_t)(s != NULL)) return -1;
        if (!s) {
            if (!strcmp(r->v[KR_KIND], "tree") || !kiosk_preparation_ambient_path(a, r->v[KR_PATH]) ||
                strcmp(r->v[KR_CLASS], "ambient") || strcmp(r->v[KR_ROLE], "ambient")) return -1;
            continue;
        }
        required++;
        if (strcmp(r->v[KR_KIND], s->kind) || strcmp(r->v[KR_CLASS], s->source_class) ||
            strcmp(r->v[KR_ROLE], s->role) || strcmp(r->v[KR_LINK], s->link ? s->link : "-")) return -1;
        if (!strcmp(s->kind, "file") && (strcmp(r->v[KR_SHA], s->sha256) ||
            strcmp(r->v[KR_LABEL], s->label) || r->number[KR_SIZE] != s->size ||
            (r->number[KR_MODE] & 07777) != s->mode || r->number[KR_UID] != KIOSK_HOST_PROOF_OWNER ||
            r->number[KR_GID] != KIOSK_HOST_PROOF_GROUP)) return -1;
    }
    return required == a->count && !strcmp(v->nodes[0].v[KR_PATH], "/usr") ? 0 : -1;
}

static inline int kiosk_preparation_mount(int fd, uint64_t *mount)
{
#ifdef SYS_statx
    struct statx sx;
    memset(&sx, 0, sizeof(sx));
    if (syscall(SYS_statx, fd, "", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, STATX_MNT_ID, &sx) ||
        !(sx.stx_mask & STATX_MNT_ID)) return -1;
    *mount = sx.stx_mnt_id; return 0;
#else
    (void)fd; (void)mount; return -1;
#endif
}

static inline int kiosk_preparation_layout(struct kiosk_preparation_plan *p, unsigned layout,
    int gate, const struct kiosk_receipt *v)
{
    struct kiosk_material_json *j = &p->json;
    if (!layout || j->nodes[layout].type != '[' || j->nodes[layout].count >= KIOSK_RECEIPT_ROWS) return -1;
    p->count = gate ? v->nn : j->nodes[layout].count + 1;
    p->rows = calloc(p->count, sizeof(*p->rows)); if (!p->rows) return -1;
    if (gate) for (unsigned i = 0; i < p->count; i++) {
        struct kiosk_preparation_row *r = p->rows + i; const struct kiosk_receipt_row *s = v->nodes + i;
        r->path = s->v[KR_PATH]; r->original_kind = s->v[KR_KIND];
        r->kind = !strcmp(r->original_kind, "directory") || !strcmp(r->original_kind, "empty-directory") ? "empty-directory" : "absent";
        r->link = s->v[KR_LINK]; r->slot = s->number[KR_INDEX];
        r->source_identity[0] = s->number[KR_DEV]; r->source_identity[1] = s->number[KR_INO];
        r->origin[0] = s->number[KR_ORIGIN_DEV]; r->origin[1] = s->number[KR_ORIGIN_INO];
        if (!i) r->kind = "tree";
    }
    else { p->rows[0].path = "/usr"; p->rows[0].kind = p->rows[0].original_kind = "tree"; p->rows[0].link = "-"; }
    unsigned index = 1; const char *previous = "/usr";
    for (unsigned n = j->nodes[layout].child; n; n = j->nodes[n].next, index++) {
        const char *path = kiosk_material_property(j, n, "path"), *kind = kiosk_material_property(j, n, "kind");
        static const char *const kinds[] = {"tree", "directory", "empty-directory", "file", "link", "absent", NULL};
        if (!path || !kind || !kiosk_material_usr(path) || strcmp(previous, path) >= 0 ||
            !kiosk_receipt_member(kind, kinds) || kiosk_material_schema(j, n, "path|kind|link", !strcmp(kind, "link") ? 3 : 2)) return -1;
        struct kiosk_preparation_row *r = gate ? kiosk_preparation_plan_find(p, path) : p->rows + index;
        if (!r || (gate && strcmp(kind, r->original_kind) &&
            !( !strcmp(r->original_kind, "directory") && !strcmp(kind, "empty-directory")))) return -1;
        const char *link = !strcmp(kind, "link") ? kiosk_material_property(j, n, "link") : "-";
        if (!link || !kiosk_receipt_text(link) || (gate && strcmp(link, r->link))) return -1;
        r->path = path; r->kind = kind; r->link = link;
        if (!gate) { r->original_kind = kind; r->slot = index; }
        previous = path;
    }
    /* Every concrete parent is a fresh tree, never a shallow ambient bind. */
    for (unsigned i = 1; i < p->count; i++) {
        char parent[PATH_MAX]; strcpy(parent, p->rows[i].path); *strrchr(parent, '/') = 0;
        struct kiosk_preparation_row *r = kiosk_preparation_plan_find(p, parent);
        if (!r || strcmp(r->kind, "tree")) return -1;
    }
    return 0;
}

static inline int kiosk_preparation_json_receipt_rows(const struct kiosk_material_json *j, unsigned n,
    const struct kiosk_receipt_row *rows, unsigned count, int coverage)
{
    static const char *const node[] = {"path","kind","required","source_class","acquisition","role","source_index",
        "origin_device","origin_inode","device","inode","size","mtime_ns","ctime_ns","mode","uid","gid","nlink",
        "sha256","label","link","mountpoint"};
    static const char *const cov[] = {"owner","path","origin_device","origin_inode","device","inode","size","mtime_ns","ctime_ns","mode","uid","gid"};
    const char *const *names = coverage ? cov : node; unsigned fields = coverage ? KC_FIELDS : KR_FIELDS;
    if (!n || j->nodes[n].type != '[' || j->nodes[n].count != count) return -1;
    unsigned i = 0;
    for (unsigned c = j->nodes[n].child; c; c = j->nodes[c].next, i++) {
        if (j->nodes[c].type != '{' || j->nodes[c].count != fields) return -1;
        for (unsigned f = 0; f < fields; f++) {
            unsigned value = kiosk_material_get(j, c, names[f]);
            int numeric = coverage ? f != KC_PATH : (f == KR_REQUIRED || (f >= KR_INDEX && f <= KR_NLINK) || f == KR_MOUNT);
            if (!value || (numeric ? j->nodes[value].type != '#' || j->nodes[value].number != rows[i].number[f] :
                !kiosk_material_equal(kiosk_material_text(j, value), rows[i].v[f]))) return -1;
        }
    }
    return 0;
}

static inline int kiosk_preparation_gate(struct kiosk_preparation_plan *p, unsigned plan,
    struct kiosk_material_authority *a, const struct kiosk_receipt *v, int clone, void *crypto)
{
    struct kiosk_material_json *j = &p->json;
    if (kiosk_material_schema(j, plan, "material|layout|sources|source_slots|source_nodes|source_coverage", 6) ||
        kiosk_preparation_view_authority_until(v, a, p->deadline) ||
        kiosk_preparation_json_receipt_rows(j, kiosk_material_get(j, plan, "source_nodes"), v->nodes, v->nn, 0) ||
        kiosk_preparation_json_receipt_rows(j, kiosk_material_get(j, plan, "source_coverage"), v->coverage, v->nc, 1) ||
        kiosk_preparation_layout(p, kiosk_material_get(j, plan, "layout"), 1, v)) return -1;
    unsigned slots = kiosk_material_get(j, plan, "source_slots"), sources = kiosk_material_get(j, plan, "sources");
    if (!slots || j->nodes[slots].type != '{' || j->nodes[slots].count != p->count ||
        !sources || j->nodes[sources].type != '{' || j->nodes[sources].count > p->count) return -1;
    for (unsigned i = 0; i < p->count; i++) {
        struct kiosk_preparation_row *r = p->rows + i;
        const struct kiosk_receipt_row *original = v->nodes + i;
        unsigned slot = kiosk_material_get(j, slots, r->path), source = kiosk_material_get(j, sources, r->path);
        if (!slot || j->nodes[slot].type != '#' || j->nodes[slot].number != r->slot) return -1;
        r->spec = kiosk_material_find(a, r->path); r->required = r->spec != NULL;
        r->source_class = original->v[KR_CLASS]; r->role = original->v[KR_ROLE]; r->source_path = r->path;
        if (!source) {
            if (r->required || (strcmp(r->kind, "absent") && strcmp(r->kind, "empty-directory"))) return -1;
            continue;
        }
        if (kiosk_material_schema(j, source, "index|assertion", 2) ||
            kiosk_material_number(j, source, "index", &r->index) || r->index != r->slot ||
            kiosk_preparation_array(j, kiosk_material_get(j, source, "assertion"), r->assertion, 8) ||
            (!strcmp(r->kind, "absent")) || !strcmp(r->kind, "empty-directory")) return -1;
        r->has_source = 1;
        if (!i) r->kind = "tree";
        int fd = kiosk_preparation_open(clone, r->path, !strcmp(r->kind, "file"), p->deadline);
        struct stat info; int ok = fd >= 0 && !fstat(fd, &info) && kiosk_preparation_kind(&info, r->kind) && kiosk_preparation_same(&info, r->assertion) &&
            (uint64_t)info.st_dev == r->source_identity[0] && (uint64_t)info.st_ino == r->source_identity[1] && kiosk_host_trust(&info);
        if (ok && r->spec && !strcmp(r->kind, "file")) ok = !kiosk_preparation_file(fd, r->spec, a->backend, crypto, p->deadline, 0, r->assertion);
        if (ok && !strcmp(r->kind, "link")) {
            char text[PATH_MAX]; ssize_t length = readlinkat(fd, "", text, sizeof(text) - 1);
            if (length <= 0) ok = 0; else { text[length] = 0; ok = !strcmp(text, r->link); }
        }
        if (fd >= 0) close(fd);
        if (!ok) return -1;
    }
    for (unsigned n = j->nodes[sources].child; n; n = j->nodes[n].next)
        if (!kiosk_preparation_plan_find(p, j->nodes[n].key)) return -1;
    return 0;
}

static inline int kiosk_preparation_payload_record(const struct kiosk_material_json *j, unsigned record,
    const struct kiosk_material_spec *s, const char *backend)
{
    uint64_t size, mode;
    if (!s || strcmp(s->source_class, "payload") ||
        kiosk_material_schema(j, record, "path|kind|role|sha256|size|mode|label", 7) ||
        !kiosk_material_equal(kiosk_material_property(j, record, "path"), s->path) ||
        !kiosk_material_equal(kiosk_material_property(j, record, "kind"), "file") ||
        !kiosk_material_equal(kiosk_material_property(j, record, "role"), "asset") ||
        kiosk_material_number(j, record, "size", &size) || size != s->size ||
        kiosk_material_number(j, record, "mode", &mode) || mode != s->mode ||
        !kiosk_material_equal(kiosk_material_property(j, record, "sha256"), s->sha256) ||
        !kiosk_material_equal(kiosk_material_label(j, record, "label", backend), s->label)) return -1;
    return 0;
}

static inline unsigned kiosk_preparation_record_path(const struct kiosk_material_json *j,
    unsigned records, const char *path, uint64_t *index)
{
    if (!records || j->nodes[records].type != '[') return 0;
    uint64_t i = 0;
    for (unsigned n = j->nodes[records].child; n; n = j->nodes[n].next, i++) {
        if (kiosk_receipt_before(j->deadline)) return 0;
        if (kiosk_material_equal(kiosk_material_property(j, n, "path"), path)) {
            if (index) *index = i;
            return n;
        }
    }
    return 0;
}
static inline int kiosk_preparation_copy_rows(struct kiosk_preparation_plan *p,
    unsigned copies, unsigned records, int native)
{
    struct kiosk_material_json *j = &p->json;
    if (!copies || j->nodes[copies].type != '[') return -1;
    unsigned count = 0;
    for (unsigned i = 0; i < p->count; i++)
        if (p->rows[i].copied && (!strcmp(p->rows[i].source_class, "native")) == native) count++;
    if (count != j->nodes[copies].count) return -1;
    uint64_t previous = 0; int first = 1;
    for (unsigned n = j->nodes[copies].child; n; n = j->nodes[n].next) {
        uint64_t index, identity[8];
        const char *name = kiosk_material_property(j, n, "name");
        if (kiosk_material_schema(j, n, "index|name|identity", 3) ||
            kiosk_material_number(j, n, "index", &index) || (!first && index <= previous) ||
            kiosk_preparation_array(j, kiosk_material_get(j, n, "identity"), identity, 8)) return -1;
        unsigned record = j->nodes[records].child;
        for (uint64_t i = 0; i < index && record; i++) record = j->nodes[record].next;
        if (!record) return -1;
        const char *path = kiosk_material_property(j, record, "path");
        struct kiosk_preparation_row *r = path ? kiosk_preparation_plan_find(p, path) : NULL;
        if (!r || !r->copied || r->index != index || !kiosk_material_equal(name, r->copy_name) ||
            memcmp(identity, r->copy_identity, sizeof(identity))) return -1;
        previous = index; first = 0;
    }
    return 0;
}

static inline int kiosk_preparation_initial(struct kiosk_preparation_plan *p, unsigned plan, unsigned ticket,
    int copy, struct kiosk_material_authority *a, struct kiosk_host_proof *host, void *crypto)
{
    struct kiosk_material_json *j = &p->json, *m = &a->material_json;
    uint64_t format; struct stat root;
    if (copy < 0 || kiosk_material_schema(j, plan, "format|material|backend|layout|sources|runtime|proofs|native", 8) ||
        kiosk_material_number(j, plan, "format", &format) || format != 1 ||
        !kiosk_material_equal(kiosk_material_property(j, plan, "backend"), a->backend) ||
        !kiosk_preparation_equal(j, kiosk_material_get(j, plan, "proofs"), m, kiosk_material_get(m, 1, "proofs"), 0) ||
        kiosk_preparation_layout(p, kiosk_material_get(j, plan, "layout"), 0, NULL) ||
        kiosk_material_schema(j, ticket, "format|name|root|parent|members", 5) ||
        kiosk_material_number(j, ticket, "format", &format) || format != 1 ||
        kiosk_preparation_array(j, kiosk_material_get(j, ticket, "root"), p->ticket_root, 2) ||
        kiosk_preparation_array(j, kiosk_material_get(j, ticket, "parent"), p->ticket_parent, 2)) return -1;
    p->ticket_name = kiosk_material_property(j, ticket, "name");
    if (!p->ticket_name || strlen(p->ticket_name) != 41 || strncmp(p->ticket_name, ".runtime-", 9)) return -1;
    for (unsigned i = 9; i < 41; i++) if (!strchr("0123456789abcdef", p->ticket_name[i])) return -1;
    if (fstat(copy, &root) || !S_ISDIR(root.st_mode) || root.st_uid != KIOSK_HOST_PROOF_OWNER ||
        root.st_gid != KIOSK_HOST_PROOF_GROUP || (root.st_mode & 07777) != 0700 ||
        (uint64_t)root.st_dev != p->ticket_root[0] || (uint64_t)root.st_ino != p->ticket_root[1]) return -1;
    int parent = openat(copy, "..", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    struct stat parent_info, named;
    int ok = parent >= 0 && !fstat(parent, &parent_info) &&
        (uint64_t)parent_info.st_dev == p->ticket_parent[0] && (uint64_t)parent_info.st_ino == p->ticket_parent[1] &&
        kiosk_host_trust(&parent_info) && !fstatat(parent, p->ticket_name, &named, AT_SYMLINK_NOFOLLOW) && kiosk_host_same(&root, &named);
    if (parent >= 0) close(parent);
    if (!ok) return -1;
    unsigned members = kiosk_material_get(j, ticket, "members"), runtime = kiosk_material_get(j, plan, "runtime"), native = kiosk_material_get(j, plan, "native");
    if (!members || j->nodes[members].type != '{' ||
        kiosk_material_schema(j, runtime, "format|backend|root|mount|manifest|manifest_identity|records|copies", 8) ||
        kiosk_material_schema(j, native, "records|copies", 2) ||
        !kiosk_preparation_equal(j, kiosk_material_get(j, native, "records"), m, kiosk_material_get(m, 1, "native"), 0)) return -1;
    unsigned runtime_records = kiosk_material_get(j, runtime, "records"), native_records = kiosk_material_get(j, native, "records");
    unsigned m_runtime = kiosk_material_get(m, 1, "runtime"), m_payload = kiosk_material_get(m, 1, "payload");
    uint64_t receipt_root[2], mount, expected_mount, parent_mount;
    const char *mount_text = kiosk_material_property(j, runtime, "mount");
    if (kiosk_material_number(j, runtime, "format", &format) || format != 1 ||
        !kiosk_material_equal(kiosk_material_property(j, runtime, "backend"), a->backend) ||
        kiosk_preparation_array(j, kiosk_material_get(j, runtime, "root"), receipt_root, 2) ||
        memcmp(receipt_root, p->ticket_root, sizeof(receipt_root)) || !mount_text ||
        kiosk_receipt_uint(mount_text, &expected_mount) || kiosk_preparation_mount(copy, &mount) || mount != expected_mount ||
        !runtime_records || j->nodes[runtime_records].type != '[' ||
        j->nodes[runtime_records].count != m->nodes[m_runtime].count + m->nodes[m_payload].count) return -1;
    parent = openat(copy, "..", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    ok = parent >= 0 && !kiosk_preparation_mount(parent, &parent_mount) && parent_mount == mount;
    if (parent >= 0) close(parent);
    if (!ok) return -1;
    if (!strcmp(a->backend, "selinux")) {
        char label[256];
        if (kiosk_host_label(copy, label) || strcmp(label, "system_u:object_r:onpc_kiosk_runtime_t:s0")) return -1;
    }
    const char *previous_record = "";
    for (unsigned n = j->nodes[runtime_records].child; n; n = j->nodes[n].next) {
        const char *path = kiosk_material_property(j, n, "path");
        if (!path || strcmp(previous_record, path) >= 0) return -1;
        previous_record = path;
        unsigned expected = kiosk_preparation_record_path(m, m_runtime, path, NULL);
        if (expected) {
            if (!kiosk_preparation_equal(j, n, m, expected, 0)) return -1;
        } else {
            expected = kiosk_preparation_record_path(m, m_payload, path, NULL);
            const struct kiosk_material_spec *s = kiosk_material_find(a, path);
            if (!expected || kiosk_preparation_payload_record(j, n, s, a->backend)) return -1;
        }
    }
    unsigned sources = kiosk_material_get(j, plan, "sources"), copies = 0;
    if (!sources || j->nodes[sources].type != '{' || j->nodes[sources].count != p->count) return -1;
    for (unsigned i = 0; i < p->count; i++) {
        struct kiosk_preparation_row *r = p->rows + i; unsigned n = kiosk_material_get(j, sources, r->path), required;
        r->spec = kiosk_material_find(a, r->path); r->required = r->spec != NULL;
        required = kiosk_material_get(j, n, "required");
        const char *class = kiosk_material_property(j, n, "source_class");
        if (!n || !class || !required || j->nodes[required].type != (r->required ? 't' : 'f') ||
            (!r->required && (!strcmp(r->kind, "tree") || !kiosk_preparation_ambient_path(a, r->path))) ||
            !kiosk_material_equal(kiosk_material_property(j, n, "kind"), r->kind) ||
            (!strcmp(r->kind, "link") && !kiosk_material_equal(kiosk_material_property(j, n, "link"), r->link)) ||
            kiosk_material_number(j, n, "source_index", &r->index) || r->index != r->slot) return -1;
        r->source_class = r->spec ? r->spec->source_class : !strcmp(r->kind, "tree") ? "skeleton" : "ambient";
        r->role = r->spec ? r->spec->role : !strcmp(r->kind, "tree") ? "skeleton" : "ambient";
        if (r->required && (strcmp(r->kind, r->spec->kind) || strcmp(r->link, r->spec->link ? r->spec->link : "-"))) return -1;
        int file_copy = r->spec && !strcmp(r->kind, "file") && strcmp(r->source_class, "vendor");
        int asserted = file_copy || !strcmp(r->kind, "file") || !strcmp(r->kind, "directory") || !strcmp(r->kind, "link");
        int source_path_field = asserted && (!file_copy || !strcmp(r->source_class, "native"));
        unsigned fields = 4 + (!strcmp(r->kind, "link")) + (asserted ? 2 + source_path_field : 0) + (file_copy ? 2 : 0) +
            (r->spec && !strcmp(r->kind, "file") ? 1 : 0);
        if (kiosk_material_schema(j, n, "kind|required|source_index|source_class|link|index|path|assertion|record|name|copy_identity", fields)) return -1;
        const char *expected_class = file_copy || (r->spec && !strcmp(r->source_class, "vendor")) ? r->source_class :
            !strcmp(r->kind, "link") && r->required ? "alias" :
            !strcmp(r->kind, "tree") ? "skeleton" : "ambient";
        if (strcmp(class, expected_class)) return -1;
        struct stat info;
        if (asserted) {
            if (kiosk_material_number(j, n, "index", &r->index) ||
                kiosk_preparation_array(j, kiosk_material_get(j, n, "assertion"), r->assertion, 8)) return -1;
            struct stat asserted_kind = {.st_mode = (mode_t)r->assertion[5]};
            if (!kiosk_preparation_kind(&asserted_kind, r->kind)) return -1;
            r->source_path = r->spec && !strcmp(r->kind, "file") ? r->spec->source : r->path;
            if ((!file_copy || !strcmp(r->source_class, "native")) &&
                !kiosk_material_equal(kiosk_material_property(j, n, "path"), r->source_path)) return -1;
            const struct kiosk_host_row *source = kiosk_material_host_row(host, r->source_path);
            if (r->required && (!source || !kiosk_preparation_same(&source->info, r->assertion))) return -1;
            if (r->required) {
                int fd = kiosk_preparation_open(host->roots.usr, r->source_path, 0, p->deadline);
                ok = fd >= 0 && !fstat(fd, &info) && kiosk_preparation_kind(&info, r->kind) &&
                    kiosk_preparation_same(&info, r->assertion) && kiosk_host_trust(&info);
                if (ok && !strcmp(r->kind, "link")) {
                    char text[PATH_MAX]; ssize_t length = readlinkat(fd, "", text, sizeof(text) - 1);
                    if (length <= 0) ok = 0;
                    else { text[length] = 0; ok = !strcmp(text, r->link); }
                }
                if (fd >= 0) close(fd);
                if (!ok) return -1;
            }
            /* Ambient initial assertions are frozen provenance only. Native
             * binding must observe the named object again; a changed/missing
             * source can only become an actual omission/mask in V. Never bind
             * a new inode or derive required authority from this assertion. */
            r->origin[0] = r->assertion[0]; r->origin[1] = r->assertion[1]; r->has_source = 1;
            memcpy(r->source_identity, r->origin, sizeof(r->origin));
        }
        if (r->spec && !strcmp(r->kind, "file")) {
            unsigned group = !strcmp(r->source_class, "native") ? native_records :
                !strcmp(r->source_class, "vendor") ? kiosk_material_get(m, 1, "preserved") : runtime_records;
            const struct kiosk_material_json *owner = !strcmp(r->source_class, "vendor") ? m : j;
            uint64_t expected_index;
            unsigned expected = kiosk_preparation_record_path(owner, group, r->path, &expected_index);
            if (!expected || r->index != expected_index ||
                !kiosk_preparation_equal(j, kiosk_material_get(j, n, "record"), owner, expected, 0)) return -1;
        }
        if (file_copy) {
            r->copied = 1; copies++;
            r->copy_name = kiosk_material_property(j, n, "name"); char expected[64];
            snprintf(expected, sizeof(expected), !strcmp(r->source_class, "native") ? "native-%llu" : "%llu", (unsigned long long)r->index);
            if (!r->copy_name || strcmp(r->copy_name, expected) ||
                kiosk_preparation_array(j, kiosk_material_get(j, n, "copy_identity"), r->copy_identity, 8) ||
                (r->copy_identity[0] == r->origin[0] && r->copy_identity[1] == r->origin[1])) return -1;
            uint64_t member[2];
            if (kiosk_preparation_array(j, kiosk_material_get(j, members, r->copy_name), member, 2) ||
                member[0] != r->copy_identity[0] || member[1] != r->copy_identity[1]) return -1;
            int fd = openat(copy, r->copy_name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
            ok = fd >= 0 && !kiosk_preparation_file(fd, r->spec, a->backend, crypto, p->deadline, 1, r->copy_identity) &&
                !fstat(fd, &named) && named.st_dev == root.st_dev && !kiosk_preparation_mount(fd, &parent_mount) && parent_mount == mount &&
                !fstatat(copy, r->copy_name, &info, AT_SYMLINK_NOFOLLOW) && kiosk_preparation_same(&info, r->copy_identity);
            if (fd >= 0) close(fd);
            if (!ok) return -1;
        }
    }
    /* No material requirement may disappear, and unknown scratch members never
     * become cleanup or copy authority. runtime.json is separately checked. */
    for (unsigned i = 0; i < a->count; i++) if (!kiosk_preparation_plan_find(p, a->specs[i].path)) return -1;
    if (kiosk_preparation_copy_rows(p, kiosk_material_get(j, runtime, "copies"), runtime_records, 0) ||
        kiosk_preparation_copy_rows(p, kiosk_material_get(j, native, "copies"), native_records, 1)) return -1;
    if (j->nodes[members].count != copies + 1) return -1;
    uint64_t manifest[8], ticket_manifest[2];
    if (kiosk_preparation_array(j, kiosk_material_get(j, runtime, "manifest_identity"), manifest, 8) ||
        kiosk_preparation_array(j, kiosk_material_get(j, members, "runtime.json"), ticket_manifest, 2) ||
        manifest[0] != ticket_manifest[0] || manifest[1] != ticket_manifest[1]) return -1;
    int manifest_fd = openat(copy, "runtime.json", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    struct kiosk_material_json disk = {0}; char digest[65], manifest_label[256];
    ok = manifest_fd >= 0 && !fstat(manifest_fd, &named) && kiosk_preparation_same(&named, manifest) &&
        S_ISREG(named.st_mode) && named.st_uid == KIOSK_HOST_PROOF_OWNER && named.st_gid == KIOSK_HOST_PROOF_GROUP &&
        (named.st_mode & 07777) == 0600 && named.st_nlink == 1 && named.st_dev == root.st_dev &&
        !kiosk_preparation_mount(manifest_fd, &parent_mount) && parent_mount == mount &&
        (strcmp(a->backend, "selinux") || (!kiosk_host_label(manifest_fd, manifest_label) &&
            !strcmp(manifest_label, "system_u:object_r:onpc_kiosk_runtime_t:s0"))) &&
        !kiosk_host_sha256_library_until(manifest_fd, named.st_size, digest, crypto, p->deadline) &&
        kiosk_material_equal(digest, kiosk_material_property(j, runtime, "manifest")) &&
        !kiosk_preparation_json_fd(&disk, manifest_fd, p->deadline) &&
        !kiosk_material_schema(&disk, 1, "format|backend|records|copies", 4);
    const char *keys[] = {"format", "backend", "records", "copies"};
    for (unsigned i = 0; ok && i < 4; i++) ok = kiosk_preparation_equal(&disk, kiosk_material_get(&disk, 1, keys[i]), j, kiosk_material_get(j, runtime, keys[i]), 0);
    free(disk.storage); free(disk.nodes);
    if (manifest_fd >= 0) close(manifest_fd);
    if (!ok) return -1;
    int directory_fd = openat(copy, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    DIR *directory = directory_fd < 0 ? NULL : fdopendir(directory_fd);
    if (!directory) { if (directory_fd >= 0) close(directory_fd); return -1; }
    unsigned seen = 0; ok = 1;
    for (;;) {
        errno = 0; struct dirent *entry = readdir(directory);
        if (!entry) { if (errno) ok = 0; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        if (++seen > copies + 1 || kiosk_receipt_before(p->deadline) || !kiosk_material_get(j, members, entry->d_name)) { ok = 0; break; }
    }
    closedir(directory); p->ticket_members = copies + 1;
    return ok && seen == copies + 1 ? 0 : -1;
}

/* Exact verified flat scratch ticket, for an independently owning publisher.
 * This accessor reobserves the named inode; no descriptor ownership transfers. */
static inline int kiosk_preparation_member_at_until(const struct kiosk_preparation_plan *p,
    int copy_fd, unsigned index, const char **name, struct stat *info)
{
    if (!p || !p->verified || !p->ticket_name || index >= p->ticket_members || kiosk_receipt_before(p->deadline)) return -1;
    unsigned ticket = kiosk_material_get(&p->json, 1, "ticket");
    unsigned members = kiosk_material_get(&p->json, ticket, "members");
    unsigned member = p->json.nodes[members].child;
    for (unsigned i = 0; i < index && member; i++) member = p->json.nodes[member].next;
    uint64_t identity[2];
    if (!member || kiosk_preparation_array(&p->json, member, identity, 2) ||
        fstatat(copy_fd, p->json.nodes[member].key, info, AT_SYMLINK_NOFOLLOW) ||
        !S_ISREG(info->st_mode) || info->st_uid != KIOSK_HOST_PROOF_OWNER || info->st_gid != KIOSK_HOST_PROOF_GROUP ||
        info->st_nlink != 1 || (info->st_mode & 07022) || (uint64_t)info->st_dev != identity[0] ||
        (uint64_t)info->st_ino != identity[1]) return -1;
    const uint64_t *expected = NULL; uint64_t manifest[8];
    if (!strcmp(p->json.nodes[member].key, "runtime.json")) {
        unsigned plan = kiosk_material_get(&p->json, 1, "plan"), runtime = kiosk_material_get(&p->json, plan, "runtime");
        if (kiosk_preparation_array(&p->json, kiosk_material_get(&p->json, runtime, "manifest_identity"), manifest, 8)) return -1;
        expected = manifest;
    } else for (unsigned i = 0; i < p->count; i++) {
        if (kiosk_receipt_before(p->deadline)) return -1;
        if (p->rows[i].copy_name && !strcmp(p->rows[i].copy_name, p->json.nodes[member].key)) {
            expected = p->rows[i].copy_identity; break;
        }
    }
    if (!expected || !kiosk_preparation_same(info, expected)) return -1;
    *name = p->json.nodes[member].key; return 0;
}

static inline int kiosk_preparation_plan_verify_until(struct kiosk_preparation_plan *p, int result_fd,
    int copy_fd, struct kiosk_material_authority *a, struct kiosk_host_proof *host,
    const struct kiosk_receipt *source_v, int clone_usr_fd, void *crypto, uint64_t deadline)
{
    uint64_t format; int gate = source_v != NULL;
    if (!p || !a || !host || !crypto || deadline != a->deadline || deadline != host->deadline ||
        kiosk_receipt_before(deadline)) return -1;
    memset(p, 0, sizeof(*p)); p->deadline = deadline;
    if (kiosk_preparation_json_fd(&p->json, result_fd, deadline)) goto failed;
    struct kiosk_material_json *j = &p->json;
    if (kiosk_material_schema(j, 1, "format|role|backend|material|source|plan|ticket", 7) ||
        kiosk_material_number(j, 1, "format", &format) || format != 1 ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "role"), gate ? "gate" : "manager") ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "backend"), a->backend) ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "material"), a->digest) ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "source"), gate ? source_v->digest : "-")) goto failed;
    unsigned plan = kiosk_material_get(j, 1, "plan"), ticket = kiosk_material_get(j, 1, "ticket");
    if (!kiosk_material_equal(kiosk_material_property(j, plan, "material"), a->digest) ||
        kiosk_material_verify_host_until(a, host) || kiosk_material_verify_routes_until(a, host)) goto failed;
    if (gate) {
        if (copy_fd >= 0 || !ticket || j->nodes[ticket].type != 'n' ||
            kiosk_preparation_gate(p, plan, a, source_v, clone_usr_fd, crypto)) goto failed;
    } else if (kiosk_preparation_initial(p, plan, ticket, copy_fd, a, host, crypto)) goto failed;
    if (kiosk_material_verify_host_until(a, host) || kiosk_material_verify_routes_until(a, host) ||
        kiosk_receipt_before(deadline)) goto failed;
    p->verified = 1; return 0;
failed:
    kiosk_preparation_plan_free(p); return -1;
}
#endif
