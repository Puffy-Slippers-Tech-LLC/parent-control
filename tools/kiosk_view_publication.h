/* Native completion records. Supporting copies and mutually matching helper
 * records are never ready authority. The coordinator calls this owner only
 * after independently verifying copies, actual receipt and completed mounts.
 * Include after the confinement, material and receipt owners. */
#ifndef ONPC_KIOSK_VIEW_PUBLICATION_H
#define ONPC_KIOSK_VIEW_PUBLICATION_H

struct kiosk_publication_inventory {
    char *storage;
    struct kiosk_pin_entry *entries;
    unsigned count;
};

static inline void kiosk_publication_inventory_close(struct kiosk_publication_inventory *inventory)
{
    free(inventory->storage); free(inventory->entries);
    memset(inventory, 0, sizeof(*inventory));
}

static inline int kiosk_publication_inventory_parse(struct kiosk_publication_inventory *out,
    const char *bytes, size_t size, uint64_t deadline)
{
    memset(out, 0, sizeof(*out));
    const char header[] = "ONPC-KIOSK-PINS\t1\n";
    if (!bytes || size <= sizeof(header) - 1 || size > KIOSK_VIEW_BYTES ||
        memcmp(bytes, header, sizeof(header) - 1) || bytes[size - 1] != '\n' || memchr(bytes, 0, size) ||
        kiosk_pin_before(deadline)) return -1;
    unsigned count = 0;
    for (size_t i = sizeof(header) - 1; i < size; i++) if (bytes[i] == '\n' && ++count > KIOSK_VIEW_ROWS) return -1;
    out->storage = malloc(size + 1); out->entries = calloc(count, sizeof(*out->entries));
    if (!out->storage || !out->entries) goto failed;
    memcpy(out->storage, bytes, size); out->storage[size] = 0;
    char *line = out->storage + sizeof(header) - 1;
    while (*line) {
        char *next = strchr(line, '\n'), *fields[9];
        if (!next || kiosk_pin_before(deadline)) goto failed;
        *next++ = 0;
        if (kiosk_receipt_fields(line, fields, 9) || strcmp(fields[0], "P")) goto failed;
        uint64_t n[7];
        for (unsigned i = 0; i < 7; i++) if (kiosk_receipt_uint(fields[i + 2], n + i)) goto failed;
        struct kiosk_pin_entry *e = &out->entries[out->count];
        e->relative = out->count ? fields[1] : "";
        if (out->count ? !kiosk_path(fields[1], 0) : strcmp(fields[1], "-")) goto failed;
        e->device = (dev_t) n[0]; e->inode = (ino_t) n[1]; e->mode = (mode_t) n[2];
        e->uid = (uid_t) n[3]; e->gid = (gid_t) n[4]; e->parent = (unsigned) n[5]; e->mountpoint = (unsigned) n[6];
        if ((uint64_t) e->device != n[0] || (uint64_t) e->inode != n[1] || (uint64_t) e->mode != n[2] ||
            (uint64_t) e->uid != n[3] || (uint64_t) e->gid != n[4] || e->parent != n[5] || e->mountpoint != n[6] ||
            !e->inode || e->uid || (e->mode & 022) || (!S_ISREG(e->mode) && !S_ISDIR(e->mode)) ||
            e->mountpoint > 1 || (out->count ? e->parent >= out->count ||
            strcmp(out->entries[out->count - 1].relative, e->relative) >= 0 : e->parent || !e->mountpoint || !S_ISDIR(e->mode))) goto failed;
        if (out->count) {
            const char *slash = strrchr(e->relative, '/');
            size_t length = slash ? (size_t) (slash - e->relative) : 0;
            const struct kiosk_pin_entry *parent = out->entries + e->parent;
            if (!S_ISDIR(parent->mode) || strlen(parent->relative) != length || strncmp(parent->relative, e->relative, length)) goto failed;
        }
        out->count++; line = next;
    }
    if (out->count != count || kiosk_pin_before(deadline)) goto failed;
    return 0;
failed:
    kiosk_publication_inventory_close(out); return -1;
}

static inline int kiosk_publication_inventory_encode(const struct kiosk_pin_entry *entries, unsigned count,
    char **bytes, size_t *size, uint64_t deadline)
{
    *bytes = NULL; *size = 0;
    if (!entries || !count || count > KIOSK_VIEW_ROWS || kiosk_pin_before(deadline)) return -1;
    char *data = NULL; size_t used = 0;
    FILE *stream = open_memstream(&data, &used);
    if (!stream) return -1;
    int result = -1;
    size_t bound = sizeof("ONPC-KIOSK-PINS\t1\n") - 1;
    if (fputs("ONPC-KIOSK-PINS\t1\n", stream) < 0) goto done;
    for (unsigned i = 0; i < count; i++) {
        char row[PATH_MAX + 256];
        const struct kiosk_pin_entry *e = entries + i;
        if (!e->relative || kiosk_pin_before(deadline)) goto done;
        int n = snprintf(row, sizeof(row), "P\t%s\t%llu\t%llu\t%llu\t%llu\t%llu\t%u\t%u\n",
            *e->relative ? e->relative : "-", (unsigned long long) e->device, (unsigned long long) e->inode,
            (unsigned long long) e->mode, (unsigned long long) e->uid, (unsigned long long) e->gid, e->parent, e->mountpoint);
        if (n <= 0 || (size_t) n >= sizeof(row) || (size_t) n > KIOSK_VIEW_BYTES - bound ||
            fwrite(row, 1, (size_t) n, stream) != (size_t) n) goto done;
        bound += (size_t) n;
    }
    if (fflush(stream) || used != bound || kiosk_pin_before(deadline)) goto done;
    struct kiosk_publication_inventory parsed;
    if (kiosk_publication_inventory_parse(&parsed, data, used, deadline)) goto done;
    kiosk_publication_inventory_close(&parsed); result = 0;
done:
    if (fclose(stream)) result = -1;
    if (result) free(data); else { *bytes = data; *size = used; }
    return result;
}

struct kiosk_publication_member { char *name; struct stat info; };
struct kiosk_publication {
    int parent, root, renamed, ready, removed;
    char name[80];
    struct stat parent_info, root_info;
    unsigned long long mount;
    struct kiosk_publication_member *members;
    unsigned count;
    uint64_t deadline;
};

struct kiosk_publication_ready_record {
    char material[65], view[65], inventory[65], boot[37];
    uint64_t root_device, root_inode, source_device, source_inode;
    uint64_t marker_device, marker_inode, attachment, publisher;
};

/* Closed reader for the exact native completion encoding. Parsing is only a
 * syntax check: selection must additionally bind its root/boot/material/V,
 * inventory hash, actual manager marker and recursive mounted source. */
static inline int kiosk_publication_ready_parse(struct kiosk_publication_ready_record *out,
    const void *bytes, size_t size, uint64_t deadline)
{
    memset(out, 0, sizeof(*out));
    if (!bytes || !size || size >= 1024 || ((const char *) bytes)[size - 1] != '\n' ||
        memchr(bytes, 0, size) || kiosk_pin_before(deadline)) return -1;
    char text[1024], *fields[14];
    memcpy(text, bytes, size); text[size - 1] = 0;
    if (strchr(text, '\n') || kiosk_receipt_fields(text, fields, 14) ||
        strcmp(fields[0], "ONPC-KIOSK-READY") || strcmp(fields[1], "2") ||
        !kiosk_receipt_hex(fields[2]) || !kiosk_receipt_hex(fields[3]) || !kiosk_receipt_hex(fields[4]) ||
        strlen(fields[5]) != 36 || strspn(fields[5], "0123456789abcdef-") != 36 ||
        fields[5][8] != '-' || fields[5][13] != '-' || fields[5][18] != '-' || fields[5][23] != '-') return -1;
    for (unsigned i = 0; i < 36; i++) if (i != 8 && i != 13 && i != 18 && i != 23 && fields[5][i] == '-') return -1;
    uint64_t values[8];
    for (unsigned i = 0; i < 8; i++) if (kiosk_receipt_uint(fields[6 + i], values + i)) return -1;
    if (!values[1] || !values[3] || !values[5] || !values[6] || !values[7] || values[7] > INT_MAX) return -1;
    strcpy(out->material, fields[2]); strcpy(out->view, fields[3]); strcpy(out->inventory, fields[4]); strcpy(out->boot, fields[5]);
    out->root_device = values[0]; out->root_inode = values[1];
    out->source_device = values[2]; out->source_inode = values[3];
    out->marker_device = values[4]; out->marker_inode = values[5];
    out->attachment = values[6]; out->publisher = values[7];
    return kiosk_pin_before(deadline);
}

static inline int kiosk_publication_name(const char *name)
{
    return name && kiosk_path(name, 0) && !strchr(name, '/');
}

/* Bounded stable descriptor read, including named records and anonymous
 * preparation records. Anonymous memfds use safe mode 0777 by default, so
 * their channel identity is the authority; disk records additionally require
 * exact private metadata in their callers. */
static inline int kiosk_publication_read(int fd, char **data, size_t *size, uint64_t deadline)
{
    struct stat before, after;
    *data = NULL; *size = 0;
    if (kiosk_pin_before(deadline) || fstat(fd, &before) || !S_ISREG(before.st_mode) ||
        before.st_size <= 0 || (uint64_t) before.st_size > KIOSK_VIEW_BYTES) return -1;
    char *bytes = malloc((size_t) before.st_size + 1);
    if (!bytes) return -1;
    size_t offset = 0;
    while (offset < (size_t) before.st_size) {
        if (kiosk_pin_before(deadline)) goto failed;
        ssize_t n = pread(fd, bytes + offset, (size_t) before.st_size - offset, (off_t) offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) goto failed;
        offset += (size_t) n;
    }
    if (kiosk_pin_before(deadline) || fstat(fd, &after) || !kiosk_pin_same_stat(&before, &after) ||
        before.st_nlink != after.st_nlink) goto failed;
    bytes[offset] = 0; *data = bytes; *size = offset; return 0;
failed:
    free(bytes); return -1;
}

static inline int kiosk_publication_private(const struct stat *info, int directory)
{
    return kiosk_trusted_stat(info, directory ? S_IFDIR : S_IFREG) && info->st_gid == 0 &&
        (info->st_mode & 07777) == (directory ? 0700 : 0600) &&
        (directory || info->st_nlink == 1);
}

static inline void kiosk_publication_close(struct kiosk_publication *p)
{
    if (p->root >= 0) close(p->root);
    if (p->parent >= 0) close(p->parent);
    for (unsigned i = 0; i < p->count; i++) free(p->members[i].name);
    free(p->members);
    memset(p, 0, sizeof(*p)); p->root = p->parent = -1;
}

static inline int kiosk_publication_current(struct kiosk_publication *p)
{
    struct stat parent, root, named;
    unsigned long long mount;
    return !kiosk_pin_before(p->deadline) && fstat(p->parent, &parent) == 0 &&
        kiosk_publication_private(&parent, 1) && parent.st_dev == p->parent_info.st_dev &&
        parent.st_ino == p->parent_info.st_ino && kiosk_pin_fd_mount(p->parent, &mount) == 0 && mount == p->mount &&
        fstat(p->root, &root) == 0 && kiosk_publication_private(&root, 1) &&
        root.st_dev == p->root_info.st_dev && root.st_ino == p->root_info.st_ino &&
        kiosk_pin_fd_mount(p->root, &mount) == 0 && mount == p->mount &&
        fstatat(p->parent, p->name, &named, AT_SYMLINK_NOFOLLOW) == 0 &&
        kiosk_publication_private(&named, 1) && named.st_dev == root.st_dev && named.st_ino == root.st_ino ? 0 : -1;
}

/* Adopts only a caller-verified initial ticket or newly native-created private
 * invocation record directory. It copies descriptors and records every exact
 * member before mutation. The supplied ticket membership is independently
 * verified by the preparation-plan owner, never inferred by a cleanup sweep. */
static inline int kiosk_publication_open_until(struct kiosk_publication *p, int parent, int root,
    const char *name, const struct kiosk_publication_member *members, unsigned count, uint64_t deadline)
{
    memset(p, 0, sizeof(*p)); p->parent = p->root = -1; p->deadline = deadline;
    if (!kiosk_publication_name(name) || strlen(name) >= sizeof(p->name) || count > KIOSK_VIEW_ROWS - 4 ||
        (count && !members) || kiosk_pin_before(deadline)) return -1;
    strcpy(p->name, name);
    p->parent = fcntl(parent, F_DUPFD_CLOEXEC, 3); p->root = fcntl(root, F_DUPFD_CLOEXEC, 3);
    p->members = calloc(KIOSK_VIEW_ROWS, sizeof(*p->members));
    if (p->parent < 0 || p->root < 0 || !p->members || fstat(p->parent, &p->parent_info) ||
        fstat(p->root, &p->root_info) || kiosk_pin_fd_mount(p->parent, &p->mount) ||
        kiosk_publication_current(p)) goto failed;
    for (unsigned i = 0; i < count; i++) {
        struct stat named;
        if (!kiosk_publication_name(members[i].name) || kiosk_pin_before(deadline) ||
            fstatat(root, members[i].name, &named, AT_SYMLINK_NOFOLLOW) ||
            !kiosk_pin_same_stat(&named, &members[i].info) || named.st_nlink != 1 ||
            !kiosk_trusted_stat(&named, S_IFREG) ||
            !(p->members[i].name = strdup(members[i].name))) goto failed;
        p->members[i].info = named; p->count++;
        for (unsigned j = 0; j < i; j++) if (!strcmp(p->members[j].name, members[i].name)) goto failed;
    }
    return 0;
failed:
    kiosk_publication_close(p); return -1;
}

/* Exact closed membership is checked on both read/reuse and write paths. No
 * directory timestamp is a material identity; every named member is checked. */
static inline int kiosk_publication_members(struct kiosk_publication *p)
{
    if (kiosk_publication_current(p)) return -1;
    int scan = openat(p->root, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    DIR *directory = scan < 0 ? NULL : fdopendir(scan);
    if (!directory) { if (scan >= 0) close(scan); return -1; }
    unsigned count = 0;
    struct dirent *entry;
    int result = -1;
    errno = 0;
    while ((entry = readdir(directory))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        if (kiosk_pin_before(p->deadline) || ++count > p->count) goto done;
        unsigned i;
        for (i = 0; i < p->count; i++) if (!strcmp(entry->d_name, p->members[i].name)) break;
        struct stat named;
        if (i == p->count || fstatat(p->root, entry->d_name, &named, AT_SYMLINK_NOFOLLOW) ||
            !kiosk_pin_same_stat(&named, &p->members[i].info) || named.st_nlink != 1 ||
            !kiosk_trusted_stat(&named, S_IFREG)) goto done;
        int fd = openat(p->root, entry->d_name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        unsigned long long mount;
        int valid = fd >= 0 && kiosk_pin_fd_mount(fd, &mount) == 0 && mount == p->mount;
        if (fd >= 0) close(fd);
        if (!valid) goto done;
        errno = 0;
    }
    if (!errno && count == p->count && !kiosk_publication_current(p)) result = 0;
done:
    closedir(directory); return result;
}

static inline int kiosk_publication_write(struct kiosk_publication *p, const char *name,
    const void *data, size_t size, int selinux)
{
    if (p->ready || !kiosk_publication_name(name) || !data || !size || size > KIOSK_VIEW_BYTES ||
        p->count >= KIOSK_VIEW_ROWS || kiosk_publication_members(p) ||
        kiosk_label(p->parent, NULL, 0, selinux) || kiosk_label(p->root, NULL, 0, selinux)) return -1;
    char *owned_name = strdup(name);
    if (!owned_name) return -1;
    int fd = openat(p->root, name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) { free(owned_name); return -1; }
    /* Immediately record the exact created object, including failed writes. */
    struct kiosk_publication_member *member = &p->members[p->count++];
    member->name = owned_name;
    int result = -1;
    if (fstat(fd, &member->info)) goto done;
    if (selinux) {
        const char context[] = "system_u:object_r:onpc_kiosk_runtime_t:s0";
        if (fsetxattr(fd, "security.selinux", context, sizeof(context), 0)) goto done;
    }
    if (fchmod(fd, 0600)) goto done;
    size_t offset = 0;
    while (offset < size) {
        if (kiosk_pin_before(p->deadline)) goto done;
        ssize_t written = write(fd, (const char *) data + offset, size - offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) goto done;
        offset += (size_t) written;
    }
    if (kiosk_pin_before(p->deadline) || fsync(fd) || fstat(fd, &member->info) ||
        !kiosk_publication_private(&member->info, 0) || kiosk_label(fd, NULL, 0, selinux) ||
        (size_t) member->info.st_size != size || kiosk_publication_members(p)) goto done;
    result = 0;
done:
    /* Keep identity current even on a partial write. Cleanup will require
     * inode/type/ownership/link/mount identity, never merely this name. */
    (void) fstat(fd, &member->info);
    close(fd); return result;
}

static inline int kiosk_publication_rename_until(struct kiosk_publication *p, const char *view)
{
    if (!kiosk_receipt_hex(view) || p->renamed || p->ready || kiosk_publication_members(p)) return -1;
    int scan = openat(p->parent, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    DIR *directory = scan < 0 ? NULL : fdopendir(scan);
    if (!directory) { if (scan >= 0) close(scan); return -1; }
    unsigned generations = 0, rows = 0;
    struct dirent *entry;
    int result = -1;
    errno = 0;
    while ((entry = readdir(directory))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        if (kiosk_pin_before(p->deadline) || ++rows > KIOSK_VIEW_ROWS) goto done;
        if (kiosk_receipt_hex(entry->d_name) && ++generations >= 4) goto done;
        errno = 0;
    }
    if (errno || kiosk_publication_members(p) ||
        renameat2(p->parent, p->name, p->parent, view, RENAME_NOREPLACE)) goto done;
    strcpy(p->name, view); p->renamed = 1;
    if (kiosk_pin_before(p->deadline) || fsync(p->parent) || kiosk_publication_members(p)) goto done;
    result = 0;
done:
    closedir(directory); return result;
}

/* A ready record cannot qualify without a live manager and its exact mounted
 * view. It binds native objects omitted from V to avoid recursive hashes:
 * marker inode, masks/coverage inventory, publication root, boot and publisher.
 * Local mount/namespace numbers are decision witnesses, not portable V inputs. */
static inline int kiosk_publication_ready_until(struct kiosk_publication *p,
    const struct kiosk_source_pin *pin, const char *material, const char *view,
    const char *inventory, const char *boot, const struct stat *marker, int selinux)
{
    if (!pin || !pin->complete || !pin->verified || !pin->attached || pin->worker >= 0 ||
        !kiosk_receipt_hex(material) || !kiosk_receipt_hex(view) || !kiosk_receipt_hex(inventory) ||
        !boot || strlen(boot) != 36 || strspn(boot, "0123456789abcdef-") != 36 ||
        !marker || !kiosk_trusted_stat(marker, S_IFREG) || marker->st_nlink != 1 ||
        kiosk_publication_members(p) || kiosk_label(p->parent, NULL, 0, selinux) ||
        kiosk_label(p->root, NULL, 0, selinux)) return -1;
    struct stat attached;
    if (fstat(pin->fd, &attached)) return -1;
    char record[1024];
    int length = snprintf(record, sizeof(record),
        "ONPC-KIOSK-READY\t2\t%s\t%s\t%s\t%s\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%llu\t%lu\n",
        material, view, inventory, boot, (unsigned long long) p->root_info.st_dev,
        (unsigned long long) p->root_info.st_ino, (unsigned long long) attached.st_dev,
        (unsigned long long) attached.st_ino, (unsigned long long) marker->st_dev,
        (unsigned long long) marker->st_ino, pin->attached_id, (unsigned long) getpid());
    struct kiosk_publication_ready_record checked;
    if (length <= 0 || (size_t) length >= sizeof(record) ||
        kiosk_publication_ready_parse(&checked, record, (size_t) length, p->deadline)) return -1;
    char *ready_name = strdup("ready");
    if (!ready_name) return -1;
    if (length <= 0 || (size_t) length >= sizeof(record) ||
        kiosk_publication_write(p, "ready.pending", record, (size_t) length, selinux) ||
        kiosk_pin_before(p->deadline) || renameat2(p->root, "ready.pending", p->root, "ready", RENAME_NOREPLACE)) {
        free(ready_name); return -1;
    }
    struct kiosk_publication_member *member = &p->members[p->count - 1];
    free(member->name); member->name = ready_name;
    /* rename already committed: preserve even if the subsequent durability or
     * identity check refuses. Failed MAC likewise keeps completion. */
    p->ready = 1;
    struct stat named;
    if (fstatat(p->root, "ready", &named, AT_SYMLINK_NOFOLLOW) ||
        named.st_dev != member->info.st_dev || named.st_ino != member->info.st_ino ||
        !kiosk_publication_private(&named, 0)) return -1;
    member->info = named;
    return !kiosk_pin_before(p->deadline) && fsync(p->root) == 0 &&
        kiosk_publication_members(p) == 0 ? 0 : -1;
}

/* Explicit failed-attempt recovery only. Completed records survive until
 * reboot. Validate the entire finite ownership set before the first unlink. */
static inline int kiosk_publication_abort_until(struct kiosk_publication *p, uint64_t recovery_deadline)
{
    /* Recovery is a separate, explicit owner operation. An expired admission
     * never receives a renewed budget or any completion credit from cleanup. */
    p->deadline = recovery_deadline;
    if (p->removed) {
        struct stat parent;
        unsigned long long mount;
        return !kiosk_pin_before(recovery_deadline) && fstat(p->parent, &parent) == 0 &&
            kiosk_publication_private(&parent, 1) && parent.st_dev == p->parent_info.st_dev &&
            parent.st_ino == p->parent_info.st_ino && kiosk_pin_fd_mount(p->parent, &mount) == 0 &&
            mount == p->mount && fsync(p->parent) == 0 ? 0 : -1;
    }
    if (p->ready || kiosk_publication_members(p)) return -1;
    for (unsigned i = 0; i < p->count; i++) {
        struct stat named;
        int fd = openat(p->root, p->members[i].name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        unsigned long long mount;
        int valid = fd >= 0 && fstat(fd, &named) == 0 && S_ISREG(named.st_mode) && named.st_uid == 0 &&
            !(named.st_mode & 022) && named.st_nlink == 1 &&
            named.st_dev == p->members[i].info.st_dev && named.st_ino == p->members[i].info.st_ino &&
            kiosk_pin_fd_mount(fd, &mount) == 0 && mount == p->mount;
        if (fd >= 0) close(fd);
        if (!valid) return -1;
    }
    while (p->count) {
        unsigned i = p->count - 1;
        struct stat named;
        if (kiosk_publication_current(p) ||
            fstatat(p->root, p->members[i].name, &named, AT_SYMLINK_NOFOLLOW) ||
            named.st_dev != p->members[i].info.st_dev || named.st_ino != p->members[i].info.st_ino ||
            named.st_nlink != 1 || unlinkat(p->root, p->members[i].name, 0)) return -1;
        free(p->members[i].name); p->members[i].name = NULL; p->count--;
    }
    if (kiosk_publication_current(p) || unlinkat(p->parent, p->name, AT_REMOVEDIR)) return -1;
    p->removed = 1;
    return fsync(p->parent) == 0 ? 0 : -1;
}
#endif
