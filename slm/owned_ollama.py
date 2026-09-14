"""Fail-safe termination of the explicitly owned S3 server; never another user's server."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
from threading import Lock
from urllib.parse import urlsplit

from slm.resource_monitor import hidden_run
from slm.windows_process import NativeProcessHandle


class OwnedOllama:
    def __init__(self, owner_path, *, journal, endpoint):
        self.owner_path = Path(owner_path)
        owner_bytes = self.owner_path.read_bytes()
        self.owner_sha256 = hashlib.sha256(owner_bytes).hexdigest()
        self.owner = json.loads(owner_bytes.decode("utf-8-sig"))
        self.identity_path = self.owner_path.with_name(self.owner_path.name + ".native_identity.json")
        self.native_process = None
        self.native_evidence = None
        self.native_binding_rejected = False
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
        self._pin_native_process(process)

    def _verify_native_evidence(self, evidence):
        if evidence.get("version") != "owned-native-process-v1" or evidence.get("owner_sha256") != self.owner_sha256:
            raise ValueError("native process evidence does not match owner record")
        process, identity = evidence["verified_process"], evidence["native_identity"]
        self._verify_process(process)
        listeners = process.get("ListenerPids")
        if type(listeners) is int:
            listeners = [listeners]
        if not isinstance(listeners, list) or set(listeners) != {int(self.owner["pid"])}:
            raise ValueError("native evidence lacks original listener verification")
        if identity["pid"] != int(self.owner["pid"]) or Path(identity["image_path"]).name.lower() != "ollama.exe":
            raise ValueError("native identity is not the owned Ollama process")
        from datetime import datetime, timezone
        created = datetime.fromisoformat(process["CreatedUtc"].replace("Z", "+00:00"))
        epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        delta = created.astimezone(timezone.utc) - epoch
        ticks = (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10
        # CIM DateTime has microsecond precision; native FILETIME has 100ns precision.
        if type(identity["creation_filetime"]) is not int or not 0 <= identity["creation_filetime"] - ticks < 10:
            raise ValueError("native creation time differs from verified process")

    def _pin_native_process(self, process):
        if self.native_process is not None:
            return
        pinned = None
        try:
            pinned = NativeProcessHandle(int(self.owner["pid"]))
            evidence = dict(version="owned-native-process-v1", owner_sha256=self.owner_sha256,
                verified_process=process, native_identity=pinned.identity())
            self._verify_native_evidence(evidence)
            if pinned.wait_exited(0):
                raise ValueError("owned process exited during native binding")
            if self.identity_path.exists():
                existing = json.loads(self.identity_path.read_text(encoding="utf-8"))
                self._verify_native_evidence(existing)
                if existing["native_identity"] != evidence["native_identity"]:
                    raise ValueError("existing native identity cannot be replaced")
                evidence = existing
            else:
                # Exclusive creation preserves prior run evidence and owner bytes.
                with self.identity_path.open("x", encoding="utf-8") as stream:
                    json.dump(evidence, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
            self.native_process, self.native_evidence = pinned, evidence
            self.journal.emit("native_process_identity_bound", evidence)
        except OSError as exc:
            if pinned is not None:
                pinned.close()
            # Original CIM verification remains mandatory on this compatibility
            # path. A failed API never grants permission to kill an uncertain PID.
            self.journal.emit("native_process_identity_unavailable", dict(error_type=type(exc).__name__))
        except Exception:
            self.native_binding_rejected = True
            if pinned is not None:
                pinned.close()
            raise

    def _restore_native_process(self):
        if self.native_process is not None or not self.identity_path.exists():
            return
        evidence = json.loads(self.identity_path.read_text(encoding="utf-8"))
        self._verify_native_evidence(evidence)
        pinned = NativeProcessHandle(int(self.owner["pid"]))
        try:
            if pinned.identity() != evidence["native_identity"] or pinned.wait_exited(0):
                raise ValueError("owned native process identity changed or exited")
            self.native_process, self.native_evidence = pinned, evidence
        except Exception:
            pinned.close()
            raise

    def _stop_native_process(self, pid):
        self._verify_native_evidence(self.native_evidence)
        if self.native_process.identity() != self.native_evidence["native_identity"] or self.native_process.wait_exited(0):
            raise ValueError("owned native process identity changed or exited")
        # Holding this handle keeps the process object/PID bound through taskkill.
        hidden_run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=10)
        if not self.native_process.wait_exited(2000):
            raise TimeoutError("owned server did not signal exit within 2 seconds")
        self.native_process.close()
        self.native_process = None

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
                if self.native_binding_rejected:
                    raise ValueError("native identity binding was rejected; explicit reconciliation required")
                self._restore_native_process()
                if self.native_process is not None:
                    self._stop_native_process(pid)
                    self.stopped = True
                    self.proof = dict(status="owned_process_tree_terminated", pid=pid,
                        identity_method="native_handle_and_persisted_identity", lease_released=False,
                        restart_requires_explicit_reconciliation=True)
                    self.journal.emit("server_stop", self.proof)
                    return self.proof
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
