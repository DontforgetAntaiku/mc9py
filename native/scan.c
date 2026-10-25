#include "scan.h"
#include <string.h>
#include <ctype.h>
#include <stdlib.h>

static void collect_ranges(Module *m) {
    BYTE *p = m->base, *end = m->base + m->size;
    m->nr = 0;
    while (p < end && m->nr < MAX_RANGES) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(p, &mbi, sizeof mbi)) break;
        BYTE *lo = (BYTE *)mbi.BaseAddress, *hi = lo + mbi.RegionSize;
        int ok = mbi.State == MEM_COMMIT && !(mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) && mbi.Protect != 0;
        if (ok) {
            if (lo < m->base) lo = m->base;
            if (hi > end) hi = end;
            if (m->nr && m->r[m->nr - 1].lo + m->r[m->nr - 1].len == lo) m->r[m->nr - 1].len += (size_t)(hi - lo);
            else { m->r[m->nr].lo = lo; m->r[m->nr].len = (size_t)(hi - lo); m->nr++; }
        }
        p = hi > p ? hi : p + 0x1000;
    }
}

int mod_open(Module *m, HMODULE h) {
    BYTE *b = (BYTE *)h;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)b;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(b + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;
    memset(m, 0, sizeof *m);
    m->base = b; m->size = nt->OptionalHeader.SizeOfImage; m->stamp = nt->FileHeader.TimeDateStamp;
    collect_ranges(m);
    DWORD hash = 2166136261u ^ m->size;               /* FNV-1a over the first 64 KiB of code (RVA 0x1000) */
    if (m->size > 0x1000 + 65536)
        for (DWORD i = 0; i < 65536; i++) hash = (hash ^ b[0x1000 + i]) * 16777619u;
    m->fingerprint = hash;
    return m->nr > 0;
}

int mod_unpacked(const Module *m) {
    for (int i = 0; i < 256; i++) if (m->base[0x1000 + i]) return 1;   /* UPX leaves the code area empty until it has run */
    return 0;
}

int in_text(const Module *m, const void *p) {
    return (const BYTE *)p >= m->base + 0x1000 && (const BYTE *)p < m->base + m->size;
}

static int hexval(int c) { return isdigit(c) ? c - '0' : (tolower(c) >= 'a' && tolower(c) <= 'f') ? tolower(c) - 'a' + 10 : -1; }

int pat_parse(Pattern *p, const char *t) {
    p->n = 0;
    while (*t) {
        while (*t == ' ') t++;
        if (!*t) break;
        if (p->n >= PAT_MAX) return 0;
        if (t[0] == '?') { p->b[p->n] = 0; p->m[p->n++] = 0; t += (t[1] == '?') ? 2 : 1; continue; }
        int hi = hexval(t[0]), lo = hexval(t[1]);
        if (hi < 0 || lo < 0) return 0;
        p->b[p->n] = (BYTE)(hi * 16 + lo); p->m[p->n++] = 1; t += 2;
    }
    return p->n > 0;
}

size_t pat_scan(const BYTE *lo, size_t len, const Pattern *p, BYTE **out, size_t max) {
    size_t found = 0;
    int first = 0;
    while (first < p->n && !p->m[first]) first++;        /* index of the first fixed byte, anchors memchr */
    if (first >= p->n || len < (size_t)p->n) return 0;
    const BYTE *end = lo + len - p->n;
    const BYTE *s = lo;
    while (s <= end) {
        const BYTE *c = memchr(s + first, p->b[first], (size_t)(end - s) + 1);
        if (!c) break;
        s = c - first;
        int ok = 1;
        for (int i = 0; i < p->n; i++) if (p->m[i] && s[i] != p->b[i]) { ok = 0; break; }
        if (ok) { if (found < max) out[found] = (BYTE *)s; found++; }
        s++;
    }
    return found;
}

static size_t scan_all(const Module *m, const Pattern *p, BYTE **out, size_t max) {
    size_t found = 0;
    for (int i = 0; i < m->nr; i++) {
        BYTE *tmp[64];
        size_t n = pat_scan(m->r[i].lo, m->r[i].len, p, tmp, 64);
        for (size_t k = 0; k < n && k < 64; k++) { if (found < max) out[found] = tmp[k]; found++; }
    }
    return found;
}

BYTE *pat_unique(const Module *m, const Pattern *p, size_t *count) {
    BYTE *hit[2];
    size_t n = scan_all(m, p, hit, 2);
    if (count) *count = n;
    return n == 1 ? hit[0] : NULL;
}

size_t pat_scan_module(const Module *m, const Pattern *p, BYTE **out, size_t max) { return scan_all(m, p, out, max); }

BYTE *find_string(const Module *m, const char *s) {
    size_t n = strlen(s) + 1;
    for (int i = 0; i < m->nr; i++) {
        const Range *r = &m->r[i];
        for (BYTE *c = r->lo; c + n <= r->lo + r->len; c++) {
            c = memchr(c, s[0], (size_t)(r->lo + r->len - n - c) + 1);
            if (!c) break;
            if (memcmp(c, s, n) == 0 && (c == m->base || c[-1] == 0)) return c;
        }
    }
    return NULL;
}

/* an immediate/absolute operand: push imm32, mov r32,imm32, or a ModRM [disp32] form of the common opcodes */
static int code_ref(const BYTE *c) {
    BYTE p1 = c[-1], p2 = c[-2];
    if (p1 == 0x68 || (p1 >= 0xB8 && p1 <= 0xBF) || p1 == 0xA1 || p1 == 0xA3) return 1;
    if ((p1 & 0xC7) == 0x05 && (p2 == 0x8B || p2 == 0x8D || p2 == 0x89 || p2 == 0x03 || p2 == 0x3B || p2 == 0x39 || p2 == 0x2B || p2 == 0xFF)) return 1;
    if ((p1 & 0xF8) == 0xC0 && p2 == 0x81) return 1;
    if (p1 == 0x05 && p2 == 0xC7) return 1;
    return 0;
}

size_t xrefs(const Module *m, DWORD value, BYTE **out, size_t max) {
    size_t found = 0;
    BYTE v[4]; memcpy(v, &value, 4);
    for (int i = 0; i < m->nr; i++) {
        const Range *r = &m->r[i];
        if (r->len < 4) continue;
        for (BYTE *c = r->lo; c + 4 <= r->lo + r->len; c++) {
            c = memchr(c, v[0], (size_t)(r->lo + r->len - 4 - c) + 1);
            if (!c) break;
            if (memcmp(c, v, 4) == 0 && in_text(m, c) && code_ref(c)) { if (found < max) out[found] = c; found++; }
        }
    }
    return found;
}

BYTE *func_start(const Module *m, BYTE *p) {
    if (!in_text(m, p)) return NULL;
    BYTE *lim = p - 0x4000 > m->base + 0x1000 ? p - 0x4000 : m->base + 0x1000;
    /* MSVC pads functions to 16 bytes with CC after a ret/jmp; take the nearest 16-aligned start behind that padding */
    for (BYTE *c = p; c > lim; c--) {
        if (c[-1] == 0xCC && c[0] != 0xCC && ((size_t)c & 15) == 0 && (c[-2] == 0xCC || c[-2] == 0xC3 || c[-4] == 0xC2)) return c;
    }
    return NULL;
}

size_t msgmap_handlers(const Module *m, DWORD id, BYTE **out, size_t max) {
    /* AFX_MSGMAP_ENTRY (32-bit): UINT msg, code, id, lastId; UINT_PTR sig; PMSG pfn  (24 bytes) */
    size_t found = 0;
    for (int i = 0; i < m->nr; i++) {
        const Range *r = &m->r[i];
        for (BYTE *c = r->lo; c + 24 <= r->lo + r->len; c += 4) {
            const DWORD *e = (const DWORD *)c;
            if (e[0] == 0x111 && e[1] == 0 && e[2] == id && e[3] == id && in_text(m, (void *)e[5])) {
                if (found < max) out[found] = (BYTE *)e[5];
                found++;
            }
        }
    }
    return found;
}
