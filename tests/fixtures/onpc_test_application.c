/*
 * Identity-preserving GUI owner for application catalog and enforcement tests.
 * The separately built mechanical variant and --stay-alive mode report only
 * a fixed readiness marker. GUI variants expose synthetic activity via AT-SPI.
 */
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <sys/wait.h>

#ifndef FIXTURE_KIND
#define FIXTURE_KIND "native"
#endif
#ifndef FIXTURE_GUI_DEFAULT
#define FIXTURE_GUI_DEFAULT 1
#endif

static volatile sig_atomic_t termination_signal = 0;

static void
stop(int signal_number)
{
    termination_signal = signal_number;
}

int
main(int argc, char **argv)
{
    struct sigaction action = {0};
    const struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
    int stay_alive = 0;
    const char *instance = "primary";

    for (int index = 1; index < argc; index++) {
        if (strcmp(argv[index], "--stay-alive") == 0) {
            stay_alive = 1;
        } else if (strcmp(argv[index], "--instance") == 0 && index + 1 < argc &&
                   (strcmp(argv[index + 1], "primary") == 0 || strcmp(argv[index + 1], "secondary") == 0)) {
            instance = argv[++index];
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

    if (!stay_alive && FIXTURE_GUI_DEFAULT) {
        char script[4096];
        ssize_t length = readlink("/proc/self/exe", script, sizeof(script) - 1);
        if (length < 0 || (size_t)length >= sizeof(script) - 1) {
            fprintf(stderr, "onpc-test-application: executable location unavailable\n");
            return 1;
        }
        script[length] = '\0';
        char *name = strrchr(script, '/');
        if (name == NULL || (size_t)(name - script) + sizeof("/onpc-test-gui.py") > sizeof(script)) {
            return 1;
        }
        strcpy(name, "/onpc-test-gui.py");
        /* Retain this executable's native policy identity while the GUI runs.
         * Signal only our unreaped child; death of this owner also closes it. */
        pid_t owner = getpid();
        pid_t child = fork();
        if (child < 0) return 1;
        if (child == 0) {
            action.sa_handler = SIG_DFL;
            if (sigaction(SIGTERM, &action, NULL) != 0 ||
                    sigaction(SIGINT, &action, NULL) != 0 ||
                    prctl(PR_SET_PDEATHSIG, SIGTERM) != 0 || getppid() != owner) {
                _exit(1);
            }
            execl("/usr/bin/python3", "python3", "-B", script, "--kind", FIXTURE_KIND,
                  "--instance", instance, (char *)NULL);
            _exit(1);
        }
        int status;
        int termination_sent = 0;
        for (;;) {
            pid_t result = waitpid(child, &status, WNOHANG);
            if (result == child) {
                if (WIFEXITED(status)) return WEXITSTATUS(status);
                if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
                return 1;
            }
            if (result < 0 && errno != EINTR) return 1;
            /* Check for exit before signalling, and signal only once.  Until
             * waitpid reaps it, this exact child PID cannot be reused. */
            if (termination_signal != 0 && !termination_sent) {
                if (kill(child, termination_signal) != 0 && errno != ESRCH) return 1;
                termination_sent = 1;
            }
            if (nanosleep(&pause, NULL) != 0 && errno != EINTR) return 1;
        }
    }

    puts("ONPC_TEST_APPLICATION_READY");
    fflush(stdout);
    while (stay_alive && termination_signal == 0) {
        if (nanosleep(&pause, NULL) != 0 && errno != EINTR) {
            fprintf(stderr, "onpc-test-application: wait failed\n");
            return 1;
        }
    }
    return 0;
}
