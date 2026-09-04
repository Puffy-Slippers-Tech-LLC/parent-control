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
    onpc_preview_shell_start_time=''
    onpc_preview_devkit_pid=''
    onpc_preview_devkit_start_time=''
    onpc_preview_devkit_path=/usr/libexec/mutter-devkit
    onpc_preview_bus_pid=''
    onpc_preview_bus_start_time=''
    onpc_preview_registry_pid=''
    onpc_preview_registry_start_time=''
    onpc_preview_pipewire_pid=''
    onpc_preview_pipewire_start_time=''
    onpc_preview_bus_address=''
    onpc_preview_stop_attempts=50
    onpc_preview_stop_interval=0.1
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
    [[ -x "$onpc_preview_devkit_path" ]] || {
        printf '%s\n' 'Mutter Devkit is required for the child preview (install mutter-dev-bin on Ubuntu).' >&2
        return 1
    }
    [[ -d "$onpc_preview_schema_source" ]] || {
        printf 'GNOME settings schemas are missing from %s.\n' "$onpc_preview_schema_source" >&2
        return 1
    }
}

onpc_preview_require_lifecycle_dependencies() {
    local dependency
    for dependency in dbus-daemon gdbus gnome-extensions gnome-shell gsettings \
            glib-compile-schemas pipewire setsid; do
        command -v "$dependency" >/dev/null || {
            printf '%s is required for the child Shell lifecycle smoke.\n' "$dependency" >&2
            return 1
        }
    done
    [[ -x "$onpc_preview_devkit_path" ]] || {
        printf '%s\n' 'Mutter Devkit is required (install mutter-dev-bin on Ubuntu).' >&2
        return 1
    }
    onpc_preview_registry_path=''
    for dependency in /usr/lib/at-spi2-core/at-spi2-registryd \
            /usr/libexec/at-spi2-registryd /usr/lib/at-spi2-registryd; do
        if [[ -x "$dependency" ]]; then
            onpc_preview_registry_path=$dependency
            break
        fi
    done
    [[ -n "$onpc_preview_registry_path" ]] || {
        printf '%s\n' 'AT-SPI registryd is required (install at-spi2-core on Ubuntu).' >&2
        return 1
    }
}

onpc_preview_require_supported_shell_version() {
    case $(gnome-shell --version) in
        'GNOME Shell 50.'*) return 0 ;;
        *)
            printf '%s\n' 'The child Shell lifecycle smoke requires GNOME Shell 50.x.' >&2
            return 1
            ;;
    esac
}

onpc_preview_prepare_environment() {
    local extension_dir source repo_root schema_dir
    extension_dir="$onpc_preview_root/data/gnome-shell/extensions/$onpc_preview_uuid"
    schema_dir="$onpc_preview_root/schemas"
    repo_root="$(cd "$onpc_preview_source_dir/.." && pwd)"

    mkdir -p "$extension_dir" "$onpc_preview_root/config" "$onpc_preview_root/cache" \
        "$onpc_preview_root/state" "$onpc_preview_root/runtime" "$onpc_preview_root/home" \
        "$schema_dir" "$onpc_preview_log_dir"
    chmod 0700 "$onpc_preview_root/runtime"
    if [[ ${ONPC_PREVIEW_PAYLOAD_MODE:-symlink} == copy ]]; then
        # Exercise the same immutable payload list as installation.  In
        # particular, automated runs must not follow edits in the checkout
        # after Shell has started.
        make --no-print-directory -C "$repo_root" install-extension \
            EXTENSION_BASE="$onpc_preview_root/data" >/dev/null
    else
        # Keep source edits live for the interactive preview while limiting
        # Shell discovery to the temporary extension tree.
        for source in "$onpc_preview_source_dir"/*.js "$onpc_preview_source_dir"/*.mjs \
                "$onpc_preview_source_dir"/*.css "$onpc_preview_source_dir"/*.json; do
            [[ -e "$source" ]] || continue
            ln -s "$source" "$extension_dir/${source##*/}"
        done
        for source in "$repo_root"/data/{app_logo.png,company_logo.png,brand.json,app.json} \
                "$repo_root"/{LICENSE,COPYRIGHT,NOTICE}; do
            ln -s "$source" "$extension_dir/${source##*/}"
        done
    fi

    cp -a "$onpc_preview_schema_source/." "$schema_dir/"
    glib-compile-schemas "$schema_dir"

    export XDG_DATA_HOME="$onpc_preview_root/data"
    export XDG_CONFIG_HOME="$onpc_preview_root/config"
    export XDG_CACHE_HOME="$onpc_preview_root/cache"
    export XDG_STATE_HOME="$onpc_preview_root/state"
    export XDG_RUNTIME_DIR="$onpc_preview_root/runtime"
    export HOME="$onpc_preview_root/home"
    export GSETTINGS_BACKEND=keyfile
    export GSETTINGS_SCHEMA_DIR="$schema_dir"
    export OH_NO_PARENT_CONTROL_PREVIEW=1
    export PYTHONPATH="$repo_root:$repo_root/kiosk${PYTHONPATH:+:$PYTHONPATH}"
    export OH_NO_PARENT_CONTROL_REQUEST_APP="$(command -v python3) -m oh_no_parent_control_kiosk.main --preview --child-overlay --soundtrack $repo_root/data/Gearbox_Waltz.mp3"
    # Do not inherit an IDE's X11 setting into Mutter Devkit's Wayland display.
    unset GDK_BACKEND GI_TYPELIB_PATH GTK_EXE_PREFIX GTK_IM_MODULE \
        GTK_IM_MODULE_FILE GTK_MODULES GTK_PATH
    unset DISPLAY WAYLAND_DISPLAY
    gsettings set org.gnome.desktop.interface toolkit-accessibility true
    gsettings set org.gnome.shell disable-user-extensions false
    gsettings set org.gnome.shell enabled-extensions "['$onpc_preview_uuid']"
}

onpc_preview_build_shell_command() {
    if [[ -n ${onpc_preview_bus_address:-} ]]; then
        onpc_preview_shell_command=(gnome-shell --devkit --wayland --force-animations)
    else
        onpc_preview_shell_command=(dbus-run-session -- gnome-shell --devkit --wayland --force-animations)
    fi
}

onpc_preview_start_private_bus() {
    local deadline
    onpc_preview_bus_log_path="$onpc_preview_log_dir/session-bus.log"
    : >"$onpc_preview_bus_log_path"
    setsid dbus-daemon --session --nofork --print-address=1 \
        >>"$onpc_preview_bus_log_path" 2>&1 &
    onpc_preview_bus_pid=$!
    onpc_preview_record_owned_process "$onpc_preview_bus_pid" \
        onpc_preview_bus_start_time 'private session bus' || return
    deadline=$((SECONDS + onpc_preview_ready_timeout))
    while onpc_preview_process_is_running "$onpc_preview_bus_pid"; do
        IFS= read -r onpc_preview_bus_address <"$onpc_preview_bus_log_path" || true
        if [[ $onpc_preview_bus_address == unix:* ]]; then
            export DBUS_SESSION_BUS_ADDRESS="$onpc_preview_bus_address"
            export AT_SPI_BUS_ADDRESS="$onpc_preview_bus_address"
            return 0
        fi
        if (( SECONDS >= deadline )); then
            printf 'Private session bus did not publish an address within %ss; log: %s\n' \
                "$onpc_preview_ready_timeout" "$onpc_preview_bus_log_path" >&2
            return 1
        fi
        read -r -t 0.05 _ || true
    done
    printf 'Private session bus exited before readiness; log: %s\n' \
        "$onpc_preview_bus_log_path" >&2
    return 1
}

onpc_preview_start_pipewire() {
    local deadline
    onpc_preview_pipewire_log_path="$onpc_preview_log_dir/pipewire.log"
    setsid pipewire >"$onpc_preview_pipewire_log_path" 2>&1 &
    onpc_preview_pipewire_pid=$!
    onpc_preview_record_owned_process "$onpc_preview_pipewire_pid" \
        onpc_preview_pipewire_start_time 'private PipeWire' || return
    deadline=$((SECONDS + onpc_preview_ready_timeout))
    while onpc_preview_process_is_running "$onpc_preview_pipewire_pid"; do
        [[ -S "$XDG_RUNTIME_DIR/pipewire-0" ]] && return 0
        if (( SECONDS >= deadline )); then
            printf 'Private PipeWire did not become ready within %ss; log: %s\n' \
                "$onpc_preview_ready_timeout" "$onpc_preview_pipewire_log_path" >&2
            return 1
        fi
        read -r -t 0.05 _ || true
    done
    printf 'Private PipeWire exited before readiness; log: %s\n' \
        "$onpc_preview_pipewire_log_path" >&2
    return 1
}

onpc_preview_wait_for_bus_name() {
    local name=$1 log_path=$2
    if timeout "${onpc_preview_ready_timeout}s" \
            gdbus wait --address "$onpc_preview_bus_address" "$name"; then
        return 0
    fi
    printf 'Timed out waiting for private D-Bus name %s; log: %s\n' \
        "$name" "$log_path" >&2
    return 1
}

onpc_preview_start_accessibility() {
    onpc_preview_registry_log_path="$onpc_preview_log_dir/at-spi-registry.log"
    setsid "$onpc_preview_registry_path" >"$onpc_preview_registry_log_path" 2>&1 &
    onpc_preview_registry_pid=$!
    onpc_preview_record_owned_process "$onpc_preview_registry_pid" \
        onpc_preview_registry_start_time 'AT-SPI registry' || return
    onpc_preview_wait_for_bus_name org.a11y.atspi.Registry \
        "$onpc_preview_registry_log_path"
}

onpc_preview_start() {
    local generation=$1
    onpc_preview_build_shell_command
    onpc_preview_log_path="$onpc_preview_log_dir/child-preview-generation-$generation.log"
    # A new session leader lets cleanup terminate dbus-run-session and every
    # helper it owns, including when the wrapper receives a signal.
    setsid "${onpc_preview_shell_command[@]}" >"$onpc_preview_log_path" 2>&1 &
    onpc_preview_shell_pid=$!
    onpc_preview_record_owned_process "$onpc_preview_shell_pid" \
        onpc_preview_shell_start_time 'GNOME Shell'
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
    local candidate='' discovery_status=0 status=0
    if [[ -z ${onpc_preview_devkit_pid:-} \
            && -n ${onpc_preview_shell_pid:-} \
            && -n ${onpc_preview_shell_start_time:-} ]] \
            && candidate=$(onpc_preview_find_mutter_devkit_descendant); then
        onpc_preview_devkit_pid=$candidate
        onpc_preview_record_owned_process "$onpc_preview_devkit_pid" \
            onpc_preview_devkit_start_time 'Mutter Devkit' || status=1
    else
        discovery_status=$?
        if (( discovery_status > 1 )); then
            status=1
        fi
    fi
    if [[ -n ${onpc_preview_shell_pid:-} ]]; then
        onpc_preview_stop_owned_process "$onpc_preview_shell_pid" \
            "${onpc_preview_shell_start_time:-}" 'GNOME Shell' || status=1
        onpc_preview_shell_pid=''
        onpc_preview_shell_start_time=''
    fi
    if [[ -n ${onpc_preview_devkit_pid:-} ]]; then
        onpc_preview_stop_owned_process "$onpc_preview_devkit_pid" \
            "${onpc_preview_devkit_start_time:-}" 'Mutter Devkit' || status=1
        onpc_preview_devkit_pid=''
        onpc_preview_devkit_start_time=''
    fi
    return "$status"
}

onpc_preview_read_process_identity() {
    local pid=$1 process_stat
    local -a fields
    [[ $pid =~ ^[0-9]+$ && -r /proc/$pid/stat ]] || return 1
    IFS= read -r process_stat <"/proc/$pid/stat" || return 1
    # The command name is parenthesized and may itself contain spaces or a
    # closing parenthesis. Remove through the final ") " before indexing the
    # stable fields that follow it.
    process_stat=${process_stat##*) }
    [[ -n $process_stat ]] || return 1
    read -r -a fields <<<"$process_stat"
    (( ${#fields[@]} >= 20 )) || return 1
    # state, process group, session, and kernel start time respectively.
    printf '%s %s %s %s\n' \
        "${fields[0]}" "${fields[2]}" "${fields[3]}" "${fields[19]}"
}

onpc_preview_record_owned_process() {
    local pid=$1 start_time_variable=$2 label=$3
    local max_attempts=${4:-50} retry_interval=${5:-0.01}
    local attempt process_group session start_time state
    printf -v "$start_time_variable" '%s' ''
    for (( attempt = 0; attempt < max_attempts; attempt++ )); do
        if IFS=' ' read -r state process_group session start_time \
                < <(onpc_preview_read_process_identity "$pid"); then
            printf -v "$start_time_variable" '%s' "$start_time"
            if [[ $state != Z && $process_group == "$pid" && $session == "$pid" ]]; then
                return 0
            fi
        else
            printf '%s process %s exited before ownership could be recorded.\n' \
                "$label" "$pid" >&2
            return 1
        fi
        sleep "$retry_interval"
    done
    printf '%s process %s did not become its expected session and process-group leader.\n' \
        "$label" "$pid" >&2
    return 1
}

onpc_preview_process_parent() {
    local pid=$1 field value remainder
    [[ $pid =~ ^[0-9]+$ && -r /proc/$pid/status ]] || return 1
    while read -r field value remainder; do
        if [[ $field == PPid: ]]; then
            [[ $value =~ ^[0-9]+$ ]] || return 1
            printf '%s\n' "$value"
            return 0
        fi
    done <"/proc/$pid/status"
    return 1
}

onpc_preview_process_is_descendant_of() {
    local process_id=$1 ancestor_id=$2 depth parent_id
    for (( depth = 0; depth < 64; depth++ )); do
        parent_id=$(onpc_preview_process_parent "$process_id") || return 1
        [[ $parent_id == "$ancestor_id" ]] && return 0
        (( parent_id > 1 )) || return 1
        process_id=$parent_id
    done
    return 1
}

onpc_preview_find_mutter_devkit_descendant() {
    local child children_path found='' index=0 parent
    local -a children queue
    onpc_preview_owned_process_identity_matches \
        "${onpc_preview_shell_pid:-}" "${onpc_preview_shell_start_time:-}" || return 1
    queue=("$onpc_preview_shell_pid")
    while (( index < ${#queue[@]} )); do
        parent=${queue[index++]}
        children_path="/proc/$parent/task/$parent/children"
        [[ -r $children_path ]] || continue
        children=()
        read -r -a children <"$children_path" || true
        for child in "${children[@]}"; do
            [[ $child =~ ^[0-9]+$ ]] || continue
            (( ${#queue[@]} < 4096 )) || {
                printf '%s\n' 'Refusing Mutter Devkit discovery because the owned Shell descendant tree exceeded 4096 processes.' >&2
                return 2
            }
            queue+=("$child")
            [[ /proc/$child/exe -ef "$onpc_preview_devkit_path" ]] || continue
            onpc_preview_process_is_descendant_of \
                "$child" "$onpc_preview_shell_pid" || continue
            if [[ -n $found ]]; then
                printf '%s\n' 'Refusing Mutter Devkit discovery because multiple matching owned descendants were found.' >&2
                return 2
            fi
            found=$child
        done
    done
    [[ -n $found ]] || return 1
    printf '%s\n' "$found"
}

onpc_preview_record_mutter_devkit() {
    local candidate='' deadline discovery_status
    [[ -z ${onpc_preview_devkit_pid:-} ]] || return 0
    deadline=$((SECONDS + onpc_preview_ready_timeout))
    while onpc_preview_owned_process_identity_matches \
            "${onpc_preview_shell_pid:-}" "${onpc_preview_shell_start_time:-}"; do
        if candidate=$(onpc_preview_find_mutter_devkit_descendant); then
            onpc_preview_devkit_pid=$candidate
            onpc_preview_record_owned_process "$onpc_preview_devkit_pid" \
                onpc_preview_devkit_start_time 'Mutter Devkit' \
                "$((onpc_preview_ready_timeout * 20 + 1))" 0.05 || return
            if ! [[ /proc/$onpc_preview_devkit_pid/exe -ef "$onpc_preview_devkit_path" ]] \
                    || ! onpc_preview_process_is_descendant_of \
                        "$onpc_preview_devkit_pid" "$onpc_preview_shell_pid"; then
                printf '%s\n' 'Refusing Mutter Devkit ownership because its executable or Shell ancestry changed during registration.' >&2
                return 1
            fi
            printf 'Recorded owned Mutter Devkit process group %s from the GNOME Shell descendant tree.\n' \
                "$onpc_preview_devkit_pid" >&2
            return 0
        else
            discovery_status=$?
            (( discovery_status == 1 )) || return "$discovery_status"
        fi
        if (( SECONDS >= deadline )); then
            printf 'Mutter Devkit did not appear as an owned GNOME Shell descendant within %ss.\n' \
                "$onpc_preview_ready_timeout" >&2
            return 1
        fi
        sleep 0.05
    done
    printf '%s\n' 'GNOME Shell exited before Mutter Devkit ownership could be recorded.' >&2
    return 1
}

onpc_preview_owned_process_identity_matches() {
    local pid=$1 expected_start_time=$2
    local process_group session start_time state
    [[ -n $expected_start_time ]] || return 1
    IFS=' ' read -r state process_group session start_time \
        < <(onpc_preview_read_process_identity "$pid") || return 1
    [[ -n $state && -n $process_group && -n $session \
        && $start_time == "$expected_start_time" ]]
}

onpc_preview_owned_process_is_group_leader() {
    local pid=$1 expected_start_time=$2
    local process_group session start_time state
    [[ -n $expected_start_time ]] || return 1
    IFS=' ' read -r state process_group session start_time \
        < <(onpc_preview_read_process_identity "$pid") || return 1
    [[ $start_time == "$expected_start_time" \
        && $process_group == "$pid" && $session == "$pid" ]]
}

onpc_preview_owned_process_is_running() {
    local pid=$1 expected_start_time=$2
    local process_group session start_time state
    IFS=' ' read -r state process_group session start_time \
        < <(onpc_preview_read_process_identity "$pid") || return 1
    [[ $state != Z && -n $process_group && -n $session \
        && $start_time == "$expected_start_time" ]]
}

onpc_preview_stop_owned_process() {
    local pid=$1 expected_start_time=$2 label=$3 attempt
    [[ $pid =~ ^[0-9]+$ && -n $expected_start_time ]] || {
        printf 'Refusing to signal %s because no complete owned-process identity was recorded.\n' \
            "$label" >&2
        return 1
    }
    if ! onpc_preview_owned_process_identity_matches "$pid" "$expected_start_time"; then
        if onpc_preview_process_group_is_running "$pid"; then
            printf 'Refusing to signal %s process group %s because its recorded leader identity no longer matches.\n' \
                "$label" "$pid" >&2
            return 1
        fi
        wait "$pid" 2>/dev/null || true
        return 0
    fi
    if ! onpc_preview_owned_process_is_group_leader "$pid" "$expected_start_time"; then
        if ! onpc_preview_owned_process_is_running "$pid" "$expected_start_time"; then
            wait "$pid" 2>/dev/null || true
            return 0
        fi
        printf 'Stopping explicitly owned %s process %s by PID because it is not the recorded session and process-group leader.\n' \
            "$label" "$pid" >&2
        kill -TERM -- "$pid" 2>/dev/null || true
        for (( attempt = 0; attempt < onpc_preview_stop_attempts; attempt++ )); do
            onpc_preview_owned_process_is_running \
                "$pid" "$expected_start_time" || break
            sleep "$onpc_preview_stop_interval"
        done
        if onpc_preview_owned_process_is_running "$pid" "$expected_start_time"; then
            printf 'Explicitly owned %s process %s ignored SIGTERM; escalating that PID to SIGKILL.\n' \
                "$label" "$pid" >&2
            kill -KILL -- "$pid" 2>/dev/null || true
            for (( attempt = 0; attempt < onpc_preview_stop_attempts; attempt++ )); do
                onpc_preview_owned_process_is_running \
                    "$pid" "$expected_start_time" || break
                sleep "$onpc_preview_stop_interval"
            done
        fi
        wait "$pid" 2>/dev/null || true
        if onpc_preview_owned_process_is_running "$pid" "$expected_start_time"; then
            printf '%s process %s survived direct SIGKILL.\n' "$label" "$pid" >&2
            return 1
        fi
        return 0
    fi
    if ! onpc_preview_process_group_is_running "$pid"; then
        wait "$pid" 2>/dev/null || true
        return 0
    fi

    printf 'Stopping owned %s process group %s with SIGTERM.\n' "$label" "$pid" >&2
    kill -TERM -- "-$pid" 2>/dev/null || true
    for (( attempt = 0; attempt < onpc_preview_stop_attempts; attempt++ )); do
        onpc_preview_process_group_is_running "$pid" || break
        sleep "$onpc_preview_stop_interval"
    done
    if onpc_preview_process_group_is_running "$pid"; then
        if ! onpc_preview_owned_process_is_group_leader "$pid" "$expected_start_time"; then
            printf 'Refusing SIGKILL for %s process group %s because its recorded leader identity no longer matches.\n' \
                "$label" "$pid" >&2
            return 1
        fi
        printf 'Owned %s process group %s ignored SIGTERM; escalating to SIGKILL.\n' \
            "$label" "$pid" >&2
        kill -KILL -- "-$pid" 2>/dev/null || true
        for (( attempt = 0; attempt < onpc_preview_stop_attempts; attempt++ )); do
            onpc_preview_process_group_is_running "$pid" || break
            sleep "$onpc_preview_stop_interval"
        done
    fi
    wait "$pid" 2>/dev/null || true
    if onpc_preview_process_group_is_running "$pid"; then
        printf '%s process group %s survived SIGKILL.\n' "$label" "$pid" >&2
        return 1
    fi
}

onpc_preview_process_group_is_running() {
    local pid=$1
    # procps does not expose a portable process-group selector. Enumerate only
    # status and process-group metadata, then match the already recorded group;
    # this never infers ownership from environment or other ambient state.
    LC_ALL=C ps -e -o stat= -o pgrp= 2>/dev/null \
        | awk -v expected="$pid" \
            '$2 == expected && $1 !~ /^Z/ { found = 1 } END { exit !found }'
}

onpc_preview_stop_private_services() {
    local status=0
    if [[ -n ${onpc_preview_registry_pid:-} ]]; then
        onpc_preview_stop_owned_process "$onpc_preview_registry_pid" \
            "${onpc_preview_registry_start_time:-}" \
            'AT-SPI registry' || status=1
        onpc_preview_registry_pid=''
        onpc_preview_registry_start_time=''
    fi
    if [[ -n ${onpc_preview_pipewire_pid:-} ]]; then
        onpc_preview_stop_owned_process "$onpc_preview_pipewire_pid" \
            "${onpc_preview_pipewire_start_time:-}" \
            'private PipeWire' || status=1
        onpc_preview_pipewire_pid=''
        onpc_preview_pipewire_start_time=''
    fi
    if [[ -n ${onpc_preview_bus_pid:-} ]]; then
        onpc_preview_stop_owned_process "$onpc_preview_bus_pid" \
            "${onpc_preview_bus_start_time:-}" \
            'private session bus' || status=1
        onpc_preview_bus_pid=''
        onpc_preview_bus_start_time=''
    fi
    return "$status"
}

onpc_preview_cleanup() {
    local status=0
    onpc_preview_stop_shell || status=1
    onpc_preview_stop_private_services || status=1
    # The wrapper creates this private root with mktemp. Refuse broad or
    # caller-supplied locations before removing its isolated runtime state.
    [[ ${onpc_preview_root:-} == /tmp/* && "$onpc_preview_root" != /tmp/ ]] || return "$status"
    rm -rf -- "$onpc_preview_root"
    return "$status"
}
