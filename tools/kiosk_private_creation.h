/* Initialization is authority to mutate only a proven new object. Callers
 * retain exclusive creation, named/opened identity and mount/cleanup proofs.
 * Existing private state is always validation-only. */
#ifndef ONPC_KIOSK_PRIVATE_CREATION_H
#define ONPC_KIOSK_PRIVATE_CREATION_H
#include <errno.h>
#include <fcntl.h>
#include <sys/fsuid.h>
#include <sys/stat.h>
#include <unistd.h>

static inline int kiosk_private_fsuid(void)
{
    /* -1 queries Linux filesystem credentials without changing them. Effective
     * root alone does not establish the identity used by filesystem creation. */
    return geteuid() == 0 && (uid_t)setfsuid((uid_t)-1) == 0 ? 0 : -1;
}

static inline int kiosk_private_initialize(int fd, mode_t mode, int root_group)
{
    struct stat before, after;
    if (kiosk_private_fsuid() || fstat(fd, &before) || before.st_uid != 0 ||
        (!S_ISDIR(before.st_mode) && !S_ISREG(before.st_mode)) ||
        (S_ISREG(before.st_mode) && before.st_nlink != 1)) return -1;
    /* Group inheritance (including SGID parents) is irrelevant to a new
     * root:root object. chown must precede the final mode initialization. */
    if ((root_group && fchown(fd, 0, 0)) || fchmod(fd, mode) || fstat(fd, &after) ||
        after.st_dev != before.st_dev || after.st_ino != before.st_ino ||
        (after.st_mode & S_IFMT) != (before.st_mode & S_IFMT) || after.st_uid != 0 ||
        (root_group ? after.st_gid != 0 : after.st_gid != before.st_gid) ||
        (after.st_mode & 07777) != mode || after.st_nlink != before.st_nlink) return -1;
    return 0;
}

/* Locks intentionally permit any group: UID ownership, exact mode 0600 and
 * single-link named identity are their access policy. Preserve that policy on
 * reuse and preserve the inherited group on new locks. O_CREAT without EXCL
 * would not establish permission to initialize the returned object. */
static inline int kiosk_private_lock_open(const char *path, uid_t owner, int extra)
{
    struct stat opened, named;
    if (geteuid() != owner || (uid_t)setfsuid((uid_t)-1) != owner) return -1;
    int fd = open(path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC | extra, 0600);
    if (fd < 0) {
        if (errno != EEXIST) return -1;
        return open(path, O_RDWR | O_NOFOLLOW | O_CLOEXEC | extra);
    }
    if (fstat(fd, &opened) || lstat(path, &named) || !S_ISREG(opened.st_mode) ||
        !S_ISREG(named.st_mode) || opened.st_uid != owner || named.st_uid != owner ||
        opened.st_nlink != 1 || named.st_nlink != 1 ||
        opened.st_dev != named.st_dev || opened.st_ino != named.st_ino ||
        fchmod(fd, 0600)) {
        close(fd); return -1;
    }
    return fd;
}
#endif
