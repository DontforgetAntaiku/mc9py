/* mc9launch.exe <dll> <program.exe> [args...]   start the program and load <dll> into it
 * mc9launch.exe --attach <pid> <dll>            load <dll> into a program that is already running
 * (a 32-bit injector: MC9 is a 32-bit process, so LoadLibrary must be called with the 32-bit kernel32). */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int inject(HANDLE process, const char *dll_arg) {
    char dll[MAX_PATH]; GetFullPathNameA(dll_arg, sizeof dll, dll, NULL);
    SIZE_T n = strlen(dll) + 1;
    void *mem = VirtualAllocEx(process, NULL, n, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!mem || !WriteProcessMemory(process, mem, dll, n, NULL)) { fprintf(stderr, "cannot write into the process: %lu\n", GetLastError()); return 1; }
    HANDLE t = CreateRemoteThread(process, NULL, 0, (LPTHREAD_START_ROUTINE)GetProcAddress(GetModuleHandleA("kernel32.dll"), "LoadLibraryA"), mem, 0, NULL);
    if (!t) { fprintf(stderr, "CreateRemoteThread failed: %lu\n", GetLastError()); return 1; }
    WaitForSingleObject(t, 10000);
    DWORD ok = 0; GetExitCodeThread(t, &ok);
    printf("loaded=%s\n", ok ? "yes" : "NO");
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc >= 4 && !strcmp(argv[1], "--attach")) {
        HANDLE p = OpenProcess(PROCESS_ALL_ACCESS, FALSE, (DWORD)atoi(argv[2]));
        if (!p) { fprintf(stderr, "OpenProcess failed: %lu\n", GetLastError()); return 1; }
        return inject(p, argv[3]);
    }
    if (argc < 3) { fprintf(stderr, "usage: mc9launch <dll> <exe> [args]  |  mc9launch --attach <pid> <dll>\n"); return 2; }
    char cmd[4096] = ""; for (int i = 2; i < argc; i++) { strcat(cmd, "\""); strcat(cmd, argv[i]); strcat(cmd, "\" "); }
    STARTUPINFOA si; ZeroMemory(&si, sizeof si); si.cb = sizeof si; PROCESS_INFORMATION pi;
    char dir[MAX_PATH]; strcpy(dir, argv[2]); char *sl = strrchr(dir, '\\'); if (sl) *sl = 0; else strcpy(dir, ".");
    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi)) { fprintf(stderr, "CreateProcess failed: %lu\n", GetLastError()); return 1; }
    Sleep(1500);                                   /* let the packed program unpack and initialise first */
    printf("pid=%lu ", (unsigned long)pi.dwProcessId);
    return inject(pi.hProcess, argv[1]);
}
