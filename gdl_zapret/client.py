
import json
import urllib.error
import urllib.request
from typing import Any

from .daemon import DAEMON_HOST, DAEMON_PORT

BASE_URL = f"http://{DAEMON_HOST}:{DAEMON_PORT}"
_TIMEOUT = 10

class DaemonError(RuntimeError):
    pass

class DaemonUnavailable(DaemonError):
    pass

def _request(method: str, path: str, body: dict | None = None) -> Any:
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise DaemonUnavailable(
            f"Демон недоступен ({e}). Убедитесь, что zapretd запущен."
        ) from e
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        try:
            err = json.loads(body_text).get("message", body_text)
        except (json.JSONDecodeError, AttributeError):
            err = body_text
        raise DaemonError(f"Ошибка демона [{e.code}]: {err}") from e

def _get(path: str) -> Any:
    return _request("GET", path)

def _post(path: str, body: dict | None = None) -> Any:
    return _request("POST", path, body or {})

class DaemonClient:
    
    def is_running(self) -> bool:
        
        try:
            return bool(_get("/status").get("running"))
        except DaemonUnavailable:
            return False

    def daemon_alive(self) -> bool:
        
        try:
            _get("/status")
            return True
        except DaemonUnavailable:
            return False

    def status(self) -> dict:
        return _get("/status")

    def start(self, config: dict | None = None) -> tuple[bool, str]:
        
        resp = _post("/start", config)
        return resp.get("ok", False), resp.get("message", "")

    def stop(self) -> tuple[bool, str]:
        resp = _post("/stop")
        return resp.get("ok", False), resp.get("message", "")

    def reload(self, config: dict | None = None) -> tuple[bool, str]:
        
        resp = _post("/reload", config)
        return resp.get("ok", False), resp.get("message", "")

    def set_config(self, config: dict) -> dict:
        
        return _post("/config", config)

    def strategies(self) -> list[str]:
        try:
            return _get("/strategies")
        except DaemonUnavailable:
            return []

    def backends(self) -> list[str]:
        try:
            return _get("/backends")
        except DaemonUnavailable:
            return []

    def get_log(self, lines: int = 500) -> list[str]:
        try:
            return _get("/log").get("lines", [])
        except (DaemonUnavailable, DaemonError):
            return []

    def clear_log(self) -> bool:
        try:
            return _post("/log/clear").get("ok", False)
        except (DaemonUnavailable, DaemonError):
            return False
