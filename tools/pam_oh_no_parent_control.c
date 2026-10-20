#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <security/pam_ext.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <syslog.h>
#include <time.h>
#include <unistd.h>

/*
 * Translate the fixed-purpose policy helper's result into a PAM status which
 * GDM can explain accurately. The policy and system-bus work stay in the
 * separately testable helper; this module owns PAM transaction state, locking,
 * bounded execution and the PAM status contract.
 */
#ifndef SESSION_LIMIT_CHECK_PATH
#define SESSION_LIMIT_CHECK_PATH \
    "/usr/libexec/oh-no-parent-control-session-limit-check"
#endif

#ifndef LOGIN_CHECK_PATH
#define LOGIN_CHECK_PATH "/usr/libexec/oh-no-parent-control-login-check"
#endif
#ifndef KIOSK_ACCOUNT_NAME
#define KIOSK_ACCOUNT_NAME "oh-no-parent-control"
#endif
#ifndef KIOSK_LOGIN_LOCK_PATH
#define KIOSK_LOGIN_LOCK_PATH "/run/oh-no-parent-control-kiosk-login.lock"
#endif
#ifndef KIOSK_LOGIN_LOCK_OWNER
#define KIOSK_LOGIN_LOCK_OWNER 0
#endif
#ifndef KIOSK_LOGIN_TIMEOUT_SECONDS
#define KIOSK_LOGIN_TIMEOUT_SECONDS 25
#endif

#define KIOSK_LOGIN_DATA "oh-no-parent-control.kiosk-login"

#include "kiosk_confinement.h"

struct kiosk_login {
    int fd;
    int account_result;
};

static void
release_kiosk_login(pam_handle_t *pamh, void *data, int status)
{
    struct kiosk_login *login = data;
    (void) pamh;
    (void) status;
    if (login->fd >= 0)
        close(login->fd);
    free(login);
}

/* Nonstation accounts never acquire a lock or query another account. */
static int
kiosk_identity(pam_handle_t *pamh, const char **username, const char **service)
{
    int result = pam_get_user(pamh, username, NULL);
    if (result != PAM_SUCCESS || *username == NULL)
        return PAM_USER_UNKNOWN;
    if (strcmp(*username, KIOSK_ACCOUNT_NAME) != 0)
        return PAM_IGNORE;
    result = pam_get_item(pamh, PAM_SERVICE, (const void **) service);
    if (result != PAM_SUCCESS || *service == NULL)
        return PAM_SERVICE_ERR;
    if (strcmp(*service, "systemd-user") == 0)
        return PAM_IGNORE;
    if (strcmp(*service, "gdm-password") != 0) {
        pam_syslog(pamh, LOG_WARNING,
                   "onpc.pam kiosk confinement stage=service outcome=denied");
        return PAM_PERM_DENIED;
    }
    return PAM_SUCCESS;
}

static int
run_kiosk_check(pam_handle_t *pamh, const char *username, const char *service,
                const char *operation, const char *session_type, int lock_fd)
{
    char *user_env = NULL, *service_env = NULL, *type_env = NULL;
    char *environment[5] = {NULL, NULL, NULL, NULL, NULL};
    char *arguments[] = {(char *) LOGIN_CHECK_PATH, (char *) operation, NULL};
    struct timespec start, now, pause = {0, 10000000};
    pid_t child, waited;
    int status;
    int admission_fd = kiosk_admission_fd(pamh);
    const char *stage = strcmp(operation, "--kiosk-account") == 0 ? "account" :
        strcmp(operation, "--kiosk-integrity") == 0 ? "integrity" : "session";

    if (asprintf(&user_env, "PAM_USER=%s", username) < 0 ||
        asprintf(&service_env, "PAM_SERVICE=%s", service) < 0 ||
        asprintf(&type_env, "XDG_SESSION_TYPE=%s",
                 session_type == NULL ? "" : session_type) < 0) {
        free(user_env);
        free(service_env);
        free(type_env);
        return PAM_BUF_ERR;
    }
    environment[0] = user_env;
    environment[1] = service_env;
    environment[2] = type_env;
    environment[3] = (char *) "PATH=/usr/sbin:/usr/bin:/sbin:/bin";
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0) {
        free(user_env);
        free(service_env);
        free(type_env);
        return PAM_SYSTEM_ERR;
    }
    child = fork();
    if (child == 0) {
        int null_fd = open("/dev/null", O_RDWR | O_CLOEXEC);
        /* Keep the same lock alive if GDM aborts/kills the PAM worker while
         * its bounded helper is still mutating routing state. The helper's
         * busctl children close inherited descriptors by default. */
        /* F_DUPFD preserves it above stdio even if the worker had fd 0/1/2
         * closed when the lock was opened. The duplicate survives exec. */
        if (null_fd < 0 || (lock_fd >= 0 && fcntl(lock_fd, F_DUPFD, STDERR_FILENO + 1) < 0) ||
            (admission_fd >= 0 && fcntl(admission_fd, F_DUPFD, STDERR_FILENO + 1) < 0))
            _exit(127);
        if (dup2(null_fd, STDIN_FILENO) < 0 ||
            dup2(null_fd, STDOUT_FILENO) < 0 ||
            dup2(null_fd, STDERR_FILENO) < 0)
            _exit(127);
        if (null_fd > STDERR_FILENO)
            close(null_fd);
        execve(LOGIN_CHECK_PATH, arguments, environment);
        _exit(127);
    }
    free(user_env);
    free(service_env);
    free(type_env);
    if (child < 0)
        return PAM_SYSTEM_ERR;
    for (;;) {
        waited = waitpid(child, &status, WNOHANG);
        if (waited == child) {
            if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
                pam_syslog(pamh, LOG_ERR,
                           "onpc.pam kiosk confinement stage=%s outcome=helper-failed", stage);
            return WIFEXITED(status) && WEXITSTATUS(status) == 0
                ? PAM_SUCCESS : PAM_PERM_DENIED;
        }
        if (waited < 0 && errno != EINTR)
            return PAM_SYSTEM_ERR;
        if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
            now.tv_sec - start.tv_sec > KIOSK_LOGIN_TIMEOUT_SECONDS ||
            (now.tv_sec - start.tv_sec == KIOSK_LOGIN_TIMEOUT_SECONDS &&
             now.tv_nsec >= start.tv_nsec)) {
            /* This is our unreaped fork child; its identity cannot be reused. */
            kill(child, SIGKILL);
            do {
                waited = waitpid(child, &status, 0);
            } while (waited < 0 && errno == EINTR);
            pam_syslog(pamh, LOG_ERR,
                       "onpc.pam kiosk confinement stage=%s outcome=helper-timeout", stage);
            return PAM_SYSTEM_ERR;
        }
        nanosleep(&pause, NULL);
    }
}

static int
kiosk_account_check(pam_handle_t *pamh)
{
    const char *username = NULL, *service = NULL;
    const void *existing = NULL;
    struct kiosk_login *login;
    struct stat info;
    int result = kiosk_identity(pamh, &username, &service);
    if (username != NULL && strcmp(username, KIOSK_ACCOUNT_NAME) == 0 &&
        kiosk_admission(pamh, username) != PAM_SUCCESS)
        return PAM_PERM_DENIED;
    if (result != PAM_SUCCESS)
        return result == PAM_IGNORE ? PAM_SUCCESS : result;

    result = pam_get_data(pamh, KIOSK_LOGIN_DATA, &existing);
    if (result == PAM_SUCCESS && existing != NULL &&
        ((struct kiosk_login *) existing)->fd >= 0)
        return ((struct kiosk_login *) existing)->account_result;
    if (result != PAM_SUCCESS && result != PAM_NO_MODULE_DATA)
        return result;
    login = calloc(1, sizeof(*login));
    if (login == NULL)
        return PAM_BUF_ERR;
    login->account_result = PAM_SYSTEM_ERR;
    login->fd = kiosk_private_lock_open(KIOSK_LOGIN_LOCK_PATH,
                                         KIOSK_LOGIN_LOCK_OWNER, O_NONBLOCK);
    if (login->fd < 0 || fstat(login->fd, &info) != 0 ||
        !S_ISREG(info.st_mode) || info.st_uid != KIOSK_LOGIN_LOCK_OWNER ||
        (info.st_mode & 07777) != 0600 || info.st_nlink != 1) {
        release_kiosk_login(pamh, login, 0);
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk confinement stage=lock outcome=unsafe");
        return PAM_SYSTEM_ERR;
    }
    if (flock(login->fd, LOCK_EX | LOCK_NB) != 0) {
        release_kiosk_login(pamh, login, 0);
        pam_syslog(pamh, LOG_WARNING,
                   "onpc.pam kiosk confinement stage=lock outcome=busy");
        return PAM_PERM_DENIED;
    }
    if (kiosk_lock_identity(login->fd, KIOSK_LOGIN_LOCK_PATH, KIOSK_LOGIN_LOCK_OWNER) != 0) {
        release_kiosk_login(pamh, login, 0);
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk confinement stage=lock outcome=unsafe");
        return PAM_SYSTEM_ERR;
    }
    result = pam_set_data(pamh, KIOSK_LOGIN_DATA, login, release_kiosk_login);
    if (result != PAM_SUCCESS) {
        release_kiosk_login(pamh, login, 0);
        return result;
    }
    result = run_kiosk_check(pamh, username, service, "--kiosk-account", NULL, login->fd);
    login->account_result = result;
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam kiosk confinement stage=account outcome=%s status=%d",
               result == PAM_SUCCESS ? "allowed" : "denied", result);
    return result;
}

enum helper_result {
    HELPER_ALLOWED = 0,
    HELPER_DENIED = 1,
};

#define RUNTIME_MAX_DATA "systemd.runtime_max_sec"

PAM_EXTERN int
pam_sm_acct_mgmt(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const void *runtime_max = NULL;
    const char *service = NULL;
    int result;

    (void) flags;
    if (argc == 1 && strcmp(argv[0], "kiosk-integrity") == 0) {
        const char *username = NULL;
        if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL)
            return PAM_USER_UNKNOWN;
        if (strcmp(username, KIOSK_ACCOUNT_NAME) != 0)
            return PAM_SUCCESS;
        if (kiosk_admission(pamh, username) != PAM_SUCCESS)
            return PAM_PERM_DENIED;
        if (pam_get_item(pamh, PAM_SERVICE, (const void **) &service) != PAM_SUCCESS || service == NULL)
            return PAM_SERVICE_ERR;
        return run_kiosk_check(pamh, username, service, "--kiosk-integrity", NULL, -1);
    }
    if (argc == 1 && strcmp(argv[0], "kiosk") == 0)
        return kiosk_account_check(pamh);
    if (argc != 0)
        return PAM_SERVICE_ERR;

    /* Only GDM sessions have the GNOME screen-lock enforcement described below.
     * Keep Malcontent's kill timer for terminal, SSH and other PAM services. */
    result = pam_get_item(pamh, PAM_SERVICE, (const void **) &service);
    if (result != PAM_SUCCESS || service == NULL || service[0] == '\0')
        return PAM_SERVICE_ERR;
    if (strncmp(service, "gdm-", 4) != 0)
        return PAM_SUCCESS;

    /*
     * Run immediately after pam_malcontent's account check. Its login-time
     * snapshot must not become a session kill timer: expiry is a screen lock.
     * pam_systemd documents this PAM data key and consumes it when opening
     * the session. An external pam_exec helper cannot change this handle,
     * and clearing a scope after creation races a near-expired grant.
     *
     * The profile skips both modules for exempt/unrestricted accounts. This
     * never changes pam_malcontent's result or any other resource limit.
     */
    result = pam_get_data(pamh, RUNTIME_MAX_DATA, &runtime_max);
    if (result == PAM_NO_MODULE_DATA ||
        (result == PAM_SUCCESS && runtime_max == NULL))
        return PAM_SUCCESS;
    if (result != PAM_SUCCESS) {
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam session runtime cap outcome=failed stage=read status=%d",
                   result);
        return result;
    }
    if (strcmp(runtime_max, "infinity") == 0)
        return PAM_SUCCESS;

    /* pam_set_data invokes the previous owner's cleanup when replacing data. */
    result = pam_set_data(pamh, RUNTIME_MAX_DATA, (void *) "infinity", NULL);
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam session runtime cap outcome=%s stage=before-session status=%d",
               result == PAM_SUCCESS ? "cleared" : "failed", result);
    return result;
}

static int
run_session_limit_check(const char *username, const char *service)
{
    char *user_environment = NULL;
    char *service_environment = NULL;
    char *environment[4] = {NULL, NULL, NULL, NULL};
    char *arguments[] = {
        (char *) SESSION_LIMIT_CHECK_PATH,
        (char *) "--authenticate",
        NULL,
    };
    pid_t child;
    pid_t waited;
    int status;

    if (asprintf(&user_environment, "PAM_USER=%s", username) < 0 ||
        asprintf(&service_environment, "PAM_SERVICE=%s", service) < 0) {
        free(user_environment);
        free(service_environment);
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
            if (null_fd > STDERR_FILENO)
                close(null_fd);
        }
        execve(SESSION_LIMIT_CHECK_PATH, arguments, environment);
        _exit(127);
    }

    free(user_environment);
    free(service_environment);
    if (child < 0)
        return PAM_SYSTEM_ERR;

    do {
        waited = waitpid(child, &status, 0);
    } while (waited < 0 && errno == EINTR);

    if (waited < 0 || !WIFEXITED(status))
        return PAM_SYSTEM_ERR;
    if (WEXITSTATUS(status) == HELPER_ALLOWED)
        return PAM_SUCCESS;
    /* GDM has a localized, user-facing time-limit explanation for this. */
    if (WEXITSTATUS(status) == HELPER_DENIED)
        return PAM_ACCT_EXPIRED;
    /* An indeterminate policy check remains fail-closed but is not mislabeled. */
    return PAM_SYSTEM_ERR;
}

/* systemd calls setcred without authenticate. An absent auth group otherwise
 * invokes arbitrary global "other" callbacks before the session gate and again
 * in sd-pam. Only the kiosk gets this inert credential path; authentication
 * always fails, and ordinary accounts continue to the original fallback. */
static int
manager_credentials_identity(pam_handle_t *pamh)
{
    const char *username = NULL, *service = NULL;
    if (pam_get_item(pamh, PAM_SERVICE, (const void **) &service) != PAM_SUCCESS ||
            service == NULL || strcmp(service, "systemd-user") != 0)
        return PAM_SERVICE_ERR;
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL ||
            username[0] == '\0')
        return PAM_USER_UNKNOWN;
    return strcmp(username, KIOSK_ACCOUNT_NAME) == 0 ? PAM_SUCCESS : PAM_IGNORE;
}

PAM_EXTERN int
pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const char *username = NULL;
    const char *service = NULL;
    int result;

    (void) flags;
    if (argc > 0 && strcmp(argv[0], "kiosk-manager-credentials") == 0) {
        if (argc != 1)
            return PAM_SERVICE_ERR;
        result = manager_credentials_identity(pamh);
        return result == PAM_SUCCESS ? PAM_AUTH_ERR : result;
    }

    result = pam_get_user(pamh, &username, NULL);
    if (result != PAM_SUCCESS || username == NULL || username[0] == '\0')
        return PAM_USER_UNKNOWN;
    result = pam_get_item(pamh, PAM_SERVICE, (const void **) &service);
    if (result != PAM_SUCCESS || service == NULL || service[0] == '\0')
        return PAM_SERVICE_ERR;

    return run_session_limit_check(username, service);
}

PAM_EXTERN int
pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void) flags;
    if (argc > 0 && strcmp(argv[0], "kiosk-manager-credentials") == 0) {
        if (argc != 1)
            return PAM_SERVICE_ERR;
        return manager_credentials_identity(pamh);
    }
    return PAM_SUCCESS;
}

PAM_EXTERN int
pam_sm_open_session(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const char *username = NULL, *service = NULL;
    const void *data = NULL;
    struct kiosk_login *login;
    int result;
    (void) flags;
    if (argc == 1 && strcmp(argv[0], "kiosk-admission") == 0) {
        if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || username == NULL)
            return PAM_USER_UNKNOWN;
        return kiosk_admission(pamh, username);
    }
    if (argc == 1 && strcmp(argv[0], "kiosk-confinement") == 0)
        return kiosk_confinement(pamh);
    if (argc != 1 || strcmp(argv[0], "kiosk") != 0)
        return PAM_SERVICE_ERR;
    result = kiosk_identity(pamh, &username, &service);
    if (username != NULL && strcmp(username, KIOSK_ACCOUNT_NAME) == 0 &&
        kiosk_admission(pamh, username) != PAM_SUCCESS)
        return PAM_SESSION_ERR;
    if (result != PAM_SUCCESS)
        return result == PAM_IGNORE ? PAM_SUCCESS : result;
    result = pam_get_data(pamh, KIOSK_LOGIN_DATA, &data);
    if (result != PAM_SUCCESS || data == NULL ||
        ((struct kiosk_login *) data)->fd < 0 ||
        ((struct kiosk_login *) data)->account_result != PAM_SUCCESS) {
        pam_syslog(pamh, LOG_ERR,
                   "onpc.pam kiosk confinement stage=session outcome=unbound");
        return PAM_SESSION_ERR;
    }
    login = (struct kiosk_login *) data;
    /* Serialize preference checks/repair through session opening. Saved
     * settings cannot attest the command GDM will execute; the required final
     * confinement gate owns that check. XDG_SESSION_TYPE is available here,
     * while GDMSESSION only arrives after PAM session opening. */
    result = run_kiosk_check(pamh, username, service, "--kiosk-session",
                            pam_getenv(pamh, "XDG_SESSION_TYPE"), login->fd);
    close(login->fd);
    login->fd = -1;
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "onpc.pam kiosk confinement stage=session outcome=%s status=%d",
               result == PAM_SUCCESS ? "allowed" : "denied", result);
    return result == PAM_SUCCESS ? PAM_SUCCESS : PAM_SESSION_ERR;
}

PAM_EXTERN int
pam_sm_close_session(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    (void) pamh;
    (void) flags;
    return argc == 1 && (strcmp(argv[0], "kiosk") == 0 ||
                         strcmp(argv[0], "kiosk-admission") == 0 ||
                         strcmp(argv[0], "kiosk-confinement") == 0)
        ? PAM_SUCCESS : PAM_SERVICE_ERR;
}
