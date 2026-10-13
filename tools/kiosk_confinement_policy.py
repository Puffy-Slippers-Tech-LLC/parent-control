#!/usr/bin/python3
"""Build the finite kiosk executable inventory and its distribution MAC policy."""
import argparse
import json
from pathlib import Path


PREFIX = '/usr/libexec/oh-no-parent-control-kiosk-'
DOMAINS = ('gate', 'manager-pam', 'manager', 'session-start', 'session', 'service', 'app-start',
           'app', 'notifications-start', 'notifications', 'notification-client-start',
           'notification-client', 'wellbeing-start',
           'wellbeing', 'audio-start', 'audio', 'pipewire', 'packages-start', 'packages',
           'locale', 'scanner', 'bwrap', 'webkit', 'polkit', 'glycin-bwrap', 'glycin')

# Both supported GTK stacks use the 2+ native loader ABI. Keep the names
# finite: loader configuration in XDG_DATA_HOME must never grant a new program.
GLYCIN_LOADERS = ('glycin-svg', 'glycin-image-rs', 'glycin-heif', 'glycin-jxl',
                 'glycin-raw', 'glycin-jpeg2000')
GLYCIN_DIRECTORY = '/usr/libexec/glycin-loaders/2+'


def executables(distribution):
    entries = []

    def add(role, *paths, optional=False):
        entries.append(dict(role=role, paths=list(paths), optional=optional))

    add('manager', '/usr/lib/systemd/systemd')
    add('executor', '/usr/lib/systemd/systemd-executor')
    add('gate', '/usr/libexec/gdm-wayland-session')
    add('session-start', PREFIX + 'session')
    add('leader', '/usr/bin/gnome-session')
    for name in ('gnome-session-init-worker', 'gnome-session-service', 'gnome-session-ctl'):
        add('service', '/usr/libexec/' + name)
    for name in ('systemctl', 'dbus-daemon', 'dbus-broker', 'dbus-broker-launch'):
        add('service', '/usr/bin/' + name, optional=name in ('dbus-broker', 'dbus-broker-launch'))
    add('pipewire', '/usr/bin/pipewire', '/usr/bin/pipewire-pulse')
    add('service', '/usr/bin/gnome-kiosk')
    add('service', PREFIX + 'cleanup')
    if distribution == 'fedora':
        add('service', PREFIX + 'dbus')
    for name in ('dconf-service', 'at-spi-bus-launcher', 'at-spi2-registryd',
                 'xdg-permission-store', 'xdg-document-portal', 'xdg-desktop-portal',
                 'xdg-desktop-portal-gtk', 'xdg-desktop-portal-gnome'):
        add('service', '/usr/libexec/' + name, optional=True)
    for name in ('gvfsd', 'gvfsd-metadata', 'gvfsd-fuse'):
        add('service', '/usr/libexec/' + name, optional=True)
    add('service', '/usr/bin/systemd-tmpfiles')
    for role in ('app', 'notifications', 'notification-client', 'wellbeing', 'audio'):
        add(role + '-start', PREFIX + role)
    add('audio', '/usr/bin/wireplumber')
    add('packages-start', PREFIX + 'packages')
    add('rpm', '/usr/bin/rpm', optional=distribution != 'fedora')
    add('locale', '/usr/bin/locale')
    add('python', '/usr/bin/python3')
    # Ubuntu's public gjs command resolves to gjs-console. AppArmor checks the
    # canonical executable pathname; keep both finite distro entrypoints.
    add('gjs', '/usr/bin/gjs', '/usr/bin/gjs-console')
    add('polkit', '/usr/libexec/polkit-mate-authentication-agent-1')
    # Swap only these private-tree destinations. Never replace the host's
    # bubblewrap or copy a distribution binary into the installed package.
    entries += [dict(role='bwrap', paths=['/usr/bin/bwrap'], source=PREFIX + 'bwrap'),
                dict(role='bwrap-native', paths=[PREFIX + 'bwrap'], source='/usr/bin/bwrap')]
    # At least one distro loader must exist. Grouping alternatives also pins
    # their shared parent when optional codecs are absent: a later package
    # installation cannot expose a new executable in an admitted generation.
    add('glycin', *(GLYCIN_DIRECTORY + '/' + name for name in GLYCIN_LOADERS))
    add('service', '/usr/bin/xdg-dbus-proxy')
    webkit = ('/usr/libexec/webkitgtk-6.0/' if distribution == 'fedora'
              else '/usr/lib/x86_64-linux-gnu/webkitgtk-6.0/')
    for name in ('WebKitWebProcess', 'WebKitNetworkProcess', 'WebKitGPUProcess'):
        add('webkit', webkit + name, optional=name == 'WebKitGPUProcess')
    add('scanner', '/usr/libexec/gstreamer-1.0/gst-plugin-scanner' if distribution == 'fedora'
        else '/usr/lib/x86_64-linux-gnu/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner')
    # gst-python is native code that imports home-controlled Python in-process.
    # A private type denies its executable mappings, including inside WebKit.
    add('blocked', '/usr/lib64/gstreamer-1.0/libgstpython.so' if distribution == 'fedora'
        else '/usr/lib/x86_64-linux-gnu/gstreamer-1.0/libgstpython.so', optional=True)
    return entries


def routes():
    """Program transitions. Generic interpreters are reachable only via fixed launchers."""
    result = {
        'gate': {'gate': 'gate', 'session-start': 'session-start'},
        # The systemd executor and its non-exec PAM lifecycle child enter this
        # domain immediately. Only the real manager executable may leave it.
        'manager-pam': {'manager': 'manager', 'executor': 'manager'},
        'session-start': {'leader': 'session'},
        'app-start': {'python': 'app'},
        'notifications-start': {'python': 'notifications'},
        'notification-client-start': {'python': 'notification-client'},
        'notification-client': {'notifications-start': 'notifications-start'},
        'wellbeing-start': {'gjs': 'wellbeing'},
        'audio-start': {'audio': 'audio'},
        'audio': {},
        'pipewire': {},
        'scanner': {},
        'packages-start': {'rpm': 'packages'},
        'packages': {},
        'locale': {},
        'polkit': {'polkit': 'polkit', 'bwrap': 'glycin-bwrap'},
        'glycin-bwrap': {'bwrap-native': 'glycin-bwrap', 'glycin': 'glycin'},
        'glycin': {},
        'webkit': {'webkit': 'webkit', 'scanner': 'scanner'},
        'bwrap': {'bwrap-native': 'bwrap', 'webkit': 'webkit', 'service': 'service', 'glycin': 'glycin'},
    }
    standard = {'service': 'service', 'polkit': 'polkit', 'app-start': 'app-start',
                'notification-client-start': 'notification-client-start', 'wellbeing-start': 'wellbeing-start',
                'audio-start': 'audio-start', 'pipewire': 'pipewire'}
    result['manager'] = {**standard, 'manager': 'manager', 'executor': 'manager'}
    result['session'] = {'service': 'service'}
    result['service'] = {**standard, 'bwrap': 'glycin-bwrap'}
    result['app'] = {'bwrap': 'bwrap', 'webkit': 'webkit', 'service': 'service', 'scanner': 'scanner',
                     'locale': 'locale', 'packages-start': 'packages-start'}
    result['notifications'] = {'bwrap': 'glycin-bwrap'}
    result['wellbeing'] = {}
    return result


def selinux(entries):
    domains = {name: 'onpc_kiosk_' + name.replace('-', '_') + '_t' for name in DOMAINS}
    roles = sorted({entry['role'] for entry in entries})
    types = {role: 'onpc_kiosk_' + role.replace('-', '_') + '_exec_t' for role in roles}
    lines = ['; Generated finite kiosk execution policy; shared OS labels remain unchanged.',
             '(typeattribute onpc_kiosk_domains)', '(typeattribute onpc_kiosk_objects)',
             '(typeattribute onpc_kiosk_clients)',
             '(typeattributeset onpc_kiosk_objects (all))',
             '(typeattribute onpc_kiosk_writable)',
             '(typeattributeset onpc_kiosk_writable (and (all) (not (exec_type lib_t ld_so_t textrel_shlib_t))))']
    for name, domain in domains.items():
        lines += [f'(type {domain})', f'(roletype system_r {domain})',
                  f'(typeattributeset domain ({domain}))',
                  f'(typeattributeset onpc_kiosk_domains ({domain}))']
        if name != 'scanner':
            lines.append(f'(typeattributeset onpc_kiosk_clients ({domain}))')
    for typ in types.values():
        lines += [f'(type {typ})', f'(typeattributeset file_type ({typ}))',
                  f'(typeattributeset exec_type ({typ}))']
    runtime = 'onpc_kiosk_runtime_t'
    lines += [f'(type {runtime})', f'(roletype object_r {runtime})',
              f'(typeattributeset file_type ({runtime}))']
    # Integration creates the shared lease before native PAM admission. Give
    # restorecon an exact owned inode label as well as the native filename
    # transitions below. Fedora's /run equivalence maps to /var/run.
    for parent in ('/run', '/var/run'):
        lines.append(f'(filecon "{parent}/oh-no-parent-control-kiosk-admission[.]lock" '
                     f'file (system_u object_r {runtime} ((s0) (s0))))')
    allow = lambda source, target, cls, permissions: lines.append(
        f'(allow {source} {target} ({cls} ({permissions})))')
    # This policy adds an execution boundary. Existing DAC, D-Bus and Polkit
    # authorization continue to own data, service and administrator authority.
    obj = 'onpc_kiosk_objects'
    dom = 'onpc_kiosk_domains'
    for cls in ('file', 'lnk_file', 'fifo_file', 'sock_file', 'chr_file', 'blk_file'):
        allow('onpc_kiosk_clients', obj, cls, 'ioctl read getattr lock open')
        # Only regular files can supply executable mappings. Socket labels
        # may also carry an exec_type attribute in the vendor policy (notably
        # session_dbusd_tmp_t), which must not prevent user-bus activation.
        writable = 'onpc_kiosk_writable' if cls == 'file' else obj
        allow('onpc_kiosk_clients', writable, cls, 'write create setattr append unlink link rename')
    for typ in ('lib_t', 'ld_so_t', 'textrel_shlib_t', 'usr_t', 'etc_t', types['scanner']):
        allow(domains['scanner'], typ, 'file', 'read getattr open map')
    # The fixed GStreamer scanner follows the prepared library symlinks and
    # exchanges its result over its app/WebKit parent's inherited anonymous pipes.
    # It still cannot write regular files or execute another program.
    allow(domains['scanner'], runtime, 'lnk_file', 'read getattr')
    for parent in ('app', 'webkit'):
        allow(domains['scanner'], domains[parent], 'fifo_file', 'read write getattr ioctl')
    allow(domains['scanner'], 'null_device_t', 'chr_file', 'read write getattr open ioctl')
    allow(dom, obj, 'file', 'map watch watch_reads')
    allow(dom, obj, 'lnk_file', 'watch watch_reads')
    allow(dom, obj, 'dir', 'ioctl read write create getattr setattr lock unlink link rename rmdir add_name remove_name reparent search open watch watch_reads')
    allow(dom, obj, 'filesystem', 'getattr associate')
    allow(dom, 'self', 'process', 'fork sigchld sigkill sigstop signull signal getsched setsched getpgid setpgid getcap setcap getsession getrlimit setrlimit execmem')
    allow(dom, 'domain', 'process', 'sigchld signal signull getattr')
    allow('domain', dom, 'process', 'sigchld signal signull getattr')
    allow(dom, 'domain', 'fd', 'use')
    allow('domain', dom, 'fd', 'use')
    allow(dom, 'domain', 'dbus', 'send_msg')
    allow('domain', dom, 'dbus', 'send_msg')
    allow(dom, 'self', 'dbus', 'acquire_svc send_msg')
    for cls in ('unix_stream_socket', 'unix_dgram_socket', 'tcp_socket', 'udp_socket',
                'netlink_route_socket', 'netlink_kobject_uevent_socket'):
        allow(dom, 'self', cls, 'create ioctl read write getattr setattr lock append bind connect listen accept getopt setopt shutdown')
    allow(dom, 'domain', 'unix_stream_socket', 'connectto')
    # Role transitions retain inherited journal/IPC descriptors. fd:use alone
    # does not authorize I/O on a socket labelled by the creating parent.
    allow(dom, 'domain', 'unix_stream_socket', 'read write getattr ioctl getopt setopt')
    allow(dom, 'domain', 'unix_dgram_socket', 'sendto')
    allow('domain', dom, 'unix_stream_socket', 'connectto')
    allow('domain', dom, 'unix_dgram_socket', 'sendto')
    allow(dom, 'port_type', 'tcp_socket', 'name_connect name_bind')
    allow(dom, 'port_type', 'udp_socket', 'name_bind')
    allow(dom, 'node_type', 'tcp_socket', 'node_bind')
    allow(dom, 'node_type', 'udp_socket', 'node_bind')
    allow(dom, 'self', 'netlink_route_socket', 'nlmsg_read')
    allow(dom, 'self', 'key', 'create view read write search link setattr')
    allow(dom, obj, 'key', 'view read write search link setattr')
    allow(dom, 'self', 'capability', 'chown dac_override fowner fsetid setgid setuid setpcap sys_chroot sys_resource audit_write')
    # systemd labels runtime sockets before creating them. File creation with
    # any executable/library type remains denied by onpc_kiosk_writable.
    allow(domains['manager'], 'self', 'process', 'setfscreate setsockcreate')
    allow(domains['manager'], 'security_t', 'security', 'compute_create compute_av')
    # The manager creates vendor-labelled runtime sockets carrying the local
    # SELinux user (e.g. unconfined_u), while its own fixed SID uses system_u.
    # Satisfy Fedora's object-identity constraint without changing any process
    # identity or granting executable-file creation/relabel permissions.
    lines.append(f'(typeattributeset can_change_object_identity ({domains["manager"]}))')
    # dbus-broker performs the policy's userspace message checks itself.
    allow(domains['service'], 'security_t', 'security', 'compute_av')
    # Unmapped user-bus names use the broker's SID, not the caller's SID.
    # Name ownership remains subject to the bus configuration and unique-name
    # rules; this covers the confined user bus, not system-bus service labels.
    allow(dom, domains['service'], 'dbus', 'acquire_svc')
    allow(dom, 'systemd_unit_file_t', 'service', 'start stop status reload')
    # Fedora labels GNOME's session targets separately. The fixed native init
    # worker starts that target and imports its environment through the private
    # user manager's public API; dbus-broker also subscribes to that manager.
    # These userspace system/service checks add no executable entrypoint.
    allow(domains['service'], 'xdm_unit_file_t', 'service', 'start status')
    # GNOME's fixed shutdown helper restarts its own user bus. The compositor
    # maps its DRM device; ordinary chr_file I/O does not authorize mmap.
    allow(domains['service'], 'dbusd_unit_file_t', 'service', 'stop')
    allow(domains['service'], 'dri_device_t', 'chr_file', 'map')
    # User-bus activation also creates transient services through the manager.
    # Their exec still goes through the same finite manager entrypoint policy.
    allow(domains['service'], domains['manager'], 'system', 'reload status start')
    # The final GDM Wayland gate queries its own private user manager.
    allow(domains['gate'], domains['manager'], 'system', 'status')
    for cls in ('unix_stream_socket', 'unix_dgram_socket'):
        # Socket activation creates the server socket with the eventual
        # native service's label, before passing its FD to that service.
        for server in ('service', 'pipewire'):
            allow(domains['manager'], domains[server], cls,
                  'create ioctl read write getattr setattr lock append bind connect listen accept getopt setopt shutdown')
    # execute is necessary for executable mappings; execute_no_trans and
    # entrypoint remain absent, so invoking the ELF loader itself is denied.
    for typ in ('lib_t', 'ld_so_t', 'textrel_shlib_t'):
        allow(dom, typ, 'file', 'execute')
    allow(dom, 'onpc_kiosk_library_exec_t', 'file', 'read open getattr map execute')
    for source, targets in routes().items():
        for role, destination in targets.items():
            allow(domains[source], types[role], 'file', 'read open getattr map execute')
            if source == destination:
                allow(domains[source], types[role], 'file', 'execute_no_trans')
            else:
                allow(domains[source], domains[destination], 'process', 'transition')
                allow(domains[source], domains[destination], 'process2', 'nnp_transition nosuid_transition')
                allow(domains[destination], types[role], 'file', 'entrypoint')
                # The new SID must also map the ELF which established it. This
                # grants no execute_no_trans or new source-to-destination route.
                allow(domains[destination], types[role], 'file', 'read open getattr map execute')
                lines.append(f'(typetransition {domains[source]} {types[role]} process {domains[destination]})')
    for role, caller in (('manager', 'init_t'), ('gate', 'xdm_t')):
        # Both real PAM callers share the lock and immutable preparation tree.
        # Vendor filename transitions otherwise give init_t's files labels
        # which GDM cannot read, and sharing all init runtime files is too broad.
        for name, cls in (('oh-no-parent-control-confinement.lock', 'file'),
                          ('oh-no-parent-control-kiosk-admission.lock', 'file'),
                          ('oh-no-parent-control-confinement', 'dir')):
            lines.append(f'(typetransition {caller} var_run_t {cls} "{name}" {runtime})')
        allow(caller, runtime, 'file',
              'create read write getattr setattr open lock unlink rename relabelfrom mounton')
        allow(caller, runtime, 'dir',
              'create read write getattr setattr search open add_name remove_name rmdir rename mounton')
        allow(caller, runtime, 'lnk_file', 'create read getattr unlink')
        allow(caller, domains[role], 'process', 'transition')
        allow(caller, domains[role], 'process2', 'nosuid_transition')
        allow(caller, 'self', 'process', 'setexec')
        allow(caller, types[role], 'file', 'read open getattr map execute')
        allow(domains[role], types[role], 'file', 'entrypoint')
        for typ in types.values():
            allow(caller, typ, 'file', 'create read write getattr setattr open map relabelto')
        for typ in ('var_run_t', 'xdm_var_run_t', 'initrc_var_run_t'):
            allow(caller, typ, 'file', 'relabelfrom')
        allow(caller, domains['manager'], 'process', 'ptrace')
        allow(caller, 'self', 'capability', 'sys_ptrace')
        allow(caller, domains['manager'], 'file', 'read getattr open')
    # systemd forks sd-pam after pam_open_session. Confine that trusted,
    # single-threaded executor immediately, so its child and close callbacks
    # never depend on a pending exec SID or a census exception. There is no
    # reverse dynamic transition and manager-pam can exec only the manager.
    allow('init_t', 'self', 'process', 'setcurrent')
    allow('init_t', domains['manager-pam'], 'process', 'dyntransition')
    allow(domains['manager-pam'], 'self', 'process', 'setexec')
    # PID 1 passes its pre-existing handoff-timestamp socket to the executor.
    # Fedora's socket carries kernel_t (observed with dontaudit disabled), not
    # PID 1's current init_t label. The final write precedes execve; fd:use and
    # peer sendto do not authorize I/O on this inherited socket itself.
    allow(domains['manager-pam'], 'kernel_t', 'unix_dgram_socket', 'write')
    # Preserve the trusted system executor/PAM environment across this one
    # private manager transition. Otherwise AT_SECURE makes libsystemd ignore
    # XDG_RUNTIME_DIR and the manager exits with ENOMEDIUM before startup.
    # Only the root-owned user@ unit can reach this PAM entry; no generic
    # interpreter or distribution-original entrypoint is permitted. Subsequent
    # user-manager environments remain subject to the same executable/mapping
    # restrictions. Other role transitions retain secure execution.
    allow(domains['manager-pam'], domains['manager'], 'process', 'noatsecure')
    # Linux-PAM sends its session result after the final module returns. Use
    # Fedora's logging_send_audit_msgs permission shape, without tty auditing
    # or audit-control authority; an audit failure otherwise aborts admission.
    allow(domains['manager-pam'], 'self', 'netlink_audit_socket',
          'create ioctl read getattr lock write setattr append bind connect getopt setopt shutdown nlmsg_read nlmsg_relay')
    # GDM prepares the private service executable before its final exec. Fedora
    # otherwise denies xdm_t reading this vendor-labelled inventory member.
    # The caller receives no execute permission on the distribution original.
    allow('xdm_t', 'systemd_tmpfiles_exec_t', 'file', 'read getattr open')
    # Admission reads the existing manager's MainPID through systemd's public
    # API. This grants inspection only, never starting or stopping a unit.
    allow('xdm_t', 'systemd_unit_file_t', 'service', 'status')
    # The independent /usr skeleton checks every sibling's owner/mode before
    # pinning it. Distro packages can add siblings with otherwise unrelated
    # labels; metadata inspection must not depend on which are installed.
    # This grants neither file contents nor directory traversal/execution.
    for cls in ('file', 'dir'):
        allow('xdm_t', 'file_type', cls, 'getattr')
    # The root GDM PAM caller, before entering the gate, owns the private mount
    # namespace and its read-only bind tree. No kiosk role gains this capability.
    allow('xdm_t', 'self', 'capability', 'sys_admin')
    for sandbox in ('bwrap', 'glycin-bwrap'):
        allow(domains[sandbox], 'self', 'capability', 'sys_admin sys_chroot mknod setuid setgid setpcap')
        allow(domains[sandbox], 'self', 'cap_userns', 'sys_admin sys_chroot mknod setuid setgid setpcap')
        allow(domains[sandbox], 'self', 'user_namespace', 'create')
        allow(domains[sandbox], obj, 'dir', 'mounton')
        for typ in ('tmpfs_t', 'proc_t', 'devpts_t'):
            allow(domains[sandbox], typ, 'filesystem', 'mount remount unmount')
    # Glycin and WebKit request private network namespaces. Native bubblewrap brings
    # up its loopback with RTM_NEWADDR/RTM_NEWLINK after creating that namespace.
    # Never authorize initial-namespace NET_ADMIN or grant this to the decoder.
    for sandbox in ('bwrap', 'glycin-bwrap'):
        allow(domains[sandbox], 'self', 'cap_userns', 'net_admin')
        allow(domains[sandbox], 'self', 'netlink_route_socket', 'nlmsg_write')
    # The manager's private /usr skeleton is backed by the host filesystem,
    # not tmpfs. Bubblewrap's read-only bind remount checks that superblock's
    # fs_t even when the pinned source mount is already read-only. After making
    # oldroot private, the same native bootstrap detaches it with MNT_DETACH.
    for sandbox in ('bwrap', 'glycin-bwrap'):
        allow(domains[sandbox], 'fs_t', 'filesystem', 'remount unmount')
    # --dev creates regular-file placeholders on its private tmpfs, then binds
    # the finite native /dev nodes over them. Directory mounton is insufficient.
    for sandbox in ('bwrap', 'glycin-bwrap'):
        allow(domains[sandbox], 'tmpfs_t', 'file', 'mounton')
    # WebKit exposes read-only device metadata and the canonical timezone
    # file. These measured grants belong only to its native bootstrap.
    allow(domains['bwrap'], 'sysfs_t', 'filesystem', 'remount')
    allow(domains['bwrap'], 'locale_t', 'file', 'mounton')
    # WebKit repeats its scanner bind after exposing the containing lib tree.
    # The existing destination is already the pinned scanner executable.
    allow(domains['bwrap'], types['scanner'], 'file', 'mounton')
    # The launcher exposes the pinned /usr/bin tree before WebKit repeats
    # its individual xdg-dbus-proxy bind onto that service-labelled inode.
    allow(domains['bwrap'], types['service'], 'file', 'mounton')
    # The same native GStreamer setup repeats the vendor gst-ptp-helper bind.
    # Its bin_t remains outside every kiosk executable transition.
    allow(domains['bwrap'], 'bin_t', 'file', 'mounton')
    # Keep the distro's confined setuid password helper and its PAM policy.
    allow(domains['polkit'], 'policykit_auth_exec_t', 'file', 'read open getattr map execute')
    allow(domains['polkit'], 'policykit_auth_t', 'process', 'transition')
    lines.append(f'(typetransition {domains["polkit"]} policykit_auth_exec_t process policykit_auth_t)')
    # Fedora's native helper exchanges the PAM conversation over two pipes
    # created by the confined agent, then resolves vendor library symlinks in
    # the private /usr skeleton. Keep its vendor PAM/credential policy and
    # secure-exec behavior; no new executable route or writable object is added.
    allow('policykit_auth_t', domains['polkit'], 'fifo_file', 'read write')
    allow('policykit_auth_t', runtime, 'dir', 'search getattr')
    allow('policykit_auth_t', runtime, 'lnk_file', 'read')
    # pam_unix invokes Fedora's own unix_chkpwd in chkpwd_t when the Polkit
    # helper cannot read shadow directly. Its loader/NSS lookups inherit this
    # same private /usr skeleton. Preserve the vendor credential and executable
    # policy; only traversal of our directory/symlink objects is missing.
    allow('chkpwd_t', runtime, 'dir', 'search getattr')
    allow('chkpwd_t', runtime, 'lnk_file', 'read')
    return '\n'.join(lines) + '\n'


def apparmor(entries):
    roles = {}
    for entry in entries:
        roles.setdefault(entry['role'], []).extend(entry['paths'])
    lines = ['# Generated finite kiosk execution policy.', '#include <tunables/global>', '']
    transitions = routes()
    for domain in DOMAINS:
        lines += [f'profile onpc-kiosk-{domain} flags=(attach_disconnected,mediate_deleted) {{',
                  '  # DAC and broker authorization continue to govern data access.',
                  ('  /{usr,etc,proc,sys}/** r,\n  /dev/{null,urandom,random} rw,'
                   if domain == 'scanner' else '  /** rwkl,'),
                  '  /{,usr/}lib{,32,64,x32}/** mr,',
                  '  /usr/libexec/** mr,',
                  '  /usr/bin/** mr,',
                  '  network,', '  unix,', '  dbus,', '  signal,',
                  '  capability chown,', '  capability dac_override,',
                  '  capability fowner,', '  capability fsetid,',
                  '  capability setgid,', '  capability setuid,',
                  '  capability setpcap,', '  capability sys_chroot,',
                  '  capability sys_resource,', '  capability audit_write,']
        lines.append('  deny /{,usr/}lib{,32,64,x32}/**/libgstpython.so m,')
        if domain == 'gate':
            lines.append('  capability sys_tty_config,')
        if domain == 'manager':
            # systemd temporarily retains this capability while installing
            # the user unit's seccomp filters, then drops it before exec.
            # No mount or user-namespace permission is granted to the manager.
            lines.append('  capability sys_admin,')
        for role, destination in transitions[domain].items():
            for path in roles[role]:
                if domain == 'bwrap' and role == 'service' and path != '/usr/bin/xdg-dbus-proxy':
                    continue
                # Python is a distro symlink. Resolve only the versioned distro
                # interpreter name, never a user-selected executable directory.
                if role == 'python':
                    path = '/usr/bin/python3{,.[0-9],.[0-9][0-9]}'
                permission = 'ix' if destination == domain else f'Px -> onpc-kiosk-{destination}'
                # NNP permits adding restrictions to the existing label.
                # Keep bubblewrap in the stack while adding the payload's
                # profile, which removes mount/userns authority after exec.
                if domain in ('bwrap', 'glycin-bwrap') and destination != domain:
                    permission = f'Px -> onpc-kiosk-{domain}//&onpc-kiosk-{destination}'
                elif role == 'pipewire':
                    permission = f'Px -> onpc-kiosk-{domain}//&onpc-kiosk-pipewire'
                elif domain == 'webkit' and role == 'scanner':
                    permission = 'Px -> onpc-kiosk-webkit//&onpc-kiosk-scanner'
                lines.append(f'  {path} {permission},')
        if domain == 'bwrap':
            for path in roles['scanner']:
                lines.append(f'  {path} Px -> onpc-kiosk-bwrap//&onpc-kiosk-webkit//&onpc-kiosk-scanner,')
        if domain == 'polkit':
            # Glycin enumerates / to reproduce the distro's library symlinks
            # inside its sandbox; /** does not match the root directory itself.
            lines.append('  / r,')
            lines += ['  /usr/lib/polkit-1/polkit-agent-helper-1 Cx -> password,',
                      '  profile password {', '    /** rwkl,',
                      '    /{,usr/}lib{,32,64,x32}/** mr,',
                      '    capability,', '    network,', '    unix,',
                      '    signal,', '    /usr/sbin/unix_chkpwd ix,', '  }']
        if domain in ('bwrap', 'glycin-bwrap'):
            # Mediate the capability native bwrap already holds in its new
            # user/network namespaces; this rule supplies no Linux capability.
            lines.append('  capability net_admin,')
        if domain in ('bwrap', 'glycin-bwrap'):
            # Native bubblewrap opens its temporary / before the second pivot
            # so it can detach that old root afterward; /** excludes / itself.
            lines += ['  / r,', '  userns,', '  capability sys_admin,', '  capability mknod,',
                      '  mount fstype=tmpfs -> /tmp/,',
                      '  mount fstype=tmpfs -> /newroot/{tmp,tmp-home,tmp-run,dev,dev/shm}/,',
                      '  mount fstype=proc -> /newroot/proc/,',
                      '  mount fstype=devpts -> /newroot/dev/pts/,',
                      '  pivot_root oldroot=/tmp/oldroot/ /tmp/,',
                      '  pivot_root oldroot=/newroot/ /newroot/,',
                      '  umount /oldroot/,',
                      '  umount /,',
                      '  mount options=(rw, silent, rslave) -> /,',
                      '  mount options=(rw, silent, rprivate) -> /oldroot/,',
                      '  mount options=(rw, rbind) /tmp/newroot/ -> /tmp/newroot/,',
                      '  mount options=(rw, rbind) /oldroot/proc/ -> /proc/,']
            # AppArmor strips MS_SILENT from binds, but retains it for native
            # bubblewrap's propagation and remount operations. Bubblewrap uses
            # MS_REC for file binds too. Match those kernel-mediated flags at
            # the existing finite paths, never a general mount-options subset.
            # Trusted code binds keep their own names, apart from the exact
            # usr-merge aliases below. The native launcher binds /usr/bin
            # first, preserving its pinned proxy inode without code writes.
            directories = ('usr', 'usr/bin', 'usr/share', 'usr/local/share', 'usr/lib', 'usr/lib64',
                           'usr/local/lib', 'usr/local/lib64', 'usr/lib/x86_64-linux-gnu',
                           'lib', 'lib64', 'etc',
                           'sys/block', 'sys/bus', 'sys/class', 'sys/dev', 'sys/devices',
                           'dev/dri', 'dev/snd', 'usr/share/fonts', 'usr/local/share/fonts',
                           'var/cache/fontconfig', 'etc/fonts', 'etc/fonts/conf.d')
            if domain == 'glycin-bwrap':
                directories = ('usr', 'usr/bin', 'lib', 'lib64', 'etc/fonts', 'etc/fonts/conf.d',
                               'var/cache/fontconfig')
            else:
                webkit_directories = sorted({str(Path(path).parent).lstrip('/')
                                             for path in roles['webkit']})
                directories += tuple(path for directory in webkit_directories
                                     for path in (directory, directory + '/injected-bundle'))
            for path in directories:
                lines.append(f'  mount options=(rw, rbind) /oldroot/{path}/ -> /newroot/{path}/,')
            if domain == 'bwrap':
                for path in ('lib', 'lib64'):
                    lines.append(f'  mount options=(rw, rbind) /oldroot/usr/{path}/ -> /newroot/{path}/,')
            files = ('usr/bin/xdg-dbus-proxy', 'dev/null', 'dev/zero', 'dev/random',
                     'dev/urandom', 'dev/full', 'dev/tty', 'run/systemd/resolve/stub-resolv.conf',
                     'run/systemd/resolve/resolv.conf', 'run/NetworkManager/resolv.conf',
                     'run/systemd/journal/socket', 'run/systemd/journal/stdout',
                     'etc/ld.so.cache', 'etc/fonts/fonts.conf')
            if domain == 'glycin-bwrap':
                files = ('dev/null', 'dev/zero', 'dev/random', 'dev/urandom', 'dev/full',
                         'dev/tty', 'etc/ld.so.cache', 'etc/fonts/fonts.conf')
            else:
                # GStreamer 1.28 software decoders expose this DMA buffer device.
                files += ('dev/udmabuf',)
                # WebKit repeats these GStreamer file binds after exposing
                # the containing library tree. Neither grants execution of
                # the vendor PTP helper, which has no executable route.
                files += tuple(path.lstrip('/') for path in roles['scanner'])
                files += tuple(str(Path(path).with_name('gst-ptp-helper')).lstrip('/')
                               for path in roles['scanner'])
            for path in files:
                lines.append(f'  mount options=(rw, rbind) /oldroot/{path} -> /newroot/{path},')
            if domain == 'bwrap':
                # /etc/localtime resolves into this non-executable data tree.
                # A configured timezone may contain multiple path components.
                lines.append('  mount options=(rw, rbind) /oldroot/usr/share/zoneinfo/** -> /newroot/usr/share/zoneinfo/**,')
            # Data aliases cannot replace a trusted executable pathname. Data
            # remains non-executable in every destination profile.
            for path in ('run/user/*', 'home/oh-no-parent-control'):
                lines += [f'  mount options=(rw, rbind) /oldroot/{path}/{{,**}} -> /newroot/{path}/{{,**}},',
                          f'  mount options=(rw, bind) /oldroot/{path}/{{,**}} -> /newroot/{path}/{{,**}},']
            # --ro-bind-data copies the sealed metadata into this native
            # mkstemp file before binding it. Only the data destination is
            # permitted; this is never an executable-path placeholder.
            lines += ['  mount options=(rw, rbind) /bindfile?????? -> /newroot/.flatpak-info,',
                      '  mount options in (ro, silent, remount, bind, nosuid, nodev, noexec, relatime, noatime, nodiratime) -> /newroot/**,',
                      '  deny /{,tmp/}newroot/{usr,lib,lib64,bin,sbin}/**[^/] wkl,',
                      '  deny /{usr,lib,lib64,bin,sbin}/**[^/] wkl,']
        lines += ['}', '']
    return '\n'.join(lines)


def generate(destination, distribution):
    entries = executables(distribution)
    systemd_libraries = ('/usr/lib64/systemd' if distribution == 'fedora'
                         else '/usr/lib/x86_64-linux-gnu/systemd')
    # Names contain the distro's systemd version/release. Enumerate installed
    # native libraries at preparation, then pin them with their executables.
    entries.append(dict(role='library', paths=[], library_directory=systemd_libraries))
    destination.mkdir(parents=True, exist_ok=True)
    config = dict(backend='selinux' if distribution == 'fedora' else 'apparmor',
                  domains=list(DOMAINS), executables=entries,
                  preserved_executables=[dict(path='/usr/lib/polkit-1/polkit-agent-helper-1',
                      mode=0o4755 if distribution == 'fedora' else 0o755,
                      label='system_u:object_r:policykit_auth_exec_t:s0'
                            if distribution == 'fedora' else None)],
                  reserved_directories=[systemd_libraries,
                      '/usr/lib64/gstreamer-1.0' if distribution == 'fedora'
                      else '/usr/lib/x86_64-linux-gnu/gstreamer-1.0'])
    # Preserved helpers contribute their parent to the private directory tree
    # on both targets, retaining each vendor inode, mode and security label.
    if distribution == 'ubuntu':
        config['apparmor_profiles'] = [*(f'onpc-kiosk-{name}' for name in DOMAINS),
                                       'onpc-kiosk-polkit//password']
    (destination / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    (destination / 'generation').write_text('unconfined\n')
    if distribution == 'fedora':
        (destination / 'onpc-kiosk.cil').write_text(selinux(entries))
        units = {'dbus-broker.service': 'ExecStart=\nExecStart=' + PREFIX + 'dbus\n'}
    else:
        (destination / 'onpc-kiosk.apparmor').write_text(apparmor(entries))
        # Only the kiosk manager receives this extra unit search path from
        # PAM. Existing user services keep their distribution hardening.
        # AppArmor role transitions must occur before NNP; the kernel rejects
        # nonmonotonic profile transitions even when an exec rule allows them.
        units = {
            'dbus.service': ('Environment=XDG_DATA_DIRS='
                '/usr/share/oh-no-parent-control/confinement/session-data:'
                '/usr/local/share:/usr/share\n'),
            'oh-no-parent-control-wellbeing.service': 'NoNewPrivileges=no\n',
            'wireplumber.service': ('NoNewPrivileges=no\nLockPersonality=no\n'
                'MemoryDenyWriteExecute=no\nSystemCallArchitectures=\nSystemCallFilter=\n'),
        }
    # The kiosk has no remote file/volume browser. Avoid synchronous GVfs
    # monitor activation, which otherwise waits for intentionally denied
    # desktop services before the compositor can announce readiness.
    units['org.gnome.Kiosk@wayland.service'] = 'Environment=GIO_USE_VFS=local\n'
    if distribution == 'ubuntu':
        # Snap applications cannot run in the kiosk. Mask both bus/socket
        # activation and the installed default-target services/timer in this
        # manager's owned unit path. Desktop integration and prompting have
        # Restart=on-failure and otherwise retry intentionally denied snap exec.
        unit_directory = destination / 'user-units'
        unit_directory.mkdir(parents=True, exist_ok=True)
        for name in ('snapd.session-agent.service', 'snapd.session-agent.socket',
                     'snap.snapd-desktop-integration.snapd-desktop-integration.service',
                     'snap.prompting-client.daemon.service',
                     'snap.firmware-updater.firmware-notifier.service',
                     'snap.firmware-updater.firmware-notifier.timer'):
            mask = unit_directory / name
            if not (mask.is_symlink() and mask.readlink() == Path('/dev/null')):
                mask.symlink_to('/dev/null')
        # Standard session service directories honor XDG_DATA_DIRS order.
        # These two vendor services directly exec snap rather than delegating
        # to the agent. Route them to the same masked unit in this bus only.
        # Exec is required by D-Bus even with SystemdService; its inert fallback
        # receives no new execution permission if systemd activation is absent.
        services = destination / 'session-data/dbus-1/services'
        services.mkdir(parents=True, exist_ok=True)
        for name in ('io.snapcraft.Settings', 'io.snapcraft.Launcher'):
            (services / (name + '.service')).write_text(
                '[D-BUS Service]\nName=' + name + '\nExec=/bin/false\n'
                'SystemdService=snapd.session-agent.service\n')
    for name, settings in units.items():
        directory = destination / 'user-units' / (name + '.d')
        directory.mkdir(parents=True, exist_ok=True)
        (directory / '90-kiosk-confinement.conf').write_text(
            '# Kiosk-only execution transition compatibility; see Lifecycle.md.\n'
            '[Service]\n' + settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', choices=('ubuntu', 'fedora'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.output, args.distribution)
