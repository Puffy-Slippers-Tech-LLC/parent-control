#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pwd.h>

/* A fixed command boundary: neither arguments nor startup environment can
 * select another session, a login shell, an interpreter or a user plugin. */
#ifndef GNOME_SESSION_PATH
#define GNOME_SESSION_PATH "/usr/bin/gnome-session"
#endif
#ifndef KIOSK_LAUNCH_ROLE
#define KIOSK_LAUNCH_ROLE "session"
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
        "INVOCATION_ID", "JOURNAL_STREAM", "SERVICE_RESULT",
        "XDG_SESSION_TYPE", "XDG_SESSION_CLASS", "XDG_SESSION_DESKTOP", "XDG_CURRENT_DESKTOP",
        NULL
    };
    char *values[sizeof(names) / sizeof(names[0])] = {0};
    char *const session[] = {
        (char *) GNOME_SESSION_PATH, (char *) "--no-reexec",
        (char *) "--session=oh-no-parent-control", NULL
    };
    char *const app[] = {"/usr/bin/python3", "-I", "/usr/bin/oh-no-parent-control", NULL};
    char *const notifications[] = {"/usr/bin/python3", "-I",
        "/usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/notifications.py", NULL};
    char *const notification_client[] = {"/usr/bin/python3", "-I", "/usr/bin/gnome-service-client",
        "--tag=gnome-kiosk-notification", "/usr/libexec/oh-no-parent-control-kiosk-notifications", NULL};
    char *const wellbeing[] = {"/usr/bin/gjs", "-m",
        "/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/wellbeingService.js", NULL};
    char *const cleanup[] = {"/usr/bin/systemctl", "--user", "unset-environment",
        "GNOME_SETUP_DISPLAY", "WAYLAND_DISPLAY", "DISPLAY", "XAUTHORITY", NULL};
    char *const audio[] = {"/usr/bin/wireplumber", NULL};
    char *const dbus[] = {"/usr/bin/dbus-broker-launch", "--scope", "user", NULL};
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
    if (strcmp(KIOSK_LAUNCH_ROLE, "session") == 0)
        arguments = session;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "app") == 0)
        arguments = app;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "notifications") == 0)
        arguments = notifications;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "notification-client") == 0)
        arguments = notification_client;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "wellbeing") == 0)
        arguments = wellbeing;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "cleanup") == 0)
        arguments = cleanup;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "packages") == 0)
        arguments = packages;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "dbus") == 0)
        /* The transition into this native wrapper enables AT_SECURE. After
         * clearing startup configuration, same-domain exec lets sd-bus read
         * XDG_RUNTIME_DIR without granting SELinux noatsecure to any route. */
        arguments = dbus;
    else if (strcmp(KIOSK_LAUNCH_ROLE, "audio") == 0)
        arguments = audio;
    else
        goto failed;
    if (arguments == audio || arguments == wellbeing) {
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
    if (arguments == session && (
        setenv("XDG_SESSION_TYPE", "wayland", 1) != 0 ||
        setenv("XDG_SESSION_CLASS", "user", 1) != 0 ||
        setenv("XDG_SESSION_DESKTOP", "oh-no-parent-control", 1) != 0 ||
        setenv("XDG_CURRENT_DESKTOP", "GNOME-Kiosk:GNOME", 1) != 0))
        goto failed;
    if (arguments == audio && (
        setenv("WIREPLUMBER_CONFIG_DIR", "/etc/wireplumber:/usr/share/wireplumber", 1) != 0 ||
        setenv("WIREPLUMBER_DATA_DIR", "/usr/share/wireplumber", 1) != 0 ||
        /* WirePlumber adds its trusted Lua searcher without removing Lua's
         * defaults. Empty paths disable the default cwd/native searches;
         * unset paths would restore them. clearenv removed versioned overrides. */
        setenv("LUA_PATH", "", 1) != 0 || setenv("LUA_CPATH", "", 1) != 0))
        goto failed;
    if (arguments == packages && setenv("HOME", "/", 1) != 0)
        goto failed;
    if (arguments == cleanup && getenv("SERVICE_RESULT") != NULL &&
        strcmp(getenv("SERVICE_RESULT"), "exec-condition") == 0)
        return EXIT_SUCCESS;
    execv(arguments[0], arguments);
failed:
    for (i = 0; names[i] != NULL; i++)
        free(values[i]);
    fputs("onpc.kiosk session startup outcome=failed\n", stderr);
    return EXIT_FAILURE;
}
