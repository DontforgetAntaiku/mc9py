/* Offset auto-search for a loaded PE module: byte patterns with wildcards, string anchors, MFC message maps.
 * Nothing here knows an address of Micro-Cap: every address is found at run time. */
#ifndef MC9_SCAN_H
#define MC9_SCAN_H
#include <windows.h>
#include <stddef.h>

#define PAT_MAX 160

/* A packed program (UPX) keeps the packer's section table in memory, so the sections are NOT used: the module is
 * treated as the list of committed, readable memory regions inside [base, base+size). */
#define MAX_RANGES 96
typedef struct { BYTE *lo; size_t len; } Range;
typedef struct {
    BYTE *base;               /* image base in this process */
    DWORD size;               /* SizeOfImage */
    DWORD stamp;              /* TimeDateStamp from the PE header */
    DWORD fingerprint;        /* hash of size + first 64 KiB of code: identifies the build after unpacking */
    Range r[MAX_RANGES]; int nr;
} Module;

typedef struct { BYTE b[PAT_MAX]; BYTE m[PAT_MAX]; int n; } Pattern;

int    mod_open(Module *m, HMODULE h);
/* "55 8B EC ?? ?? 83" -> Pattern; returns 0 on a syntax error */
int    pat_parse(Pattern *p, const char *text);
/* all matches inside [lo, lo+len); returns the number written to out (at most max) */
size_t pat_scan_module(const Module *m, const Pattern *p, BYTE **out, size_t max);
size_t pat_scan(const BYTE *lo, size_t len, const Pattern *p, BYTE **out, size_t max);
/* the unique match anywhere in the module, or NULL when there are none or several (count tells which) */
BYTE  *pat_unique(const Module *m, const Pattern *p, size_t *count);
/* address of the C string `s` (start of a string, i.e. preceded by a NUL) */
BYTE  *find_string(const Module *m, const char *s);
/* code locations that load the 32-bit value `value` as an immediate or absolute operand */
size_t xrefs(const Module *m, DWORD value, BYTE **out, size_t max);
/* start of the function that contains `p` (CC-padding / prologue heuristics) */
BYTE  *func_start(const Module *m, BYTE *p);
/* AFX_MSGMAP_ENTRY scan: handlers of WM_COMMAND `id` (any MFC message map in the image) */
size_t msgmap_handlers(const Module *m, DWORD id, BYTE **out, size_t max);
int    in_text(const Module *m, const void *p);   /* inside the image (the name is historical) */
int    mod_unpacked(const Module *m);              /* the code area has been filled in by the packer */
#endif
