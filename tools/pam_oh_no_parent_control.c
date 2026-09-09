#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <security/pam_ext.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <syslog.h>
#include <unistd.h>

/*
 * Translate the fixed-purpose policy helper's result into a PAM status which
 * GDM can explain accurately. The policy and system-bus work stay in the
 * separately testable helper; this module owns only the PAM status contract.
 */
#ifndef SESSION_LIMIT_CHECK_PATH
#define SESSION_LIMIT_CHECK_PATH \
    "/usr/libexec/oh-no-parent-control-session-limit-check"
#endif

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
    (void) argc;
    (void) argv;

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
                   "session runtime cap outcome=failed stage=read status=%d",
                   result);
        return result;
    }
    if (strcmp(runtime_max, "infinity") == 0)
        return PAM_SUCCESS;

    /* pam_set_data invokes the previous owner's cleanup when replacing data. */
    result = pam_set_data(pamh, RUNTIME_MAX_DATA, (void *) "infinity", NULL);
    pam_syslog(pamh, result == PAM_SUCCESS ? LOG_INFO : LOG_ERR,
               "session runtime cap outcome=%s stage=before-session status=%d",
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

PAM_EXTERN int
pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv)
{
    const char *username = NULL;
    const char *service = NULL;
    int result;

    (void) flags;
    (void) argc;
    (void) argv;

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
    (void) pamh;
    (void) flags;
    (void) argc;
    (void) argv;
    return PAM_SUCCESS;
}
