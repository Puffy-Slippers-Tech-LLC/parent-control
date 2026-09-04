/*
 * Tiny long-running fixture for application catalog and enforcement tests.
 * It deliberately accepts no user data and reports only a fixed readiness
 * marker, so test diagnostics cannot contain PII or command-line secrets.
 */
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static volatile sig_atomic_t keep_running = 1;

static void
stop(int signal_number)
{
    (void)signal_number;
    keep_running = 0;
}

int
main(int argc, char **argv)
{
    struct sigaction action = {0};
    const struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
    int stay_alive = 0;

    for (int index = 1; index < argc; index++) {
        if (strcmp(argv[index], "--stay-alive") == 0) {
            stay_alive = 1;
        } else {
            fprintf(stderr, "onpc-test-application: unsupported fixture option\n");
            return 2;
        }
    }

    action.sa_handler = stop;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, NULL) != 0 ||
            sigaction(SIGINT, &action, NULL) != 0) {
        fprintf(stderr, "onpc-test-application: signal setup failed\n");
        return 1;
    }

    puts("ONPC_TEST_APPLICATION_READY");
    fflush(stdout);
    while (stay_alive && keep_running) {
        if (nanosleep(&pause, NULL) != 0 && errno != EINTR) {
            fprintf(stderr, "onpc-test-application: wait failed\n");
            return 1;
        }
    }
    return 0;
}
