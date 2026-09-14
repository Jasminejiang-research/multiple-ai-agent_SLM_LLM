"""Missing observation intervals must not be certified from healthy endpoints."""
from threading import Event

import pytest

from slm import resource_monitor


class Journal:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))


def sample():
    return dict(ram_total_bytes=16 * resource_monitor.GIB, ram_available_bytes=4 * resource_monitor.GIB,
        pagefile_used_bytes=resource_monitor.GIB, gpu_used_bytes=0, gpu_total_bytes=2 * resource_monitor.GIB,
        loaded_models=[], missing={})


@pytest.mark.parametrize("interval,threshold", [(5, 15), (10, 30), (1, 15)])
def test_gap_threshold_is_three_intervals_with_fifteen_second_floor(monkeypatch, interval, threshold):
    clock = [0.0]
    monkeypatch.setattr(resource_monitor.time, "monotonic", lambda: clock[0])
    cancel, journal, aborted = Event(), Journal(), []
    monitor = resource_monitor.ResourceMonitor(sample, journal, cancel, interval=interval,
        abort=lambda: aborted.append(True))
    clock[0] = threshold
    monitor._record(sample())
    assert not cancel.is_set()
    clock[0] += threshold + .001
    monitor._record(sample())
    assert cancel.is_set() and aborted
    assert monitor.gate.failure == "resource_observation_gap"
    result = monitor.close()
    assert result["status"] == "failed"
    assert result["maximum_allowed_sample_gap_seconds"] == threshold
    assert result["observation_gap_count"] == 1
    event = next(payload for kind, payload in journal.events if kind == "resource_stop")
    assert event["observation_gap_seconds"] > threshold
    assert event["maximum_allowed_sample_gap_seconds"] == threshold


def test_forty_minute_gap_discovered_at_close_cannot_pass(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(resource_monitor.time, "monotonic", lambda: clock[0])
    cancel, aborted = Event(), []
    monitor = resource_monitor.ResourceMonitor(sample, Journal(), cancel, abort=lambda: aborted.append(True))
    clock[0] = 2423.437
    result = monitor.close()
    assert result["status"] == "failed" and result["reason"] == "resource_observation_gap"
    assert result["maximum_observed_sample_gap_seconds"] == 2423.437
    assert cancel.is_set() and aborted


def test_observation_gap_preserves_earlier_required_missing_failure(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(resource_monitor.time, "monotonic", lambda: clock[0])
    monitor = resource_monitor.ResourceMonitor(sample, Journal(), Event())
    monitor._record({**sample(), "pagefile_used_bytes": None})
    clock[0] = 60
    result = monitor.close()
    assert result["status"] == "failed"
    assert result["reason"] == "required_resource_telemetry_missing"
    assert result["observation_gap_count"] == 1
