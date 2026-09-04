#!/usr/bin/env bash
# Reusable lifecycle helpers for the isolated child-extension preview.  This
# file is intentionally sourceable: Task 10B supplies a real Shell readiness
# probe without duplicating preview setup or teardown.

onpc_preview_configure() {
    onpc_preview_source_dir=$1
    onpc_preview_root=$2
    onpc_preview_uuid=${3:-oh-no-parent-control@tech.puffyslippers.com}
    onpc_preview_schema_source=${ONPC_PREVIEW_SYSTEM_SCHEMA_DIR:-/usr/share/glib-2.0/schemas}
    onpc_preview_ready_timeout=${ONPC_PREVIEW_READY_TIMEOUT_SECONDS:-30}
    onpc_preview_generation=0
    onpc_preview_shell_pid=''
    onpc_preview_log_dir="$onpc_preview_root/logs"
}

onpc_preview_require_dependencies() {
    local dependency
    for dependency in gnome-shell gsettings dbus-run-session glib-compile-schemas inotifywait setsid; do
        command -v "$dependency" >/dev/null || {
            printf '%s is required for the child preview.\n' "$dependency" >&2
            return 1
        }
    done
    [[ -x /usr/libexec/mutter-devkit ]] || {
        printf '%s\n' 'Mutter Devkit is required for the child preview (install mutter-dev-bin on Ubuntu).' >&2
        return 1
    }
    [[ -d "$onpc_preview_schema_source" ]] || {
        printf 'GNOME settings schemas are missing from %s.\n' "$onpc_preview_schema_source" >&2
        return 1
    }
}

onpc_preview_prepare_environment() {
    local extension_dir source repo_root schema_dir
    extension_dir="$onpc_preview_root/data/gnome-shell/extensions/$onpc_preview_uuid"
    schema_dir="$onpc_preview_root/schemas"
    repo_root="$(cd "$onpc_preview_source_dir/.." && pwd)"

    mkdir -p "$extension_dir" "$onpc_preview_root/config" "$schema_dir" "$onpc_preview_log_dir"
    # Keep source edits live while limiting Shell discovery to the temporary
    # extension tree. The preview never writes checkout files.
    for source in "$onpc_preview_source_dir"/*.js "$onpc_preview_source_dir"/*.mjs \
            "$onpc_preview_source_dir"/*.css "$onpc_preview_source_dir"/*.json; do
        [[ -e "$source" ]] || continue
        ln -s "$source" "$extension_dir/${source##*/}"
    done
    for source in "$repo_root"/data/{app_logo.png,company_logo.png,brand.json,app.json} "$repo_root"/LICENSE; do
        ln -s "$source" "$extension_dir/${source##*/}"
    done

    cp -a "$onpc_preview_schema_source/." "$schema_dir/"
    glib-compile-schemas "$schema_dir"

    export XDG_DATA_HOME="$onpc_preview_root/data"
    export XDG_CONFIG_HOME="$onpc_preview_root/config"
    export GSETTINGS_BACKEND=keyfile
    export GSETTINGS_SCHEMA_DIR="$schema_dir"
    export OH_NO_PARENT_CONTROL_PREVIEW=1
    export PYTHONPATH="$repo_root:$repo_root/kiosk${PYTHONPATH:+:$PYTHONPATH}"
    export OH_NO_PARENT_CONTROL_REQUEST_APP="$(command -v python3) -m oh_no_parent_control_kiosk.main --preview --child-overlay --soundtrack $repo_root/data/Gearbox_Waltz.mp3"
    # Do not inherit an IDE's X11 setting into Mutter Devkit's Wayland display.
    unset GDK_BACKEND
    gsettings set org.gnome.shell enabled-extensions "['$onpc_preview_uuid']"
}

onpc_preview_build_shell_command() {
    onpc_preview_shell_command=(dbus-run-session -- gnome-shell --devkit --wayland --force-animations)
}

onpc_preview_start() {
    local generation=$1
    onpc_preview_build_shell_command
    onpc_preview_log_path="$onpc_preview_log_dir/child-preview-generation-$generation.log"
    # A new session leader lets cleanup terminate dbus-run-session and every
    # helper it owns, including when the wrapper receives a signal.
    setsid "${onpc_preview_shell_command[@]}" >"$onpc_preview_log_path" 2>&1 &
    onpc_preview_shell_pid=$!
}

onpc_preview_process_is_running() {
    kill -0 "$1" 2>/dev/null
}

onpc_preview_wait_for_readiness() {
    local pid=$1 generation=$2 deadline now
    deadline=$((SECONDS + onpc_preview_ready_timeout))
    while onpc_preview_process_is_running "$pid"; do
        if [[ -n ${ONPC_PREVIEW_READY_PROBE:-} ]] && "$ONPC_PREVIEW_READY_PROBE" "$pid" "$generation"; then
            return 0
        fi
        now=$SECONDS
        if (( now >= deadline )); then
            printf 'Child preview generation %s did not become ready within %ss; log: %s\n' \
                "$generation" "$onpc_preview_ready_timeout" "$onpc_preview_log_path" >&2
            return 1
        fi
        sleep 0.1
    done
    printf 'Child preview generation %s exited before readiness; log: %s\n' \
        "$generation" "$onpc_preview_log_path" >&2
    return 1
}

onpc_preview_source_event_is_reloadable() {
    case $1 in
        *.js|*.mjs|*.css|*.json) return 0 ;;
        *) return 1 ;;
    esac
}

onpc_preview_wait_for_reload() {
    local pid=$1 event
    while onpc_preview_process_is_running "$pid"; do
        # inotifywait supplies an event-driven bounded wait. Checking the
        # process after every one-second deadline also reports a Shell exit.
        event="$(inotifywait --quiet --recursive --event close_write,moved_to,create,delete \
            --format '%w%f' --timeout 1 "$onpc_preview_source_dir" 2>/dev/null)" || true
        [[ -n "$event" ]] && onpc_preview_source_event_is_reloadable "$event" && return 0
    done
    return 1
}

onpc_preview_stop_shell() {
    local pid=${onpc_preview_shell_pid:-}
    [[ -n "$pid" ]] || return 0
    if kill -0 "$pid" 2>/dev/null; then
        # Address the session leader first: immediately after a background
        # launch it may not have completed setsid yet, so its process group is
        # not reliable during that short handoff.
        kill "$pid" 2>/dev/null || true
        kill -- "-$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
    onpc_preview_shell_pid=''
}

onpc_preview_cleanup() {
    onpc_preview_stop_shell
    # The wrapper creates this private root with mktemp. Refuse broad or
    # caller-supplied locations before removing its isolated runtime state.
    [[ ${onpc_preview_root:-} == /tmp/* && "$onpc_preview_root" != /tmp/ ]] || return 0
    rm -rf -- "$onpc_preview_root"
}
