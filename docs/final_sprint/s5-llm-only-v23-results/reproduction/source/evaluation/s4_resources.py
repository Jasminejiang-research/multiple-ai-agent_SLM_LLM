"""Host memory samples with explicit missing states; D retains S3's sustained gate."""
from threading import Event, Thread
import time

from slm.resource_monitor import WindowsResourceProbe, SustainedResourceGate


def synthetic_probe():
    return dict(ram_total_bytes=16*1024**3, ram_available_bytes=8*1024**3,
        pagefile_used_bytes=1024**3, gpu_used_bytes=0, missing={}, synthetic=True)


class RunTelemetry:
    def __init__(self, journal, cancel, *, probe=None, interval=5, enforce_gate=False, abort=None):
        self.journal, self.cancel, self.probe = journal, cancel, probe or WindowsResourceProbe()
        self.interval, self.enforce_gate, self.abort = interval, enforce_gate, abort
        self.stop = Event()
        self.samples = []
        self.started = time.monotonic()
        self.failure = None

    def sample(self):
        try:
            sample = self.probe()
        except Exception as exc:
            sample = dict(ram_total_bytes=None, ram_available_bytes=None, pagefile_used_bytes=None,
                gpu_used_bytes=None, missing={"probe":type(exc).__name__})
        sample = {**sample, "elapsed_seconds":time.monotonic()-self.started}
        self.samples.append(sample)
        self.journal.emit("telemetry",sample)
        if self.gate and self.gate.observe(sample):
            self.failure = self.gate.failure
            self.journal.emit("resource_stop",dict(reason=self.failure))
            self.cancel.set()
            if self.abort:
                self.abort()
        return sample

    def __enter__(self):
        self.gate = None
        self.baseline = self.sample()
        self.journal.emit("resource_baseline", self.baseline)
        if self.enforce_gate:
            self.gate = SustainedResourceGate(self.baseline)
        def poll():
            while not self.stop.wait(self.interval):
                self.sample()
        self.thread = Thread(target=poll,daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=25)
        if self.thread.is_alive():
            self.failure = "telemetry_shutdown_incomplete"
        else:
            self.sample()
        self.journal.emit("telemetry_summary",dict(status="failed" if self.failure else "recorded",
            reason=self.failure, sample_count=len(self.samples), interval_seconds=self.interval,
            maximum_observed_gap_seconds=max((b["elapsed_seconds"]-a["elapsed_seconds"] for a,b in zip(self.samples,self.samples[1:])),default=0),
            scope="local host RAM/pagefile/GPU; not cloud provider hardware"))
