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
 *   memchr   ret=idx:<n>|idx:none (bounded by n <= src_n)
 *   strchr   ret=idx:<n>|idx:none (cstr must contain a NUL in-window; value= is the byte)
 *   strrchr  same shape as strchr, last match
 *   strpbrk  ret=idx:<n>|idx:none (cstr= haystack, a= accept set, both NUL-in-window)
 *   strstr   ret=idx:<n>|idx:none (cstr= haystack, a= needle, both NUL-in-window)
 *   strcmp   normalized ordering (a, b both NUL-in-window)
 *   strncmp  normalized ordering, bounded by n (a, b need NOT contain a NUL)
 *   strcpy   guarded write; cstr= source C string, cap must fit it + NUL
 *   strncpy  guarded write, exact zero-padding; src= bounded (need not be NUL-terminated)
 *   strcat   guarded write; src= dst's initial content (NUL-in-window), cstr= string to append
 *   strncat  same as strcat, bounded by n; cstr need not contain a NUL within n
 *   strdup   fresh allocation; cstr= source C string (NUL-in-window); ret=ptr:nonnull, out=, term=
 *   strndup  fresh allocation, bounded by n; src need not contain a NUL within n
 *   strspn   bounded read -> length; cstr= s, a= accept set (both NUL-in-window)
 *   strcspn  bounded read -> length; cstr= s, a= reject set (both NUL-in-window)
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

/* -1 if no NUL within [0, n); else the offset of the first one. */
static long find_nul(const unsigned char *buf, long n) {
    for (long i = 0; i < n; i++)
        if (buf[i] == 0) return i;
    return -1;
}

static int op_memchr(const struct req *r) {
    if (r->src_n < 0) return fail_pre("src-missing");
    if (r->value < 0) return fail_pre("value-missing");
    if (r->n < 0)      return fail_pre("n-missing");
    if (r->value > 255) return fail_pre("value-range");
    if (r->n > r->src_n) return fail_pre("n-gt-src");

    errno = 0;
    void *ret = memchr(r->src, (int)r->value, (size_t)r->n);
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - r->src));
    else     printf("ret=idx:none\n");
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strchr(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->value < 0)  return fail_pre("value-missing");
    if (r->value > 255) return fail_pre("value-range");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window");

    errno = 0;
    char *ret = strchr((const char *)r->cstr, (int)r->value);
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - r->cstr));
    else     printf("ret=idx:none\n");
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strrchr(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->value < 0)  return fail_pre("value-missing");
    if (r->value > 255) return fail_pre("value-range");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window");

    errno = 0;
    char *ret = strrchr((const char *)r->cstr, (int)r->value);
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - r->cstr));
    else     printf("ret=idx:none\n");
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strpbrk(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->a_n < 0)    return fail_pre("a-missing");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window:cstr");
    if (find_nul(r->a, r->a_n) < 0)       return fail_pre("no-nul-in-window:a");

    errno = 0;
    char *ret = strpbrk((const char *)r->cstr, (const char *)r->a);
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - r->cstr));
    else     printf("ret=idx:none\n");
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strstr(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->a_n < 0)    return fail_pre("a-missing");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window:cstr");
    if (find_nul(r->a, r->a_n) < 0)       return fail_pre("no-nul-in-window:a");

    errno = 0;
    char *ret = strstr((const char *)r->cstr, (const char *)r->a);
    printf("precondition=ok\n");
    if (ret) printf("ret=idx:%ld\n", (long)((unsigned char *)ret - r->cstr));
    else     printf("ret=idx:none\n");
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strcmp(const struct req *r) {
    if (r->a_n < 0) return fail_pre("a-missing");
    if (r->b_n < 0) return fail_pre("b-missing");
    if (find_nul(r->a, r->a_n) < 0) return fail_pre("no-nul-in-window:a");
    if (find_nul(r->b, r->b_n) < 0) return fail_pre("no-nul-in-window:b");

    errno = 0;
    int c = strcmp((const char *)r->a, (const char *)r->b);
    printf("precondition=ok\n");
    printf("ret=ord:%d\n", norm_ord(c));
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strncmp(const struct req *r) {
    if (r->a_n < 0) return fail_pre("a-missing");
    if (r->b_n < 0) return fail_pre("b-missing");
    if (r->n < 0)   return fail_pre("n-missing");
    if (r->n > r->a_n) return fail_pre("n-gt-a");
    if (r->n > r->b_n) return fail_pre("n-gt-b");

    errno = 0;
    int c = strncmp((const char *)r->a, (const char *)r->b, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ord:%d\n", norm_ord(c));
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strcpy(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->cap < 0)    return fail_pre("cap-missing");
    long k = find_nul(r->cstr, r->cstr_n);
    if (k < 0) return fail_pre("no-nul-in-window");
    if (k + 1 > r->cap) return fail_pre("cap-too-small");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    errno = 0;
    char *ret = strcpy((char *)d.pay, (const char *)r->cstr);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == (char *)d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_strncpy(const struct req *r) {
    if (r->src_n < 0) return fail_pre("src-missing");
    if (r->n < 0)      return fail_pre("n-missing");
    if (r->cap < 0)    return fail_pre("cap-missing");
    if (r->n > r->cap) return fail_pre("n-gt-cap");
    {
        long scan = r->n < r->src_n ? r->n : r->src_n;
        long nul_at = find_nul(r->src, scan);
        if (nul_at < 0 && r->n > r->src_n) return fail_pre("no-nul-and-n-gt-src");
    }

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    errno = 0;
    char *ret = strncpy((char *)d.pay, (const char *)r->src, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == (char *)d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

/* strcat/strncat: `src` carries the CBuffer's INITIAL content (must already
   hold a NUL somewhere within it -- that's the real strcat precondition:
   dst must already be a valid C string); `cstr` is the string to append. */
static int op_strcat(const struct req *r) {
    if (r->src_n < 0)  return fail_pre("src-missing");
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->cap < 0)    return fail_pre("cap-missing");
    if (r->src_n > r->cap) return fail_pre("src-gt-cap");
    long f = find_nul(r->src, r->src_n);
    if (f < 0) return fail_pre("dst-no-nul");
    long k = find_nul(r->cstr, r->cstr_n);
    if (k < 0) return fail_pre("cstr-no-nul-in-window");
    if (f + k + 1 > r->cap) return fail_pre("cap-too-small");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    memset(d.pay, 0xEE, (size_t)r->cap);
    memcpy(d.pay, r->src, (size_t)r->src_n);
    errno = 0;
    char *ret = strcat((char *)d.pay, (const char *)r->cstr);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == (char *)d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_strncat(const struct req *r) {
    if (r->src_n < 0)  return fail_pre("src-missing");
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->cap < 0)    return fail_pre("cap-missing");
    if (r->n < 0)      return fail_pre("n-missing");
    if (r->src_n > r->cap) return fail_pre("src-gt-cap");
    long f = find_nul(r->src, r->src_n);
    if (f < 0) return fail_pre("dst-no-nul");

    long scan = r->n < r->cstr_n ? r->n : r->cstr_n;
    long k = find_nul(r->cstr, scan);
    if (k < 0 && r->n > r->cstr_n) return fail_pre("no-nul-and-n-gt-cstr");
    long appended = (k >= 0) ? k : scan;
    if (f + appended + 1 > r->cap) return fail_pre("cap-too-small");

    struct dbuf d;
    if (dbuf_alloc(&d, r->cap, r->guard) != 0) return fail_pre("alloc");
    memset(d.pay, 0xEE, (size_t)r->cap);
    memcpy(d.pay, r->src, (size_t)r->src_n);
    errno = 0;
    char *ret = strncat((char *)d.pay, (const char *)r->cstr, (size_t)r->n);
    printf("precondition=ok\n");
    printf("ret=ptr:%s\n", ret == (char *)d.pay ? "dst" : "other");
    emit_hex("out", d.pay, r->cap);
    printf("outlen=%ld\n", r->cap);
    printf("guard=%s\n", dbuf_guard_state(&d));
    printf("errno=%s\n", errno_name(errno));
    dbuf_free(&d);
    return 0;
}

static int op_strdup(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    long k = find_nul(r->cstr, r->cstr_n);
    if (k < 0) return fail_pre("no-nul-in-window");

    errno = 0;
    char *ret = strdup((const char *)r->cstr);
    if (!ret) {
        printf("precondition=ok\n");
        printf("ret=ptr:null\n");
        printf("errno=%s\n", errno_name(errno));
        return 0;
    }
    printf("precondition=ok\n");
    printf("ret=ptr:nonnull\n");
    emit_hex("out", (const unsigned char *)ret, k);
    printf("outlen=%ld\n", k);
    printf("term=%s\n", ret[k] == 0 ? "ok" : "MISSING");
    printf("errno=%s\n", errno_name(errno));
    free(ret);
    return 0;
}

static int op_strndup(const struct req *r) {
    if (r->src_n < 0) return fail_pre("src-missing");
    if (r->n < 0)      return fail_pre("n-missing");
    {
        long scan = r->n < r->src_n ? r->n : r->src_n;
        long nul_at = find_nul(r->src, scan);
        if (nul_at < 0 && r->n > r->src_n) return fail_pre("no-nul-and-n-gt-src");
    }

    errno = 0;
    char *ret = strndup((const char *)r->src, (size_t)r->n);
    if (!ret) {
        printf("precondition=ok\n");
        printf("ret=ptr:null\n");
        printf("errno=%s\n", errno_name(errno));
        return 0;
    }
    long len = (long)strlen(ret);
    printf("precondition=ok\n");
    printf("ret=ptr:nonnull\n");
    emit_hex("out", (const unsigned char *)ret, len);
    printf("outlen=%ld\n", len);
    printf("term=%s\n", ret[len] == 0 ? "ok" : "MISSING");
    printf("errno=%s\n", errno_name(errno));
    free(ret);
    return 0;
}

static int op_strspn(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->a_n < 0)    return fail_pre("a-missing");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window:cstr");
    if (find_nul(r->a, r->a_n) < 0)       return fail_pre("no-nul-in-window:a");

    errno = 0;
    size_t len = strspn((const char *)r->cstr, (const char *)r->a);
    printf("precondition=ok\n");
    printf("ret=i:%zu\n", len);
    printf("errno=%s\n", errno_name(errno));
    return 0;
}

static int op_strcspn(const struct req *r) {
    if (r->cstr_n < 0) return fail_pre("cstr-missing");
    if (r->a_n < 0)    return fail_pre("a-missing");
    if (find_nul(r->cstr, r->cstr_n) < 0) return fail_pre("no-nul-in-window:cstr");
    if (find_nul(r->a, r->a_n) < 0)       return fail_pre("no-nul-in-window:a");

    errno = 0;
    size_t len = strcspn((const char *)r->cstr, (const char *)r->a);
    printf("precondition=ok\n");
    printf("ret=i:%zu\n", len);
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
    if (strcmp(r->fn, "memchr") == 0)  return op_memchr(r);
    if (strcmp(r->fn, "strchr") == 0)  return op_strchr(r);
    if (strcmp(r->fn, "strrchr") == 0) return op_strrchr(r);
    if (strcmp(r->fn, "strpbrk") == 0) return op_strpbrk(r);
    if (strcmp(r->fn, "strstr") == 0)  return op_strstr(r);
    if (strcmp(r->fn, "strcmp") == 0)  return op_strcmp(r);
    if (strcmp(r->fn, "strncmp") == 0) return op_strncmp(r);
    if (strcmp(r->fn, "strcpy") == 0)  return op_strcpy(r);
    if (strcmp(r->fn, "strncpy") == 0) return op_strncpy(r);
    if (strcmp(r->fn, "strcat") == 0)  return op_strcat(r);
    if (strcmp(r->fn, "strncat") == 0) return op_strncat(r);
    if (strcmp(r->fn, "strdup") == 0)  return op_strdup(r);
    if (strcmp(r->fn, "strndup") == 0) return op_strndup(r);
    if (strcmp(r->fn, "strspn") == 0)  return op_strspn(r);
    if (strcmp(r->fn, "strcspn") == 0) return op_strcspn(r);
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
