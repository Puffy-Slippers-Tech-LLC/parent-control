/* Attempt-only gate for Ubuntu's Malcontent 0.14 timer daemon.
 * The store code is linked into the executable. Interpose its GLib calls,
 * holding a genuine QueryUsage transaction without blocking the main loop.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

/* The host builder only needs a C compiler. These are public GLib/GIO ABI
 * declarations, with no dependency on the daemon's private struct layout.
 */
typedef struct GDBusConnection Connection;
typedef struct GDBusMethodInvocation Invocation;
typedef struct GDBusMessage Message;
typedef struct GVariant Variant;
typedef struct GHashTable HashTable;
typedef struct GTask Task;
typedef struct GError Error;
typedef struct {
    int ref_count;
    char *name;
} InterfaceInfo;
typedef void (*Method)(Connection *, const char *, const char *, const char *,
                       const char *, Variant *, Invocation *, void *);
typedef struct {
    Method method;
    void (*get_property)(void);
    void (*set_property)(void);
    void *padding[8];
} VTable;
extern Message *g_dbus_method_invocation_get_message(Invocation *);
extern const char *g_dbus_method_invocation_get_sender(Invocation *);
extern const char *g_dbus_method_invocation_get_method_name(Invocation *);
extern const char *g_dbus_method_invocation_get_interface_name(Invocation *);
extern const char *g_dbus_method_invocation_get_object_path(Invocation *);
extern Connection *g_dbus_method_invocation_get_connection(Invocation *);
extern Variant *g_dbus_method_invocation_get_parameters(Invocation *);
extern void *g_dbus_method_invocation_get_user_data(Invocation *);
extern const char *g_dbus_message_get_destination(Message *);
extern unsigned g_dbus_message_get_serial(Message *);
extern Variant *g_variant_ref(Variant *);
extern void g_variant_unref(Variant *);
extern int g_variant_equal(Variant *, Variant *);
extern void g_object_weak_ref(void *, void (*)(void *, void *), void *);
extern const char *g_task_get_name(Task *);
extern int g_hash_table_contains(HashTable *, const void *);
extern unsigned g_timeout_add(unsigned, int (*)(void *), void *);
extern unsigned g_unix_fd_add(int, unsigned, int (*)(int, unsigned, void *), void *);
extern int g_source_remove(unsigned);

#define TIMER "org.freedesktop.MalcontentTimer1"
#define CHILD TIMER ".Child"
#define PARENT TIMER ".Parent"
#define NEXT(symbol) __typeof__(&symbol) real = dlsym(RTLD_NEXT, #symbol)

static Method child_method, parent_method;
static int control = -1;
static unsigned watchdog, drain;
static char shells[512], reader[32];
static char target_sender[32];
/* Senders whose latest usage read completed before any later direct write. */
static char ready[16][32];
static bool armed, used, released, retry_started;
static atomic_uint in_flight;
static Invocation *target, *held_read, *reader_call;
static Variant *target_payload, *held_reply;
static Invocation *parked[64];
static size_t parked_count;

/* The timer opens, reads and rolls back in one main-context callback.
 * Only that thread can associate the returned key with its table removal.
 */
static _Thread_local bool capture_read;
static _Thread_local const void *transaction;
static _Thread_local HashTable *held_table;

int g_hash_table_remove(HashTable *table, const void *key);
void g_dbus_method_invocation_return_value(Invocation *invocation, Variant *reply);

static void notify(const char *event, Invocation *call)
{
    char packet[80];
    unsigned serial = call ?
        g_dbus_message_get_serial(g_dbus_method_invocation_get_message(call)) : 0;
    int size = snprintf(packet, sizeof packet, "%s %u %s", event, serial,
                        call ? g_dbus_method_invocation_get_sender(call) : "-");
    (void)send(control, packet, size, MSG_DONTWAIT | MSG_NOSIGNAL);
}

static bool named(const char *name, const char *expected)
{
    return name && strcmp(name, expected) == 0;
}

static bool direct_write(Invocation *call)
{
    return named(g_dbus_method_invocation_get_interface_name(call), CHILD) &&
        named(g_dbus_method_invocation_get_method_name(call), "RecordUsage") &&
        named(g_dbus_message_get_destination(g_dbus_method_invocation_get_message(call)), TIMER);
}

static bool shell_sender(const char *sender)
{
    char token[34];
    int length = snprintf(token, sizeof token, ",%s,", sender);
    return length > 0 && (size_t)length < sizeof token && strstr(shells, token);
}

static bool exact_retry(Invocation *call)
{
    return direct_write(call) &&
        named(g_dbus_method_invocation_get_sender(call), target_sender) &&
        g_variant_equal(g_dbus_method_invocation_get_parameters(call), target_payload);
}

static char *ready_slot(const char *sender, bool create)
{
    char *free_slot = NULL;
    for (size_t i = 0; i < sizeof ready / sizeof ready[0]; ++i) {
        if (named(ready[i], sender))
            return ready[i];
        if (!ready[i][0] && !free_slot)
            free_slot = ready[i];
    }
    return create ? free_slot : NULL;
}

static void mark_ready(const char *sender)
{
    char *slot = sender && strlen(sender) < sizeof ready[0] ? ready_slot(sender, true) : NULL;
    if (slot)
        snprintf(slot, sizeof ready[0], "%s", sender);
    else
        notify("ready-full", NULL);
}

static bool take_ready(const char *sender)
{
    char *slot = sender ? ready_slot(sender, false) : NULL;
    if (slot)
        slot[0] = '\0';
    return slot != NULL;
}

static void completed(void *unused, void *call)
{
    (void)unused;
    (void)call;
    --in_flight;
}

static void track(Invocation *call)
{
    ++in_flight;
    g_object_weak_ref(call, completed, NULL);
}

static void dispatch(Invocation *call)
{
    const char *interface = g_dbus_method_invocation_get_interface_name(call);
    Method method = named(interface, CHILD) ? child_method : parent_method;
    track(call);
    method(g_dbus_method_invocation_get_connection(call),
           g_dbus_method_invocation_get_sender(call),
           g_dbus_method_invocation_get_object_path(call), interface,
           g_dbus_method_invocation_get_method_name(call),
           g_dbus_method_invocation_get_parameters(call), call,
           g_dbus_method_invocation_get_user_data(call));
}

static int announce_drained(void *unused)
{
    (void)unused;
    if (in_flight)
        return 1;
    drain = 0;
    notify("gated", target);
    return 0;
}

static void close_read(void)
{
    capture_read = false;
    reader_call = NULL;
    if (held_table) {
        NEXT(g_hash_table_remove);
        real(held_table, transaction);
        held_table = NULL;
    }
    transaction = NULL;
    if (held_read) {
        NEXT(g_dbus_method_invocation_return_value);
        real(held_read, held_reply);
        held_read = NULL;
    }
}

static void clear_gate(void)
{
    armed = false;
    if (watchdog) {
        g_source_remove(watchdog);
        watchdog = 0;
    }
    if (drain) {
        g_source_remove(drain);
        drain = 0;
    }
    close_read();
    if (target) {
        dispatch(target);
        target = NULL;
    }
    for (size_t i = 0; i < parked_count; ++i)
        dispatch(parked[i]);
    parked_count = 0;
    if (target_payload) {
        g_variant_unref(target_payload);
        target_payload = NULL;
    }
}

static int expired(void *unused)
{
    (void)unused;
    watchdog = 0;
    notify("expired", NULL);
    clear_gate();
    return 0;
}

static void set_watchdog(unsigned milliseconds)
{
    if (watchdog)
        g_source_remove(watchdog);
    watchdog = g_timeout_add(milliseconds, expired, NULL);
}

static int command(int fd, unsigned condition, void *unused)
{
    (void)condition;
    (void)unused;
    char packet[576] = {0};
    ssize_t size = recv(fd, packet, sizeof packet - 1, MSG_DONTWAIT);
    if (size <= 0) {
        clear_gate();
        close(control);
        control = -1;
        return 0;
    }
    if (!used && sscanf(packet, "arm %31s %511s", reader, shells) == 2) {
        used = armed = true;
        set_watchdog(30000);
        notify("armed", NULL);
    } else if (named(packet, "write") && target && held_read) {
        Invocation *call = target;
        target = NULL;
        dispatch(call);
    } else if (named(packet, "release") && !target && held_read) {
        close_read();
        released = true;
        set_watchdog(20000);
        notify("released", NULL);
        /* Reads and estimates waited only for the held transaction; the
         * client's shared queue must not stall behind them. Writes stay
         * parked so no other save can mask recovery, except the first exact
         * retry, which may have arrived before the observer saw Busy.
         */
        size_t kept = 0;
        for (size_t i = 0; i < parked_count; ++i) {
            Invocation *call = parked[i];
            bool write = named(g_dbus_method_invocation_get_method_name(call), "RecordUsage");
            if (write && !retry_started && exact_retry(call))
                retry_started = true;
            else if (write) {
                parked[kept++] = call;
                continue;
            }
            dispatch(call);
        }
        parked_count = kept;
    } else if (named(packet, "finish") && released && armed) {
        clear_gate();
        notify("finished", NULL);
    } else {
        notify("unexpected-command", NULL);
        clear_gate();
    }
    return 1;
}

static void gate_method(Method original, Connection *connection, const char *sender,
                        const char *path, const char *interface, const char *method,
                        Variant *parameters, Invocation *call, void *data)
{
    bool write = named(interface, CHILD) && named(method, "RecordUsage");
    bool query = named(interface, PARENT) && named(method, "QueryUsage");
    bool store = write || query || (named(interface, CHILD) && named(method, "GetEstimatedTimes"));
    /* GNOME's native writer shares the Shell connection. The extension's
     * checkpoint is a direct write after its own usage read returned.
     */
    bool qualified = write && direct_write(call) && take_ready(sender);
    if (armed && qualified && !target_payload && shell_sender(sender)) {
        snprintf(target_sender, sizeof target_sender, "%s", sender);
        target = call;
        target_payload = g_variant_ref(parameters);
        if (announce_drained(NULL))
            drain = g_timeout_add(20, announce_drained, NULL);
        return;
    }
    if (armed && target_payload && query && named(sender, reader) && !drain) {
        if (target && !reader_call) {
            capture_read = true;
            reader_call = call;
        }
        dispatch(call);
        return;
    }
    if (armed && released && !retry_started && write && exact_retry(call)) {
        retry_started = true;
        dispatch(call);
        return;
    }
    if (armed && (write || (target_payload && store && !released))) {
        if (parked_count < sizeof parked / sizeof parked[0]) {
            parked[parked_count++] = call;
            return;
        }
        notify("queue-full", NULL);
        clear_gate();
    }
    if (store)
        track(call);
    original(connection, sender, path, interface, method, parameters, call, data);
}

static void gate_child(Connection *connection, const char *sender, const char *path,
                       const char *interface, const char *method, Variant *parameters,
                       Invocation *call, void *data)
{
    gate_method(child_method, connection, sender, path, interface, method, parameters, call, data);
}

static void gate_parent(Connection *connection, const char *sender, const char *path,
                        const char *interface, const char *method, Variant *parameters,
                        Invocation *call, void *data)
{
    gate_method(parent_method, connection, sender, path, interface, method, parameters, call, data);
}

unsigned g_dbus_connection_register_object(Connection *connection, const char *path,
                                            InterfaceInfo *info, const VTable *table,
                                            void *data, void (*destroy)(void *), Error **error)
{
    NEXT(g_dbus_connection_register_object);
    const char *socket_path = getenv("ONPC_CHECKPOINT_SOCKET");
    VTable gated = *table;
    if (socket_path && named(info->name, CHILD)) {
        struct sockaddr_un address = {.sun_family = AF_UNIX};
        if (control != -1 || strlen(socket_path) >= sizeof address.sun_path)
            abort();
        strcpy(address.sun_path, socket_path);
        control = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
        if (control < 0 || connect(control, (struct sockaddr *)&address, sizeof address) != 0)
            abort();
        g_unix_fd_add(control, 1 | 16 | 8, command, NULL); /* G_IO_IN | G_IO_HUP | G_IO_ERR */
        child_method = table->method;
        gated.method = gate_child;
    } else if (socket_path && named(info->name, PARENT)) {
        parent_method = table->method;
        gated.method = gate_parent;
    } else {
        return real(connection, path, info, table, data, destroy, error);
    }
    return real(connection, path, info, &gated, data, destroy, error);
}

void *g_task_propagate_pointer(Task *task, Error **error)
{
    NEXT(g_task_propagate_pointer);
    void *result = real(task, error);
    if (capture_read && result && named(g_task_get_name(task), "mct_timer_store_open_username_async"))
        transaction = result;
    return result;
}

int g_hash_table_remove(HashTable *table, const void *key)
{
    NEXT(g_hash_table_remove);
    if (transaction && key == transaction && !held_table && g_hash_table_contains(table, key)) {
        held_table = table;
        return 1;
    }
    return real(table, key);
}

void g_dbus_method_invocation_return_value(Invocation *call, Variant *reply)
{
    NEXT(g_dbus_method_invocation_return_value);
    if (named(g_dbus_method_invocation_get_interface_name(call), PARENT) &&
        named(g_dbus_method_invocation_get_method_name(call), "QueryUsage"))
        mark_ready(g_dbus_method_invocation_get_sender(call));
    if (capture_read && call == reader_call) {
        capture_read = false;
        if (held_table) {
            held_read = call;
            held_reply = reply;
            set_watchdog(8000);
            notify("held", call);
            return;
        }
        transaction = NULL;
    }
    real(call, reply);
}
