#ifndef ONPC_KIOSK_VIEW_RECEIPT_H
#define ONPC_KIOSK_VIEW_RECEIPT_H
/* Closed data format only. Parsing never proves source acquisition, mounted
 * coverage, required membership, completed publication or manager liveness.
 * The native owner must construct the expected receipt from attested material
 * and independently opened objects, then use kiosk_receipt_match(). It must
 * check every N link and C nested submount against the actual acquired tree;
 * neither a producer flag nor a matching digest supplies that authority.
 *
 * N rows are sorted by canonical /usr path and preserve original source_index,
 * even for absent/masked outcomes. Original class is separate from acquisition.
 * The eight assertion fields match file_identity() exactly. nlink is additional.
 * C rows are sorted nested mount witnesses of a shallow directory N owner;
 * they add no material/layout members. Numeric mount IDs are never hashed.
 * V/I hashes exclude their own identity; I references the completed source V.
 * All entry points use the same caller-owned absolute monotonic deadline in us.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <sys/stat.h>
#include <dlfcn.h>

#define KIOSK_RECEIPT_ROWS 32768U
#define KIOSK_RECEIPT_BYTES (64U * 1024U * 1024U)
#define KIOSK_RECEIPT_PATH 4096U
#define KIOSK_RECEIPT_MAX INT64_MAX

enum kiosk_receipt_field {
    KR_PATH, KR_KIND, KR_REQUIRED, KR_CLASS, KR_ACQUIRE, KR_ROLE, KR_INDEX,
    KR_ORIGIN_DEV, KR_ORIGIN_INO, KR_DEV, KR_INO, KR_SIZE, KR_MTIME, KR_CTIME,
    KR_MODE, KR_UID, KR_GID, KR_NLINK, KR_SHA, KR_LABEL, KR_LINK, KR_MOUNT, KR_FIELDS
};
enum kiosk_receipt_coverage_field {
    KC_OWNER, KC_PATH, KC_ORIGIN_DEV, KC_ORIGIN_INO, KC_DEV, KC_INO, KC_SIZE,
    KC_MTIME, KC_CTIME, KC_MODE, KC_UID, KC_GID, KC_FIELDS
};
struct kiosk_receipt_row { char *v[KR_FIELDS]; uint64_t number[KR_FIELDS]; };
struct kiosk_receipt {
    char *storage, *kind, *backend, *role, *material, *source, *acquisition;
    struct kiosk_receipt_row *nodes, *coverage;
    unsigned nn, nc;
    char digest[65];
};

static inline int kiosk_receipt_before(uint64_t deadline)
{
    struct timespec now;
    if (!deadline || clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec < 0) return -1;
    uint64_t value = (uint64_t) now.tv_sec * 1000000ULL + (uint64_t) now.tv_nsec / 1000ULL;
    return value < deadline ? 0 : -1;
}

static inline int kiosk_receipt_hex(const char *value)
{
    if (strlen(value) != 64) return 0;
    for (unsigned i = 0; i < 64; i++) if (!strchr("0123456789abcdef", value[i])) return 0;
    return 1;
}

static inline int kiosk_receipt_uint(const char *text, uint64_t *value)
{
    uint64_t n = 0;
    if (!*text || (*text == '0' && text[1])) return -1;
    for (const unsigned char *p = (const unsigned char *) text; *p; p++) {
        if (*p < '0' || *p > '9' || n > ((uint64_t) KIOSK_RECEIPT_MAX - (*p - '0')) / 10) return -1;
        n = n * 10 + (*p - '0');
    }
    *value = n;
    return 0;
}

static inline int kiosk_receipt_member(const char *value, const char *const *set)
{
    for (unsigned i = 0; set[i]; i++) if (!strcmp(value, set[i])) return 1;
    return 0;
}

static inline int kiosk_receipt_text(const char *value)
{
    size_t n = strlen(value);
    if (!n || n >= KIOSK_RECEIPT_PATH) return 0;
    for (const unsigned char *p = (const unsigned char *) value; *p; p++)
        if (*p < 32 || *p == 127) return 0;
    /* Require canonical UTF-8: no overlong, surrogate or out-of-range forms. */
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char) value[i];
        if (c < 128) continue;
        unsigned count = c >= 0xc2 && c <= 0xdf ? 1 : c >= 0xe0 && c <= 0xef ? 2 : c >= 0xf0 && c <= 0xf4 ? 3 : 0;
        if (!count || i + count >= n) return 0;
        unsigned char next = (unsigned char) value[i + 1];
        if ((c == 0xe0 && next < 0xa0) || (c == 0xed && next >= 0xa0) ||
            (c == 0xf0 && next < 0x90) || (c == 0xf4 && next >= 0x90)) return 0;
        for (unsigned j = 1; j <= count; j++) if (((unsigned char) value[i + j] & 0xc0) != 0x80) return 0;
        i += count;
    }
    return 1;
}

static inline int kiosk_receipt_path(const char *path)
{
    if (!kiosk_receipt_text(path) || (strcmp(path, "/usr") && strncmp(path, "/usr/", 5))) return 0;
    const char *part = path + 1;
    while (*part) {
        const char *end = strchr(part, '/');
        size_t n = end ? (size_t) (end - part) : strlen(part);
        if (!n || (n == 1 && part[0] == '.') || (n == 2 && !memcmp(part, "..", 2))) return 0;
        if (!end) return 1;
        part = end + 1;
    }
    return 0;
}

/* Resolve EVP before attachment and keep its already-trusted handle through
 * final checks. Missing symbols fail closed; no subprocess or private ABI. */
static inline int kiosk_receipt_hash(const char *domain, const void *bytes, size_t size,
                                     void *crypto, uint64_t deadline, char hex[65])
{
    if (!crypto || size > KIOSK_RECEIPT_BYTES || kiosk_receipt_before(deadline) != 0) return -1;
    void *(*create)(void) = (void *(*)(void)) dlsym(crypto, "EVP_MD_CTX_new");
    void (*release)(void *) = (void (*)(void *)) dlsym(crypto, "EVP_MD_CTX_free");
    const void *(*algorithm)(void) = (const void *(*)(void)) dlsym(crypto, "EVP_sha256");
    int (*init)(void *, const void *, void *) = (int (*)(void *, const void *, void *)) dlsym(crypto, "EVP_DigestInit_ex");
    int (*update)(void *, const void *, size_t) = (int (*)(void *, const void *, size_t)) dlsym(crypto, "EVP_DigestUpdate");
    int (*finish)(void *, unsigned char *, unsigned *) = (int (*)(void *, unsigned char *, unsigned *)) dlsym(crypto, "EVP_DigestFinal_ex");
    if (!create || !release || !algorithm || !init || !update || !finish) return -1;
    void *context = create();
    int result = -1;
    unsigned char length[8], digest[32];
    for (unsigned i = 0; i < 8; i++) length[7 - i] = (unsigned char) ((uint64_t) size >> (i * 8));
    if (!context || init(context, algorithm(), NULL) != 1 ||
        update(context, domain, strlen(domain) + 1) != 1 || update(context, length, 8) != 1) goto done;
    for (size_t offset = 0; offset < size;) {
        size_t n = size - offset > 65536 ? 65536 : size - offset;
        if (kiosk_receipt_before(deadline) != 0 || update(context, (const char *) bytes + offset, n) != 1) goto done;
        offset += n;
    }
    unsigned n = 0;
    if (kiosk_receipt_before(deadline) != 0 || finish(context, digest, &n) != 1 || n != 32) goto done;
    for (unsigned i = 0; i < 32; i++) {
        hex[2 * i] = "0123456789abcdef"[digest[i] >> 4]; hex[2 * i + 1] = "0123456789abcdef"[digest[i] & 15];
    }
    hex[64] = 0; result = 0;
done:
    if (context) release(context);
    return result;
}

/* M's existing schema uses ASCII property names, integral numbers, arrays,
 * strings, booleans and null. Validate compact sorted ensure_ascii JSON before
 * hashing it, rather than bless alternate whitespace/number/key encodings.
 * Schema/membership comes independently from attestation, not this encoder. */
struct kiosk_receipt_json { const char *p, *end; uint64_t deadline; unsigned values; };
static inline int kiosk_receipt_json_string(struct kiosk_receipt_json *j, int key)
{
    if (j->p == j->end || *j->p++ != '"') return -1;
    while (j->p < j->end) {
        unsigned char c = (unsigned char) *j->p++;
        if (c == '"') return 0;
        if (c < 32 || c >= 127) return -1;
        if (c != '\\') continue;
        if (j->p == j->end || key) return -1;
        char escaped = *j->p++;
        if (strchr("\"\\bfnrt", escaped)) continue;
        if (escaped != 'u' || j->end - j->p < 4) return -1;
        unsigned value = 0;
        for (unsigned i = 0; i < 4; i++) {
            const char *digit = strchr("0123456789abcdef", j->p[i]);
            if (!digit || !j->p[i]) return -1;
            value = value * 16 + (unsigned) (digit - "0123456789abcdef");
        }
        j->p += 4;
        if ((value >= 32 && value < 127) || value == 8 || value == 9 || value == 10 || value == 12 || value == 13) return -1;
        /* Python ensure_ascii permits lone surrogates as escaped values. */
    }
    return -1;
}

static inline int kiosk_receipt_json_value(struct kiosk_receipt_json *j, unsigned depth)
{
    if (depth > 64 || j->p == j->end || ++j->values > KIOSK_RECEIPT_ROWS * 64U || kiosk_receipt_before(j->deadline) != 0) return -1;
    char c = *j->p;
    if (c == '"') return kiosk_receipt_json_string(j, 0);
    if (c == '[' || c == '{') {
        char close = c == '[' ? ']' : '}';
        const char *previous = NULL; size_t previous_size = 0;
        j->p++;
        if (j->p < j->end && *j->p == close) { j->p++; return 0; }
        for (;;) {
            if (c == '{') {
                const char *key = j->p + 1;
                if (kiosk_receipt_json_string(j, 1) != 0) return -1;
                size_t size = (size_t) (j->p - key - 1);
                if (previous) {
                    size_t shared = size < previous_size ? size : previous_size;
                    int order = memcmp(previous, key, shared);
                    if (order > 0 || (order == 0 && previous_size >= size)) return -1;
                }
                previous = key; previous_size = size;
                if (j->p == j->end || *j->p++ != ':') return -1;
            }
            if (kiosk_receipt_json_value(j, depth + 1) != 0 || j->p == j->end) return -1;
            if (*j->p == close) { j->p++; return 0; }
            if (*j->p++ != ',') return -1;
        }
    }
    for (unsigned i = 0; i < 3; i++) {
        const char *literal = i == 0 ? "null" : i == 1 ? "true" : "false";
        size_t n = strlen(literal);
        if ((size_t) (j->end - j->p) >= n && !memcmp(j->p, literal, n)) { j->p += n; return 0; }
    }
    if (c == '-') { j->p++; if (j->p == j->end || *j->p == '0') return -1; }
    const char *start = j->p;
    if (j->p == j->end || *j->p < '0' || *j->p > '9') return -1;
    if (*j->p++ != '0') while (j->p < j->end && *j->p >= '0' && *j->p <= '9') j->p++;
    /* Finite integers match all fields in the current material schema. */
    if (j->p - start > 19) return -1;
    return 0;
}

static inline int kiosk_receipt_material_hash(const void *bytes, size_t size, void *crypto,
                                             uint64_t deadline, char hex[65])
{
    if (!bytes || !size || size > KIOSK_RECEIPT_BYTES || memchr(bytes, 0, size)) return -1;
    struct kiosk_receipt_json json = {.p = bytes, .end = (const char *) bytes + size, .deadline = deadline};
    if (*(const char *) bytes != '{' || kiosk_receipt_json_value(&json, 0) != 0 || json.p != json.end) return -1;
    return kiosk_receipt_hash("ONPC-KIOSK-MATERIAL", bytes, size, crypto, deadline, hex);
}

static inline void kiosk_receipt_free(struct kiosk_receipt *receipt)
{
    free(receipt->nodes); free(receipt->coverage); free(receipt->storage);
    memset(receipt, 0, sizeof(*receipt));
}

static inline int kiosk_receipt_fields(char *line, char **fields, unsigned wanted)
{
    unsigned count = 1; fields[0] = line;
    for (char *p = line; *p; p++) if (*p == '\t') {
        if (count == wanted) return -1;
        *p = 0; fields[count++] = p + 1;
    }
    if (count != wanted) return -1;
    for (unsigned i = 0; i < wanted; i++) if (!kiosk_receipt_text(fields[i])) return -1;
    return 0;
}

static inline const struct kiosk_receipt_row *kiosk_receipt_find(const struct kiosk_receipt *r, const char *path)
{
    unsigned low = 0, high = r->nn;
    while (low < high) {
        unsigned mid = low + (high - low) / 2;
        int compared = strcmp(r->nodes[mid].v[KR_PATH], path);
        if (compared < 0) low = mid + 1; else high = mid;
    }
    return low < r->nn && !strcmp(r->nodes[low].v[KR_PATH], path) ? &r->nodes[low] : NULL;
}

static inline int kiosk_receipt_node(struct kiosk_receipt *r, struct kiosk_receipt_row *row)
{
    static const char *const kinds[] = {"tree", "directory", "empty-directory", "file", "link", "absent", NULL};
    static const char *const classes[] = {"skeleton", "native", "runtime", "payload", "vendor", "alias", "ambient", NULL};
    static const char *const roles[] = {"manager", "executor", "gate", "session-start", "leader", "service", "pipewire",
        "app-start", "notifications-start", "notification-client-start", "wellbeing-start", "audio-start", "packages-start",
        "audio", "rpm", "locale", "python", "gjs", "polkit", "bwrap", "bwrap-native", "glycin", "webkit", "scanner",
        "blocked", "library", "data", "skeleton", "ambient", "vendor", NULL};
    if (!kiosk_receipt_path(row->v[KR_PATH]) || !kiosk_receipt_member(row->v[KR_KIND], kinds) ||
        !kiosk_receipt_member(row->v[KR_CLASS], classes) || !kiosk_receipt_member(row->v[KR_ROLE], roles) ||
        kiosk_receipt_uint(row->v[KR_REQUIRED], &row->number[KR_REQUIRED]) != 0 || row->number[KR_REQUIRED] > 1 ||
        kiosk_receipt_uint(row->v[KR_MOUNT], &row->number[KR_MOUNT]) != 0 || row->number[KR_MOUNT] > 1) return -1;
    for (unsigned i = KR_INDEX; i <= KR_NLINK; i++) if (kiosk_receipt_uint(row->v[i], &row->number[i]) != 0) return -1;
    int ambient = !strcmp(row->v[KR_CLASS], "ambient"), skeleton = !strcmp(row->v[KR_CLASS], "skeleton");
    int file = !strcmp(row->v[KR_KIND], "file"), link = !strcmp(row->v[KR_KIND], "link"), tree = !strcmp(row->v[KR_KIND], "tree");
    int omitted = !strcmp(row->v[KR_KIND], "absent") || !strcmp(row->v[KR_KIND], "empty-directory");
    if (omitted) {
        if (!ambient || strcmp(row->v[KR_ROLE], "ambient") || row->number[KR_REQUIRED] || row->number[KR_MOUNT] ||
            strcmp(row->v[KR_ACQUIRE], "none") || strcmp(row->v[KR_SHA], "-") || strcmp(row->v[KR_LABEL], "-") || strcmp(row->v[KR_LINK], "-")) return -1;
        for (unsigned i = KR_DEV; i <= KR_NLINK; i++) if (row->number[i]) return -1;
        return 0;
    }
    if (!row->number[KR_INO] || !row->number[KR_ORIGIN_INO] ||
        strcmp(row->v[KR_ACQUIRE], !strcmp(r->kind, "V") ? "initial" : "retained") ||
        (row->number[KR_MODE] & S_IFMT) != (uint64_t) (file ? S_IFREG : link ? S_IFLNK : S_IFDIR)) return -1;
    if (file && !ambient ? !kiosk_receipt_hex(row->v[KR_SHA]) : strcmp(row->v[KR_SHA], "-")) return -1;
    if (link ? !strcmp(row->v[KR_LINK], "-") || row->number[KR_MOUNT] : strcmp(row->v[KR_LINK], "-")) return -1;
    if (tree ? !skeleton || strcmp(row->v[KR_ROLE], "skeleton") : skeleton) return -1;
    if (ambient ? row->number[KR_REQUIRED] || strcmp(row->v[KR_ROLE], "ambient") : !skeleton && !row->number[KR_REQUIRED]) return -1;
    if ((!strcmp(row->v[KR_CLASS], "native") || !strcmp(row->v[KR_CLASS], "payload") || !strcmp(row->v[KR_CLASS], "vendor")) && !file) return -1;
    if (!strcmp(row->v[KR_CLASS], "runtime") && !file && !link) return -1;
    if ((!strcmp(row->v[KR_CLASS], "runtime") || !strcmp(row->v[KR_CLASS], "payload")) && strcmp(row->v[KR_ROLE], "data")) return -1;
    if (!strcmp(row->v[KR_CLASS], "vendor") && strcmp(row->v[KR_ROLE], "vendor")) return -1;
    if (!strcmp(row->v[KR_CLASS], "alias") && (!link || strcmp(row->v[KR_ROLE], "data"))) return -1;
    if (file && (!strcmp(row->v[KR_CLASS], "native") || !strcmp(row->v[KR_CLASS], "runtime") ||
        !strcmp(row->v[KR_CLASS], "payload") || !strcmp(row->v[KR_CLASS], "vendor"))) {
        int retained_vendor = !strcmp(row->v[KR_CLASS], "vendor") && !strcmp(r->kind, "I");
        if (row->number[KR_NLINK] != 1 && !(retained_vendor && row->number[KR_NLINK] == 0)) return -1;
    }
    return 0;
}

/* Caller supplies bytes read from its checked owned descriptor with size and
 * pre/post identity guards. No filename, FD number or producer hash is trusted. */
static inline int kiosk_receipt_parse(struct kiosk_receipt *r, const void *data, size_t size,
                                      void *crypto, uint64_t deadline)
{
    memset(r, 0, sizeof(*r));
    if (!data || !size || size > KIOSK_RECEIPT_BYTES || ((const char *) data)[size - 1] != '\n' ||
        memchr(data, 0, size) || kiosk_receipt_before(deadline) != 0) return -1;
    unsigned lines = 0;
    for (size_t i = 0; i < size; i++) if (((const char *) data)[i] == '\n' && ++lines > KIOSK_RECEIPT_ROWS + 1) return -1;
    if (lines < 2 || (r->storage = malloc(size + 1)) == NULL ||
        (r->nodes = calloc(lines - 1, sizeof(*r->nodes))) == NULL ||
        (r->coverage = calloc(lines - 1, sizeof(*r->coverage))) == NULL) goto bad;
    memcpy(r->storage, data, size); r->storage[size] = 0;
    char *line = r->storage, *next = strchr(line, '\n'), *header[8];
    *next++ = 0;
    if (kiosk_receipt_fields(line, header, 8) != 0 || strcmp(header[0], "ONPC-KIOSK-RECEIPT") || strcmp(header[1], "2") ||
        (strcmp(header[2], "V") && strcmp(header[2], "I")) ||
        (strcmp(header[3], "apparmor") && strcmp(header[3], "selinux")) ||
        strcmp(header[4], !strcmp(header[2], "V") ? "manager" : "gate") ||
        !kiosk_receipt_hex(header[5]) || !kiosk_receipt_hex(header[7]) ||
        (!strcmp(header[2], "V") ? strcmp(header[6], "-") : !kiosk_receipt_hex(header[6]))) goto bad;
    r->kind = header[2]; r->backend = header[3]; r->role = header[4]; r->material = header[5];
    r->source = header[6]; r->acquisition = header[7];
    if (kiosk_receipt_hash(!strcmp(r->kind, "V") ? "ONPC-KIOSK-VIEW" : "ONPC-KIOSK-INVOCATION",
                           data, size, crypto, deadline, r->digest) != 0) goto bad;
    while (*next) {
        if (kiosk_receipt_before(deadline) != 0) goto bad;
        line = next; next = strchr(line, '\n');
        if (!next) goto bad;
        *next++ = 0;
        char *fields[KR_FIELDS + 1];
        if (line[0] == 'N' && line[1] == '\t' && !r->nc) {
            if (kiosk_receipt_fields(line, fields, KR_FIELDS + 1) != 0) goto bad;
            struct kiosk_receipt_row *row = &r->nodes[r->nn];
            memcpy(row->v, fields + 1, sizeof(row->v));
            if (kiosk_receipt_node(r, row) != 0 || (r->nn &&
                (strcmp(r->nodes[r->nn - 1].v[KR_PATH], row->v[KR_PATH]) >= 0 ||
                 r->nodes[r->nn - 1].number[KR_INDEX] >= row->number[KR_INDEX]))) goto bad;
            if (!r->nn) {
                if (strcmp(row->v[KR_PATH], "/usr") || strcmp(row->v[KR_KIND], "tree") ||
                    !row->number[KR_REQUIRED] || !row->number[KR_MOUNT]) goto bad;
            } else {
                char parent[KIOSK_RECEIPT_PATH]; strcpy(parent, row->v[KR_PATH]); *strrchr(parent, '/') = 0;
                const struct kiosk_receipt_row *found = kiosk_receipt_find(r, parent);
                if (!found || strcmp(found->v[KR_KIND], "tree")) goto bad;
            }
            r->nn++;
        } else if (line[0] == 'C' && line[1] == '\t' && r->nn) {
            if (kiosk_receipt_fields(line, fields, KC_FIELDS + 1) != 0) goto bad;
            struct kiosk_receipt_row *row = &r->coverage[r->nc];
            memcpy(row->v, fields + 1, KC_FIELDS * sizeof(char *));
            for (unsigned i = 0; i < KC_FIELDS; i++) if (i != KC_PATH && kiosk_receipt_uint(row->v[i], &row->number[i]) != 0) goto bad;
            if (!kiosk_receipt_path(row->v[KC_PATH]) || row->number[KC_OWNER] >= r->nn ||
                !row->number[KC_ORIGIN_INO] || !row->number[KC_INO] ||
                ((row->number[KC_MODE] & S_IFMT) != S_IFREG && (row->number[KC_MODE] & S_IFMT) != S_IFDIR) ||
                kiosk_receipt_find(r, row->v[KC_PATH]) ||
                (r->nc && strcmp(r->coverage[r->nc - 1].v[KC_PATH], row->v[KC_PATH]) >= 0)) goto bad;
            struct kiosk_receipt_row *owner = &r->nodes[row->number[KC_OWNER]];
            size_t n = strlen(owner->v[KR_PATH]);
            if (strcmp(owner->v[KR_KIND], "directory") || strncmp(row->v[KC_PATH], owner->v[KR_PATH], n) || row->v[KC_PATH][n] != '/') goto bad;
            r->nc++;
        } else goto bad;
    }
    if (!r->nn || kiosk_receipt_before(deadline) != 0) goto bad;
    return 0;
bad:
    kiosk_receipt_free(r); return -1;
}

/* expected is constructed natively from selected attested inventory, original
 * indices and independent inode/link/coverage observations. Never construct it
 * by copying producer flags. Exact comparison also closes omitted C witnesses. */
static inline int kiosk_receipt_match(const struct kiosk_receipt *actual, const struct kiosk_receipt *expected,
                                      uint64_t deadline)
{
    if (kiosk_receipt_before(deadline) != 0 || actual->nn != expected->nn || actual->nc != expected->nc ||
        strcmp(actual->kind, expected->kind) || strcmp(actual->backend, expected->backend) ||
        strcmp(actual->role, expected->role) || strcmp(actual->material, expected->material) ||
        strcmp(actual->source, expected->source) || strcmp(actual->acquisition, expected->acquisition)) return -1;
    for (unsigned group = 0; group < 2; group++) {
        unsigned count = group ? actual->nc : actual->nn, fields = group ? KC_FIELDS : KR_FIELDS;
        const struct kiosk_receipt_row *left = group ? actual->coverage : actual->nodes, *right = group ? expected->coverage : expected->nodes;
        for (unsigned i = 0; i < count; i++) {
            if (kiosk_receipt_before(deadline) != 0) return -1;
            for (unsigned j = 0; j < fields; j++) if (strcmp(left[i].v[j], right[i].v[j])) return -1;
        }
    }
    return 0;
}

static inline int kiosk_receipt_derivation(const struct kiosk_receipt *v, const struct kiosk_receipt *invocation,
                                           uint64_t deadline)
{
    static const unsigned invariant[] = {KR_PATH, KR_REQUIRED, KR_CLASS, KR_ROLE, KR_INDEX, KR_ORIGIN_DEV, KR_ORIGIN_INO};
    static const unsigned source[] = {KR_SHA, KR_LABEL, KR_LINK, KR_MOUNT};
    static const unsigned coverage[] = {KC_OWNER, KC_PATH, KC_ORIGIN_DEV, KC_ORIGIN_INO, KC_DEV, KC_INO};
    static const unsigned required_metadata[] = {KR_SIZE, KR_MODE, KR_UID, KR_GID};
    if (kiosk_receipt_before(deadline) != 0 || strcmp(v->kind, "V") || strcmp(invocation->kind, "I") ||
        strcmp(v->backend, invocation->backend) || strcmp(v->material, invocation->material) ||
        strcmp(v->digest, invocation->source) || v->nn != invocation->nn) return -1;
    for (unsigned i = 0; i < v->nn; i++) {
        if (kiosk_receipt_before(deadline) != 0) return -1;
        const struct kiosk_receipt_row *old = &v->nodes[i], *now = &invocation->nodes[i];
        for (unsigned j = 0; j < sizeof(invariant) / sizeof(*invariant); j++) if (strcmp(old->v[invariant[j]], now->v[invariant[j]])) return -1;
        if (strcmp(old->v[KR_KIND], now->v[KR_KIND])) {
            if (old->number[KR_REQUIRED]) return -1;
            if (!strcmp(old->v[KR_KIND], "directory")) { if (strcmp(now->v[KR_KIND], "empty-directory")) return -1; }
            else if (!strcmp(old->v[KR_KIND], "file") || !strcmp(old->v[KR_KIND], "link")) { if (strcmp(now->v[KR_KIND], "absent")) return -1; }
            else return -1;
        } else if (strcmp(old->v[KR_KIND], "tree") && strcmp(old->v[KR_KIND], "empty-directory") && strcmp(old->v[KR_KIND], "absent")) {
            /* Links are recreated in new private parents. Their exact text,
             * original inode provenance and role survive, their new inode
             * must be independently witnessed by the native expected record. */
            if (strcmp(old->v[KR_KIND], "link") &&
                (strcmp(old->v[KR_DEV], now->v[KR_DEV]) || strcmp(old->v[KR_INO], now->v[KR_INO]))) return -1;
            for (unsigned j = 0; j < sizeof(source) / sizeof(*source); j++) if (strcmp(old->v[source[j]], now->v[source[j]])) return -1;
            if (!strcmp(old->v[KR_CLASS], "native") || !strcmp(old->v[KR_CLASS], "runtime") ||
                !strcmp(old->v[KR_CLASS], "payload") || !strcmp(old->v[KR_CLASS], "vendor"))
                for (unsigned j = 0; j < sizeof(required_metadata) / sizeof(*required_metadata); j++)
                    if (strcmp(old->v[required_metadata[j]], now->v[required_metadata[j]])) return -1;
        }
    }
    unsigned selected = 0;
    for (unsigned i = 0; i < v->nc; i++) {
        if (kiosk_receipt_before(deadline) != 0) return -1;
        const struct kiosk_receipt_row *old = &v->coverage[i];
        if (strcmp(invocation->nodes[old->number[KC_OWNER]].v[KR_KIND], "directory")) continue;
        if (selected >= invocation->nc) return -1;
        const struct kiosk_receipt_row *now = &invocation->coverage[selected++];
        for (unsigned j = 0; j < sizeof(coverage) / sizeof(*coverage); j++) if (strcmp(old->v[coverage[j]], now->v[coverage[j]])) return -1;
    }
    return selected == invocation->nc ? kiosk_receipt_before(deadline) : -1;
}
#endif
