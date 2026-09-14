"""Read-only native process identity and bounded exit waits on a held handle."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


class NativeProcessHandle:
    def __init__(self, pid):
        if os.name != "nt":
            raise OSError("Windows process identity required")
        self.pid, self.handle = int(pid), None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            "QueryFullProcessImageNameW": ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = arguments, result
        # Query limited information + synchronize; never request broad access.
        self.handle = self.kernel.OpenProcess(0x1000 | 0x100000, False, self.pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def identity(self):
        if not self.handle:
            raise OSError("Process identity handle is closed")
        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not self.kernel.QueryFullProcessImageNameW(self.handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        created = times[0].dwLowDateTime | (times[0].dwHighDateTime << 32)
        return dict(pid=self.pid, creation_filetime=created, image_path=buffer.value)

    def wait_exited(self, timeout_ms=0):
        if not self.handle:
            raise OSError("Process identity handle is closed")
        if type(timeout_ms) is not int or not 0 <= timeout_ms <= 10000:
            raise ValueError("Process wait must be bounded to 0..10000 milliseconds")
        status = self.kernel.WaitForSingleObject(self.handle, timeout_ms)
        if status == 0:
            return True
        if status == 0x102:
            return False
        raise OSError(ctypes.get_last_error(), "WaitForSingleObject failed")

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
