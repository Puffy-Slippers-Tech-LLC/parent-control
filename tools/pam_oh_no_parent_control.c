#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <security/pam_appl.h>
#include <security/pam_modules.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
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
