/* mc9hook.dll - loaded into Micro-Cap 9. A small worker thread answers requests that arrive as files:
 *   <dir>\hook.req   "<id> <command> <args>"   (written by the client, then renamed into place)
 *   <dir>\hook.resp  "<id> ok <text>" or "<id> err <text>"
 * <dir> is %MC9HOOK_DIR% (default C:\exchange). The same transport works from Linux, from Windows and from tests. */
#include "scan.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static Module g_mod;
static char g_dir[MAX_PATH];
#define PATHBUF (MAX_PATH * 2)
static char g_dll_dir[MAX_PATH];
#define OUT_MAX 8192

static void put(char *out, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void put(char *out, const char *fmt, ...) {
    size_t n = strlen(out);
    va_list ap; va_start(ap, fmt);
    vsnprintf(out + n, OUT_MAX - n, fmt, ap);
    va_end(ap);
}

static DWORD rva(const void *p) { return (DWORD)((const BYTE *)p - g_mod.base); }
static int readable(const void *p, size_t n) { return !IsBadReadPtr(p, n); }

/* ---- named targets: found by pattern first, then by a string anchor; see signatures.txt ----
 * line:  name | byte pattern ("" = none) | anchor string ("" = none) | which xref (0-based) of the anchor */
typedef struct { char name[48]; char pat[512]; char anchor[160]; int which; DWORD expect; BYTE *addr; char how[24]; size_t hits; } Target;
static Target g_t[128];
static int g_nt;

static char *trim(char *s) {
    while (*s == ' ' || *s == '\t') s++;
    char *e = s + strlen(s);
    while (e > s && (e[-1] == ' ' || e[-1] == '\t' || e[-1] == '\r' || e[-1] == '\n')) *--e = 0;
    return s;
}

static void load_targets(void) {
    char path[PATHBUF]; snprintf(path, sizeof path, "%s\\signatures.txt", g_dll_dir);
    FILE *f = fopen(path, "r");
    if (!f) { snprintf(path, sizeof path, "%s\\signatures.txt", g_dir); f = fopen(path, "r"); }
    if (!f) return;
    char line[1024];
    while (fgets(line, sizeof line, f) && g_nt < 128) {
        if (line[0] == '#' || line[0] == '\n' || line[0] == '\r') continue;
        char *f1 = strchr(line, '|'); if (!f1) continue; *f1++ = 0;
        char *f2 = strchr(f1, '|');   if (!f2) continue; *f2++ = 0;
        char *f3 = strchr(f2, '|');   if (!f3) continue; *f3++ = 0;
        char *f4 = strchr(f3, '|');   if (f4) *f4++ = 0;
        Target *t = &g_t[g_nt++]; memset(t, 0, sizeof *t);
        snprintf(t->name, sizeof t->name, "%s", trim(line));
        snprintf(t->pat, sizeof t->pat, "%s", trim(f1));
        snprintf(t->anchor, sizeof t->anchor, "%s", trim(f2));
        t->which = atoi(trim(f3));
        t->expect = f4 ? (DWORD)strtoul(trim(f4), NULL, 16) : 0;
    }
    fclose(f);
}

static void resolve_one(Target *t, int use_pattern) {
    t->addr = NULL; t->hits = 0; strcpy(t->how, "none");
    Pattern p;
    if (use_pattern && t->pat[0] && pat_parse(&p, t->pat)) {
        BYTE *a = pat_unique(&g_mod, &p, &t->hits);
        if (a) { t->addr = a; strcpy(t->how, "pattern"); return; }
    }
    if (t->anchor[0]) {
        BYTE *s = find_string(&g_mod, t->anchor);
        if (s) {
            BYTE *refs[16];
            size_t n = xrefs(&g_mod, (DWORD)(size_t)s, refs, 16);
            if (n > (size_t)t->which) {
                BYTE *fs = func_start(&g_mod, refs[t->which]);
                if (fs) { t->addr = fs; t->hits = n; strcpy(t->how, "anchor"); }
            }
        }
    }
}

/* ---- window messages: watch what MC9 receives, send commands the same way a menu would ---- */
typedef struct { UINT msg; WPARAM wp; LPARAM lp; HWND h; } Event;
static Event g_log[512];
static volatile LONG g_nlog;
static HHOOK g_hook;
static HWND g_frame;

static BOOL CALLBACK enum_top(HWND h, LPARAM param) {
    DWORD pid; GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || GetWindow(h, GW_OWNER)) return TRUE;
    RECT r; GetWindowRect(h, &r);
    HWND *best = (HWND *)param; RECT b = {0, 0, 0, 0};
    if (*best) GetWindowRect(*best, &b);
    if (!*best || (r.right - r.left) * (r.bottom - r.top) > (b.right - b.left) * (b.bottom - b.top)) *best = h;
    return TRUE;
}

static HWND frame(void) {                              /* the biggest visible top-level window of MC9 */
    if (g_frame && IsWindow(g_frame)) return g_frame;
    g_frame = NULL;
    EnumWindows(enum_top, (LPARAM)&g_frame);
    return g_frame;
}

static LRESULT CALLBACK watch_proc(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION) {
        const CWPSTRUCT *c = (const CWPSTRUCT *)lp;
        if ((c->message == WM_COMMAND || c->message == WM_SYSCOMMAND) && c->hwnd == g_frame) {
            LONG i = InterlockedIncrement(&g_nlog) - 1;
            if (i < 512) { g_log[i].msg = c->message; g_log[i].wp = c->wParam; g_log[i].lp = c->lParam; g_log[i].h = c->hwnd; }
        }
    }
    return CallNextHookEx(g_hook, code, wp, lp);
}

static void win_desc(HWND h, char *out) {
    char cls[64] = "", title[96] = "";
    GetClassNameA(h, cls, sizeof cls);
    GetWindowTextA(h, title, sizeof title);
    RECT r; GetWindowRect(h, &r);
    put(out, "[%p %s \"%s\" %ldx%ld%s]", (void *)h, cls, title, (long)(r.right - r.left), (long)(r.bottom - r.top), IsWindowVisible(h) ? "" : " hidden");
}

static BOOL CALLBACK enum_list(HWND h, LPARAM param) {
    DWORD pid; GetWindowThreadProcessId(h, &pid);
    if (pid == GetCurrentProcessId()) win_desc(h, (char *)param);
    return TRUE;
}

/* ---- commands ---- */
static void cmd_run(const char *cmd, char *args, char *out) {
    if (!strcmp(cmd, "ping")) { put(out, "pong"); return; }
    if (!strcmp(cmd, "info")) {
        put(out, "base=%p size=0x%lx stamp=0x%lx fp=0x%08lx ranges=%d targets=%d", (void *)g_mod.base, (unsigned long)g_mod.size,
            (unsigned long)g_mod.stamp, (unsigned long)g_mod.fingerprint, g_mod.nr, g_nt);
        return;
    }
    if (!strcmp(cmd, "scan")) {                       /* scan <pattern>  -> up to 16 rvas */
        Pattern p; if (!pat_parse(&p, args)) { put(out, "!bad pattern"); return; }
        BYTE *hit[16]; size_t n = pat_scan_module(&g_mod, &p, hit, 16);
        put(out, "%u", (unsigned)n);
        for (size_t i = 0; i < n && i < 16; i++) put(out, " %lx", (unsigned long)rva(hit[i]));
        return;
    }
    if (!strcmp(cmd, "str")) {                        /* str <text> -> rva of the string and the code that uses it */
        BYTE *s = find_string(&g_mod, args);
        if (!s) { put(out, "!string not found"); return; }
        BYTE *refs[16]; size_t n = xrefs(&g_mod, (DWORD)(size_t)s, refs, 16);
        put(out, "str=%lx refs=%u", (unsigned long)rva(s), (unsigned)n);
        for (size_t i = 0; i < n && i < 16; i++) {
            BYTE *fs = func_start(&g_mod, refs[i]);
            put(out, " %lx(f=%lx)", (unsigned long)rva(refs[i]), (unsigned long)(fs ? rva(fs) : 0));
        }
        return;
    }
    if (!strcmp(cmd, "fstart")) {
        BYTE *a = (BYTE *)(size_t)strtoul(args, NULL, 16); BYTE *fs = func_start(&g_mod, g_mod.base + (size_t)a);
        if (fs) put(out, "%lx", (unsigned long)rva(fs)); else put(out, "!none");
        return;
    }
    if (!strcmp(cmd, "msgmap")) {                     /* msgmap <command id, decimal> */
        BYTE *hit[16]; size_t n = msgmap_handlers(&g_mod, (DWORD)strtoul(args, NULL, 10), hit, 16);
        put(out, "%u", (unsigned)n);
        for (size_t i = 0; i < n && i < 16; i++) put(out, " %lx", (unsigned long)rva(hit[i]));
        return;
    }
    if (!strcmp(cmd, "peek")) {                       /* peek <rva hex> <n> */
        char *e; unsigned long r = strtoul(args, &e, 16); unsigned long n = strtoul(e, NULL, 10);
        if (n == 0 || n > 512 || !readable(g_mod.base + r, n)) { put(out, "!bad range"); return; }
        for (unsigned long i = 0; i < n; i++) put(out, "%02X%s", g_mod.base[r + i], i + 1 < n ? " " : "");
        return;
    }
    if (!strcmp(cmd, "resolve")) {                    /* resolve [anchor]: re-run the auto-search for every target */
        int use_pattern = strcmp(args, "anchor") != 0;
        for (int i = 0; i < g_nt; i++) {
            Target *t = &g_t[i];
            resolve_one(t, use_pattern);
            DWORD r = t->addr ? rva(t->addr) : 0;
            put(out, "%s=%lx(%s%s)%s", t->name, (unsigned long)r, t->how,
                !t->expect ? "" : r == t->expect ? ",as-built" : ",MOVED", i + 1 < g_nt ? " " : "");
        }
        return;
    }
    if (!strcmp(cmd, "windows")) { EnumWindows(enum_list, (LPARAM)out); return; }
    if (!strcmp(cmd, "watch")) {                      /* watch on | off | clear | dump */
        if (!strcmp(args, "on")) {
            HWND f = frame(); if (!f) { put(out, "!no window"); return; }
            g_nlog = 0;
            if (!g_hook) g_hook = SetWindowsHookExA(WH_CALLWNDPROC, watch_proc, NULL, GetWindowThreadProcessId(f, NULL));
            put(out, g_hook ? "watching" : "!hook failed");
        } else if (!strcmp(args, "off")) { if (g_hook) UnhookWindowsHookEx(g_hook); g_hook = NULL; put(out, "off"); }
        else if (!strcmp(args, "clear")) { g_nlog = 0; put(out, "cleared"); }
        else {                                        /* dump: msg wParam lParam hwnd, one per event */
            LONG n = g_nlog < 512 ? g_nlog : 512;
            for (LONG i = 0; i < n; i++) put(out, "%s%lx:%lx:%lx:%p", i ? " " : "", (unsigned long)g_log[i].msg, (unsigned long)g_log[i].wp, (unsigned long)g_log[i].lp, (void *)g_log[i].h);
        }
        return;
    }
    if (!strcmp(cmd, "post_cmd")) {                   /* post_cmd <id> : the same WM_COMMAND a menu item or accelerator sends */
        HWND f = frame(); if (!f) { put(out, "!no window"); return; }
        PostMessageA(f, WM_COMMAND, MAKEWPARAM((WORD)strtoul(args, NULL, 10), 0), 0);
        put(out, "posted");
        return;
    }
    put(out, "!unknown command");
}

static void serve(void) {
    char req[MAX_PATH + 16], tmp[MAX_PATH + 16], resp[MAX_PATH + 16];
    snprintf(req, sizeof req, "%s\\hook.req", g_dir);
    snprintf(tmp, sizeof tmp, "%s\\hook.resp.tmp", g_dir);
    snprintf(resp, sizeof resp, "%s\\hook.resp", g_dir);
    char *out = malloc(OUT_MAX);
    for (;;) {
        FILE *f = fopen(req, "rb");
        if (!f) { Sleep(15); continue; }
        char line[2048] = {0};
        size_t n = fread(line, 1, sizeof line - 1, f);
        fclose(f); line[n] = 0;
        DeleteFileA(req);
        char *id = trim(line), *sp = strchr(id, ' ');
        char *cmd = "", *args = "";
        if (sp) { *sp++ = 0; cmd = trim(sp); sp = strchr(cmd, ' '); if (sp) { *sp++ = 0; args = trim(sp); } }
        out[0] = 0;
        cmd_run(cmd, args, out);
        FILE *o = fopen(tmp, "wb");
        if (o) {
            int bad = out[0] == '!';
            fprintf(o, "%s %s %s\n", id, bad ? "err" : "ok", bad ? out + 1 : out);
            fclose(o);
            DeleteFileA(resp);
            MoveFileA(tmp, resp);
        }
    }
}

static DWORD WINAPI thread_main(LPVOID unused) {
    (void)unused;
    HMODULE exe = GetModuleHandleA(NULL);
    for (int i = 0; i < 600; i++) {                    /* a UPX-packed program fills its code area on start-up */
        if (mod_open(&g_mod, exe) && mod_unpacked(&g_mod)) break;
        Sleep(100);
    }
    if (!g_mod.nr) return 1;
    load_targets();
    serve();
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        if (!GetEnvironmentVariableA("MC9HOOK_DIR", g_dir, sizeof g_dir)) strcpy(g_dir, "C:\\exchange");
        GetModuleFileNameA(h, g_dll_dir, sizeof g_dll_dir);
        char *sl = strrchr(g_dll_dir, '\\'); if (sl) *sl = 0;
        CreateThread(NULL, 0, thread_main, NULL, 0, NULL);
    }
    return TRUE;
}
