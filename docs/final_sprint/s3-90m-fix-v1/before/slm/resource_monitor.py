"""Windows telemetry and the S3 sustained RAM/pagefile gate; no inferred zero values."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event, Thread
import time

GIB = 1024 ** 3


def hidden_run(args, *, timeout=8):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, check=True)


class WindowsResourceProbe:
    def __init__(self, *, powershell=None, endpoint=None):
        self.powershell = powershell or shutil.which("pwsh") or shutil.which("powershell")
        self.endpoint = endpoint

    def __call__(self):
        result = dict(ram_total_bytes=None, ram_available_bytes=None, pagefile_used_bytes=None,
                      gpu_used_bytes=None, gpu_total_bytes=None, loaded_models=None, missing={})
        try:
            if os.name != "nt":
                raise OSError("Windows telemetry required")
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                    (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise OSError("GlobalMemoryStatusEx failed")
            result.update(ram_total_bytes=status.total_phys, ram_available_bytes=status.avail_phys)
        except Exception as exc:
            result["missing"]["ram"] = type(exc).__name__
        try:
            # Actual pagefile occupancy, NOT commit charge, allocation size, or swap total.
            script = "$p = @(Get-CimInstance Win32_PageFileUsage -ErrorAction Stop); if ($p.Count -eq 0) { throw 'Pagefile observation unavailable' }; [long](($p | Measure-Object -Property CurrentUsage -Sum).Sum * 1MB)"
            result["pagefile_used_bytes"] = int(hidden_run([self.powershell, "-NoProfile", "-Command", script]).stdout.strip())
        except Exception as exc:
            result["missing"]["pagefile"] = type(exc).__name__
        try:
            output = hidden_run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"], timeout=4).stdout
            rows = [[int(v.strip()) for v in row.split(",")] for row in output.strip().splitlines()]
            result.update(gpu_used_bytes=sum(row[0] for row in rows)*1024**2, gpu_total_bytes=sum(row[1] for row in rows)*1024**2)
        except Exception as exc:
            result["missing"]["gpu"] = type(exc).__name__
        if self.endpoint:
            try:
                import requests
                session = requests.Session()
                session.trust_env = False
                response = session.get(self.endpoint + "/api/ps", timeout=3)
                response.raise_for_status()
                result["loaded_models"] = response.json()["models"]
            except Exception as exc:
                result["missing"]["loaded_models"] = type(exc).__name__
        return result


class SustainedResourceGate:
    def __init__(self, baseline, *, clock=time.monotonic, sustain_seconds=60):
        if baseline.get("ram_available_bytes") is None or baseline.get("pagefile_used_bytes") is None:
            raise ValueError("RAM/pagefile baseline unavailable; resource gate cannot be certified")
        if baseline["ram_available_bytes"] < 2*GIB:
            raise ValueError("less than 2 GiB RAM available before model load")
        self.baseline = baseline
        self.clock = clock
        self.sustain_seconds = sustain_seconds
        self.since = {}
        self.failure = None

    def observe(self, sample):
        if self.failure:
            return self.failure
        if sample.get("ram_available_bytes") is None or sample.get("pagefile_used_bytes") is None:
            self.failure = "required_resource_telemetry_missing"
            return self.failure
        conditions = {"available_ram_below_2gib": sample["ram_available_bytes"] < 2*GIB,
            "pagefile_growth_above_2gib": sample["pagefile_used_bytes"] - self.baseline["pagefile_used_bytes"] > 2*GIB}
        now = self.clock()
        for key, breached in conditions.items():
            if not breached:
                self.since.pop(key, None)
            else:
                self.since.setdefault(key, now)
                if now - self.since[key] >= self.sustain_seconds:
                    self.failure = key
        return self.failure


class ResourceMonitor:
    def __init__(self, probe, journal, cancel, *, interval=5, abort=None):
        self.probe, self.journal, self.cancel = probe, journal, cancel
        self.interval, self.abort = interval, abort
        self.started = time.monotonic()
        self.baseline = probe()
        journal.emit("resource_baseline", self.baseline)
        self.gate = SustainedResourceGate(self.baseline)
        self.samples = []
        self.stop = Event()
        self.thread = None
        self._record(self.baseline)

    def _record(self, sample):
        sample = {**sample, "elapsed_seconds": time.monotonic()-self.started,
            "pagefile_delta_bytes": None if sample["pagefile_used_bytes"] is None else sample["pagefile_used_bytes"]-self.baseline["pagefile_used_bytes"]}
        self.samples.append(sample)
        self.journal.emit("telemetry", sample)
        failure = self.gate.observe(sample)
        if failure:
            self.journal.emit("resource_stop", dict(reason=failure, baseline=self.baseline, last_sample=sample))
            self.cancel.set()
            if self.abort:
                self.abort()

    def start(self):
        def poll():
            while not self.stop.wait(self.interval):
                try:
                    self._record(self.probe())
                except Exception as exc:
                    self.gate.failure = "telemetry_monitor_failed"
                    self.journal.emit("resource_stop", dict(reason=self.gate.failure, error_type=type(exc).__name__))
                    self.cancel.set()
                    if self.abort:
                        self.abort()
                if self.gate.failure:
                    return
        self.thread = Thread(target=poll, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=20)
        if self.thread and self.thread.is_alive():
            self.gate.failure = self.gate.failure or "telemetry_shutdown_incomplete"
        else:
            try:
                self._record(self.probe())
            except Exception as exc:
                self.gate.failure = self.gate.failure or "final_resource_sample_failed"
                self.journal.emit("resource_stop", dict(reason=self.gate.failure, error_type=type(exc).__name__))
                self.cancel.set()
                if self.abort:
                    self.abort()
        def values(key): return [s[key] for s in self.samples if s[key] is not None]
        summary = dict(status="failed" if self.gate.failure else "passed", reason=self.gate.failure,
            sample_count=len(self.samples), sample_interval_seconds=self.interval, baseline=self.baseline,
            maximum_observed_sample_gap_seconds=max((b["elapsed_seconds"]-a["elapsed_seconds"] for a,b in zip(self.samples, self.samples[1:])), default=0),
            min_available_ram_bytes=min(values("ram_available_bytes"), default=None),
            peak_ram_used_bytes=max((s["ram_total_bytes"]-s["ram_available_bytes"] for s in self.samples if s["ram_total_bytes"] is not None and s["ram_available_bytes"] is not None), default=None),
            peak_gpu_used_bytes=max(values("gpu_used_bytes"), default=None),
            peak_pagefile_used_bytes=max(values("pagefile_used_bytes"), default=None),
            peak_pagefile_delta_bytes=max(values("pagefile_delta_bytes"), default=None),
            missing_observations=[s["missing"] for s in self.samples if s["missing"]])
        self.journal.emit("telemetry_summary", summary)
        return summary
