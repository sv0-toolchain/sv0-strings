/* sv0-strings independent C23 differential oracle -- SS-141 / BL-059 /
 * TEST-012 / SPEC Section 21.4.
 *
 * This is TEST INFRASTRUCTURE, not runtime code. It computes the expected
 * result of a C23 <string.h> operation using the host C library, on inputs
 * whose C preconditions it has already validated, so it NEVER invokes C
 * undefined behaviour:
 *
 *   1. compiled against a recorded C standard + flags (see build.sh; the
 *      compiler id and __STDC_VERSION__ are echoed in every response);
 *   2. every C precondition (non-null, capacity, no-overlap, NUL within a
 *      bounded window) is checked BEFORE the standard function is called --
 *      a failed precondition prints `precondition=FAILED:<why>` and returns
 *      without calling anything;
 *   3. mutable destination buffers are surrounded by guard bytes and the
 *      guard region is verified after the call (`guard=ok` / `VIOLATED`);
 *   4. results are serialized as semantic values -- written bytes, lengths,
 *      normalized orderings (-1/0/1), found offsets, error names -- never a
 *      raw pointer value or an unspecified comparison magnitude.
 *
 * Protocol: one request per process on stdin, `key=value` lines terminated
 * by a blank line or EOF; one response of `key=value` lines on stdout.
 *
 *   fn=<name>                which operation
 *   src=h:<hex>              a read-only byte argument (hex pairs)
 *   a=h:<hex>  b=h:<hex>     comparison operands
 *   cstr=h:<hex>             a byte argument treated as a C string
 *   value=i:<0..255>         a fill byte
 *   n=i:<k>                  an explicit length / count
 *   cap=i:<k>               destination capacity (mutable-buffer ops)
 *   guard=i:<k>              guard-byte padding each side (default 8)
 *
 * Wired operations (SS-142+ extend the table):
 *   memcpy   guarded write, forbids overlap
 *   memmove  guarded write, overlap allowed
 *   memccpy  guarded write up to a stop byte; ret=idx:<past-stop>|idx:none + written=
 *   memset   guarded write
 *   memcmp   normalized ordering
 *   strlen   bounded read -> length
 */

/* memccpy is C23 (previously POSIX.1); expose it on the C17 fallback too. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ORACLE_LINE 65536
#define ORACLE_MAXBYTES 8192
#define GUARD_BYTE 0xA5

/* ---- compiler / standard provenance -------------------------------------- */

static const char *impl_id(void) {
#if defined(__clang__)
    static char buf[64];
    snprintf(buf, sizeof buf, "clang-%d.%d.%d", __clang_major__,
             __clang_minor__, __clang_patchlevel__);
    return buf;
#elif defined(__GNUC__)
    static char buf[64];
    snprintf(buf, sizeof buf, "gcc-%d.%d.%d", __GNUC__, __GNUC_MINOR__,
             __GNUC_PATCHLEVEL__);
    return buf;
#else
    return "unknown-cc";
#endif
}

static long std_version(void) {
#ifdef __STDC_VERSION__
    return (long)__STDC_VERSION__;
#else
    return 0L;
#endif
}

/* ---- hex parsing / serialization --------------------------------------- */

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* Parse "h:<hexpairs>" into out (<= ORACLE_MAXBYTES). Returns length, or -1. */
static long parse_hex(const char *v, unsigned char *out) {
    if (v[0] != 'h' || v[1] != ':') return -1;
    v += 2;
    long n = 0;
    while (v[0] && v[1]) {
        int hi = hexval((unsigned char)v[0]);
        int lo = hexval((unsigned char)v[1]);
        if (hi < 0 || lo < 0) return -1;
        if (n >= ORACLE_MAXBYTES) return -1;
        out[n++] = (unsigned char)((hi << 4) | lo);
        v += 2;
    }
    if (v[0]) return -1; /* odd number of hex digits */
    return n;
}

static int parse_int(const char *v, long *out) {
    if (v[0] != 'i' || v[1] != ':') return -1;
    char *end = NULL;
    errno = 0;
    long r = strtol(v + 2, &end, 10);
    if (errno != 0 || end == v + 2 || *end != '\0') return -1;
    *out = r;
    return 0;
}

static void emit_hex(const char *key, const unsigned char *b, long n) {
    printf("%s=h:", key);
    for (long i = 0; i < n; i++) printf("%02x", b[i]);
    printf("\n");
}

static const char *errno_name(int e) {
    switch (e) {
        case 0: return "0";
        case EINVAL: return "EINVAL";
        case ERANGE: return "ERANGE";
        case ENOMEM: return "ENOMEM";
        default: return "OTHER";
    }
}

/* ---- request fields ---------------------------------------------------- */

struct req {
    char fn[64];
    unsigned char src[ORACLE_MAXBYTES];
    long src_n;               /* -1 if absent */
    unsigned char a[ORACLE_MAXBYTES];
    long a_n;
    unsigned char b[ORACLE_MAXBYTES];
    long b_n;
    unsigned char cstr[ORACLE_MAXBYTES];
    long cstr_n;
    long value;               /* fill byte; -1 if absent */
    long n;                   /* explicit count; -1 if absent */
    long cap;                 /* destination capacity; -1 if absent */
    long guard;               /* guard padding; default 8 */
};

static void req_init(struct req *r) {
    memset(r, 0, sizeof *r);
    r->src_n = r->a_n = r->b_n = r->cstr_n = -1;
    r->value = r->n = r->cap = -1;
    r->guard = 8;
}

/* returns 0 on ok, -1 on a malformed line */
static int req_set(struct req *r, const char *key, const char *val) {
    if (strcmp(key, "fn") == 0) {
        snprintf(r->fn, sizeof r->fn, "%s", val);
        return 0;
    }
    if (strcmp(key, "src") == 0)  { r->src_n  = parse_hex(val, r->src);  return r->src_n  < 0 ? -1 : 0; }
    if (strcmp(key, "a") == 0)    { r->a_n    = parse_hex(val, r->a);    return r->a_n    < 0 ? -1 : 0; }
    if (strcmp(key, "b") == 0)    { r->b_n    = parse_hex(val, r->b);    return r->b_n    < 0 ? -1 : 0; }
    if (strcmp(key, "cstr") == 0) { r->cstr_n = parse_hex(val, r->cstr); return r->cstr_n < 0 ? -1 : 0; }
    if (strcmp(key, "value") == 0) return parse_int(val, &r->value);
    if (strcmp(key, "n") == 0)     return parse_int(val, &r->n);
    if (strcmp(key, "cap") == 0)   return parse_int(val, &r->cap);
    if (strcmp(key, "guard") == 0) return parse_int(val, &r->guard);
    return -1; /* unknown key */
}

/* ---- guarded destination buffer -------------------------------------- */

struct dbuf {
    unsigned char *base;   /* malloc'd: [guard][payload cap][guard] */
    unsigned char *pay;    /* base + guard */
    long cap;
    long guard;
};

static int dbuf_alloc(struct dbuf *d, long cap, long guard) {
    if (cap < 0 || guard < 0 || cap > ORACLE_MAXBYTES || guard > 4096) return -1;
    d->cap = cap;
    d->guard = guard;
    d->base = malloc((size_t)(guard + cap + guard) + 1u);
    if (!d->base) return -1;
    memset(d->base, GUARD_BYTE, (size_t)(guard + cap + guard));
    d->pay = d->base + guard;
    return 0;
}

static const char *dbuf_guard_state(const struct dbuf *d) {
    for (long i = 0; i < d->guard; i++)
        if (d->base[i] != GUARD_BYTE) return "VIOLATED:lo";
    for (long i = 0; i < d->guard; i++)
        if (d->pay[d->cap + i] != GUARD_BYTE) return "VIOLATED:hi";
    return "ok";
}

static void dbuf_free(struct dbuf *d) { free(d->base); d->base = NULL; }

/* ---- response helpers ---------------------------------------------------- */

static int fail_pre(const char *why) {
    printf("precondition=FAILED:%s\n", why);
    return 0;
}

static int norm_ord(int c) { return c < 0 ? -1 : (c > 0 ? 1 : 0); }

/* ---- operations ------------------------------------------------------- */

static int op_memcpy(const struct req *r) {
    if (r->src_n < 0) return fail_pre("src-missing");
    if (r->n < 0)     return fail_pre("n-missing");
    if (r->cap < 0)   return fail_pre("cap-missing");
    if (r->n > r->src_n) return fail_pre("n-gt-src");
    if (r->n > r->cap)   return fail_pre("n-gt-cap");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    /* memcpy forbids overlap; our src is a separate malloc region, but assert
       the ranges are disjoint anyway (they always are here). */
    if (!((r->src + r->n <= d.pay) || (d.pay + r->n <= r->src))) {
        dbuf_free(&d);
        return fail_pre("overlap");
    }
    errno = 0;
    void *ret = memcpy(d.pay, r->src, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_memset(const struct req *r) {
    if (r->value < 0)  return fail_pre("value-missing");
    if (r->n < 0)      return fail_pre("n-missing");
    if (r->cap < 0)    return fail_pre("cap-missing");
    if (r->value > 255) return fail_pre("value-range");
    if (r->n > r->cap)  return fail_pre("n-gt-cap");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    errno = 0;
    void *ret = memset(d.pay, (int)r->value, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_memmove(const struct req *r) {
    if (r->src_n < 0) return fail_pre("src-missing");
    if (r->n < 0)     return fail_pre("n-missing");
    if (r->cap < 0)   return fail_pre("cap-missing");
    if (r->n > r->src_n) return fail_pre("n-gt-src");
    if (r->n > r->cap)   return fail_pre("n-gt-cap");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    errno = 0;
    void *ret = memmove(d.pay, r->src, (size_t)r->n); /* overlap allowed */
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_memccpy(const struct req *r) {
    if (r->src_n < 0)   return fail_pre("src-missing");
    if (r->value < 0)   return fail_pre("stop-missing"); /* `value` carries the stop byte */
    if (r->n < 0)       return fail_pre("n-missing");
    if (r->cap < 0)     return fail_pre("cap-missing");
    if (r->value > 255) return fail_pre("stop-range");
    if (r->n > r->cap)   return fail_pre("n-gt-cap");
    /* memccpy reads src until the stop byte or n bytes, whichever first --
       it is only safe if that many bytes exist in src. */
    {
        long scan = r->n < r->src_n ? r->n : r->src_n;
        long stop_at = -1;
        for (long i = 0; i < scan; i++)
            if (r->src[i] == (unsigned char)r->value) { stop_at = i; break; }
        if (stop_at < 0 && r->n > r->src_n) return fail_pre("no-stop-in-src");
    }

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    errno = 0;
    void *ret = memccpy(d.pay, r->src, (int)r->value, (size_t)r->n);
    long written = ret ? (long)((unsigned char *)ret - d.pay) : r->n;
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - d.pay));
    else     printf("ret=idx:none\n");
    printf("written=%ld\n", written);
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_memcmp(const struct req *r) {
    if (r->a_n < 0) return fail_pre("a-missing");
    if (r->b_n < 0) return fail_pre("b-missing");
    if (r->n < 0)   return fail_pre("n-missing");
    if (r->n > r->a_n) return fail_pre("n-gt-a");
    if (r->n > r->b_n) return fail_pre("n-gt-b");

    errno = 0;
    int c = memcmp(r->a, r->b, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ord:%d\n", norm_ord(c));
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strlen(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    /* Bounded window: the argument must contain a NUL within the bytes given,
       otherwise strlen would run off the end (UB). */
    long k = -1;
    for (long i = 0; i < r->cstr_n; i++)
        if (r->cstr[i] == 0) { k = i; break; }
    if (k < 0) return fail_pre("no-nul-in-window");

    errno = 0;
    size_t len = strlen((const char *)r->cstr);
    printf("precondition=ok\n");
    printf("ret=i:%zu\n", len);
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

/* ---- dispatch --------------------------------------------------------- */

static int dispatch(const struct req *r) {
    printf("impl=%s\n", impl_id());
    printf("std=%ld\n", std_version());
    printf("fn=%s\n", r->fn);
    if (strcmp(r->fn, "memcpy") == 0)  return op_memcpy(r);
    if (strcmp(r->fn, "memmove") == 0) return op_memmove(r);
    if (strcmp(r->fn, "memccpy") == 0) return op_memccpy(r);
    if (strcmp(r->fn, "memset") == 0)  return op_memset(r);
    if (strcmp(r->fn, "memcmp") == 0)  return op_memcmp(r);
    if (strcmp(r->fn, "strlen") == 0)  return op_strlen(r);
    printf("precondition=FAILED:unknown-fn\n");
    return 0;
}

int main(void) {
    struct req r;
    req_init(&r);
    char line[ORACLE_LINE];
    int have_fn = 0;
    while (fgets(line, sizeof line, stdin)) {
        size_t L = strlen(line);
        while (L > 0 && (line[L - 1] == '\n' || line[L - 1] == '\r')) line[--L] = 0;
        if (L == 0) break; /* blank line ends the request */
        char *eq = strchr(line, '=');
        if (!eq) {
            fprintf(stderr, "oracle: malformed line: %s\n", line);
            return 2;
        }
        *eq = 0;
        if (req_set(&r, line, eq + 1) != 0) {
            fprintf(stderr, "oracle: bad field: %s\n", line);
            return 2;
        }
        if (strcmp(line, "fn") == 0) have_fn = 1;
    }
    if (!have_fn) {
        fprintf(stderr, "oracle: no fn= given\n");
        return 2;
    }
    return dispatch(&r);
}
