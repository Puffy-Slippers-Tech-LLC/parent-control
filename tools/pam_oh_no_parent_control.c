#define _GNU_SOURCE

/* The ordinary-user time/status contract comes from
 * release 188be907c46b1cd0dabae06ac898c43e75beb05e and remains unchanged.
 * Kiosk dispatch checks public routing preferences, not the next executable.
 * The small shared lease preserves existing package-removal ownership only. */
#include <errno.h>
#include <fcntl.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <security/pam_ext.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/fsuid.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <syslog.h>
#include <time.h>
#include <unistd.h>

#ifndef SESSION_LIMIT_CHECK_PATH
#define SESSION_LIMIT_CHECK_PATH "/usr/libexec/oh-no-parent-control-session-limit-check"
#endif
#ifndef LOGIN_CHECK_PATH
#define LOGIN_CHECK_PATH "/usr/libexec/oh-no-parent-control-login-check"
#endif
#ifndef KIOSK_ACCOUNT_NAME
#define KIOSK_ACCOUNT_NAME "oh-no-parent-control"
#endif
#ifndef KIOSK_ADMISSION_LOCK
#define KIOSK_ADMISSION_LOCK "/run/oh-no-parent-control-kiosk-admission.lock"
#endif
#ifndef KIOSK_ADMISSION_DISABLED
#define KIOSK_ADMISSION_DISABLED "/var/lib/oh-no-parent-control/kiosk-confinement-removing"
#endif
#ifndef KIOSK_ADMISSION_LOCK_OWNER
#define KIOSK_ADMISSION_LOCK_OWNER 0
#endif
#ifndef KIOSK_LOGIN_TIMEOUT_SECONDS
#define KIOSK_LOGIN_TIMEOUT_SECONDS 25
#endif
#define ADMISSION_DATA "oh-no-parent-control.kiosk-admission"
#define ACCOUNT_DATA "oh-no-parent-control.kiosk-account-checked"
#define RUNTIME_MAX_DATA "systemd.runtime_max_sec"

static int
admission_check_failed(pam_handle_t *pamh, const char *check, int error)
{
    /* Fixed check names and numeric errors only; never account/path metadata.
     * Keep the original denial marker separately for existing consumers. */
    pam_syslog(pamh, LOG_WARNING,
               "onpc.pam kiosk admission check=%s errno=%d", check, error);
    return 0;
}

static int
lock_current(pam_handle_t *pamh, int fd)
{
    struct stat opened, named, barrier;
    if (fstat(fd, &opened) != 0)
        return admission_check_failed(pamh, "lock-fstat", errno);
    if (lstat(KIOSK_ADMISSION_LOCK, &named) != 0)
        return admission_check_failed(pamh, "lock-lstat", errno);
    if (!S_ISREG(opened.st_mode) || !S_ISREG(named.st_mode) ||
        opened.st_uid != KIOSK_ADMISSION_LOCK_OWNER ||
        (opened.st_mode & 07777) != 0600 || opened.st_nlink != 1 ||
        opened.st_dev != named.st_dev || opened.st_ino != named.st_ino)
        return admission_check_failed(pamh, "lock-identity", 0);
    if (lstat(KIOSK_ADMISSION_DISABLED, &barrier) == 0)
        return admission_check_failed(pamh, "removal-barrier-present", 0);
    if (errno != ENOENT)
        return admission_check_failed(pamh, "removal-barrier-lstat", errno);
    return 1;
}

static void
release_admission(pam_handle_t *pamh, void *data, int status)
{
    (void) pamh;
    (void) status;
    close(*(int *) data);
    free(data);
}

static int
admission(pam_handle_t *pamh)
{
    const void *existing = NULL;
    struct stat opened, named;
    int *fd, result, created = 0;
    result = pam_get_data(pamh, ADMISSION_DATA, &existing);
    if (result == PAM_SUCCESS && existing != NULL)
        return lock_current(pamh, *(const int *) existing) ? PAM_SUCCESS : PAM_PERM_DENIED;
    if (result != PAM_SUCCESS && result != PAM_NO_MODULE_DATA)
        return result;
    if (geteuid() != KIOSK_ADMISSION_LOCK_OWNER ||
        (uid_t) setfsuid((uid_t) -1) != KIOSK_ADMISSION_LOCK_OWNER)
        return PAM_PERM_DENIED;
    fd = malloc(sizeof(*fd));
    if (fd == NULL)
        return PAM_BUF_ERR;
    *fd = open(KIOSK_ADMISSION_LOCK, O_RDONLY | O_CREAT | O_EXCL | O_NOFOLLOW |
               O_CLOEXEC | O_NONBLOCK, 0600);
    if (*fd >= 0)
        created = 1;
    else if (errno == EEXIST) {
        *fd = open(KIOSK_ADMISSION_LOCK, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
        if (*fd < 0)
            admission_check_failed(pamh, "existing-lock-open", errno);
    } else {
        admission_check_failed(pamh, "new-lock-open", errno);
    }
    /* Initialize only a proven new owned inode. Never change umask, repair an
     * existing lock or unlink it; the lifecycle uses the same named inode.
     * A shared flock needs no write access: GDM and the user-manager executor
     * can have different SELinux write authority over this shared inode. */
    if (*fd < 0)
        goto denied;
    if (created) {
        if (fstat(*fd, &opened) != 0) {
            admission_check_failed(pamh, "new-lock-fstat", errno);
            goto denied;
        }
        if (lstat(KIOSK_ADMISSION_LOCK, &named) != 0) {
            admission_check_failed(pamh, "new-lock-lstat", errno);
            goto denied;
        }
        if (!S_ISREG(opened.st_mode) || opened.st_uid != KIOSK_ADMISSION_LOCK_OWNER ||
            opened.st_nlink != 1 || opened.st_dev != named.st_dev ||
            opened.st_ino != named.st_ino) {
            admission_check_failed(pamh, "new-lock-identity", 0);
            goto denied;
        }
        if (fchmod(*fd, 0600) != 0) {
            admission_check_failed(pamh, "new-lock-chmod", errno);
            goto denied;
        }
    }
    if (flock(*fd, LOCK_SH | LOCK_NB) != 0) {
        admission_check_failed(pamh, "shared-lock", errno);
        goto denied;
    }
    if (!lock_current(pamh, *fd))
        goto denied;
    result = pam_set_data(pamh, ADMISSION_DATA, fd, release_admission);
    if (result != PAM_SUCCESS)
        release_admission(pamh, fd, result);
    return result;

denied:
    if (*fd >= 0)
        close(*fd);
    free(fd);
    pam_syslog(pamh, LOG_WARNING, "onpc.pam kiosk admission outcome=denied stage=removal-barrier");
    return PAM_PERM_DENIED;
}

static int
kiosk_identity(pam_handle_t *pamh, const char **user, const char **service)
{
    if (pam_get_user(pamh, user, NULL) != PAM_SUCCESS || *user == NULL || **user == '\0')
        return PAM_USER_UNKNOWN;
    if (strcmp(*user, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_IGNORE;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **) service) != PAM_SUCCESS ||
        *service == NULL || **service == '\0')
        return PAM_SERVICE_ERR;
    if (strcmp(*service, "gdm-password") != 0 && strcmp(*service, "systemd-user") != 0)
        return PAM_PERM_DENIED;
    return admission(pamh);
}

static int
run_kiosk_check(pam_handle_t *pamh, const char *user, const char *service,
                const char *operation, const char *transport)
{
    char *user_env = NULL, *service_env = NULL, *type_env = NULL;
    char *environment[5] = {NULL, NULL, NULL, NULL, NULL};
    char *arguments[] = {(char *) LOGIN_CHECK_PATH, (char *) operation, NULL};
    const void *lease = NULL;
    struct timespec start, now, pause = {0, 10000000};
    pid_t child, waited;
    int status;
    if (pam_get_data(pamh, ADMISSION_DATA, &lease) != PAM_SUCCESS || lease == NULL)
        return PAM_SYSTEM_ERR;
    if (asprintf(&user_env, "PAM_USER=%s", user) < 0 ||
        asprintf(&service_env, "PAM_SERVICE=%s", service) < 0 ||
        asprintf(&type_env, "XDG_SESSION_TYPE=%s", transport == NULL ? "" : transport) < 0) {
        free(user_env); free(service_env); free(type_env);
        return PAM_BUF_ERR;
    }
    environment[0] = user_env;
    environment[1] = service_env;
    environment[2] = type_env;
    environment[3] = (char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin";
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) {
        free(user_env); free(service_env); free(type_env);
        return PAM_SYSTEM_ERR;
    }
    child = fork();
    if (child == 0) {
        int null_fd = open("/dev/null", O_RDWR | O_CLOEXEC);
        /* Keep the same removal lease if the caller aborts while our bounded
         * helper is still working. Its busctl children close inherited fds. */
        if (null_fd < 0 || fcntl(*(const int *) lease, F_DUPFD, STDERR_FILENO + 1) < 0 ||
            dup2(null_fd, STDIN_FILENO) < 0 || dup2(null_fd, STDOUT_FILENO) < 0 ||
            dup2(null_fd, STDERR_FILENO) < 0)
            _exit(127);
        if (null_fd > STDERR_FILENO)
            close(null_fd);
        execve(LOGIN_CHECK_PATH, arguments, environment);
        _exit(127);
    }
    free(user_env); free(service_env); free(type_env);
    if (child < 0)
        return PAM_SYSTEM_ERR;
    for (;;) {
        waited = waitpid(child, &status, WNOHANG);
        if (waited == child) {
            if (!WIFEXITED(status))
                return PAM_SYSTEM_ERR;
            return WEXITSTATUS(status) == 0 ? PAM_SUCCESS :
                WEXITSTATUS(status) == 1 ? PAM_PERM_DENIED : PAM_SYSTEM_ERR;
        }
        if (waited < 0 && errno != EINTR)
            return PAM_SYSTEM_ERR;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
            now.tv_sec - start.tv_sec > KIOSK_LOGIN_TIMEOUT_SECONDS ||
            (now.tv_sec - start.tv_sec == KIOSK_LOGIN_TIMEOUT_SECONDS && now.tv_nsec >= start.tv_nsec)) {
            /* Our unreaped fork child cannot have had its PID reused. */
            kill(child, SIGKILL);
            do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
            pam_syslog(pamh, LOG_ERR, "onpc.pam kiosk routing outcome=unavailable reason=timeout");
            return PAM_SYSTEM_ERR;
        }
        nanosleep(&pause, NULL);
    }
}

PAM_EXTERN int
pam_sm_acct_mgmt(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const void *runtime_max = NULL;
    const char *service = NULL, *user = NULL;
    int result;
    (void) flags;
    if (argc == 1 && strcmp(argv[0], "kiosk") == 0) {
        result = kiosk_identity(pamh, &user, &service);
        if (result != PAM_SUCCESS)
            return result == PAM_IGNORE ? PAM_SUCCESS : result;
        if (strcmp(service, "systemd-user") == 0)
            return PAM_SUCCESS;
        result = run_kiosk_check(pamh, user, service, "--kiosk-account", NULL);
        /* Remember failure too: a previously successful account check cannot
         * authorize session opening after a later failed account check. */
        if (pam_set_data(pamh, ACCOUNT_DATA, (void *) (result == PAM_SUCCESS ? "allowed" : "denied"), NULL) != PAM_SUCCESS)
            return PAM_SYSTEM_ERR;
        return result;
    }
    if (argc != 0)
        return PAM_SERVICE_ERR;
    result = pam_get_item(pamh, PAM_SERVICE, (const void **) &service);
    if (result != PAM_SUCCESS || service == NULL || service[0] == '\0')
        return PAM_SERVICE_ERR;
    if (strncmp(service, "gdm-", 4) != 0)
        return PAM_SUCCESS;
    /* Preserve Malcontent's time policy, but use GNOME lock rather than a
     * login-time kill timer. Terminal/SSH/sudo keep their existing timer. */
    result = pam_get_data(pamh, RUNTIME_MAX_DATA, &runtime_max);
    if (result == PAM_NO_MODULE_DATA || (result == PAM_SUCCESS && runtime_max == NULL))
        return PAM_SUCCESS;
    if (result != PAM_SUCCESS) {
        pam_syslog(pamh, LOG_ERR, "onpc.pam session runtime cap outcome=failed stage=read status=%d", result);
        return result;
    }
    if (strcmp(runtime_max, "infinity") == 0)
        return PAM_SUCCESS;
    result = pam_set_data(pamh, RUNTIME_MAX_DATA, (void *) "infinity", NULL);
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam session runtime cap outcome=%s stage=before-session status=%d",
               result == PAM_SUCCESS ? "cleared" : "failed", result);
    return result;
}

static int
run_session_limit_check(const char *username, const char *service)
{
    char *user_environment = NULL, *service_environment = NULL;
    char *environment[4] = {NULL, NULL, NULL, NULL};
    char *arguments[] = {(char *) SESSION_LIMIT_CHECK_PATH, (char *) "--authenticate", NULL};
    pid_t child, waited;
    int status;
    if (asprintf(&user_environment, "PAM_USER=%s", username) < 0 ||
        asprintf(&service_environment, "PAM_SERVICE=%s", service) < 0) {
        free(user_environment); free(service_environment);
        return PAM_BUF_ERR;
    }
    environment[0] = user_environment;
    environment[1] = service_environment;
    environment[2] = (char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin";
    child = fork();
    if (child == 0) {
        int null_fd = open("/dev/null", O_RDWR | O_CLOEXEC);
        if (null_fd >= 0) {
            (void) dup2(null_fd, STDIN_FILENO);
            (void) dup2(null_fd, STDOUT_FILENO);
            (void) dup2(null_fd, STDERR_FILENO);
            if (null_fd > STDERR_FILENO) close(null_fd);
        }
        execve(SESSION_LIMIT_CHECK_PATH, arguments, environment);
        _exit(127);
    }
    free(user_environment); free(service_environment);
    if (child < 0) return PAM_SYSTEM_ERR;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited < 0 || !WIFEXITED(status)) return PAM_SYSTEM_ERR;
    if (WEXITSTATUS(status) == 0) return PAM_SUCCESS;
    if (WEXITSTATUS(status) == 1) return PAM_ACCT_EXPIRED;
    return PAM_SYSTEM_ERR;
}

PAM_EXTERN int
pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const char *username = NULL, *service = NULL;
    (void) flags; (void) argv;
    if (argc != 0) return PAM_SERVICE_ERR;
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL || *username == '\0')
        return PAM_USER_UNKNOWN;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **) &service) != PAM_SUCCESS || service == NULL || *service == '\0')
        return PAM_SERVICE_ERR;
    return run_session_limit_check(username, service);
}

PAM_EXTERN int
pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void) pamh; (void) flags; (void) argv;
    return argc == 0 ? PAM_SUCCESS : PAM_SERVICE_ERR;
}

PAM_EXTERN int
pam_sm_open_session(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const char *user = NULL, *service = NULL;
    const void *checked = NULL;
    int result;
    (void) flags;
    if (argc != 1 || strcmp(argv[0], "kiosk") != 0) return PAM_SERVICE_ERR;
    result = kiosk_identity(pamh, &user, &service);
    if (result != PAM_SUCCESS) return result == PAM_IGNORE ? PAM_SUCCESS : PAM_SESSION_ERR;
    if (strcmp(service, "systemd-user") == 0) return PAM_SUCCESS;
    if (pam_get_data(pamh, ACCOUNT_DATA, &checked) != PAM_SUCCESS || checked == NULL ||
        strcmp(checked, "allowed") != 0) return PAM_SESSION_ERR;
    result = run_kiosk_check(pamh, user, service, "--kiosk-session", pam_getenv(pamh, "XDG_SESSION_TYPE"));
    return result == PAM_SUCCESS ? PAM_SUCCESS : PAM_SESSION_ERR;
}

PAM_EXTERN int
pam_sm_close_session(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void) pamh; (void) flags;
    /* Retain the removal lease until pam_end, including the root executor. */
    return argc == 1 && strcmp(argv[0], "kiosk") == 0 ? PAM_SUCCESS : PAM_SERVICE_ERR;
}
