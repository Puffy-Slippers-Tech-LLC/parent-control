/* Called in the PAM executor, never in its preparation subprocess. */
#include <dlfcn.h>
#include <limits.h>
#include <sched.h>
#include <sys/mount.h>
#include <sys/prctl.h>

#ifndef KIOSK_CONFINEMENT_PREPARE
#define KIOSK_CONFINEMENT_PREPARE "/usr/libexec/oh-no-parent-control-kiosk-confinement"
#endif
#define KIOSK_CONFINEMENT_LOCK "/run/oh-no-parent-control-confinement.lock"
#define KIOSK_CONFINEMENT_RUNTIME "/run/oh-no-parent-control-confinement"
#define KIOSK_CONFINEMENT_BINDINGS "/run/oh-no-parent-control-confinement/bindings"
#ifndef KIOSK_ADMISSION_LOCK
#define KIOSK_ADMISSION_LOCK "/run/oh-no-parent-control-kiosk-admission.lock"
#endif
#ifndef KIOSK_ADMISSION_DISABLED
#define KIOSK_ADMISSION_DISABLED "/var/lib/oh-no-parent-control/kiosk-confinement-removing"
#endif
#ifndef KIOSK_ADMISSION_LOCK_OWNER
#define KIOSK_ADMISSION_LOCK_OWNER 0
#endif
#define KIOSK_ADMISSION_DATA "oh-no-parent-control.kiosk-admission"

static void
release_kiosk_admission(pam_handle_t *pamh, void *data, int status)
{
    int *fd = data;
    (void) pamh;
    (void) status;
    close(*fd);
    free(fd);
}

/* A lease spans the entire PAM handle, including the trusted root worker's
 * interval between returning from open_session and setting UID/exec. Forked
 * PAM lifecycle children inherit the same open-file description. Never unlink
 * this inode: removal takes its exclusive lock before scanning processes. */
static int
kiosk_admission(pam_handle_t *pamh, const char *username)
{
    const void *existing = NULL;
    struct stat info, path_info;
    int *fd, result;
    if (strcmp(username, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_SUCCESS;
    result = pam_get_data(pamh, KIOSK_ADMISSION_DATA, &existing);
    if (result == PAM_SUCCESS && existing != NULL)
        return PAM_SUCCESS;
    if (result != PAM_NO_MODULE_DATA && result != PAM_SUCCESS)
        return result;
    fd = malloc(sizeof(*fd));
    if (fd == NULL)
        return PAM_BUF_ERR;
    *fd = open(KIOSK_ADMISSION_LOCK,
               O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, 0600);
    if (*fd < 0 || fstat(*fd, &info) != 0 || !S_ISREG(info.st_mode) ||
        info.st_uid != KIOSK_ADMISSION_LOCK_OWNER || (info.st_mode & 07777) != 0600 ||
        info.st_nlink != 1 || flock(*fd, LOCK_SH | LOCK_NB) != 0 ||
        lstat(KIOSK_ADMISSION_LOCK, &path_info) != 0 ||
        path_info.st_dev != info.st_dev || path_info.st_ino != info.st_ino ||
        lstat(KIOSK_ADMISSION_DISABLED, &path_info) == 0 || errno != ENOENT) {
        if (*fd >= 0)
            close(*fd);
        free(fd);
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk admission outcome=denied stage=removal-barrier");
        return PAM_PERM_DENIED;
    }
    result = pam_set_data(pamh, KIOSK_ADMISSION_DATA, fd, release_kiosk_admission);
    if (result != PAM_SUCCESS)
        release_kiosk_admission(pamh, fd, result);
    return result;
}

static int
kiosk_admission_fd(pam_handle_t *pamh)
{
    const void *data = NULL;
    return pam_get_data(pamh, KIOSK_ADMISSION_DATA, &data) == PAM_SUCCESS && data != NULL
        ? *(const int *) data : -1;
}

static int
prepare_kiosk_confinement(const char *role, int lock_fd, int admission_fd)
{
    char *const args[] = {(char *) KIOSK_CONFINEMENT_PREPARE, (char *) role, NULL};
    char *const env[] = {(char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                        (char *) "LC_ALL=C", NULL};
    struct timespec start, now, pause = {0, 10000000};
    pid_t child, waited;
    int status;
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0)
        return -1;
    child = fork();
    if (child == 0) {
        if (fcntl(lock_fd, F_DUPFD, STDERR_FILENO + 1) < 0 ||
            fcntl(admission_fd, F_DUPFD, STDERR_FILENO + 1) < 0)
            _exit(127);
        execve(KIOSK_CONFINEMENT_PREPARE, args, env);
        _exit(127);
    }
    if (child < 0)
        return -1;
    for (;;) {
        waited = waitpid(child, &status, WNOHANG);
        if (waited == child)
            return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
        if (waited < 0 && errno != EINTR)
            return -1;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec - start.tv_sec >= 60) {
            kill(child, SIGKILL);
            do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
            return -1;
        }
        nanosleep(&pause, NULL);
    }
}

static int
preserved_kiosk_identity(const struct stat *info, const char *assertion)
{
    unsigned long long device, inode, size, mtime, ctime, mode, uid, gid;
    char extra;
    if (strspn(assertion, "0123456789 ") != strlen(assertion) ||
        sscanf(assertion, "%llu %llu %llu %llu %llu %llu %llu %llu%c",
               &device, &inode, &size, &mtime, &ctime, &mode, &uid, &gid, &extra) != 8)
        return -1;
    return (device == (unsigned long long) info->st_dev &&
            inode == (unsigned long long) info->st_ino &&
            size == (unsigned long long) info->st_size &&
            mtime == (unsigned long long) info->st_mtim.tv_sec * 1000000000ULL + info->st_mtim.tv_nsec &&
            ctime == (unsigned long long) info->st_ctim.tv_sec * 1000000000ULL + info->st_ctim.tv_nsec &&
            mode == (unsigned long long) info->st_mode && uid == info->st_uid && gid == info->st_gid)
        ? 0 : -1;
}

static int
bind_kiosk_executables(char *backend, size_t size)
{
    struct stat info, target_info;
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY};
    char line[PATH_MAX * 2 + 4], fd_path[64], target_fd_path[64];
    const char *runtime = "/run/oh-no-parent-control-confinement/";
    FILE *stream = NULL;
    char **staged = NULL;
    unsigned staged_count = 0;
    int fd = -1, source = -1, target = -1, result = -1, attached = 0;
    unsigned count = 0;
    fd = open(KIOSK_CONFINEMENT_BINDINGS, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0 || fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) ||
        info.st_uid != 0 || (info.st_mode & 07777) != 0600 || info.st_nlink != 1 ||
        (stream = fdopen(fd, "r")) == NULL)
        goto done;
    fd = -1;
    if (fgets(backend, (int) size, stream) == NULL)
        goto done;
    if (strcmp(backend, "apparmor\n") != 0 && strcmp(backend, "selinux\n") != 0)
        goto done;
    backend[strcspn(backend, "\n")] = '\0';
    staged = calloc(32768, sizeof(*staged));
    if (staged == NULL)
        goto done;
    if (unshare(CLONE_NEWNS) != 0 || mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) != 0)
        goto done;
    while (fgets(line, sizeof(line), stream) != NULL) {
        char *destination = strchr(line, '\t');
        char *assertion;
        size_t length = strlen(line);
        if (++count > 32769 || attached || length == 0 || line[length - 1] != '\n' || destination == NULL)
            goto done;
        line[length - 1] = '\0';
        *destination++ = '\0';
        assertion = strchr(destination, '\t');
        if (assertion != NULL)
            *assertion++ = '\0';
        if ((strncmp(line, "/usr/", 5) != 0 && strncmp(line, runtime, strlen(runtime)) != 0) ||
            strstr(line, "/../") != NULL ||
            (strncmp(destination, runtime, strlen(runtime)) != 0 && strcmp(destination, "/usr") != 0) ||
            strstr(destination, "/../") != NULL || strchr(destination, '\t') != NULL)
            goto done;
        source = open(line, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        target = open(destination, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (source < 0 || target < 0 || fstat(source, &info) != 0 ||
            fstat(target, &target_info) != 0 ||
            (!S_ISREG(info.st_mode) && !S_ISDIR(info.st_mode)) ||
            (info.st_mode & S_IFMT) != (target_info.st_mode & S_IFMT) ||
            info.st_uid != 0 || target_info.st_uid != 0 ||
            (info.st_mode & 022) != 0 || (target_info.st_mode & 022) != 0 ||
            (S_ISREG(target_info.st_mode) && target_info.st_nlink != 1))
            goto done;
        if (assertion != NULL && (!S_ISREG(info.st_mode) || info.st_nlink != 1 ||
                                  preserved_kiosk_identity(&info, assertion) != 0))
            goto done;
        snprintf(fd_path, sizeof(fd_path), "/proc/self/fd/%d", source);
        snprintf(target_fd_path, sizeof(target_fd_path), "/proc/self/fd/%d", target);
        if (mount(fd_path, target_fd_path, NULL, MS_BIND | MS_REC, NULL) != 0 ||
            mount_setattr(AT_FDCWD, destination, AT_RECURSIVE, &readonly, sizeof(readonly)) != 0)
            goto done;
        if (assertion != NULL && (fstat(source, &info) != 0 ||
                preserved_kiosk_identity(&info, assertion) != 0))
            goto done;
        if (strcmp(destination, "/usr") == 0) {
            if (strncmp(line, runtime, strlen(runtime)) != 0 || !S_ISDIR(info.st_mode))
                goto done;
            attached = 1;
        } else {
            if (staged_count >= 32768 ||
                (staged[staged_count] = strdup(destination)) == NULL)
                goto done;
            staged_count++;
        }
        close(source);
        close(target);
        source = -1;
        target = -1;
    }
    if (!ferror(stream) && count > 1 && attached) {
        /* MS_REC cloned the complete pinned view onto /usr. Its original
         * staging mounts are now redundant, and would otherwise make the
         * user manager synthesize thousands of extra mount units. Detach only
         * destinations recorded by this invocation, before entering MAC.
         * The /usr clones retain their independent read-only inode pins. */
        for (unsigned i = 0; i < staged_count; i++)
            if (umount2(staged[i], MNT_DETACH) != 0)
                goto done;
        result = 0;
    }
done:
    for (unsigned i = 0; i < staged_count; i++)
        free(staged[i]);
    free(staged);
    if (source >= 0)
        close(source);
    if (target >= 0)
        close(target);
    if (stream != NULL)
        fclose(stream);
    if (fd >= 0)
        close(fd);
    return result;
}

static int
apply_kiosk_mac(const char *backend, const char *role)
{
    char context[128];
    void *library;
    int result = -1;
    if (strcmp(backend, "apparmor") == 0) {
        int (*change_profile)(const char *);
        int (*getcon)(char **, char **);
        char *label = NULL, *mode = NULL;
        library = dlopen("libapparmor.so.1", RTLD_NOW | RTLD_LOCAL);
        if (library == NULL)
            return -1;
        change_profile = (int (*)(const char *)) dlsym(library, "aa_change_profile");
        getcon = (int (*)(char **, char **)) dlsym(library, "aa_getcon");
        snprintf(context, sizeof(context), "onpc-kiosk-%s", role);
        /* Unconfined change_onexec does not check the first executable against
         * the target policy. Immediate change_profile closes that gap. */
        if (change_profile != NULL && getcon != NULL && change_profile(context) == 0 &&
            getcon(&label, &mode) >= 0 && label != NULL && mode != NULL &&
            strcmp(label, context) == 0 && strcmp(mode, "enforce") == 0)
            result = 0;
        free(label); /* mode points into the allocation returned in label. */
    } else {
        int (*enabled)(void), (*enforcing)(void), (*setexec)(const char *);
        char *pending = NULL;
        int (*getexec)(char **);
        int (*setcurrent)(const char *), (*getcurrent)(char **);
        void (*freecon)(char *);
        library = dlopen("libselinux.so.1", RTLD_NOW | RTLD_LOCAL);
        if (library == NULL)
            return -1;
        enabled = (int (*)(void)) dlsym(library, "is_selinux_enabled");
        enforcing = (int (*)(void)) dlsym(library, "security_getenforce");
        setexec = (int (*)(const char *)) dlsym(library, "setexeccon_raw");
        getexec = (int (*)(char **)) dlsym(library, "getexeccon_raw");
        setcurrent = (int (*)(const char *)) dlsym(library, "setcon_raw");
        getcurrent = (int (*)(char **)) dlsym(library, "getcon_raw");
        freecon = (void (*)(char *)) dlsym(library, "freecon");
        snprintf(context, sizeof(context), "system_u:system_r:onpc_kiosk_%s_t:s0", role);
        if (enabled != NULL && enforcing != NULL && setexec != NULL && getexec != NULL &&
            freecon != NULL && enabled() == 1 && enforcing() == 1) {
            if (strcmp(role, "manager") == 0) {
                /* systemd forks its PAM lifecycle child before the real exec.
                 * Enter a restricted current domain in the trusted executor;
                 * both descendants stay confined even when pam_selinux close
                 * clears its pending exec context. The kernel refuses unsafe
                 * multithreaded dynamic transitions. No reverse grant exists. */
                snprintf(context, sizeof(context), "system_u:system_r:onpc_kiosk_manager_pam_t:s0");
                if (setcurrent != NULL && getcurrent != NULL && setexec(NULL) == 0 &&
                    setcurrent(context) == 0 && getcurrent(&pending) == 0 && pending != NULL &&
                    strcmp(pending, context) == 0)
                    result = 0;
            } else {
                /* GDM's trusted root worker retains its vendor context. The
                 * session child must exec the private gate entrypoint; the
                 * kernel checks the actual selected command, not metadata. */
                if (setexec(context) == 0 && getexec(&pending) == 0 && pending != NULL &&
                    strcmp(pending, context) == 0)
                    result = 0;
            }
        }
        if (pending != NULL && freecon != NULL)
            freecon(pending);
    }
    dlclose(library);
    return result;
}

static int
kiosk_confinement(pam_handle_t *pamh)
{
    const char *username = NULL, *service = NULL, *role, *stage = "identity";
    struct stat info;
    char backend[32];
    int fd = -1, result = PAM_SESSION_ERR;
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL)
        return PAM_USER_UNKNOWN;
    if (strcmp(username, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_SUCCESS;
    stage = "admission";
    if (kiosk_admission(pamh, username) != PAM_SUCCESS)
        goto done;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **) &service) != PAM_SUCCESS ||
        service == NULL || geteuid() != 0)
        goto done;
    if (strcmp(service, "systemd-user") == 0)
        role = "manager";
    else if (strcmp(service, "gdm-password") == 0)
        role = "gate";
    else
        goto done;
    stage = "lock";
    fd = open(KIOSK_CONFINEMENT_LOCK, O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0 || fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_uid != 0 ||
        (info.st_mode & 07777) != 0600 || info.st_nlink != 1 ||
        flock(fd, LOCK_EX | LOCK_NB) != 0)
        goto done;
    /* Create the shared tree in the actual PAM caller's SELinux domain.
     * Fedora may transition the preparation interpreter to unconfined_t;
     * letting that subprocess create this directory loses the named runtime
     * type transition shared by systemd and GDM. The lock serializes creation.
     * Never repair a foreign directory or follow a pre-existing symlink. */
    stage = "runtime";
    if ((mkdir(KIOSK_CONFINEMENT_RUNTIME, 0700) != 0 && errno != EEXIST) ||
        lstat(KIOSK_CONFINEMENT_RUNTIME, &info) != 0 || !S_ISDIR(info.st_mode) ||
        info.st_uid != 0 || (info.st_mode & 07777) != 0700)
        goto done;
    stage = "prepare";
    if (prepare_kiosk_confinement(role, fd, kiosk_admission_fd(pamh)) != 0)
        goto done;
    stage = "bind";
    if (bind_kiosk_executables(backend, sizeof(backend)) != 0)
        goto done;
    /* No subprocesses after setting the boundary: pending SELinux context is
     * reserved for the caller's real executable, not a verification helper. */
    stage = "environment";
    if (strcmp(role, "manager") == 0 &&
        pam_putenv(pamh, "SYSTEMD_UNIT_PATH=/usr/share/oh-no-parent-control/confinement/user-units:") != PAM_SUCCESS)
        goto done;
    /* pam_systemd may grant CAP_WAKE_ALARM to regular login accounts. The
     * kiosk needs no ambient capabilities. Clear them before AppArmor masks
     * capget: systemd reads PAM's ambient set and otherwise tries to raise a
     * capability its new profile no longer permits. */
    stage = "ambient";
    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) != 0)
        goto done;
    stage = "mac";
    if (apply_kiosk_mac(backend, role) != 0)
        goto done;
    result = PAM_SUCCESS;
    stage = "armed";
done:
    if (fd >= 0)
        close(fd);
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam kiosk execution-boundary outcome=%s stage=%s",
               result == PAM_SUCCESS ? "armed" : "denied", stage);
    return result;
}
