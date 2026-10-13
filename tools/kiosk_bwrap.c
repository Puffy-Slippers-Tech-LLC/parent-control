#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

#define NATIVE_BWRAP "/usr/libexec/oh-no-parent-control-kiosk-bwrap"

/* In the admitted private /usr, /usr/bin/bwrap is this launcher and
 * NATIVE_BWRAP is the independently pinned distribution bubblewrap. Bind the
 * immutable executable directory before WebKit's individual proxy bind, so
 * bubblewrap need not create a writable executable-path placeholder. Keep all
 * caller arguments, inherited descriptors and native sandboxing unchanged. */
int
main(int argc, char **argv)
{
    struct stat self, native;
    char **arguments = NULL;
    if (stat("/proc/self/exe", &self) != 0 || stat(NATIVE_BWRAP, &native) != 0 ||
        (self.st_dev == native.st_dev && self.st_ino == native.st_ino))
        goto failed;
    arguments = calloc((size_t) argc + 4, sizeof(*arguments));
    if (arguments == NULL)
        goto failed;
    arguments[0] = NATIVE_BWRAP;
    arguments[1] = "--ro-bind";
    arguments[2] = "/usr/bin";
    arguments[3] = "/usr/bin";
    for (int i = 1; i < argc; i++)
        arguments[i + 3] = argv[i];
    execv(NATIVE_BWRAP, arguments);
failed:
    free(arguments);
    fputs("onpc.kiosk sandbox startup outcome=failed\n", stderr);
    return EXIT_FAILURE;
}
