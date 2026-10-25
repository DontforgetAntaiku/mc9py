"""Windows Python (also Wine): start MC9 and dump its menu bar (ids + text) to find command ids."""

import ctypes
import subprocess
import time
from ctypes import wintypes as w

u = ctypes.windll.user32
u.GetMenu.restype = ctypes.c_void_p
u.GetMenu.argtypes = [w.HWND]
u.GetMenuItemCount.argtypes = [ctypes.c_void_p]
u.GetSubMenu.restype = ctypes.c_void_p
u.GetSubMenu.argtypes = [ctypes.c_void_p, ctypes.c_int]
u.GetMenuItemID.argtypes = [ctypes.c_void_p, ctypes.c_int]
u.GetMenuStringW.argtypes = [ctypes.c_void_p, w.UINT, w.LPWSTR, ctypes.c_int, w.UINT]
u.GetMenuItemID.restype = w.UINT
EXE = r"C:\Program Files (x86)\mc9g\mc9.exe"
p = subprocess.Popen([EXE, r"C:\exchange\auto_ce_amp.cir"])
found = []
CB = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)


def enum(h, _):
    pid = w.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == p.pid and u.IsWindowVisible(h):
        found.append(h)
    return True


for _ in range(60):
    time.sleep(1)
    u.EnumWindows(CB(enum), 0)
    if found and u.GetMenu(found[0]):
        break
    found.clear()
h = found[0]
buf = ctypes.create_unicode_buffer(256)
u.GetClassNameW(h, buf, 256)
print("hwnd", hex(h), "class", buf.value)
u.GetWindowTextW(h, buf, 256)
print("title", buf.value)


def dump(menu, depth=0):
    for i in range(u.GetMenuItemCount(menu)):
        s = ctypes.create_unicode_buffer(256)
        u.GetMenuStringW(menu, i, s, 256, 0x400)
        mid = u.GetMenuItemID(menu, i)
        sub = u.GetSubMenu(menu, i)
        print("  " * depth + "[%d] id=%s %r" % (i, mid & 0xFFFFFFFF, s.value))
        if sub:
            dump(sub, depth + 1)


m = u.GetMenu(h)
print('menu', hex(m & 0xFFFFFFFF), 'count', u.GetMenuItemCount(m))
dump(m)
p.kill()
