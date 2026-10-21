#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pwd.h>

/* Fixed feature commands: neither arguments nor kiosk startup environment can
 * select another command, interpreter or user plugin. */
#ifndef KIOSK_LAUNCH_ROLE
#error "KIOSK_LAUNCH_ROLE must select a feature command"
#endif

int
main(int argc, char **argv)
{
    static const char *const names[] = {
        "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE",
        "LC_MESSAGES", "LC_TIME", "LC_NUMERIC", "LC_COLLATE", "LC_MONETARY",
        "DISPLAY", "WAYLAND_DISPLAY", "WAYLAND_SOCKET", "XAUTHORITY", "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_ID", "XDG_SEAT", "XDG_VTNR",
        "NOTIFY_SOCKET", "LISTEN_FDS", "LISTEN_PID", "LISTEN_FDNAMES",
        "INVOCATION_ID", "JOURNAL_STREAM",
        "XDG_SESSION_TYPE", "XDG_SESSION_CLASS", "XDG_SESSION_DESKTOP", "XDG_CURRENT_DESKTOP",
        NULL
    };
    char *values[sizeof(names) / sizeof(names[0])] = {0};
    char *const wellbeing[] = {"/usr/bin/gjs", "-m",
        "/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/wellbeingService.js", NULL};
    char *const packages[] = {"/usr/bin/rpm",
        "--rcfile", "/usr/lib/rpm/rpmrc:/etc/rpmrc",
        "--macros", "/usr/lib/rpm/macros:/usr/lib/rpm/macros.d/macros.*:/etc/rpm/macros.*:/etc/rpm/macros",
        "--query", "--queryformat", "%{NAME}\t%{VERSION}\t%{ARCH}\n", "--",
        "accountsservice", "fapolicyd", "gdm", "gnome-kiosk", "gnome-shell", "gjs",
        "malcontent", "polkit", "systemd", "dbus", "glib2", "gtk4", "libadwaita",
        "webkitgtk6.0", "malcontent-libs", "malcontent-pam", "python3",
        "python3-gobject", "python3-requests", "dconf", NULL};
    char *const *arguments = NULL;
    size_t i;
    (void) argv;
    if (argc != 1)
        goto failed;
    if (strcmp(KIOSK_LAUNCH_ROLE, "wellbeing") == 0)
        arguments = wellbeing;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "packages") == 0)
        arguments = packages;
    else
        goto failed;
    if (arguments == wellbeing) {
        struct passwd *account = getpwnam("oh-no-parent-control");
        /* Shared user units and D-Bus activation must keep the ordinary
         * user's settings backend and configuration environment. Only the
         * package kiosk identity needs the restricted startup environment. */
        if (account == NULL)
            goto failed;
        if (account->pw_uid != getuid()) {
            execv(arguments[0], arguments);
            goto failed;
        }
    }
    for (i = 0; names[i] != NULL; i++) {
        const char *value = getenv(names[i]);
        if (value != NULL && (values[i] = strdup(value)) == NULL)
            goto failed;
    }
    if (clearenv() != 0)
        goto failed;
    for (i = 0; names[i] != NULL; i++) {
        if (values[i] != NULL && setenv(names[i], values[i], 1) != 0)
            goto failed;
        free(values[i]);
        values[i] = NULL;
    }
    if (setenv("PATH", "/usr/bin:/bin", 1) != 0 ||
        setenv("SHELL", "/usr/sbin/nologin", 1) != 0 ||
        setenv("GIO_USE_VFS", "local", 1) != 0 ||
        setenv("XDG_CONFIG_DIRS", "/etc/xdg", 1) != 0 ||
        setenv("XDG_DATA_DIRS", "/usr/local/share:/usr/share", 1) != 0)
        goto failed;
    if (arguments == packages && setenv("HOME", "/", 1) != 0)
        goto failed;
    execv(arguments[0], arguments);
failed:
    for (i = 0; names[i] != NULL; i++)
        free(values[i]);
    fputs("onpc.kiosk session startup outcome=failed\n", stderr);
    return EXIT_FAILURE;
}
