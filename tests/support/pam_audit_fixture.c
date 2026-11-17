/* Host-safe libpam tests use private stacks, never the host audit service. */
#include <errno.h>

int audit_open(void)
{
    /* Linux-PAM preserves the module result when kernel auditing is absent. */
    errno = EPROTONOSUPPORT;
    return -1;
}
