"""Run-scoped Windows power requests; never a change to the user's power plan.

Modern Standby on DC power can end system/execution requests five minutes after
the sleep timeout. User-initiated sleep also ends requests. Acceptance of these
requests is therefore not proof that a run cannot be suspended; telemetry gaps
must still invalidate continuous resource certification.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os

SYSTEM_REQUIRED = 1
EXECUTION_REQUIRED = 3
REQUEST_LIMITATIONS = (
    "Modern Standby on DC power can terminate system/execution requests five minutes after the sleep timeout.",
    "User-initiated sleep, lid close, shutdown and operating-system power policy remain authoritative.",
    "No display or away-mode request is made; global power settings are unchanged.",
)


class _DetailedReason(ctypes.Structure):
    _fields_ = [("module", wintypes.HMODULE), ("reason_id", wintypes.ULONG),
        ("string_count", wintypes.ULONG), ("strings", ctypes.POINTER(wintypes.LPWSTR))]


class _ReasonUnion(ctypes.Union):
    _fields_ = [("detailed", _DetailedReason), ("simple", wintypes.LPWSTR)]


class _ReasonContext(ctypes.Structure):
    _fields_ = [("version", wintypes.ULONG), ("flags", wintypes.DWORD), ("reason", _ReasonUnion)]


class _NativePowerAPI:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows run-scoped power requests required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "PowerCreateRequest": ([ctypes.POINTER(_ReasonContext)], wintypes.HANDLE),
            "PowerSetRequest": ([wintypes.HANDLE, ctypes.c_int], wintypes.BOOL),
            "PowerClearRequest": ([wintypes.HANDLE, ctypes.c_int], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = arguments, result

    def create(self, reason):
        context = _ReasonContext(version=0, flags=1)
        context.reason.simple = reason
        handle = self.kernel.PowerCreateRequest(ctypes.byref(context))
        if handle in (None, 0, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def set(self, handle, request):
        if not self.kernel.PowerSetRequest(handle, request):
            raise ctypes.WinError(ctypes.get_last_error())

    def clear(self, handle, request):
        if not self.kernel.PowerClearRequest(handle, request):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


class WindowsAwake:
    """Acquire only for a run, releasing both requests on every exit path.

    Use ``with WindowsAwake(journal=journal):`` around the run. A successful
    enter means Windows accepted the requests, not a guarantee against sleep.
    """
    def __init__(self, *, journal=None, reason="Bounded AI proposal generation run", api=None):
        self.journal, self.reason, self.api = journal, reason, api
        self.handle = None
        self.active_requests = []

    def _emit(self, kind, payload):
        if self.journal is not None:
            self.journal.emit(kind, payload)

    def __enter__(self):
        if self.handle is not None:
            raise RuntimeError("Power-request scope is already active")
        try:
            if self.api is None:
                self.api = _NativePowerAPI()
            self.handle = self.api.create(self.reason)
            for request in (SYSTEM_REQUIRED, EXECUTION_REQUIRED):
                self.api.set(self.handle, request)
                self.active_requests.append(request)
            self._emit("power_requests_acquired", dict(request_types=list(self.active_requests),
                method="PowerCreateRequest/PowerSetRequest", reason=self.reason,
                prevents_all_sleep=False, limitations=list(REQUEST_LIMITATIONS)))
            return self
        except BaseException as exc:
            cleanup_errors = self._release()
            self._emit("power_requests_failed", dict(error_type=type(exc).__name__,
                cleanup_errors=cleanup_errors, limitations=list(REQUEST_LIMITATIONS)))
            raise

    def _release(self):
        errors = []
        if self.handle is None:
            return errors
        handle, self.handle = self.handle, None
        for request in reversed(self.active_requests):
            try:
                self.api.clear(handle, request)
            except Exception as exc:
                errors.append(dict(operation="PowerClearRequest", request_type=request,
                    error_type=type(exc).__name__))
        self.active_requests.clear()
        try:
            self.api.close(handle)
        except Exception as exc:
            errors.append(dict(operation="CloseHandle", error_type=type(exc).__name__))
        self._emit("power_requests_released", dict(status="failed" if errors else "released", errors=errors))
        return errors

    def __exit__(self, exc_type, exc, traceback):
        errors = self._release()
        if errors and exc is None:
            raise OSError("Run-scoped power request cleanup failed: " + str(errors))
        if errors and exc is not None and hasattr(exc, "add_note"):
            exc.add_note("Power-request cleanup errors: " + str(errors))
        return False
