"""Fail-safe termination of the explicitly owned S3 server; never another user's server."""
import json
from pathlib import Path
import shutil
import subprocess
from threading import Lock
from urllib.parse import urlsplit

from slm.resource_monitor import hidden_run


class OwnedOllama:
    def __init__(self, owner_path, *, journal, endpoint):
        self.owner = json.loads(Path(owner_path).read_text(encoding="utf-8-sig"))
        if self.owner.get("endpoint") != endpoint or self.owner.get("num_parallel") != 1 or self.owner.get("max_loaded_models") != 1 or self.owner.get("context_length") != 32768:
            raise ValueError("server ownership/config does not certify single concurrency and 32768 context")
        self.journal = journal
        self.lock = Lock()
        self.stopped = False
        self.proof = None

    def validate(self):
        """Bind the recorded server to its live PID and listening port before inference."""
        pid = int(self.owner["pid"])
        port = urlsplit(self.owner["endpoint"]).port
        shell = shutil.which("pwsh") or shutil.which("powershell")
        script = (f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
            f"$listeners = @(Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction Stop); "
            "$p | Select-Object Name,CommandLine,@{Name='CreatedUtc';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}},"
            "@{Name='ListenerPids';Expression={@($listeners.OwningProcess)}} | ConvertTo-Json -Compress")
        process = json.loads(hidden_run([shell, "-NoProfile", "-Command", script]).stdout)
        self._verify_process(process)
        # Windows PowerShell may unwrap a one-element calculated property to an integer.
        listeners = process.get("ListenerPids")
        if type(listeners) is int:
            listeners = [listeners]
        if not isinstance(listeners, list) or set(listeners) != {pid}:
            raise ValueError("endpoint listener is not the explicitly owned server")
        self.journal.emit("server_ownership_verified", dict(pid=pid, port=port, process=process))

    def _verify_process(self, process):
        if not isinstance(process, dict):
            raise ValueError("recorded Ollama server is no longer running")
        if process["Name"].lower() != "ollama.exe" or "serve" not in process["CommandLine"]:
            raise ValueError("owned PID no longer identifies the launched Ollama serve")
        from datetime import datetime
        created = datetime.fromisoformat(process["CreatedUtc"].replace("Z", "+00:00"))
        recorded = datetime.fromisoformat(self.owner["started_at_utc"].replace("Z", "+00:00"))
        if abs((created-recorded).total_seconds()) > 10:
            raise ValueError("server PID creation time no longer matches ownership")

    def stop(self):
        with self.lock:
            if self.stopped:
                return self.proof
            pid = int(self.owner["pid"])
            shell = shutil.which("pwsh") or shutil.which("powershell")
            script = (f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | "
                "Select-Object Name,CommandLine,@{Name='CreatedUtc';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
            try:
                raw = hidden_run([shell, "-NoProfile", "-Command", script]).stdout.strip()
                if not raw:
                    raise ValueError("owned PID absent; process tree cannot be inferred")
                process = json.loads(raw)
                self._verify_process(process)
                hidden_run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=10)
                after = hidden_run([shell, "-NoProfile", "-Command", script]).stdout.strip()
                if after:
                    raise ValueError("owned server still present after termination")
                self.stopped = True
                self.proof = dict(status="owned_process_tree_terminated", pid=pid,
                    lease_released=False, restart_requires_explicit_reconciliation=True)
            except Exception as exc:
                self.proof = dict(status="termination_unconfirmed", error_type=type(exc).__name__, pid=pid,
                    lease_released=False, restart_requires_explicit_reconciliation=True)
            self.journal.emit("server_stop", self.proof)
            return self.proof
