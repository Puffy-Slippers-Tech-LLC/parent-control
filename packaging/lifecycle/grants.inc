grant_state=/var/lib/oh-no-parent-control
grant_store="$grant_state/grants"
retired_grants="$grant_state/grants.removed"
enforcement_snapshot="$grant_state/uninstall-enforcement.json"

refuse_grant_cleanup() {
    echo 'oh-no-parent-control: refusing cleanup of unsafe saved-time state' >&2
    exit 1
}

check_private_grant_directory() {
    if [ -L "$1" ] || [ ! -d "$1" ] || [ ! -O "$1" ]; then
        refuse_grant_cleanup
    fi
    grant_mode=$(stat -c '%a' -- "$1") || refuse_grant_cleanup
    [ "$((0$grant_mode & 077))" -eq 0 ] || refuse_grant_cleanup
}

check_grant_mount() {
    grant_mount_status=0
    mountpoint -q "$1" || grant_mount_status=$?
    # 32 means the path is not a mount point. Refuse inspection failures too.
    [ "$grant_mount_status" -eq 32 ] || refuse_grant_cleanup
}

check_grant_store() {
    check_private_grant_directory "$grant_state"
    check_private_grant_directory "$1"
    check_grant_mount "$grant_state"
    check_grant_mount "$1"
    for grant_entry in "$1"/* "$1"/.[!.]* "$1"/..?*; do
        [ ! -L "$grant_entry" ] || refuse_grant_cleanup
        [ -e "$grant_entry" ] || continue
        [ -f "$grant_entry" ] || refuse_grant_cleanup
        check_grant_mount "$grant_entry"
    done
}

discard_enforcement_snapshot() {
    if [ -d "$grant_state" ]; then
        rm -f -- "$enforcement_snapshot"
        sync "$grant_state"
    fi
}

finish_grant_retirement() {
    if [ ! -e "$retired_grants" ] && [ ! -L "$retired_grants" ]; then
        return
    fi
    [ ! -e "$grant_store" ] && [ ! -L "$grant_store" ] || refuse_grant_cleanup
    check_grant_store "$retired_grants"
    # The rename commits removal. Flush it before dropping rollback material,
    # and flush the snapshot deletion before erasing the retirement marker.
    sync "$grant_state"
    discard_enforcement_snapshot
    find "$retired_grants" -mindepth 1 -maxdepth 1 -type f -delete
    rmdir -- "$retired_grants"
    sync "$grant_state"
}
