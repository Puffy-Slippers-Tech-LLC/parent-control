#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int
main(void)
{
    const struct passwd *station = getpwnam("oh-no-parent-control");

    /* GDM offers the same session list to every user. Exit before GNOME
     * Session starts so GDM can return an ordinary user to the greeter. */
    if (station == NULL || station->pw_uid == 0 || station->pw_uid != getuid()) {
        fputs("onpc.kiosk entry outcome=denied reason=station-identity\n", stderr);
        return EXIT_FAILURE;
    }

    char *const args[] = {"/usr/bin/gnome-session", "--session", "oh-no-parent-control", NULL};
    execv(args[0], args);
    fputs("onpc.kiosk entry outcome=failed reason=session-exec\n", stderr);
    return EXIT_FAILURE;
}
