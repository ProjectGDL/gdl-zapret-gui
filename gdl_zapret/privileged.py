
import os
import shlex
import shutil
import subprocess

class ElevationError(RuntimeError):
    pass

def shq(value) -> str:
    return shlex.quote(str(value))

class Elevation:
    
    def __init__(self):
        self._method = None

    def detect(self) -> str | None:
        if os.geteuid() == 0:
            return "direct"
        if shutil.which("sudo"):
            r = subprocess.run(
                ["sudo", "-n", "-v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if r.returncode == 0:
                return "sudo"
        if shutil.which("pkexec"):
            return "pkexec"
        return None

    @property
    def method(self) -> str | None:
        if self._method is None:
            self._method = self.detect()
        return self._method

    def reset(self):
        self._method = None

    @property
    def available(self) -> bool:
        return self.method is not None

    def describe(self) -> str:
        return {"direct": "root", "sudo": "sudo", "pkexec": "pkexec"}.get(
            self.method or "", "нет прав root"
        )

    def run_shell(self, script: str, *, timeout: int = 120) -> subprocess.CompletedProcess:
        if self.method is None:
            raise ElevationError(
                "Не удалось найти способ повышения привилегий (требуется sudo или pkexec)"
            )
        kwargs = dict(capture_output=True, text=True, timeout=timeout)
        if self.method == "direct":
            return subprocess.run(["bash", "-c", script], **kwargs)
        if self.method == "sudo":
            return subprocess.run(["sudo", "-n", "bash", "-c", script], **kwargs)
        return subprocess.run(
            ["pkexec", "/usr/bin/env", "bash", "-c", script], **kwargs
        )
