/* Read-only completed-generation selection. The caller supplies an actually
 * acquired manager's /usr and marker, independently attested M and boot. This
 * owner never acquires a manager, clones a tree, writes a record or repairs it.
 * Live identity and actual recursive source verification remain coordinator
 * obligations, before and after clone acquisition and at the final decision. */
#ifndef ONPC_KIOSK_RETAINED_RECORD_H
#define ONPC_KIOSK_RETAINED_RECORD_H
#include "kiosk_preparation_plan.h"
#include "kiosk_view_publication.h"
#include <sys/mman.h>

#define KIOSK_RETAINED_MARKER "/usr/share/oh-no-parent-control/confinement/retained-view"

struct kiosk_retained_record {
    struct kiosk_receipt receipt;
    struct kiosk_publication_inventory inventory;
    struct kiosk_publication publication;
    unsigned char *ambient;
    char (*hashes)[65];
    int view_fd, slots_fd, manager_executable, marker;
    struct stat marker_info, source_info;
    char material[65], view[65], boot[37], marker_bytes[256];
    size_t marker_size;
    uint64_t deadline;
    int verified;
};

static inline void kiosk_retained_record_init(struct kiosk_retained_record *r)
{
    memset(r, 0, sizeof(*r));
    r->view_fd = r->slots_fd = r->manager_executable = r->marker = -1;
    r->publication.parent = r->publication.root = -1;
}

static inline void kiosk_retained_record_close(struct kiosk_retained_record *r)
{
    if (r->view_fd >= 0) close(r->view_fd);
    if (r->slots_fd >= 0) close(r->slots_fd);
    if (r->manager_executable >= 0) close(r->manager_executable);
    if (r->marker >= 0) close(r->marker);
    kiosk_receipt_free(&r->receipt);
    kiosk_publication_inventory_close(&r->inventory);
    kiosk_publication_close(&r->publication);
    free(r->ambient); free(r->hashes);
    kiosk_retained_record_init(r);
}

/* Metadata for masks is not encoded in V. Its root-only pins record is bound
 * by ready, and still has to match the actual selected manager tree. */
static inline int kiosk_retained_inventory_until(struct kiosk_retained_record *r,
    struct kiosk_material_authority *a)
{
    const struct kiosk_receipt *v = &r->receipt;
    if (kiosk_preparation_view_authority_until(v, a, r->deadline) ||
        !r->inventory.count || r->inventory.entries[0].device != r->source_info.st_dev ||
        r->inventory.entries[0].inode != r->source_info.st_ino ||
        !(r->ambient = calloc(r->inventory.count, 1))) return -1;
    unsigned concrete = 1; /* private marker */
    for (unsigned i = 0; i < v->nn; i++)
        concrete += strcmp(v->nodes[i].v[KR_KIND], "absent") && strcmp(v->nodes[i].v[KR_KIND], "link");
    unsigned found_nodes = 0, found_marker = 0, found_coverage = 0;
    for (unsigned i = 0; i < r->inventory.count; i++) {
        const struct kiosk_pin_entry *e = r->inventory.entries + i;
        char path[PATH_MAX];
        int n = snprintf(path, sizeof(path), "/usr%s%s", *e->relative ? "/" : "", e->relative);
        if (n < 0 || n >= PATH_MAX || kiosk_pin_before(r->deadline)) return -1;
        const struct kiosk_receipt_row *node = kiosk_receipt_find(v, path);
        if (node) {
            const char *kind = node->v[KR_KIND];
            if (!strcmp(kind, "absent") || !strcmp(kind, "link")) return -1;
            found_nodes++;
            if (!strcmp(kind, "empty-directory")) {
                if (!S_ISDIR(e->mode) || (e->mode & 07777) != 0755 || e->mountpoint) return -1;
            } else if ((uint64_t)e->device != node->number[KR_DEV] || (uint64_t)e->inode != node->number[KR_INO] ||
                (uint64_t)e->mode != node->number[KR_MODE] || e->uid != node->number[KR_UID] ||
                e->gid != node->number[KR_GID] || e->mountpoint != node->number[KR_MOUNT]) return -1;
            r->ambient[i] = kiosk_material_find(a, path) == NULL;
        } else if (!strcmp(path, KIOSK_RETAINED_MARKER)) {
            if (++found_marker != 1 || e->device != r->marker_info.st_dev || e->inode != r->marker_info.st_ino ||
                e->mode != r->marker_info.st_mode || e->uid != r->marker_info.st_uid ||
                e->gid != r->marker_info.st_gid || e->mountpoint) return -1;
        } else {
            /* Only C witnesses and their necessary parents can extend the
             * inventory beyond the concrete N domain and private marker. */
            int allowed = 0, owner = -1;
            for (unsigned j = 0; j < v->nc; j++) {
                const struct kiosk_receipt_row *c = v->coverage + j;
                if (!strcmp(path, c->v[KC_PATH])) {
                    if (allowed == 2 || (uint64_t)e->device != c->number[KC_DEV] || (uint64_t)e->inode != c->number[KC_INO] ||
                        (uint64_t)e->mode != c->number[KC_MODE] || e->uid != c->number[KC_UID] || e->gid != c->number[KC_GID] ||
                        !e->mountpoint) return -1;
                    allowed = 2; owner = (int)c->number[KC_OWNER]; found_coverage++;
                } else if (!allowed && kiosk_below(c->v[KC_PATH], path)) {
                    allowed = 1; owner = (int)c->number[KC_OWNER];
                }
            }
            if (!allowed || owner < 0 || (unsigned)owner >= v->nn ||
                !kiosk_below(path, v->nodes[owner].v[KR_PATH]) ||
                (allowed == 1 && (!S_ISDIR(e->mode) || e->mountpoint))) return -1;
            r->ambient[i] = kiosk_material_find(a, v->nodes[owner].v[KR_PATH]) == NULL;
        }
        /* Never relax a required path or any of its ancestors, even if an
         * otherwise syntactically valid record calls that branch ambient. */
        for (unsigned j = 0; j < a->count; j++) {
            if (kiosk_pin_before(r->deadline)) return -1;
            if ((!strcmp(path, a->specs[j].path) || kiosk_below(a->specs[j].path, path)) && r->ambient[i]) return -1;
        }
        if (i && r->ambient[e->parent] && !r->ambient[i]) return -1;
    }
    return found_nodes + found_marker == concrete && found_marker == 1 && found_coverage == v->nc ? 0 : -1;
}

static inline int kiosk_retained_marker_until(struct kiosk_retained_record *r, int usr, int marker,
    struct kiosk_material_authority *a, int initial)
{
    struct stat opened, named, after; char bytes[256];
    int fd = kiosk_preparation_open(usr, KIOSK_RETAINED_MARKER, 1, r->deadline);
    int valid = fd >= 0 && !fstat(marker, &opened) && !fstat(fd, &named) &&
        kiosk_host_same(&opened, &named) && S_ISREG(named.st_mode) && named.st_uid == 0 && named.st_gid == 0 &&
        (named.st_mode & 07777) == 0444 && named.st_nlink == 1 && named.st_size > 0 && named.st_size < 256 &&
        pread(fd, bytes, (size_t)named.st_size, 0) == named.st_size &&
        !fstat(fd, &after) && kiosk_host_same(&named, &after) &&
        !kiosk_label(fd, NULL, 0, !strcmp(a->backend, "selinux"));
    if (valid && initial) {
        char text[256], *fields[5]; memcpy(text, bytes, (size_t)named.st_size); text[named.st_size - 1] = 0;
        valid = bytes[named.st_size - 1] == '\n' && !memchr(bytes, 0, (size_t)named.st_size) &&
            !strchr(text, '\n') && !kiosk_receipt_fields(text, fields, 5) &&
            !strcmp(fields[0], "ONPC-KIOSK-VIEW") && !strcmp(fields[1], "1") &&
            !strcmp(fields[2], a->backend) && kiosk_receipt_hex(fields[3]) &&
            (initial == 2 || !strcmp(fields[3], a->digest)) && kiosk_receipt_hex(fields[4]);
        if (valid) {
            strcpy(r->material, fields[3]); strcpy(r->view, fields[4]);
            r->marker_info = named; r->marker_size = (size_t)named.st_size;
            memcpy(r->marker_bytes, bytes, r->marker_size);
            r->marker = fcntl(marker, F_DUPFD_CLOEXEC, 3); valid = r->marker >= 0;
        }
    } else if (valid) valid = kiosk_host_same(&r->marker_info, &named) &&
        (size_t)named.st_size == r->marker_size && !memcmp(bytes, r->marker_bytes, r->marker_size);
    if (fd >= 0) close(fd);
    return valid && !kiosk_pin_before(r->deadline) ? 0 : -1;
}

static inline int kiosk_retained_member_add(struct kiosk_publication_member *members, unsigned *count,
    int root, const char *name, uint64_t deadline)
{
    if (*count >= KIOSK_VIEW_ROWS || !kiosk_publication_name(name) || kiosk_pin_before(deadline)) return -1;
    for (unsigned i = 0; i < *count; i++) if (!strcmp(members[i].name, name)) return -1;
    struct kiosk_publication_member *m = members + *count;
    if (fstatat(root, name, &m->info, AT_SYMLINK_NOFOLLOW) || !kiosk_trusted_stat(&m->info, S_IFREG) ||
        m->info.st_gid || m->info.st_nlink != 1 || !(m->name = strdup(name))) return -1;
    (*count)++; return 0;
}

static inline int kiosk_retained_copy_until(struct kiosk_retained_record *r, int root,
    struct kiosk_material_authority *a, const char *path, const char *name,
    const uint64_t *manifest_identity, void *crypto)
{
    const struct kiosk_material_spec *spec = kiosk_material_find(a, path);
    const struct kiosk_receipt_row *node = kiosk_receipt_find(&r->receipt, path);
    struct stat info, named; uint64_t identity[8];
    int fd = openat(root, name, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
    int ok = fd >= 0 && spec && node && !strcmp(spec->kind, "file") && !fstat(fd, &info);
    if (ok) {
        kiosk_preparation_assertion(&info, identity);
        ok = (!manifest_identity || !memcmp(identity, manifest_identity, sizeof(identity))) &&
            identity[0] == node->number[KR_DEV] && identity[1] == node->number[KR_INO] &&
            (identity[0] != node->number[KR_ORIGIN_DEV] || identity[1] != node->number[KR_ORIGIN_INO]) &&
            !kiosk_preparation_file(fd, spec, a->backend, crypto, r->deadline, 1, identity) &&
            !fstatat(root, name, &named, AT_SYMLINK_NOFOLLOW) && kiosk_host_same(&info, &named);
        if (ok && !strcmp(spec->source_class, "native") && !strcmp(spec->role, "manager")) {
            if (r->manager_executable >= 0) ok = 0;
            else { r->manager_executable = fcntl(fd, F_DUPFD_CLOEXEC, 3); ok = r->manager_executable >= 0; }
        }
    }
    if (fd >= 0) close(fd);
    return ok ? 0 : -1;
}

/* Supporting manifest records are independently compared to current M. The
 * native copy list is derived directly from M, never a producer's list. */
static inline int kiosk_retained_copies_until(struct kiosk_retained_record *r, int root,
    struct kiosk_material_authority *a, struct kiosk_publication_member *members, unsigned *count, void *crypto)
{
    struct kiosk_material_json disk = {0}, *m = &a->material_json;
    int fd = openat(root, "runtime.json", O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC), result = -1;
    uint64_t format;
    if (fd < 0 || kiosk_preparation_runtime_fd(&disk, fd, r->deadline) ||
        kiosk_material_schema(&disk, 1, "format|backend|records|copies", 4) ||
        kiosk_material_number(&disk, 1, "format", &format) || format != 1 ||
        !kiosk_material_equal(kiosk_material_property(&disk, 1, "backend"), a->backend)) goto done;
    unsigned records = kiosk_material_get(&disk, 1, "records"), copies = kiosk_material_get(&disk, 1, "copies");
    unsigned runtime = kiosk_material_get(m, 1, "runtime"), payload = kiosk_material_get(m, 1, "payload");
    if (!records || disk.nodes[records].type != '[' || !copies || disk.nodes[copies].type != '[' ||
        disk.nodes[records].count != m->nodes[runtime].count + m->nodes[payload].count) goto done;
    const char *previous = ""; unsigned index = 0, copy = disk.nodes[copies].child;
    for (unsigned n = disk.nodes[records].child; n; n = disk.nodes[n].next, index++) {
        const char *path = kiosk_material_property(&disk, n, "path"), *kind = kiosk_material_property(&disk, n, "kind");
        if (!path || !kind || strcmp(previous, path) >= 0 || kiosk_pin_before(r->deadline)) goto done;
        previous = path;
        unsigned expected = kiosk_preparation_record_path(m, runtime, path, NULL);
        if (expected) { if (!kiosk_preparation_equal(&disk, n, m, expected, 0)) goto done; }
        else if (!kiosk_preparation_record_path(m, payload, path, NULL) ||
            kiosk_preparation_payload_record(&disk, n, kiosk_material_find(a, path), a->backend)) goto done;
        if (strcmp(kind, "file")) continue;
        uint64_t given, identity[8]; char name[64];
        snprintf(name, sizeof(name), "%u", index);
        if (!copy || kiosk_material_schema(&disk, copy, "index|name|identity", 3) ||
            kiosk_material_number(&disk, copy, "index", &given) || given != index ||
            !kiosk_material_equal(kiosk_material_property(&disk, copy, "name"), name) ||
            kiosk_preparation_array(&disk, kiosk_material_get(&disk, copy, "identity"), identity, 8) ||
            kiosk_retained_copy_until(r, root, a, path, name, identity, crypto) ||
            kiosk_retained_member_add(members, count, root, name, r->deadline)) goto done;
        copy = disk.nodes[copy].next;
    }
    if (copy) goto done;
    index = 0;
    unsigned native = kiosk_material_get(m, 1, "native");
    for (unsigned n = m->nodes[native].child; n; n = m->nodes[n].next, index++) {
        char name[64]; snprintf(name, sizeof(name), "native-%u", index);
        if (kiosk_retained_copy_until(r, root, a, kiosk_material_property(m, n, "path"), name, NULL, crypto) ||
            kiosk_retained_member_add(members, count, root, name, r->deadline)) goto done;
    }
    if (r->manager_executable >= 0) result = 0;
done:
    if (fd >= 0) close(fd);
    free(disk.storage); free(disk.nodes); return result;
}

/* Bound every write before growing the memory stream, including UTF-8's ASCII
 * escape expansion. All chunks belong to the original transaction deadline. */
static inline int kiosk_retained_slots_write(FILE *stream, const char *bytes, size_t count,
    size_t *used, uint64_t deadline)
{
    if (kiosk_pin_before(deadline) || *used > KIOSK_RECEIPT_BYTES ||
        count > KIOSK_RECEIPT_BYTES - *used || fwrite(bytes, 1, count, stream) != count) return -1;
    *used += count; return 0;
}

/* V already admits canonical UTF-8 names. Match Python's ensure_ascii JSON
 * encoding without a locale: quote/backslash escapes, lowercase \u escapes,
 * and UTF-16 surrogate pairs for supplementary Unicode code points. Key order
 * remains V's original UTF-8 order, which matches Unicode scalar ordering. */
static inline int kiosk_retained_slots_key(FILE *stream, const char *path,
    size_t *used, uint64_t deadline)
{
    if (!kiosk_receipt_text(path) || kiosk_retained_slots_write(stream, "\"", 1, used, deadline)) return -1;
    const unsigned char *p = (const unsigned char *)path;
    while (*p) {
        if (kiosk_pin_before(deadline)) return -1;
        uint32_t point = *p++; unsigned continuation = 0;
        if (point >= 0xf0) { point &= 7; continuation = 3; }
        else if (point >= 0xe0) { point &= 15; continuation = 2; }
        else if (point >= 0xc0) { point &= 31; continuation = 1; }
        for (unsigned i = 0; i < continuation; i++) {
            if (kiosk_pin_before(deadline)) return -1;
            point = (point << 6) | (*p++ & 63);
        }
        char escaped[13]; size_t count;
        if (point == '"' || point == '\\') {
            escaped[0] = '\\'; escaped[1] = (char)point; count = 2;
        } else if (point < 127) { escaped[0] = (char)point; count = 1; }
        else if (point <= 0xffff) {
            int n = snprintf(escaped, sizeof(escaped), "\\u%04x", (unsigned)point);
            if (n != 6) return -1;
            count = 6;
        } else {
            point -= 0x10000;
            int n = snprintf(escaped, sizeof(escaped), "\\u%04x\\u%04x",
                (unsigned)(0xd800 + (point >> 10)), (unsigned)(0xdc00 + (point & 1023)));
            if (n != 12) return -1;
            count = 12;
        }
        if (kiosk_retained_slots_write(stream, escaped, count, used, deadline)) return -1;
    }
    return kiosk_retained_slots_write(stream, "\"", 1, used, deadline);
}

/* Canonical JSON source slots are native-derived and immutable in transit. */
static inline int kiosk_retained_slots_until(struct kiosk_retained_record *r)
{
    char *bytes = NULL; size_t size = 0, used = 0;
    FILE *stream = open_memstream(&bytes, &size);
    if (!stream) return -1;
    int result = -1, writable = -1;
    char fixed[256];
    int count = snprintf(fixed, sizeof(fixed), "{\"format\":1,\"material\":\"%s\",\"slots\":{", r->material);
    if (count < 0 || (size_t)count >= sizeof(fixed) ||
        kiosk_retained_slots_write(stream, fixed, (size_t)count, &used, r->deadline)) goto done;
    for (unsigned i = 0; i < r->receipt.nn; i++) {
        const struct kiosk_receipt_row *n = r->receipt.nodes + i;
        if ((i && kiosk_retained_slots_write(stream, ",", 1, &used, r->deadline)) ||
            kiosk_retained_slots_key(stream, n->v[KR_PATH], &used, r->deadline)) goto done;
        count = snprintf(fixed, sizeof(fixed), ":%llu", (unsigned long long)n->number[KR_INDEX]);
        if (count < 0 || (size_t)count >= sizeof(fixed) ||
            kiosk_retained_slots_write(stream, fixed, (size_t)count, &used, r->deadline)) goto done;
    }
    count = snprintf(fixed, sizeof(fixed), "},\"source\":\"%s\"}", r->view);
    if (count < 0 || (size_t)count >= sizeof(fixed) ||
        kiosk_retained_slots_write(stream, fixed, (size_t)count, &used, r->deadline) ||
        fflush(stream) || size != used) goto done;
    writable = memfd_create("onpc-kiosk-source-slots", MFD_CLOEXEC | MFD_ALLOW_SEALING);
    if (writable < 0) goto done;
    for (size_t offset = 0; offset < size;) {
        if (kiosk_pin_before(r->deadline)) goto done;
        ssize_t n = write(writable, bytes + offset, size - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) goto done;
        offset += (size_t)n;
    }
    if (fcntl(writable, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)) goto done;
    char path[64]; snprintf(path, sizeof(path), "/proc/self/fd/%d", writable);
    r->slots_fd = open(path, O_RDONLY | O_CLOEXEC);
    if (r->slots_fd >= 0 && !kiosk_pin_before(r->deadline)) result = 0;
done:
    if (writable >= 0) close(writable);
    if (fclose(stream)) result = -1;
    free(bytes); return result;
}

static inline int kiosk_retained_hashes_until(struct kiosk_retained_record *r, void *crypto, int initial)
{
    int selinux = !strcmp(r->receipt.backend, "selinux");
    if (kiosk_publication_members(&r->publication) ||
        kiosk_label(r->publication.parent, NULL, 0, selinux) ||
        kiosk_label(r->publication.root, NULL, 0, selinux)) return -1;
    uint64_t measured = 0;
    for (unsigned i = 0; i < r->publication.count; i++) {
        struct kiosk_publication_member *m = r->publication.members + i;
        struct stat before, after; char hash[65]; unsigned long long mount;
        int fd = openat(r->publication.root, m->name, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
        int control = !strcmp(m->name, "material.json") || !strcmp(m->name, "view") ||
            !strcmp(m->name, "pins") || !strcmp(m->name, "ready") || !strcmp(m->name, "runtime.json");
        int valid = fd >= 0 && !fstat(fd, &before) && kiosk_host_same(&before, &m->info) &&
            before.st_nlink == 1 && before.st_size >= 0 && (uint64_t)before.st_size <= KIOSK_HOST_FILE_BYTES - measured &&
            !kiosk_pin_fd_mount(fd, &mount) && mount == r->publication.mount &&
            (!control || (kiosk_publication_private(&before, 0) && !kiosk_label(fd, NULL, 0, selinux))) &&
            !kiosk_host_sha256_library_until(fd, before.st_size, hash, crypto, r->deadline) &&
            !fstat(fd, &after) && kiosk_host_same(&before, &after);
        if (fd >= 0) close(fd);
        if (!valid) return -1;
        measured += (uint64_t)before.st_size;
        if (initial) strcpy(r->hashes[i], hash); else if (strcmp(r->hashes[i], hash)) return -1;
    }
    return kiosk_publication_members(&r->publication);
}

static inline int kiosk_retained_record_recheck_until(struct kiosk_retained_record *r, int manager_usr,
    int manager_marker, struct kiosk_material_authority *a, void *crypto, uint64_t deadline)
{
    struct stat source;
    return r && r->verified && deadline == r->deadline && deadline == a->deadline &&
        !strcmp(r->material, a->digest) && !strcmp(r->receipt.backend, a->backend) &&
        !fstat(manager_usr, &source) && kiosk_host_same(&source, &r->source_info) &&
        !kiosk_retained_marker_until(r, manager_usr, manager_marker, a, 0) &&
        !kiosk_retained_hashes_until(r, crypto, 0) && !kiosk_pin_before(deadline) ? 0 : -1;
}

static inline int kiosk_retained_record_open_until(struct kiosk_retained_record *r, int runtime,
    int manager_usr, int manager_marker, struct kiosk_material_authority *a, const char *boot,
    void *crypto, uint64_t deadline)
{
    kiosk_retained_record_init(r); r->deadline = deadline;
    int root = -1, fd = -1, result = -1;
    struct kiosk_publication_member *members = NULL; unsigned count = 0;
    char *material = NULL, *view = NULL, *pins = NULL, *ready = NULL;
    size_t material_size = 0, view_size = 0, pins_size = 0, ready_size = 0;
    char digest[65]; struct kiosk_publication_ready_record completion;
    unsigned long long source_mount;
    if (!a || !crypto || !boot || strlen(boot) != 36 || deadline != a->deadline || kiosk_pin_before(deadline) ||
        fstat(manager_usr, &r->source_info) || !S_ISDIR(r->source_info.st_mode) ||
        kiosk_retained_marker_until(r, manager_usr, manager_marker, a, 1) ||
        (root = openat(runtime, r->view, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
        !(members = calloc(KIOSK_VIEW_ROWS, sizeof(*members)))) goto done;
    strcpy(r->boot, boot);
    const char *names[] = {"material.json", "view", "pins", "ready", "runtime.json"};
    char **data[] = {&material, &view, &pins, &ready};
    size_t *sizes[] = {&material_size, &view_size, &pins_size, &ready_size};
    for (unsigned i = 0; i < 5; i++) {
        if (kiosk_retained_member_add(members, &count, root, names[i], deadline) ||
            !kiosk_publication_private(&members[count - 1].info, 0)) goto done;
        if (i == 4) continue;
        fd = openat(root, names[i], O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0 || kiosk_publication_read(fd, data[i], sizes[i], deadline)) goto done;
        if (i == 1) { r->view_fd = fd; fd = -1; } else { close(fd); fd = -1; }
    }
    if (kiosk_receipt_material_hash(material, material_size, crypto, deadline, digest) || strcmp(digest, a->digest) ||
        kiosk_receipt_parse(&r->receipt, view, view_size, crypto, deadline) || strcmp(r->receipt.digest, r->view) ||
        kiosk_preparation_view_authority_until(&r->receipt, a, deadline) ||
        kiosk_publication_inventory_parse(&r->inventory, pins, pins_size, deadline) ||
        kiosk_material_sha256(pins, pins_size, crypto, deadline, digest) ||
        kiosk_publication_ready_parse(&completion, ready, ready_size, deadline) ||
        strcmp(completion.material, a->digest) || strcmp(completion.view, r->view) || strcmp(completion.inventory, digest) ||
        strcmp(completion.boot, boot) || completion.marker_device != (uint64_t)r->marker_info.st_dev ||
        completion.marker_inode != (uint64_t)r->marker_info.st_ino ||
        completion.source_device != (uint64_t)r->source_info.st_dev || completion.source_inode != (uint64_t)r->source_info.st_ino ||
        /* This descriptor belongs to the original manager attachment, before
         * recursive cloning creates new mount IDs in the caller's namespace. */
        kiosk_pin_fd_mount(manager_usr, &source_mount) || completion.attachment != source_mount ||
        kiosk_retained_inventory_until(r, a) || kiosk_retained_copies_until(r, root, a, members, &count, crypto) ||
        kiosk_publication_open_until(&r->publication, runtime, root, r->view, members, count, deadline) ||
        completion.root_device != (uint64_t)r->publication.root_info.st_dev ||
        completion.root_inode != (uint64_t)r->publication.root_info.st_ino ||
        !(r->hashes = calloc(count, sizeof(*r->hashes))) ||
        kiosk_retained_hashes_until(r, crypto, 1) || kiosk_retained_slots_until(r)) goto done;
    r->verified = 1;
    if (kiosk_retained_record_recheck_until(r, manager_usr, manager_marker, a, crypto, deadline)) goto done;
    result = 0;
done:
    if (fd >= 0) close(fd);
    if (root >= 0) close(root);
    for (unsigned i = 0; i < count; i++) free(members[i].name);
    free(members); free(material); free(view); free(pins); free(ready);
    if (result) kiosk_retained_record_close(r);
    return result;
}

/* Diagnostic-only old-M proof. Mode 2 reads a trusted marker's digest without
 * treating it as current material. Decode that old M against the independently
 * attested current config/policy, then reuse the complete strict record/copy
 * verifier. Success grants no admission: the coordinator must still prove the
 * original manager and its actual source tree before reporting a mismatch. */
static inline int kiosk_retained_record_previous_until(struct kiosk_retained_record *r,
    struct kiosk_material_authority *previous, int runtime, int manager_usr, int manager_marker,
    struct kiosk_material_authority *current, const void *config, size_t config_size,
    const void *policy, size_t policy_size, const char *boot, void *crypto, uint64_t deadline)
{
    int root = -1, fd = -1, result = -1;
    char *material = NULL; size_t size = 0;
    struct stat marker;
    char digest[65], view[65];
    kiosk_retained_record_init(r); r->deadline = deadline;
    if (!current || deadline != current->deadline || kiosk_pin_before(deadline) ||
        kiosk_retained_marker_until(r, manager_usr, manager_marker, current, 2) ||
        !strcmp(r->material, current->digest)) goto done;
    marker = r->marker_info; strcpy(digest, r->material); strcpy(view, r->view);
    root = openat(runtime, view, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (root < 0 || (fd = openat(root, "material.json", O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC)) < 0 ||
        kiosk_publication_read(fd, &material, &size, deadline) ||
        kiosk_material_decode_until(previous, material, size, config, config_size, policy, policy_size, crypto, deadline) ||
        strcmp(previous->digest, digest) || strcmp(previous->backend, current->backend)) goto done;
    kiosk_retained_record_close(r);
    if (kiosk_retained_record_open_until(r, runtime, manager_usr, manager_marker, previous, boot, crypto, deadline) ||
        !kiosk_host_same(&marker, &r->marker_info) || strcmp(view, r->view)) goto done;
    result = 0;
done:
    if (fd >= 0) close(fd);
    if (root >= 0) close(root);
    free(material);
    if (result) kiosk_retained_record_close(r);
    return result;
}
#endif
