#ifndef ONPC_KIOSK_MATERIAL_AUTHORITY_H
#define ONPC_KIOSK_MATERIAL_AUTHORITY_H
/* Semantic M authority, independent of V/I and helper source assertions.
 * The caller supplies independently attested config/policy bytes, a preloaded
 * crypto handle and its original absolute monotonic transaction deadline.
 * Decoding proves only the finite required names/classes/content contract.
 * kiosk_host_proof_capture_until() must still observe original-host objects,
 * followed by kiosk_material_verify_host_until() for sizes/ELF/source modes;
 * actual copies, clone provenance, mounts and publication need their own proofs.
 */
#include "kiosk_host_proof.h"
#include "kiosk_view_receipt.h"
#include <dirent.h>

struct kiosk_material_spec {
    const char *path, *source, *kind, *source_class, *role;
    const char *sha256, *source_label, *label, *link;
    uint64_t size;
    mode_t mode;
    int privileged, terminal_link;
};
struct kiosk_material_json_node {
    char *key, *text;
    uint64_t number;
    unsigned child, next, count;
    char type;
};
struct kiosk_material_json {
    char *storage, *p, *end;
    struct kiosk_material_json_node *nodes;
    unsigned used, capacity;
    uint64_t deadline;
};
struct kiosk_material_proof { const char *path, *kind, *link; int used; };
struct kiosk_material_route {
    const char *path, *role, *source, *library_directory;
    int optional, selected;
};
struct kiosk_material_authority {
    struct kiosk_material_json material_json, config_json;
    const char *backend;
    char digest[65], config_digest[65], policy_digest[65];
    struct kiosk_material_spec *specs;
    struct kiosk_host_spec *host_specs;
    struct kiosk_material_proof *proofs;
    /* Every finite config candidate, including unselected optional names.
     * verify_routes_until observes absence and declared library membership
     * independently of M. These routes confer no sources. */
    struct kiosk_material_route *routes;
    unsigned count, host_count, proof_count, route_count;
    uint64_t copy_bytes, deadline;
};

static inline void kiosk_material_free(struct kiosk_material_authority *a)
{
    free(a->material_json.storage); free(a->material_json.nodes);
    free(a->config_json.storage); free(a->config_json.nodes);
    free(a->specs); free(a->host_specs); free(a->proofs); free(a->routes);
    memset(a, 0, sizeof(*a));
}

static inline void kiosk_material_space(struct kiosk_material_json *j)
{ while (j->p < j->end && strchr(" \n\r\t", *j->p)) j->p++; }

static inline int kiosk_material_hex4(struct kiosk_material_json *j, unsigned *value)
{
    *value = 0;
    if (j->end - j->p < 4) return -1;
    for (unsigned i = 0; i < 4; i++) {
        char c = *j->p++;
        unsigned n = c >= '0' && c <= '9' ? (unsigned)(c - '0') :
            c >= 'a' && c <= 'f' ? (unsigned)(c - 'a' + 10) :
            c >= 'A' && c <= 'F' ? (unsigned)(c - 'A' + 10) : 16;
        if (n == 16) return -1;
        *value = *value * 16 + n;
    }
    return 0;
}

/* Decode JSON strings without a locale, embedded NUL or lone surrogate.
 * Product paths/labels additionally pass the protocol text/path validators. */
static inline char *kiosk_material_string(struct kiosk_material_json *j)
{
    if (j->p == j->end || *j->p++ != '"') return NULL;
    char *start = j->p, *out = start;
    while (j->p < j->end) {
        unsigned char c = (unsigned char)*j->p++;
        if (c == '"') { *out = 0; return start; }
        if (c < 32) return NULL;
        if (c != '\\') { *out++ = (char)c; continue; }
        if (j->p == j->end) return NULL;
        c = (unsigned char)*j->p++;
        static const char escape_names[] = "\"\\/bfnrt";
        static const char escape_values[] = "\"\\/\b\f\n\r\t";
        const char *escaped = strchr(escape_names, c);
        if (escaped) { *out++ = escape_values[escaped - escape_names]; continue; }
        unsigned value;
        if (c != 'u' || kiosk_material_hex4(j, &value) != 0 || value == 0) return NULL;
        if (value >= 0xd800 && value <= 0xdbff) {
            unsigned low;
            if (j->end - j->p < 6 || *j->p++ != '\\' || *j->p++ != 'u' ||
                kiosk_material_hex4(j, &low) != 0 || low < 0xdc00 || low > 0xdfff) return NULL;
            value = 0x10000 + ((value - 0xd800) << 10) + low - 0xdc00;
        } else if (value >= 0xdc00 && value <= 0xdfff) return NULL;
        if (value < 128) *out++ = (char)value;
        else if (value < 2048) { *out++ = (char)(0xc0 | (value >> 6)); *out++ = (char)(0x80 | (value & 63)); }
        else if (value < 65536) {
            *out++ = (char)(0xe0 | (value >> 12)); *out++ = (char)(0x80 | ((value >> 6) & 63));
            *out++ = (char)(0x80 | (value & 63));
        } else {
            *out++ = (char)(0xf0 | (value >> 18)); *out++ = (char)(0x80 | ((value >> 12) & 63));
            *out++ = (char)(0x80 | ((value >> 6) & 63)); *out++ = (char)(0x80 | (value & 63));
        }
    }
    return NULL;
}

static inline unsigned kiosk_material_value(struct kiosk_material_json *j, unsigned depth)
{
    kiosk_material_space(j);
    if (depth > 64 || j->p == j->end || j->used >= KIOSK_RECEIPT_ROWS * 64U ||
        kiosk_receipt_before(j->deadline) != 0) return 0;
    if (j->used + 1 >= j->capacity) {
        unsigned capacity = j->capacity ? j->capacity * 2 : 256;
        if ((size_t)capacity * sizeof(*j->nodes) > KIOSK_RECEIPT_BYTES) return 0;
        void *allocation = realloc(j->nodes, (size_t)capacity * sizeof(*j->nodes));
        if (!allocation) return 0;
        j->nodes = allocation; j->capacity = capacity;
    }
    unsigned index = ++j->used;
    memset(j->nodes + index, 0, sizeof(*j->nodes));
    char c = *j->p;
    j->nodes[index].type = c;
    if (c == '"') {
        j->nodes[index].text = kiosk_material_string(j);
        return j->nodes[index].text ? index : 0;
    }
    if (c == '[' || c == '{') {
        char close = c == '[' ? ']' : '}'; j->p++; kiosk_material_space(j);
        if (j->p < j->end && *j->p == close) { j->p++; return index; }
        unsigned previous = 0;
        for (;;) {
            char *key = NULL;
            if (c == '{') {
                key = kiosk_material_string(j);
                if (!key) return 0;
                for (unsigned n = j->nodes[index].child; n; n = j->nodes[n].next) {
                    if (kiosk_receipt_before(j->deadline) || !strcmp(j->nodes[n].key, key)) return 0;
                }
                kiosk_material_space(j);
                if (j->p == j->end || *j->p++ != ':') return 0;
            }
            unsigned child = kiosk_material_value(j, depth + 1);
            if (!child) return 0;
            j->nodes[child].key = key;
            if (previous) j->nodes[previous].next = child; else j->nodes[index].child = child;
            previous = child; j->nodes[index].count++;
            kiosk_material_space(j);
            if (j->p == j->end) return 0;
            if (*j->p == close) { j->p++; return index; }
            if (*j->p++ != ',') return 0;
            kiosk_material_space(j);
        }
    }
    const char *literal = c == 'n' ? "null" : c == 't' ? "true" : c == 'f' ? "false" : NULL;
    if (literal) {
        size_t n = strlen(literal);
        if ((size_t)(j->end - j->p) < n || memcmp(j->p, literal, n)) return 0;
        j->p += n; return index;
    }
    /* All material/config numbers are nonnegative bounded integers. */
    if (c < '0' || c > '9') return 0;
    uint64_t value = 0; char *start = j->p;
    do {
        unsigned digit = (unsigned)(*j->p++ - '0');
        if (value > ((uint64_t)INT64_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    } while (j->p < j->end && *j->p >= '0' && *j->p <= '9');
    if (*start == '0' && j->p - start != 1) return 0;
    j->nodes[index].type = '#'; j->nodes[index].number = value; return index;
}

static inline int kiosk_material_json_parse(struct kiosk_material_json *j, const void *bytes,
                                            size_t size, uint64_t deadline)
{
    if (!bytes || !size || size > KIOSK_RECEIPT_BYTES || memchr(bytes, 0, size)) return -1;
    j->storage = malloc(size + 1);
    if (!j->storage) return -1;
    memcpy(j->storage, bytes, size); j->storage[size] = 0;
    j->p = j->storage; j->end = j->p + size; j->deadline = deadline;
    if (kiosk_material_value(j, 0) != 1) return -1;
    kiosk_material_space(j);
    return j->p == j->end && j->nodes[1].type == '{' ? 0 : -1;
}

static inline unsigned kiosk_material_get(const struct kiosk_material_json *j, unsigned object, const char *key)
{
    if (!object || j->nodes[object].type != '{') return 0;
    for (unsigned n = j->nodes[object].child; n; n = j->nodes[n].next) {
        if (kiosk_receipt_before(j->deadline)) return 0;
        if (!strcmp(j->nodes[n].key, key)) return n;
    }
    return 0;
}
static inline const char *kiosk_material_text(const struct kiosk_material_json *j, unsigned n)
{ return n && j->nodes[n].type == '"' ? j->nodes[n].text : NULL; }
static inline const char *kiosk_material_property(const struct kiosk_material_json *j, unsigned n, const char *key)
{ return kiosk_material_text(j, kiosk_material_get(j, n, key)); }
static inline int kiosk_material_number(const struct kiosk_material_json *j, unsigned n, const char *key, uint64_t *value)
{
    unsigned member = kiosk_material_get(j, n, key);
    if (!member || j->nodes[member].type != '#') return -1;
    *value = j->nodes[member].number; return 0;
}
static inline int kiosk_material_schema(const struct kiosk_material_json *j, unsigned n, const char *keys, unsigned count)
{
    if (!n || j->nodes[n].type != '{' || j->nodes[n].count != count) return -1;
    for (unsigned child = j->nodes[n].child; child; child = j->nodes[child].next) {
        if (kiosk_receipt_before(j->deadline)) return -1;
        const char *key = j->nodes[child].key; size_t size = strlen(key); int found = 0;
        for (const char *p = keys; *p;) {
            const char *end = strchr(p, '|'); size_t len = end ? (size_t)(end - p) : strlen(p);
            if (len == size && !memcmp(p, key, size)) { found = 1; break; }
            p += len; if (*p) p++;
        }
        if (!found) return -1;
    }
    return 0;
}
static inline int kiosk_material_path(const char *path)
{
    if (!path || !kiosk_receipt_text(path) || *path != '/') return 0;
    if (!path[1]) return 1;
    for (const char *p = path + 1; *p;) {
        const char *end = strchr(p, '/'); size_t n = end ? (size_t)(end - p) : strlen(p);
        if (!n || (n == 1 && *p == '.') || (n == 2 && !memcmp(p, "..", 2))) return 0;
        if (!end) return 1;
        p = end + 1;
    }
    return 0;
}
static inline int kiosk_material_usr(const char *path)
{ return kiosk_material_path(path) && (!strcmp(path, "/usr") || !strncmp(path, "/usr/", 5)); }
static inline int kiosk_material_equal(const char *a, const char *b)
{ return a && b && !strcmp(a, b); }
static inline const char *kiosk_material_label(const struct kiosk_material_json *j, unsigned n, const char *key, const char *backend)
{
    unsigned member = kiosk_material_get(j, n, key);
    if (!member) return NULL;
    if (!strcmp(backend, "apparmor")) return j->nodes[member].type == 'n' ? "-" : NULL;
    const char *text = kiosk_material_text(j, member);
    if (!text || !kiosk_receipt_text(text) || strlen(text) >= 256) return NULL;
    for (const char *p = text; *p; p++)
        if (!strchr("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_:.,-", *p)) return NULL;
    return text;
}

static inline struct kiosk_material_proof *kiosk_material_proof_find(struct kiosk_material_authority *a, const char *path)
{
    unsigned low = 0, high = a->proof_count;
    while (low < high) {
        unsigned mid = low + (high - low) / 2;
        if (strcmp(a->proofs[mid].path, path) < 0) low = mid + 1; else high = mid;
    }
    return low < a->proof_count && !strcmp(a->proofs[low].path, path) ? a->proofs + low : NULL;
}

/* Walk only declared component/link text; no kernel lookup or ambient source.
 * Every lexical endpoint and every expanded target/component must be present.
 * Terminal links are reserved for config-declared runtime links, e.g. masks. */
static inline int kiosk_material_resolve(struct kiosk_material_authority *a, const char *path,
                                        int terminal, int mark, char resolved[PATH_MAX])
{
    if (!kiosk_material_path(path)) return -1;
    struct kiosk_material_proof *lexical = kiosk_material_proof_find(a, path);
    if (!lexical) return -1;
    char current[PATH_MAX] = "/", pending[PATH_MAX]; strcpy(pending, path + 1);
    unsigned links = 0, steps = 0;
    for (;;) {
        if (++steps > KIOSK_RECEIPT_ROWS || kiosk_receipt_before(a->deadline) != 0) return -1;
        struct kiosk_material_proof *p = kiosk_material_proof_find(a, current);
        if (!p) return -1;
        if (mark) p->used = 1;
        if (!pending[0] && terminal) {
            if (strcmp(p->kind, lexical->kind) || strcmp(p->link, lexical->link)) return -1;
            break;
        }
        if (!strcmp(p->kind, "link")) {
            if (++links > 40) return -1;
            char expanded[PATH_MAX];
            int n = snprintf(expanded, sizeof(expanded), "%s%s%s", p->link + (p->link[0] == '/'),
                             pending[0] ? "/" : "", pending);
            if (n < 0 || n >= PATH_MAX) return -1;
            if (p->link[0] == '/') strcpy(current, "/");
            else { char *slash = strrchr(current, '/'); if (slash == current) current[1] = 0; else *slash = 0; }
            strcpy(pending, expanded); continue;
        }
        if (!pending[0]) {
            if (strcmp(lexical->kind, "link") && (strcmp(p->kind, lexical->kind) || strcmp(p->link, lexical->link))) return -1;
            break;
        }
        if (strcmp(p->kind, "directory")) return -1;
        char component[PATH_MAX], *slash = strchr(pending, '/');
        size_t n = slash ? (size_t)(slash - pending) : strlen(pending);
        memcpy(component, pending, n); component[n] = 0;
        memmove(pending, pending + n + (slash != NULL), strlen(pending + n + (slash != NULL)) + 1);
        if (!strcmp(component, ".") || !component[0]) continue;
        if (!strcmp(component, "..")) {
            char *last = strrchr(current, '/'); if (last == current) current[1] = 0; else *last = 0;
        } else {
            size_t used = strlen(current);
            if (used + n + 1 >= sizeof(current)) return -1;
            if (used != 1) strcat(current, "/");
            strcat(current, component);
        }
    }
    if (mark) lexical->used = 1;
    if (resolved) strcpy(resolved, current);
    return 0;
}

static inline int kiosk_material_spec_compare(const void *left, const void *right)
{ return strcmp(((const struct kiosk_material_spec *)left)->path, ((const struct kiosk_material_spec *)right)->path); }
static inline const struct kiosk_material_spec *kiosk_material_find(const struct kiosk_material_authority *a, const char *path)
{
    unsigned low = 0, high = a->count;
    while (low < high) {
        unsigned mid = low + (high - low) / 2;
        if (strcmp(a->specs[mid].path, path) < 0) low = mid + 1; else high = mid;
    }
    return low < a->count && !strcmp(a->specs[low].path, path) ? a->specs + low : NULL;
}
static inline int kiosk_material_concrete(struct kiosk_material_authority *a, const char *path)
{
    if (!kiosk_material_usr(path)) return 0;
    char parent[PATH_MAX]; strcpy(parent, path);
    for (char *slash = strrchr(parent, '/'); slash && slash != parent; slash = strrchr(parent, '/')) {
        *slash = 0; struct kiosk_material_proof *p = kiosk_material_proof_find(a, parent);
        if (!p || strcmp(p->kind, "directory")) return 0;
    }
    return 1;
}
static inline int kiosk_material_host_file(struct kiosk_material_authority *a, const char *path,
                                          const char *sha, const char *label, mode_t mode, int privileged)
{
    if (label && !strcmp(label, "-")) label = NULL;
    char resolved[PATH_MAX];
    if (kiosk_material_resolve(a, path, 0, 1, resolved) || strcmp(path, resolved)) return -1;
    struct kiosk_material_proof *found = kiosk_material_proof_find(a, path);
    if (found) {
        struct kiosk_host_spec *spec = a->host_specs + (found - a->proofs);
        if (spec->kind != S_IFREG || (spec->sha256 &&
            (strcmp(spec->sha256, sha) || (label ? !kiosk_material_equal(spec->label, label) : spec->label != NULL) ||
             spec->privileged != privileged || spec->mode != mode))) return -1;
        spec->sha256 = sha; spec->label = label; spec->mode = mode; spec->privileged = privileged;
        return 0;
    }
    return -1;
}

/* Plain SHA-256 binds the exact attested payload bytes, not M's domain hash. */
static inline int kiosk_material_sha256(const void *bytes, size_t size, void *crypto, uint64_t deadline, char hex[65])
{
    if (!bytes || size > KIOSK_RECEIPT_BYTES || !crypto || kiosk_receipt_before(deadline)) return -1;
    void *(*create)(void) = (void *(*)(void))dlsym(crypto, "EVP_MD_CTX_new");
    void (*release)(void *) = (void (*)(void *))dlsym(crypto, "EVP_MD_CTX_free");
    const void *(*algorithm)(void) = (const void *(*)(void))dlsym(crypto, "EVP_sha256");
    int (*init)(void *, const void *, void *) = (int (*)(void *, const void *, void *))dlsym(crypto, "EVP_DigestInit_ex");
    int (*update)(void *, const void *, size_t) = (int (*)(void *, const void *, size_t))dlsym(crypto, "EVP_DigestUpdate");
    int (*finish)(void *, unsigned char *, unsigned *) = (int (*)(void *, unsigned char *, unsigned *))dlsym(crypto, "EVP_DigestFinal_ex");
    if (!create || !release || !algorithm || !init || !update || !finish) return -1;
    void *ctx = create(); int result = -1; unsigned char digest[32]; unsigned n = 0;
    if (!ctx || init(ctx, algorithm(), NULL) != 1) goto done;
    for (size_t offset = 0; offset < size;) {
        size_t count = size - offset > 65536 ? 65536 : size - offset;
        if (kiosk_receipt_before(deadline) || update(ctx, (const char *)bytes + offset, count) != 1) goto done;
        offset += count;
    }
    if (kiosk_receipt_before(deadline) || finish(ctx, digest, &n) != 1 || n != 32) goto done;
    for (unsigned i = 0; i < 32; i++) { hex[i * 2] = "0123456789abcdef"[digest[i] >> 4]; hex[i * 2 + 1] = "0123456789abcdef"[digest[i] & 15]; }
    hex[64] = 0; result = 0;
done:
    if (ctx) release(ctx);
    return result;
}

static inline int kiosk_material_file_record(struct kiosk_material_authority *a, unsigned n, const char *class,
                                             const char *role, const char *source, int native, int privileged)
{
    struct kiosk_material_json *j = &a->material_json;
    const char *path = kiosk_material_property(j, n, "path"), *sha = kiosk_material_property(j, n, "sha256");
    const char *label = kiosk_material_label(j, n, "label", a->backend);
    const char *source_label = native ? kiosk_material_label(j, n, "source_label", a->backend) : label;
    uint64_t size, mode;
    if (!kiosk_material_usr(path) || !kiosk_material_concrete(a, path) || !sha || !kiosk_receipt_hex(sha) ||
        !label || !source_label || kiosk_material_number(j, n, "size", &size) ||
        kiosk_material_number(j, n, "mode", &mode) || size > KIOSK_HOST_FILE_BYTES || mode > 07777 ||
        (!privileged && (mode & 06000)) || (mode & 022) || a->count >= KIOSK_RECEIPT_ROWS) return -1;
    const struct kiosk_material_spec *found = kiosk_material_find(a, path);
    struct kiosk_material_spec *spec = found ? a->specs + (found - a->specs) : NULL;
    if (!spec || strcmp(spec->source_class, "proof") || strcmp(spec->kind, "file")) return -1;
    spec->source_class = class; spec->role = role; spec->source = source ? source : path;
    spec->sha256 = sha; spec->source_label = source_label; spec->label = label;
    spec->size = size; spec->mode = (mode_t)mode; spec->privileged = privileged;
    if (strcmp(class, "vendor")) {
        if (size > KIOSK_HOST_FILE_BYTES - a->copy_bytes) return -1;
        a->copy_bytes += size;
    }
    return kiosk_material_host_file(a, spec->source, sha, source_label,
                                    native ? 0 : (mode_t)mode, privileged);
}

static inline int kiosk_material_config_routes(struct kiosk_material_authority *a)
{
    struct kiosk_material_json *c = &a->config_json;
    unsigned entries = kiosk_material_get(c, 1, "executables");
    if (!entries || c->nodes[entries].type != '[' || !c->nodes[entries].count) return -1;
    for (unsigned n = c->nodes[entries].child; n; n = c->nodes[n].next) {
        const char *role = kiosk_material_property(c, n, "role");
        const char *source = kiosk_material_property(c, n, "source");
        const char *library = kiosk_material_property(c, n, "library_directory");
        unsigned paths = kiosk_material_get(c, n, "paths"), optional = kiosk_material_get(c, n, "optional");
        if (!role || !kiosk_receipt_text(role) || !paths || c->nodes[paths].type != '[' ||
            (optional && c->nodes[optional].type != 't' && c->nodes[optional].type != 'f') ||
            kiosk_material_schema(c, n, "role|paths|optional|source|library_directory", 2 + !!optional + !!source + !!library)) return -1;
        if ((source && (!kiosk_material_usr(source) || c->nodes[paths].count != 1 || library ||
                        (optional && c->nodes[optional].type == 't'))) ||
            (library && (!kiosk_material_usr(library) || strcmp(role, "library") || c->nodes[paths].count || source))) return -1;
        if (library) {
            char resolved[PATH_MAX];
            if (kiosk_material_resolve(a, library, 0, 1, resolved)) return -1;
            struct kiosk_material_proof *directory = kiosk_material_proof_find(a, resolved);
            if (!directory || strcmp(directory->kind, "directory")) return -1;
        }
        if (!library && !c->nodes[paths].count) return -1;
        unsigned p = c->nodes[paths].child;
        do {
            if (a->route_count >= KIOSK_RECEIPT_ROWS) return -1;
            const char *path = library ? NULL : kiosk_material_text(c, p);
            if (!library && !kiosk_material_path(path)) return -1;
            a->routes[a->route_count++] = (struct kiosk_material_route){.path = path, .role = role,
                .source = source, .library_directory = library, .optional = optional && c->nodes[optional].type == 't'};
            if (library) break;
            p = c->nodes[p].next;
        } while (p);
    }
    return 0;
}

/* Match the lexical glob input, before inventory() resolves symlinks. The
 * canonical source may have a different basename or live in another /usr
 * directory; its full proof closure remains mandatory. */
static inline int kiosk_material_library_candidate(const char *directory, const char *path)
{
    if (!directory || !kiosk_material_path(path)) return 0;
    size_t length = strlen(directory);
    if (strncmp(path, directory, length) || path[length] != '/') return 0;
    const char *name = path + length + 1; size_t size = strlen(name);
    return !strchr(name, '/') && size >= 14 && !strncmp(name, "libsystemd-", 11) && !strcmp(name + size - 3, ".so");
}

static inline int kiosk_material_native(struct kiosk_material_authority *a, unsigned group)
{
    struct kiosk_material_json *j = &a->material_json;
    static const char *const roles[] = {"manager", "executor", "gate", "session-start", "leader", "service",
        "pipewire", "app-start", "notifications-start", "notification-client-start", "wellbeing-start",
        "audio-start", "packages-start", "audio", "rpm", "locale", "python", "gjs", "polkit", "bwrap",
        "bwrap-native", "glycin", "webkit", "scanner", "blocked", "library", NULL};
    for (unsigned n = j->nodes[group].child; n; n = j->nodes[n].next) {
        const char *role = kiosk_material_property(j, n, "role"), *path = kiosk_material_property(j, n, "path");
        const char *source = kiosk_material_property(j, n, "source");
        unsigned aliases = kiosk_material_get(j, n, "aliases");
        if (!role || !kiosk_receipt_member(role, roles) || !path ||
            kiosk_material_schema(j, n, "role|path|sha256|size|source_label|mode|label|source|aliases", 7 + !!source + !!aliases) ||
            (aliases && (j->nodes[aliases].type != '[' || !j->nodes[aliases].count))) return -1;
        uint64_t mode;
        if (kiosk_material_number(j, n, "mode", &mode) || mode !=
            (uint64_t)((!strcmp(role, "blocked") || !strcmp(role, "library")) ? 0644 : 0755)) return -1;
        const char *label = kiosk_material_label(j, n, "label", a->backend);
        if (!strcmp(a->backend, "selinux")) {
            char expected[256], converted[128]; size_t length = strlen(role);
            if (length >= sizeof(converted)) return -1;
            for (size_t i = 0; i <= length; i++) converted[i] = role[i] == '-' ? '_' : role[i];
            snprintf(expected, sizeof(expected), "system_u:object_r:onpc_kiosk_%s_exec_t:s0", converted);
            if (!kiosk_material_equal(label, expected)) return -1;
        }
        if (kiosk_material_file_record(a, n, "native", role, source, 1, 0)) return -1;
        char canonical[PATH_MAX];
        if (kiosk_material_resolve(a, path, 0, 1, canonical) || strcmp(path, canonical)) return -1;
        int matched = 0;
        for (unsigned i = 0; i < a->route_count; i++) {
            if (kiosk_receipt_before(a->deadline)) return -1;
            struct kiosk_material_route *route = a->routes + i;
            if (strcmp(role, route->role) || (source ? !kiosk_material_equal(source, route->source) : route->source != NULL)) continue;
            if (route->library_directory) {
                int candidate = kiosk_material_library_candidate(route->library_directory, path);
                for (unsigned alias = aliases ? j->nodes[aliases].child : 0; !candidate && alias; alias = j->nodes[alias].next) {
                    const char *name = kiosk_material_text(j, alias);
                    if (kiosk_material_library_candidate(route->library_directory, name) &&
                        !kiosk_material_resolve(a, name, 0, 1, canonical) && !strcmp(canonical, path)) candidate = 1;
                }
                if (!candidate) continue;
                route->selected = 1; matched = 1; continue;
            }
            if (!kiosk_material_proof_find(a, route->path)) continue;
            if (!kiosk_material_resolve(a, route->path, 0, 1, canonical) && !strcmp(canonical, path)) {
                route->selected = 1; matched = 1;
                if (strcmp(route->path, path)) {
                    int found = 0;
                    for (unsigned alias = aliases ? j->nodes[aliases].child : 0; alias; alias = j->nodes[alias].next)
                        if (kiosk_material_equal(kiosk_material_text(j, alias), route->path)) found = 1;
                    if (!found) return -1;
                }
            }
        }
        if (!matched) return -1;
        const char *previous = "";
        for (unsigned alias = aliases ? j->nodes[aliases].child : 0; alias; alias = j->nodes[alias].next) {
            const char *name = kiosk_material_text(j, alias); int found = 0;
            if (!kiosk_material_path(name) || strcmp(name, previous) <= 0 || !strcmp(name, path)) return -1;
            previous = name;
            for (unsigned i = 0; i < a->route_count; i++) {
                if (kiosk_receipt_before(a->deadline)) return -1;
                if (a->routes[i].selected && !strcmp(a->routes[i].role, role) &&
                    (source ? kiosk_material_equal(source, a->routes[i].source) : a->routes[i].source == NULL) &&
                    (kiosk_material_equal(a->routes[i].path, name) ||
                     kiosk_material_library_candidate(a->routes[i].library_directory, name))) found = 1;
            }
            if (!found || kiosk_material_resolve(a, name, 0, 1, canonical) || strcmp(canonical, path)) return -1;
        }
    }
    /* Config alternatives form one program. Every mandatory group must have
     * at least one selected member; sole mandatory names cannot disappear. */
    struct kiosk_material_json *c = &a->config_json;
    unsigned entries = kiosk_material_get(c, 1, "executables"), route_index = 0;
    for (unsigned n = c->nodes[entries].child; n; n = c->nodes[n].next) {
        unsigned paths = kiosk_material_get(c, n, "paths"), count = c->nodes[paths].count;
        if (!count) count = 1;
        int selected = 0, optional = a->routes[route_index].optional;
        for (unsigned i = 0; i < count; i++) selected |= a->routes[route_index++].selected;
        if (!optional && !selected) return -1;
    }
    return 0;
}

static inline int kiosk_material_decode_until(struct kiosk_material_authority *a,
    const void *material, size_t material_size, const void *config, size_t config_size,
    const void *policy, size_t policy_size, void *crypto, uint64_t deadline)
{
    memset(a, 0, sizeof(*a)); a->deadline = deadline;
    if (material_size > KIOSK_RECEIPT_BYTES || config_size > KIOSK_RECEIPT_BYTES - material_size ||
        policy_size > KIOSK_RECEIPT_BYTES - material_size - config_size ||
        kiosk_receipt_material_hash(material, material_size, crypto, deadline, a->digest) ||
        kiosk_material_sha256(config, config_size, crypto, deadline, a->config_digest) ||
        kiosk_material_sha256(policy, policy_size, crypto, deadline, a->policy_digest) ||
        kiosk_material_json_parse(&a->material_json, material, material_size, deadline) ||
        kiosk_material_json_parse(&a->config_json, config, config_size, deadline)) goto failed;
    struct kiosk_material_json *j = &a->material_json, *c = &a->config_json;
    uint64_t format;
    a->backend = kiosk_material_property(j, 1, "backend");
    if (kiosk_material_schema(j, 1, "format|backend|config|policy|native|preserved|runtime|proofs|payload", 9) ||
        kiosk_material_number(j, 1, "format", &format) || format != 1 || !a->backend ||
        (strcmp(a->backend, "apparmor") && strcmp(a->backend, "selinux")) ||
        !kiosk_material_equal(kiosk_material_property(c, 1, "backend"), a->backend) ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "config"), a->config_digest) ||
        !kiosk_material_equal(kiosk_material_property(j, 1, "policy"), a->policy_digest)) goto failed;
    unsigned profiles = kiosk_material_get(c, 1, "apparmor_profiles");
    if (kiosk_material_schema(c, 1, "backend|domains|executables|preserved_executables|reserved_directories|runtime_inputs|apparmor_profiles", 6 + !!profiles)) goto failed;
    unsigned domains = kiosk_material_get(c, 1, "domains");
    if (!domains || c->nodes[domains].type != '[' || !c->nodes[domains].count ||
        (profiles && (strcmp(a->backend, "apparmor") || c->nodes[profiles].type != '['))) goto failed;
    for (unsigned array = domains; array; array = array == domains ? profiles : 0) {
        for (unsigned n = c->nodes[array].child; n; n = c->nodes[n].next) {
            const char *text = kiosk_material_text(c, n);
            if (!text || !kiosk_receipt_text(text)) goto failed;
        }
    }
    const char *groups[] = {"native", "preserved", "runtime", "proofs", "payload"};
    unsigned group[5], rows = 0;
    for (unsigned i = 0; i < 5; i++) {
        group[i] = kiosk_material_get(j, 1, groups[i]);
        if (!group[i] || j->nodes[group[i]].type != '[' || j->nodes[group[i]].count > KIOSK_RECEIPT_ROWS - rows) goto failed;
        rows += j->nodes[group[i]].count;
    }
    if (!j->nodes[group[0]].count || !j->nodes[group[2]].count || j->nodes[group[4]].count != 2) goto failed;
    a->proof_count = j->nodes[group[3]].count;
    if (!a->proof_count) goto failed;
    a->proofs = calloc(a->proof_count, sizeof(*a->proofs));
    a->host_specs = calloc(a->proof_count, sizeof(*a->host_specs));
    a->specs = calloc(a->proof_count, sizeof(*a->specs));
    a->routes = calloc(KIOSK_RECEIPT_ROWS, sizeof(*a->routes));
    if (!a->proofs || !a->host_specs || !a->specs || !a->routes) goto failed;
    unsigned index = 0;
    const char *previous = "";
    for (unsigned n = j->nodes[group[3]].child; n; n = j->nodes[n].next, index++) {
        if (j->nodes[n].type != '[' || j->nodes[n].count != 3) goto failed;
        unsigned field = j->nodes[n].child;
        const char *kind = kiosk_material_text(j, field); field = j->nodes[field].next;
        const char *path = kiosk_material_text(j, field); field = j->nodes[field].next;
        const char *link = kiosk_material_text(j, field);
        if (!kind || !kiosk_material_path(path) || !link || strcmp(previous, path) >= 0 ||
            (strcmp(kind, "directory") && strcmp(kind, "file") && strcmp(kind, "link")) ||
            (!strcmp(kind, "link") ? !kiosk_receipt_text(link) || !strcmp(link, "-") : strcmp(link, "-"))) goto failed;
        previous = path; a->proofs[index] = (struct kiosk_material_proof){path, kind, link, 0};
        a->host_specs[index] = (struct kiosk_host_spec){.path = path,
            .kind = !strcmp(kind, "directory") ? S_IFDIR : !strcmp(kind, "file") ? S_IFREG : S_IFLNK,
            .link = !strcmp(kind, "link") ? link : NULL};
    }
    a->host_count = a->proof_count;
    for (unsigned i = 0; i < a->proof_count; i++) {
        struct kiosk_material_proof *p = a->proofs + i;
        if (!kiosk_material_concrete(a, p->path)) continue;
        a->specs[a->count++] = (struct kiosk_material_spec){.path = p->path, .source = p->path,
            .kind = !strcmp(p->kind, "directory") ? "tree" : p->kind,
            .source_class = !strcmp(p->kind, "directory") ? "skeleton" : !strcmp(p->kind, "link") ? "alias" : "proof",
            .role = !strcmp(p->kind, "directory") ? "skeleton" : "data", .link = p->link,
            .sha256 = "-", .label = "-", .source_label = "-"};
    }
    qsort(a->specs, a->count, sizeof(*a->specs), kiosk_material_spec_compare);
    if (kiosk_material_config_routes(a) || kiosk_material_native(a, group[0])) goto failed;
    unsigned preserved = kiosk_material_get(c, 1, "preserved_executables");
    if (!preserved || c->nodes[preserved].type != '[' || c->nodes[preserved].count != j->nodes[group[1]].count) goto failed;
    unsigned configured = c->nodes[preserved].child;
    for (unsigned n = j->nodes[group[1]].child; n; n = j->nodes[n].next, configured = c->nodes[configured].next) {
        const char *path = kiosk_material_property(j, n, "path"); uint64_t mode, expected, uid, gid;
        if (kiosk_material_schema(j, n, "path|sha256|size|mode|uid|gid|label", 7) ||
            kiosk_material_schema(c, configured, "path|mode|label", 3) ||
            !kiosk_material_equal(path, kiosk_material_property(c, configured, "path")) ||
            kiosk_material_number(j, n, "mode", &mode) || kiosk_material_number(c, configured, "mode", &expected) || mode != expected ||
            kiosk_material_number(j, n, "uid", &uid) || uid || kiosk_material_number(j, n, "gid", &gid) || gid ||
            !kiosk_material_equal(kiosk_material_label(j, n, "label", a->backend), kiosk_material_label(c, configured, "label", a->backend)) ||
            kiosk_material_file_record(a, n, "vendor", "vendor", NULL, 0, 1)) goto failed;
    }
    unsigned inputs = kiosk_material_get(c, 1, "runtime_inputs");
    if (!inputs || c->nodes[inputs].type != '{' || c->nodes[inputs].count != j->nodes[group[2]].count) goto failed;
    previous = "";
    for (unsigned n = j->nodes[group[2]].child; n; n = j->nodes[n].next) {
        const char *path = kiosk_material_property(j, n, "path"), *kind = kiosk_material_property(j, n, "kind"), *role = kiosk_material_property(j, n, "role");
        if (!kiosk_material_usr(path) || strcmp(previous, path) >= 0 || !kind || !role) goto failed;
        previous = path; configured = kiosk_material_get(c, inputs, path);
        static const char *const roles[] = {"script", "module", "asset", "wellbeing", "unit", "session-data", NULL};
        if (!kiosk_receipt_member(role, roles) || !kiosk_material_equal(kind, kiosk_material_property(c, configured, "kind")) ||
            !kiosk_material_equal(role, kiosk_material_property(c, configured, "role"))) goto failed;
        if (!strcmp(kind, "file")) {
            uint64_t mode;
            if (kiosk_material_schema(c, configured, "kind|role", 2) ||
                kiosk_material_schema(j, n, "path|kind|role|sha256|size|mode|label", 7) ||
                kiosk_material_number(j, n, "mode", &mode) || mode != (uint64_t)(!strcmp(role, "script") ? 0755 : 0644) ||
                kiosk_material_file_record(a, n, "runtime", "data", NULL, 0, 0)) goto failed;
            const char *label = kiosk_material_label(j, n, "label", a->backend);
            if (!strcmp(a->backend, "selinux") && strstr(label, ":onpc_kiosk_") && strstr(label, "_exec_t:")) goto failed;
        } else if (!strcmp(kind, "directory") || !strcmp(kind, "link")) {
            int is_link = !strcmp(kind, "link");
            if (kiosk_material_schema(c, configured, "kind|role|link", 2 + is_link) ||
                kiosk_material_schema(j, n, "path|kind|role|link", 3 + is_link)) goto failed;
            const struct kiosk_material_spec *found = kiosk_material_find(a, path);
            if (!found || strcmp(found->kind, is_link ? "link" : "tree")) goto failed;
            if (is_link) {
                const char *link = kiosk_material_property(j, n, "link");
                if (!link || !kiosk_material_equal(link, kiosk_material_property(c, configured, "link")) || strcmp(link, found->link)) goto failed;
                if (strcmp(link, "/dev/null") || strcmp(role, "unit")) {
                    if (*link == '/' || !kiosk_receipt_text(link)) goto failed;
                    char target[PATH_MAX]; const char *slash = strrchr(path, '/');
                    int length = snprintf(target, sizeof(target), "%.*s/%s", (int)(slash - path), path, link);
                    if (length < 0 || length >= PATH_MAX || !kiosk_material_path(target) || !kiosk_material_get(c, inputs, target)) goto failed;
                }
                struct kiosk_material_spec *mutable = a->specs + (found - a->specs);
                mutable->source_class = "runtime"; mutable->terminal_link = 1;
                struct kiosk_material_proof *proof = kiosk_material_proof_find(a, path);
                if (!proof) goto failed;
                a->host_specs[proof - a->proofs].terminal_link = 1;
            }
            if (kiosk_material_resolve(a, path, is_link, 1, NULL)) goto failed;
        } else goto failed;
    }
    unsigned payload_index = 0;
    for (unsigned n = j->nodes[group[4]].child; n; n = j->nodes[n].next, payload_index++) {
        const char *path = kiosk_material_property(j, n, "path");
        const char *expected = payload_index == 0 ? "/usr/share/oh-no-parent-control/confinement/config.json" :
            !strcmp(a->backend, "selinux") ? "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.cil" :
            "/usr/share/oh-no-parent-control/confinement/onpc-kiosk.apparmor";
        uint64_t mode, size;
        if (kiosk_material_schema(j, n, "path|sha256|size|mode|label", 5) || !kiosk_material_equal(path, expected) ||
            !kiosk_material_equal(kiosk_material_property(j, n, "sha256"), payload_index ? a->policy_digest : a->config_digest) ||
            kiosk_material_number(j, n, "size", &size) || size != (uint64_t)(payload_index ? policy_size : config_size) ||
            kiosk_material_number(j, n, "mode", &mode) || mode != 0644 ||
            kiosk_material_file_record(a, n, "payload", "data", NULL, 0, 0)) goto failed;
    }
    unsigned reserved = kiosk_material_get(c, 1, "reserved_directories");
    if (!reserved || c->nodes[reserved].type != '[') goto failed;
    for (unsigned n = c->nodes[reserved].child; n; n = c->nodes[n].next) {
        const char *path = kiosk_material_text(c, n); char resolved[PATH_MAX];
        if (!kiosk_material_usr(path) || kiosk_material_resolve(a, path, 0, 1, resolved) || !kiosk_material_usr(resolved)) goto failed;
        struct kiosk_material_proof *proof = kiosk_material_proof_find(a, resolved);
        if (!proof || strcmp(proof->kind, "directory")) goto failed;
    }
    for (unsigned i = 0; i < a->count; i++) if (!strcmp(a->specs[i].source_class, "proof")) goto failed;
    for (unsigned i = 0; i < a->proof_count; i++) {
        struct kiosk_material_proof *p = a->proofs + i;
        int terminal = a->host_specs[i].terminal_link;
        if (kiosk_material_resolve(a, p->path, terminal, 0, NULL) || !p->used) goto failed;
    }
    if (!kiosk_material_find(a, "/usr") || kiosk_receipt_before(deadline)) goto failed;
    return 0;
failed:
    kiosk_material_free(a); return -1;
}

static inline const struct kiosk_host_row *kiosk_material_host_row(const struct kiosk_host_proof *proof, const char *path)
{
    unsigned low = 0, high = proof->count;
    while (low < high) {
        unsigned mid = low + (high - low) / 2;
        if (strcmp(proof->rows[mid].path, path) < 0) low = mid + 1; else high = mid;
    }
    return low < proof->count && !strcmp(proof->rows[low].path, path) ? proof->rows + low : NULL;
}

/* Existence lookup without following a kernel symlink or consulting attached
 * /usr. Unselected absence does not make unknown ancestors required or trusted;
 * selected routes must use only the sealed proof. No discovered node becomes
 * a source. Return 1 for Path.exists() absence, 0 for a pinned endpoint. */
static inline int kiosk_material_route_open(struct kiosk_material_authority *a,
    const struct kiosk_host_proof *proof, const char *path, int required,
    char resolved[PATH_MAX], int *endpoint)
{
    int stack[PATH_MAX / 2 + 1], child = -1, result = -1;
    unsigned depth = 0, links = 0, steps = 0;
    char pending[PATH_MAX], current[PATH_MAX] = "/";
    struct stat info;
    *endpoint = -1;
    if (!kiosk_material_path(path) || strlen(path) >= PATH_MAX) return -1;
    stack[0] = fcntl(proof->roots.root, F_DUPFD_CLOEXEC, 3);
    if (stack[0] < 0) return -1;
    const struct kiosk_host_row *root = kiosk_material_host_row(proof, "/");
    if (!root || fstat(stack[0], &info) || !kiosk_host_same(&root->info, &info)) goto done;
    strcpy(pending, path + 1);
    while (pending[0]) {
        char part[PATH_MAX], next[PATH_MAX], expanded[PATH_MAX];
        char *slash = strchr(pending, '/');
        size_t length = slash ? (size_t)(slash - pending) : strlen(pending);
        memcpy(part, pending, length); part[length] = 0;
        memmove(pending, pending + length + !!slash, strlen(pending + length + !!slash) + 1);
        if (++steps > KIOSK_HOST_PROOF_ROWS || kiosk_receipt_before(a->deadline)) goto done;
        if (!part[0] || !strcmp(part, ".")) continue;
        if (!strcmp(part, "..")) {
            if (depth) {
                close(stack[depth--]); char *last = strrchr(current, '/');
                if (last == current) last[1] = 0; else *last = 0;
            }
            continue;
        }
        int used = snprintf(next, sizeof(next), "%s%s%s", current, depth ? "/" : "", part);
        if (used < 0 || used >= PATH_MAX || depth >= PATH_MAX / 2) goto done;
        child = !strcmp(next, "/usr") ? fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3) :
            openat(stack[depth], part, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (child < 0) {
            if (!required && errno == ENOENT) result = 1;
            goto done;
        }
        const struct kiosk_host_row *row = kiosk_material_host_row(proof, next);
        if (fstat(child, &info) || (required && !row) ||
            ((required || row) && !kiosk_host_trust(&info)) ||
            (row && !kiosk_host_same(&row->info, &info))) goto done;
        int named = !strcmp(next, "/usr") ? fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3) :
            openat(stack[depth], part, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        struct stat named_info;
        int same = named >= 0 && !fstat(named, &named_info) && kiosk_host_same(&info, &named_info);
        if (named >= 0) close(named);
        if (!same) goto done;
        if (S_ISLNK(info.st_mode)) {
            char link[PATH_MAX]; struct stat after;
            ssize_t size = readlinkat(child, "", link, sizeof(link));
            if (size <= 0 || size >= PATH_MAX) goto done;
            if (++links > 40) { if (!required) result = 1; goto done; }
            link[size] = 0;
            if ((required && !kiosk_receipt_text(link)) || (row && (!row->link || strcmp(row->link, link))) ||
                fstat(child, &after) || !kiosk_host_same(&info, &after)) goto done;
            used = snprintf(expanded, sizeof(expanded), "%s%s%s", link + (link[0] == '/'),
                            pending[0] ? "/" : "", pending);
            if (used < 0 || used >= PATH_MAX) goto done;
            close(child); child = -1;
            if (link[0] == '/') { while (depth) close(stack[depth--]); strcpy(current, "/"); }
            strcpy(pending, expanded); continue;
        }
        if (pending[0] && !S_ISDIR(info.st_mode)) {
            /* Path.exists() treats a non-directory prefix as absent. */
            if (!required) result = 1;
            goto done;
        }
        stack[++depth] = child; child = -1; strcpy(current, next);
    }
    if (kiosk_receipt_before(a->deadline)) goto done;
    if (resolved) strcpy(resolved, current);
    *endpoint = stack[depth]; stack[depth] = -1; result = 0;
done:
    if (child >= 0) close(child);
    do { if (stack[depth] >= 0) close(stack[depth]); } while (depth--);
    return result;
}

/* A library lexical name must be explicitly retained by its own unsubstituted
 * native record; resolving to another selected file is insufficient. */
static inline int kiosk_material_library_member(struct kiosk_material_authority *a,
    const struct kiosk_material_route *route, const char *name, const char *canonical)
{
    struct kiosk_material_json *j = &a->material_json;
    unsigned native = kiosk_material_get(j, 1, "native");
    for (unsigned n = j->nodes[native].child; n; n = j->nodes[n].next) {
        if (kiosk_receipt_before(a->deadline)) return 0;
        const char *path = kiosk_material_property(j, n, "path");
        if (!kiosk_material_equal(kiosk_material_property(j, n, "role"), route->role) ||
            kiosk_material_get(j, n, "source") || (canonical && strcmp(path, canonical))) continue;
        if (!strcmp(path, name)) return 1;
        unsigned aliases = kiosk_material_get(j, n, "aliases");
        for (unsigned alias = aliases ? j->nodes[aliases].child : 0; alias; alias = j->nodes[alias].next) {
            if (kiosk_receipt_before(a->deadline)) return 0;
            if (kiosk_material_equal(kiosk_material_text(j, alias), name)) return 1;
        }
    }
    return 0;
}

/* Required after host capture and at final source revalidation. Only declared
 * directories are scanned; unrelated siblings contribute neither identity nor
 * metadata assertions. Aggregate directory work and every lookup share the
 * original transaction deadline. Absence cannot be established by M alone. */
static inline int kiosk_material_verify_routes_until(struct kiosk_material_authority *a,
                                                     struct kiosk_host_proof *proof)
{
    if (!a || !proof || proof->deadline != a->deadline ||
        kiosk_host_proof_recheck(proof, a->host_specs, a->host_count)) return -1;
    unsigned entries = 0;
    for (unsigned i = 0; i < a->route_count; i++) {
        const struct kiosk_material_route *route = a->routes + i;
        char canonical[PATH_MAX], expected[PATH_MAX]; int fd = -1;
        if (kiosk_receipt_before(a->deadline)) return -1;
        if (!route->library_directory) {
            int found = kiosk_material_route_open(a, proof, route->path, route->selected, canonical, &fd);
            if (fd >= 0) close(fd);
            if (!route->selected) { if (found != 1) return -1; continue; }
            if (found || kiosk_material_resolve(a, route->path, 0, 0, expected) || strcmp(canonical, expected)) return -1;
            continue;
        }
        if (kiosk_material_route_open(a, proof, route->library_directory, 1, canonical, &fd)) return -1;
        struct stat before, opened;
        if (fstat(fd, &before) || !S_ISDIR(before.st_mode)) { close(fd); return -1; }
        int readable = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (readable < 0 || fstat(readable, &opened) || !kiosk_host_same(&before, &opened)) {
            close(fd); if (readable >= 0) close(readable); return -1;
        }
        close(fd);
        DIR *directory = fdopendir(readable);
        if (!directory) { close(readable); return -1; }
        unsigned matched = 0; int result = 0;
        for (;;) {
            errno = 0; struct dirent *entry = readdir(directory);
            if (!entry) { if (errno) result = -1; break; }
            if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
            if (++entries > KIOSK_HOST_PROOF_ROWS || kiosk_receipt_before(a->deadline)) { result = -1; break; }
            char name[PATH_MAX];
            int length = snprintf(name, sizeof(name), "%s/%s", route->library_directory, entry->d_name);
            /* Nonmatching ambient names need no protocol representation. */
            size_t size = strlen(entry->d_name);
            if (size < 14 || strncmp(entry->d_name, "libsystemd-", 11) || strcmp(entry->d_name + size - 3, ".so")) continue;
            if (length < 0 || length >= PATH_MAX ||
                !kiosk_material_library_candidate(route->library_directory, name) ||
                kiosk_material_route_open(a, proof, name, 1, canonical, &fd)) { result = -1; break; }
            close(fd); fd = -1;
            if (!kiosk_material_library_member(a, route, name, canonical)) { result = -1; break; }
            matched++;
        }
        closedir(directory);
        if (result || (!route->optional && !matched)) return -1;
        /* Rechecking the sealed required closure below proves no declared
         * lexical member disappeared; enumeration above rejects extra members. */
    }
    return kiosk_host_proof_recheck(proof, a->host_specs, a->host_count);
}

/* Open a canonical native source exclusively through the independently pinned
 * original /usr root. Every nofollow edge must retain capture's identity.
 * Reading four magic bytes adds no authority to the source pathname. */
static inline int kiosk_material_host_elf(struct kiosk_material_authority *a, struct kiosk_host_proof *proof,
                                         const struct kiosk_material_spec *spec)
{
    const char *source = spec->source;
    if (!source || strncmp(source, "/usr/", 5)) return -1;
    int current = fcntl(proof->roots.usr, F_DUPFD_CLOEXEC, 3), result = -1;
    if (current < 0) return -1;
    char pending[PATH_MAX], path[PATH_MAX] = "/usr";
    strcpy(pending, source + 5); char *component = pending;
    for (;;) {
        if (kiosk_receipt_before(a->deadline)) break;
        char *slash = strchr(component, '/'); if (slash) *slash = 0;
        size_t used = strlen(path), length = strlen(component);
        if (!length || used + length + 1 >= sizeof(path)) break;
        strcat(path, "/"); strcat(path, component);
        int child = openat(current, component, (slash ? O_PATH | O_DIRECTORY : O_RDONLY | O_NONBLOCK) | O_NOFOLLOW | O_CLOEXEC);
        if (child < 0) break;
        close(current); current = child;
        const struct kiosk_host_row *row = kiosk_material_host_row(proof, path); struct stat before, after;
        if (!row || fstat(current, &before) || !kiosk_host_same(&before, &row->info)) break;
        if (!slash) {
            unsigned char magic[4];
            if (!S_ISREG(before.st_mode) || (uint64_t)before.st_size != spec->size ||
                (!strcmp(spec->source_class, "native") && strcmp(spec->role, "blocked") && strcmp(spec->role, "library") && !(before.st_mode & 0111)) ||
                pread(current, magic, sizeof(magic), 0) != (ssize_t)sizeof(magic) || memcmp(magic, "\177ELF", sizeof(magic)) ||
                fstat(current, &after) || !kiosk_host_same(&before, &after)) break;
            result = 0; break;
        }
        component = slash + 1;
    }
    close(current); return result;
}

/* Required after capture and again at final source revalidation. A SHA match
 * alone does not establish inventory()'s native ELF/executable predicates.
 * The proof must use this exact required closure and original deadline.
 * kiosk_material_verify_routes_until() separately checks candidate absence and
 * library membership. Enforcing MAC/attestation and actual copied/retained mount
 * sources remain caller obligations. */
static inline int kiosk_material_verify_host_until(struct kiosk_material_authority *a, struct kiosk_host_proof *proof)
{
    if (!a || !proof || proof->deadline != a->deadline ||
        kiosk_host_proof_recheck(proof, a->host_specs, a->host_count)) return -1;
    for (unsigned i = 0; i < a->count; i++) {
        const struct kiosk_material_spec *spec = a->specs + i;
        if (kiosk_receipt_before(a->deadline)) return -1;
        if (strcmp(spec->kind, "file")) continue;
        const struct kiosk_host_row *row = kiosk_material_host_row(proof, spec->source);
        if (!row || !S_ISREG(row->info.st_mode) || row->info.st_size < 0 || (uint64_t)row->info.st_size != spec->size) return -1;
        if ((!strcmp(spec->source_class, "native") || !strcmp(spec->source_class, "vendor")) && kiosk_material_host_elf(a, proof, spec)) return -1;
    }
    return kiosk_host_proof_recheck(proof, a->host_specs, a->host_count);
}
#endif
