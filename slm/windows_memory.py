"""Read actual Windows pagefile occupancy without starting PowerShell or WMI.

EnumPageFilesW reports each pagefile's TotalInUse in pages. Multiplying the
sum by GetSystemInfo.dwPageSize preserves the existing CurrentUsage meaning,
with page precision instead of CIM's integer MiB precision. Commit charge,
pagefile allocation size, and peak usage are deliberately not substituted.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from functools import lru_cache
import os


class _SystemInfo(ctypes.Structure):
    _fields_ = [
        ("processor_union", wintypes.DWORD),
        ("page_size", wintypes.DWORD),
        ("minimum_address", wintypes.LPVOID),
        ("maximum_address", wintypes.LPVOID),
        ("processor_mask", ctypes.c_size_t),
        ("processor_count", wintypes.DWORD),
        ("processor_type", wintypes.DWORD),
        ("allocation_granularity", wintypes.DWORD),
        ("processor_level", wintypes.WORD),
        ("processor_revision", wintypes.WORD),
    ]


class _PagefileInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("reserved", wintypes.DWORD),
        ("total_size", ctypes.c_size_t),
        ("total_in_use", ctypes.c_size_t),
        ("peak_usage", ctypes.c_size_t),
    ]


class _NativePagefileAPI:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows pagefile telemetry required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self.kernel.GetSystemInfo.argtypes = [ctypes.POINTER(_SystemInfo)]
        self.kernel.GetSystemInfo.restype = None
        system = _SystemInfo()
        self.kernel.GetSystemInfo(ctypes.byref(system))
        self.page_size = system.page_size
        self.callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.LPVOID,
            ctypes.POINTER(_PagefileInfo), wintypes.LPCWSTR,
        )
        self.enum_pagefiles = self.psapi.EnumPageFilesW
        self.enum_pagefiles.argtypes = [self.callback_type, wintypes.LPVOID]
        self.enum_pagefiles.restype = wintypes.BOOL
        self.last_error = ctypes.get_last_error


@lru_cache(maxsize=1)
def _native_api():
    # Cache only stable DLL bindings and page size, never a usage observation.
    return _NativePagefileAPI()


def _read_pagefile_usage(api):
    if not isinstance(api.page_size, int) or api.page_size <= 0:
        raise OSError("Windows page size observation unavailable")
    used_pages = []
    callback_errors = []

    @api.callback_type
    def collect(_context, pointer, _filename):
        # ctypes callbacks cannot propagate exceptions through the native stack.
        # Capture and re-raise them after enumeration; never accept partial data.
        try:
            if not pointer:
                raise OSError("Pagefile information pointer unavailable")
            info = pointer.contents
            if info.cb < ctypes.sizeof(_PagefileInfo):
                raise OSError("Pagefile information structure incomplete")
            if info.total_in_use > info.total_size:
                raise OSError("Pagefile usage exceeds observed allocation")
            used_pages.append(int(info.total_in_use))
            return True
        except Exception as exc:
            callback_errors.append(exc)
            return False

    succeeded = api.enum_pagefiles(collect, None)
    if callback_errors:
        raise callback_errors[0]
    if not succeeded:
        raise OSError(api.last_error(), "EnumPageFilesW failed")
    if not used_pages:
        # Preserve the existing gate's treatment of absent observations. An
        # installed pagefile with zero occupancy is valid; no rows is missing.
        raise OSError("Pagefile observation unavailable")
    return sum(used_pages) * api.page_size


def read_pagefile_used_bytes():
    """Return a fresh current-occupancy sample, or raise on any missing data."""
    return _read_pagefile_usage(_native_api())
