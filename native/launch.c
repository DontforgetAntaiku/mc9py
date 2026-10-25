/* mc9launch.exe <dll> <program.exe> [args...]: start the program suspended, load <dll> into it, resume. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: mc9launch <dll> <exe> [args]\n"); return 2; }
    char dll[MAX_PATH]; GetFullPathNameA(argv[1], sizeof dll, dll, NULL);
    char cmd[4096] = ""; for (int i = 2; i < argc; i++) { strcat(cmd, "\""); strcat(cmd, argv[i]); strcat(cmd, "\" "); }
    STARTUPINFOA si; ZeroMemory(&si, sizeof si); si.cb = sizeof si; PROCESS_INFORMATION pi;
    char dir[MAX_PATH]; strcpy(dir, argv[2]); char *sl = strrchr(dir, '\\'); if (sl) *sl = 0; else strcpy(dir, ".");
    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, dir, &si, &pi)) { fprintf(stderr, "CreateProcess failed: %lu\n", GetLastError()); return 1; }
    /* The process is suspended at its entry stub: let it unpack and initialise first, then load the DLL. */
    ResumeThread(pi.hThread);
    Sleep(1500);
    SIZE_T n = strlen(dll) + 1;
    void *mem = VirtualAllocEx(pi.hProcess, NULL, n, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    WriteProcessMemory(pi.hProcess, mem, dll, n, NULL);
    HANDLE t = CreateRemoteThread(pi.hProcess, NULL, 0, (LPTHREAD_START_ROUTINE)GetProcAddress(GetModuleHandleA("kernel32.dll"), "LoadLibraryA"), mem, 0, NULL);
    if (!t) { fprintf(stderr, "CreateRemoteThread failed: %lu\n", GetLastError()); return 1; }
    WaitForSingleObject(t, 10000);
    DWORD ok = 0; GetExitCodeThread(t, &ok);
    printf("pid=%lu loaded=%s\n", (unsigned long)pi.dwProcessId, ok ? "yes" : "NO");
    return ok ? 0 : 1;
}
