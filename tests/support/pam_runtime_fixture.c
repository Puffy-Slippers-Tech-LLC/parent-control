/* Private PAM-stack fixture: no system services, accounts or session scopes. */
#define _GNU_SOURCE
#include <security/pam_modules.h>
#include <stdlib.h>
#include <string.h>

static void cleanup(pam_handle_t *pamh, void *data, int status)
{
    (void) pamh;
    (void) status;
    free(data);
}

static int store(pam_handle_t *pamh, const char *key, const char *value)
{
    char *copy = strdup(value);
    int result;
    if (!copy)
        return PAM_BUF_ERR;
    result = pam_set_data(pamh, key, copy, cleanup);
    if (result != PAM_SUCCESS)
        free(copy);
    return result;
}

PAM_EXTERN int pam_sm_acct_mgmt(pam_handle_t *pamh, int flags,
                              int argc, const char **argv)
{
    int result = PAM_SUCCESS;
    (void) flags;
    for (int i = 0; i < argc; i++) {
        if (strncmp(argv[i], "seed=", 5) == 0) {
            result = store(pamh, "systemd.runtime_max_sec", argv[i] + 5);
            if (result != PAM_SUCCESS)
                return result;
        } else if (strcmp(argv[i], "memory") == 0) {
            result = store(pamh, "systemd.memory_max", "200M");
            if (result != PAM_SUCCESS)
                return result;
        } else if (strcmp(argv[i], "ignore") == 0) {
            result = PAM_IGNORE;
        } else if (strcmp(argv[i], "expired") == 0) {
            result = PAM_ACCT_EXPIRED;
        } else if (strcmp(argv[i], "error") == 0) {
            result = PAM_SYSTEM_ERR;
        } else if (strcmp(argv[i], "success") != 0) {
            return PAM_SERVICE_ERR;
        }
    }
    return result;
}

PAM_EXTERN int pam_sm_open_session(pam_handle_t *pamh, int flags,
                                 int argc, const char **argv)
{
    const void *value = NULL;
    int result;
    (void) flags;
    if (argc != 1)
        return PAM_SERVICE_ERR;
    result = pam_get_data(pamh, "systemd.memory_max", &value);
    if (result != PAM_SUCCESS || !value || strcmp(value, "200M") != 0)
        return PAM_SESSION_ERR;
    result = pam_get_data(pamh, "systemd.runtime_max_sec", &value);
    if (strcmp(argv[0], "absent") == 0)
        return result == PAM_NO_MODULE_DATA ? PAM_SUCCESS : PAM_SESSION_ERR;
    if (result != PAM_SUCCESS || !value || strcmp(value, argv[0]) != 0)
        return PAM_SESSION_ERR;
    return PAM_SUCCESS;
}

PAM_EXTERN int pam_sm_close_session(pam_handle_t *pamh, int flags,
                                  int argc, const char **argv)
{
    (void) pamh;
    (void) flags;
    (void) argc;
    (void) argv;
    return PAM_SUCCESS;
}
