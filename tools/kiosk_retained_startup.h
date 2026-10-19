/* Retained gate transaction in the actual PAM executor. The manager is selected
 * once; neither a helper result nor a completed record authorizes its sources.
 * Include after kiosk_fresh_startup.h and the native confinement primitives. */
#ifndef ONPC_KIOSK_RETAINED_STARTUP_H
#define ONPC_KIOSK_RETAINED_STARTUP_H
#include "kiosk_manager_admission.h"
#include "kiosk_retained_record.h"

struct kiosk_retained_startup {
    struct kiosk_fresh_startup common;
    struct kiosk_manager_proof manager;
    struct kiosk_retained_record record;
    struct kiosk_source_pin source;
    int mountinfo, marker, invocation;
};

static inline void kiosk_retained_startup_init(struct kiosk_retained_startup *g)
{
    memset(g, 0, sizeof(*g));
    kiosk_fresh_startup_init(&g->common);
    g->manager.proc = g->manager.pidfd = g->manager.root = g->manager.usr = -1;
    g->manager.executable = g->manager.marker = g->manager.mount_namespace.fd = -1;
    kiosk_retained_record_init(&g->record);
    g->source.fd = g->source.parent = g->source.worker = -1;
    g->mountinfo = g->marker = g->invocation = -1;
}

static inline void kiosk_retained_descriptors_close(struct kiosk_retained_startup *g)
{
    if (g->mountinfo >= 0) close(g->mountinfo);
    if (g->marker >= 0) close(g->marker);
    if (g->invocation >= 0) close(g->invocation);
    g->mountinfo = g->marker = g->invocation = -1;
    kiosk_retained_record_close(&g->record);
    kiosk_manager_release(&g->manager);
}

/* Only failed-attempt recovery may receive another budget. It never selects
 * another manager, rewrites a completed record or revives admission. */
static inline int kiosk_retained_recover_until(struct kiosk_retained_startup *g, uint64_t deadline)
{
    if (!g || g->common.armed || kiosk_pin_before(deadline)) return -1;
    if (g->source.worker >= 0) {
        if (kiosk_pin_reap_worker_until(g->source.worker, deadline, &g->common.cleanup_failure)) return -1;
        close(g->source.worker); g->source.worker = -1;
    }
    if (kiosk_pin_release(&g->source, 0, &g->common.cleanup_failure)) return -1;
    if (kiosk_fresh_recover_until(&g->common, deadline)) return -1;
    kiosk_retained_descriptors_close(g);
    return 0;
}

static inline int kiosk_retained_close(struct kiosk_retained_startup *g)
{
    if (!g || g->source.worker >= 0 || g->source.fd >= 0 || g->source.attached ||
        kiosk_fresh_close(&g->common)) return -1;
    kiosk_retained_descriptors_close(g);
    return 0;
}

static inline int kiosk_retained_source_check_at(struct kiosk_retained_startup *g, int source)
{
    struct kiosk_fresh_startup *s = &g->common;
    return !kiosk_retained_record_recheck_until(&g->record, g->manager.usr, g->marker,
            &s->authority, s->crypto, s->deadline) &&
        !kiosk_realization_verify_source_until(source, &g->record.receipt, &s->authority,
            KIOSK_FRESH_MARKER, g->record.inventory.entries, g->record.inventory.count,
            g->record.ambient, s->crypto, s->deadline, &s->failure) &&
        !kiosk_manager_recheck(&g->manager, &s->failure) ? 0 : -1;
}

static inline int kiosk_retained_source_check(struct kiosk_retained_startup *g)
{
    return kiosk_retained_source_check_at(g, g->source.fd);
}

/* A detached open_tree descriptor can be inspected but Linux does not permit
 * legacy recursive bind sources from it. Attach only to this invocation's
 * already-owned tmpfs, using the existing identity/read-only/topology guard.
 * The helper receives a separate empty parent; it never owns the source tree. */
static inline int kiosk_retained_staging_until(struct kiosk_retained_startup *g)
{
    struct kiosk_fresh_startup *s = &g->common;
    int placeholder = -1, result = -1;
    struct stat parent, target;
    unsigned long long parent_mount, target_mount;
    if (kiosk_pin_before(s->deadline) || mkdirat(s->view.root, "source", 0700) ||
        mkdirat(s->view.root, "invocation", 0700)) goto done;
    placeholder = openat(s->view.root, "source", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    g->invocation = openat(s->view.root, "invocation", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (placeholder < 0 || g->invocation < 0) goto done;
    if (s->view.selinux) {
        const char context[] = "system_u:object_r:onpc_kiosk_runtime_t:s0";
        if (fsetxattr(placeholder, "security.selinux", context, sizeof(context), 0) ||
            fsetxattr(g->invocation, "security.selinux", context, sizeof(context), 0)) goto done;
    }
    if (fstat(s->view.root, &parent) || fstat(placeholder, &target) ||
        !kiosk_publication_private(&parent, 1) || !kiosk_publication_private(&target, 1) ||
        kiosk_pin_fd_mount(s->view.root, &parent_mount) || kiosk_pin_fd_mount(placeholder, &target_mount) ||
        kiosk_label(g->invocation, NULL, 0, s->view.selinux)) goto done;
    struct kiosk_pin_target expected = {.parent_device = parent.st_dev, .parent_inode = parent.st_ino,
        .device = target.st_dev, .inode = target.st_ino, .parent_mount = parent_mount, .mount = target_mount};
    if (kiosk_pin_attach_policy_until(&g->source, s->view.root, "source", &expected,
            g->record.inventory.entries, g->record.inventory.count, g->record.ambient,
            s->deadline, &s->failure) || kiosk_retained_source_check(g)) goto done;
    result = 0;
done:
    if (placeholder >= 0) close(placeholder);
    return result;
}

static inline int kiosk_retained_final_proofs(struct kiosk_retained_startup *g, int lock, int lease)
{
    if (!g) return -1;
    struct kiosk_fresh_startup *s = &g->common;
    s->stage = "final-host";
    if (kiosk_fresh_runtime_current(s) ||
        kiosk_host_proof_recheck(&s->account, s->account.specs, s->account.requested) ||
        kiosk_material_verify_host_until(&s->authority, &s->host) ||
        kiosk_material_verify_routes_until(&s->authority, &s->host) ||
        kiosk_policy_recheck_until(&s->policy, s->deadline)) return -1;
    s->stage = "final-invocation";
    if (kiosk_receipt_derivation(&g->record.receipt, &s->realized.receipt, s->deadline) ||
        kiosk_fresh_marker_check(s) ||
        kiosk_pin_coverage_policy_until(s->pin.fd, s->realized.entries, s->realized.entry_count,
            NULL, 1, s->deadline, &s->failure) ||
        kiosk_pin_attached_topology_until(s->pin.fd, s->realized.entries, s->realized.entry_count,
            s->deadline, &s->failure)) return -1;
    s->stage = "final-source";
    /* Lazy staging detach removes the clone's subordinate mounts even while
     * its root FD survives. Re-prove the original manager through its already
     * pinned /usr/proc objects, never a new manager or a host ambient lookup.
     * The clone was proved before binding; strict actual I coverage above and
     * V-to-I derivation bind its required inodes to these rehashed sources. */
    unsigned long long source_mount;
    if (kiosk_pin_fd_mount(g->manager.usr, &source_mount) ||
        kiosk_pin_topology_until(g->mountinfo, source_mount, "/usr", g->record.inventory.entries,
            g->record.inventory.count, s->deadline, &s->failure) ||
        kiosk_retained_source_check_at(g, g->manager.usr) || kiosk_fresh_marker_check(s)) return -1;
    s->stage = "final-lock";
    return !kiosk_fresh_locks(lock, lease) && !kiosk_pin_before(s->deadline) ? 0 : -1;
}

static inline int kiosk_retained_startup_until(struct kiosk_retained_startup *g, pam_handle_t *pamh,
    int lock, int lease, uint64_t deadline)
{
    if (!g) return -1;
    struct kiosk_fresh_startup *s = &g->common;
    unsigned char material[32], view[32], random[32];
    struct stat runtime, named, parent, target;
    struct kiosk_pin_target destination;
    struct kiosk_owned_mount *stages = NULL;
    const char *username = NULL, *service = NULL;
    uint64_t now; int result = -1;
    if (s->attempted || s->closed || s->recovered) return -1;
    s->attempted = 1; s->deadline = deadline; s->stage = "identity";
    if (pam_get_user(pamh, &username, NULL) != PAM_SUCCESS || !username || strcmp(username, KIOSK_ACCOUNT_NAME) ||
        pam_get_item(pamh, PAM_SERVICE, (const void **)&service) != PAM_SUCCESS ||
        !service || strcmp(service, "gdm-password") || geteuid() != 0 ||
        kiosk_pin_now(&now) || deadline <= now || deadline - now > 60000000ULL ||
        kiosk_preparation_deadline_ns(deadline, &s->child.deadline_ns) || lock == lease ||
        kiosk_admission_current(lease) || flock(lease, LOCK_SH | LOCK_NB) ||
        kiosk_lock_identity(lock, KIOSK_CONFINEMENT_LOCK, 0) || flock(lock, LOCK_EX | LOCK_NB) ||
        kiosk_fresh_locks(lock, lease)) goto done;
    s->stage = "host";
    if (kiosk_host_roots_open(&s->roots) ||
        !(s->crypto = dlopen("libcrypto.so.3", RTLD_NOW | RTLD_LOCAL))) goto done;
    s->stage = "runtime";
    /* Reuse may not create, repair or adopt a replacement runtime root. */
    s->runtime = open(KIOSK_CONFINEMENT_RUNTIME, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (s->runtime < 0 || fstat(s->runtime, &runtime) || !kiosk_publication_private(&runtime, 1) ||
        lstat(KIOSK_CONFINEMENT_RUNTIME, &named) || !kiosk_pin_same_stat(&runtime, &named) ||
        setup_kiosk_view(&s->view)) goto done;
    s->stage = "host-anchor";
    if (kiosk_fresh_reanchor_until(s) || kiosk_fresh_account_until(s) || kiosk_fresh_boot_until(s)) goto done;
    s->stage = "helper-launch";
    if (kiosk_fresh_locks(lock, lease) || kiosk_preparation_launch(&s->child, "gate", lock, lease, deadline)) goto done;
    s->stage = "measurement";
    if (kiosk_preparation_child_measurement(&s->child, 2, &s->measurement) ||
        s->child.account.uid != s->uid ||
        kiosk_publication_read(s->measurement.fds[0], &s->material_bytes, &s->material_size, deadline) ||
        kiosk_publication_read(s->measurement.fds[1], &s->config_bytes, &s->config_size, deadline)) goto done;
    s->stage = "authority";
    if (kiosk_policy_acquire_until(&s->policy, &s->roots, s->config_bytes, s->config_size, s->crypto, deadline) ||
        kiosk_material_decode_until(&s->authority, s->material_bytes, s->material_size,
            s->policy.config, s->policy.config_size, s->policy.policy, s->policy.policy_size, s->crypto, deadline) ||
        strcmp(s->policy.backend, s->authority.backend) ||
        s->child.backend != (!strcmp(s->authority.backend, "apparmor") ? 1U : 2U) ||
        kiosk_fresh_hex(s->authority.digest, material) || memcmp(material, s->child.material, 32) ||
        kiosk_host_proof_capture_until(&s->host, &s->roots, s->authority.host_specs, s->authority.host_count, deadline) ||
        kiosk_material_verify_host_until(&s->authority, &s->host) || kiosk_material_verify_routes_until(&s->authority, &s->host) ||
        kiosk_gate_mac_preload(&s->mac, s->authority.backend) ||
        s->view.selinux != !strcmp(s->authority.backend, "selinux")) goto done;
    memcpy(s->material, s->authority.digest, sizeof(s->material));
    s->stage = "manager";
    if (kiosk_manager_acquire_until(&g->manager, s->child.account.uid, s->child.account.gid,
            s->child.account.groups, s->child.account.count, s->view.selinux,
            deadline, &s->failure)) goto done;
    s->stage = "completed-record";
    g->marker = kiosk_preparation_open(g->manager.usr, KIOSK_FRESH_MARKER, 1, deadline);
    if (g->marker < 0 || kiosk_retained_record_open_until(&g->record, s->runtime, g->manager.usr,
            g->marker, &s->authority, s->boot, s->crypto, deadline) ||
        kiosk_manager_select(&g->manager, g->record.manager_executable, g->marker,
            s->material, g->record.receipt.digest, &s->failure) ||
        kiosk_fresh_hex(g->record.receipt.digest, view)) goto done;
    s->stage = "source-clone";
    g->mountinfo = openat(g->manager.proc, "mountinfo", O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (g->mountinfo < 0 || kiosk_pin_acquire_policy_until(&g->source, g->manager.usr, g->mountinfo, "/usr",
            &g->manager.mount_namespace, g->record.inventory.entries, g->record.inventory.count,
            g->record.ambient, deadline, &s->failure, &s->cleanup_failure) ||
        kiosk_retained_source_check(g)) goto done;
    s->stage = "source-staging";
    if (kiosk_retained_staging_until(g)) goto done;
    s->stage = "selection";
    int selection[] = {g->record.view_fd, g->source.fd, g->record.slots_fd, g->invocation};
    if (kiosk_fresh_locks(lock, lease) || kiosk_preparation_child_select(&s->child, 2, s->child.backend,
            material, view, selection, 4) ||
        kiosk_preparation_child_result(&s->child, 2, s->child.backend, material, view, &s->response)) goto done;
    s->stage = "reap";
    if (kiosk_preparation_finish(&s->child)) goto done;
    s->stage = "retained-plan";
    if (kiosk_retained_source_check(g) || kiosk_preparation_plan_verify_until(&s->plan,
            s->response.fds[0], -1, &s->authority, &s->host, &g->record.receipt,
            g->source.fd, s->crypto, deadline)) goto done;
    s->stage = "realization";
    size_t used = 0;
    while (used < sizeof(random)) {
        if (kiosk_pin_before(deadline)) goto done;
        ssize_t n = getrandom(random + used, sizeof(random) - used, GRND_NONBLOCK);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) goto done;
        used += (size_t)n;
    }
    for (unsigned i = 0; i < sizeof(random); i++) snprintf(s->acquisition + i * 2, 3, "%02x", random[i]);
    s->skeleton = openat(g->invocation, "tree", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (s->skeleton < 0 || kiosk_realization_bind_until(&s->realized, s->skeleton, &s->plan, &s->authority,
            &s->roots, g->source.fd, -1, &g->record.receipt, s->acquisition, s->crypto, deadline, &s->failure) ||
        kiosk_fresh_marker_until(s)) goto done;
    s->stage = "attachment";
    s->target_parent = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    int target_fd = s->target_parent < 0 ? -1 : openat(s->target_parent, "usr", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    unsigned long long parent_mount, target_mount;
    int valid = target_fd >= 0 && !fstat(s->target_parent, &parent) && !fstat(target_fd, &target) &&
        !kiosk_pin_fd_mount(s->target_parent, &parent_mount) && !kiosk_pin_fd_mount(target_fd, &target_mount);
    if (target_fd >= 0) close(target_fd);
    if (!valid) goto done;
    destination = (struct kiosk_pin_target){.parent_device = parent.st_dev, .parent_inode = parent.st_ino,
        .device = target.st_dev, .inode = target.st_ino, .parent_mount = parent_mount, .mount = target_mount};
    if (kiosk_realization_attach_until(&s->realized, &s->pin, s->target_parent, "usr", &destination, deadline, &s->failure)) goto done;
    s->stage = "staging";
    if (s->realized.stage_count > KIOSK_VIEW_ROWS - 2 ||
        !(stages = calloc(s->realized.stage_count + 2, sizeof(*stages)))) goto done;
    stages[0] = (struct kiosk_owned_mount){.path = (char *)KIOSK_CONFINEMENT_VIEW, .id = s->view.root_id, .live = s->view.mounted};
    stages[1] = (struct kiosk_owned_mount){.path = (char *)KIOSK_CONFINEMENT_VIEW "/source",
        .id = g->source.attached_id, .live = g->source.attached};
    for (unsigned i = 0; i < s->realized.stage_count; i++) stages[i + 2] = s->realized.stages[i];
    int finished = kiosk_pin_finish_until(&s->pin, stages, s->realized.stage_count + 2,
        s->realized.entries, s->realized.entry_count, deadline, &s->failure);
    s->view.mounted = stages[0].live;
    g->source.attached = stages[1].live;
    for (unsigned i = 0; i < s->realized.stage_count; i++) s->realized.stages[i].live = stages[i + 2].live;
    free(stages); stages = NULL;
    if (finished) goto done;
    /* I is invocation-private. No completed generation is allocated or changed. */
    s->stage = "final-proof";
    if (kiosk_retained_final_proofs(g, lock, lease) ||
        prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0)) goto done;
    s->stage = "closure";
    s->view.cloned = 1; s->view.clone_id = s->pin.attached_id;
    s->pin.published = 1; /* Private I is complete; this does not publish a generation. */
    if (kiosk_pin_release(&s->pin, 1, &s->cleanup_failure)) goto done;
    s->pin.attached = 0;
    if (kiosk_pin_release(&g->source, 0, &s->cleanup_failure)) goto done;
    /* All other setup objects close before the last same-manager observation.
     * Keep its original pidfd/proc/bus through that check, then close them too. */
    if (g->mountinfo >= 0) close(g->mountinfo);
    if (g->marker >= 0) close(g->marker);
    if (g->invocation >= 0) close(g->invocation);
    g->mountinfo = g->marker = g->invocation = -1;
    kiosk_retained_record_close(&g->record);
    kiosk_fresh_descriptors_close(s);
    if (kiosk_manager_recheck(&g->manager, &s->failure)) goto done;
    kiosk_manager_release(&g->manager);
    s->stage = "lock";
    if (kiosk_fresh_locks(lock, lease) || kiosk_pin_before(deadline)) goto done;
    s->stage = "mac";
    if (kiosk_fresh_mac_apply(&s->mac) || kiosk_pin_before(deadline)) goto done;
    s->armed = 1; s->stage = "armed"; result = 0;
done:
    free(stages);
    if (result) {
        kiosk_failure(&s->failure, s->stage, "refused", -1);
        if (kiosk_retained_recover_until(g, deadline)) kiosk_failure(&s->cleanup_failure, "recovery", "unresolved", -1);
    }
    return result;
}
#endif
