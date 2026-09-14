"""Native occupancy semantics and fail-closed integration, without model calls."""
import ctypes
import os
from types import SimpleNamespace

import pytest

from slm import resource_monitor, windows_memory


class FakeAPI:
    callback_type = staticmethod(lambda function: function)
    last_error = staticmethod(lambda: 5)

    def __init__(self, rows, *, page_size=4096, success=True):
        self.rows, self.page_size, self.success = rows, page_size, success

    def enum_pagefiles(self, callback, context):
        for row in self.rows:
            pointer = ctypes.pointer(row) if row is not None else None
            if not callback(context, pointer, "C:\\pagefile.sys"):
                return False
        return self.success


def row(used=2, total=100, peak=80, cb=None):
    return windows_memory._PagefileInfo(
        cb=ctypes.sizeof(windows_memory._PagefileInfo) if cb is None else cb,
        total_size=total, total_in_use=used, peak_usage=peak,
    )


def test_current_occupancy_aggregates_all_files_in_actual_page_size():
    api = FakeAPI([row(used=2), row(used=7)], page_size=8192)
    assert windows_memory._read_pagefile_usage(api) == 9 * 8192


def test_zero_usage_requires_a_real_pagefile_observation():
    assert windows_memory._read_pagefile_usage(FakeAPI([row(used=0)])) == 0
    with pytest.raises(OSError, match="observation unavailable"):
        windows_memory._read_pagefile_usage(FakeAPI([]))


def test_failed_enumeration_rejects_partial_data():
    with pytest.raises(OSError, match="EnumPageFilesW failed"):
        windows_memory._read_pagefile_usage(FakeAPI([row()], success=False))


@pytest.mark.parametrize("bad_row", [None, row(cb=0), row(used=101)])
def test_callback_failures_reject_partial_data(bad_row):
    with pytest.raises(OSError):
        windows_memory._read_pagefile_usage(FakeAPI([row(), bad_row]))


@pytest.mark.parametrize("page_size", [0, -1, None])
def test_missing_page_size_is_not_assumed(page_size):
    with pytest.raises(OSError, match="page size"):
        windows_memory._read_pagefile_usage(FakeAPI([row()], page_size=page_size))


def test_public_probe_does_not_cache_usage(monkeypatch):
    api = FakeAPI([row(used=1)])
    monkeypatch.setattr(windows_memory, "_native_api", lambda: api)
    assert windows_memory.read_pagefile_used_bytes() == 4096
    api.rows = [row(used=3)]
    assert windows_memory.read_pagefile_used_bytes() == 12288


def test_resource_probe_uses_native_pagefile_and_keeps_gpu_sampling(monkeypatch):
    calls = []
    monkeypatch.setattr(resource_monitor, "read_pagefile_used_bytes", lambda: 123456)
    def run(args, **kwargs):
        calls.append(args)
        assert args[0] == "nvidia-smi"
        return SimpleNamespace(stdout="0, 2048\n")
    monkeypatch.setattr(resource_monitor, "hidden_run", run)
    sample = resource_monitor.WindowsResourceProbe()()
    assert sample["pagefile_used_bytes"] == 123456
    assert "pagefile" not in sample["missing"]
    assert sample["gpu_total_bytes"] == 2 * resource_monitor.GIB
    assert len(calls) == 1


def test_native_failure_remains_missing_and_stops_original_gate(monkeypatch):
    def fail():
        raise OSError("native pagefile unavailable")
    monkeypatch.setattr(resource_monitor, "read_pagefile_used_bytes", fail)
    monkeypatch.setattr(resource_monitor, "hidden_run", lambda *args, **kwargs: SimpleNamespace(stdout="0, 2048\n"))
    sample = resource_monitor.WindowsResourceProbe()()
    assert sample["pagefile_used_bytes"] is None
    assert sample["missing"]["pagefile"] == "OSError"
    gate = resource_monitor.SustainedResourceGate({
        "ram_available_bytes": 4 * resource_monitor.GIB,
        "pagefile_used_bytes": 0,
    })
    assert gate.observe(sample) == "required_resource_telemetry_missing"


@pytest.mark.skipif(os.name != "nt", reason="requires local Windows telemetry")
def test_native_windows_smoke_is_fresh_and_page_aligned():
    api = windows_memory._native_api()
    values = [windows_memory.read_pagefile_used_bytes() for _ in range(3)]
    assert all(type(value) is int and value >= 0 for value in values)
    assert all(value % api.page_size == 0 for value in values)
    assert ctypes.sizeof(windows_memory._PagefileInfo) == (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 20)
