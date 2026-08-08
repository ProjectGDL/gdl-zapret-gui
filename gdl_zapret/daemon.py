
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import firewall, strategy
from .app_paths import DaemonPaths

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 57080

class _State:
    
    def __init__(self):
        self.paths: DaemonPaths | None = None
        self.config: dict = {}
        self._proc: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _open_log(self, mode="a"):
        self.paths.log_file.parent.mkdir(parents=True, exist_ok=True)
        return open(self.paths.log_file, mode, encoding="utf-8", buffering=1)

    def _tail_log(self, lines: int = 500) -> list[str]:
        try:
            text = self.paths.log_file.read_text(encoding="utf-8", errors="replace")
            return text.splitlines()[-lines:]
        except OSError:
            return []

    def _stream_output(self, proc: subprocess.Popen):
        
        try:
            with self._open_log("a") as fh:
                for line in proc.stdout:
                    fh.write(line)
        except Exception:
            pass

    def start(self) -> tuple[bool, str]:
        if not self.paths.nfqws_bin.is_file():
            return False, "nfqws не установлен"

        cfg = self.config
        gt = bool(cfg.get("gamefiltertcp"))
        gu = bool(cfg.get("gamefilterudp"))
        sname = cfg.get("strategy", "general.bat")

        spath = strategy.get_strategy_path(self.paths, sname)
        if not spath:
            return False, f"Стратегия «{sname}» не найдена"

        try:
            parsed = strategy.parse_bat_file(spath, gt, gu, user_lists_dir=self.paths.user_lists_dir)
        except strategy.StrategyError as e:
            return False, str(e)

        backend = firewall.detect_backend(cfg.get("firewall_backend", "auto"))
        if not backend:
            return False, "firewall недоступен (требуется nftables или iptables)"

        iface = cfg.get("interface", "any")

        if self._proc is not None:
            self.stop()

        fw_script = firewall.build_setup_script(backend, parsed.tcp_ports, parsed.udp_ports, iface)
        r = subprocess.run(["bash", "-c", fw_script], capture_output=True, text=True)
        if r.returncode != 0:
            return False, "firewall настройка не удалась:\n" + (r.stderr or r.stdout or "").strip()

        cmd = strategy.build_nfqws_command(self.paths, parsed)

        with self._open_log("a") as fh:
            fh.write(f"\n--- старт {sname} [{time.strftime('%Y-%m-%d %H:%M:%S')}] ---\n")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._proc = proc

        t = threading.Thread(target=self._stream_output, args=(proc,), daemon=True)
        t.start()
        self._log_thread = t

        time.sleep(0.5)
        if proc.poll() is not None:
            out = ""
            try:
                out = self.paths.log_file.read_text(encoding="utf-8")[-500:]
            except OSError:
                pass
            self._proc = None
            return False, f"nfqws завершился сразу:\n{out}"

        return True, f"запущен (pid={proc.pid}, стратегия={sname}, firewall={backend}, iface={iface})"

    def stop(self) -> tuple[bool, str]:
        msgs = []
        backend = firewall.detect_backend(self.config.get("firewall_backend", "auto"))

        if self._proc is not None:
            pid = self._proc.pid
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._proc = None
            msgs.append(f"nfqws (pid={pid}) убит")
        else:
            subprocess.run(["pkill", "-9", "-f", "nfqws"], capture_output=True)
            msgs.append("nfqws убит через pkill -9")

        if backend:
            fw_script = firewall.build_clear_script(backend)
            r = subprocess.run(["bash", "-c", fw_script], capture_output=True, text=True)
            if r.returncode != 0:
                msgs.append("предупреждение при очистке firewall: " + (r.stderr or "").strip())
            else:
                msgs.append(f"firewall ({backend}) очищен")

        with self._open_log("a") as fh:
            fh.write(f"--- остановлен [{time.strftime('%Y-%m-%d %H:%M:%S')}] ---\n")

        return True, "; ".join(msgs)

    def status(self) -> dict:
        running = self.is_running()
        pid = self._proc.pid if running and self._proc else None
        return {
            "running": running,
            "pid": pid,
            "strategy": self.config.get("strategy"),
            "interface": self.config.get("interface"),
            "firewall_backend": self.config.get("firewall_backend"),
        }

_state = _State()

def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode()

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[zapretd] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        if self.path == "/status":
            self._send(200, _json(_state.status()))
        elif self.path == "/strategies":
            names = strategy.get_strategies(_state.paths)
            self._send(200, _json(names))
        elif self.path == "/backends":
            self._send(200, _json(firewall.available_backends()))
        elif self.path == "/log":
            lines = _state._tail_log(500)
            self._send(200, _json({"lines": lines}))
        else:
            self._send(404, _json({"error": "not found"}))

    def do_POST(self):
        body = self._read_body()

        if self.path == "/start":
            if body:
                _state.config.update(body)
                _save_config(_state.paths, _state.config)
            ok, msg = _state.start()
            self._send(200, _json({"ok": ok, "message": msg}))

        elif self.path == "/stop":
            ok, msg = _state.stop()
            self._send(200, _json({"ok": ok, "message": msg}))

        elif self.path == "/reload":
            if body:
                _state.config.update(body)
                _save_config(_state.paths, _state.config)
            _state.stop()
            ok, msg = _state.start()
            self._send(200, _json({"ok": ok, "message": msg}))

        elif self.path == "/config":
            if body:
                _state.config.update(body)
                _save_config(_state.paths, _state.config)
            self._send(200, _json({"ok": True, "config": _state.config}))

        elif self.path == "/log/clear":
            try:
                _state.paths.log_file.write_text("", encoding="utf-8")
                self._send(200, _json({"ok": True}))
            except OSError as e:
                self._send(200, _json({"ok": False, "message": str(e)}))

        elif self.path == "/sync-lists":
            if body:
                try:
                    _state.paths.user_lists_dir.mkdir(parents=True, exist_ok=True)
                    for fname, content in body.items():
                        fpath = _state.paths.user_lists_dir / fname
                        fpath.write_text(content, encoding="utf-8")
                    self._send(200, _json({"ok": True}))
                except Exception as e:
                    self._send(200, _json({"ok": False, "message": str(e)}))
            else:
                self._send(200, _json({"ok": True}))

        else:
            self._send(404, _json({"error": "not found"}))

def _save_config(paths: DaemonPaths, config: dict):
    try:
        paths.config_file.parent.mkdir(parents=True, exist_ok=True)
        paths.config_file.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        print(f"[zapretd] не удалось сохранить конфиг: {e}")

def _load_config(paths: DaemonPaths) -> dict:
    from .config import DEFAULTS
    data = dict(DEFAULTS)
    if paths.config_file.exists():
        try:
            loaded = json.loads(paths.config_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return data

def run_daemon(paths: DaemonPaths):
    if os.geteuid() != 0:
        print("[zapretd] ОШИБКА: демон должен запускаться от root", file=sys.stderr)
        sys.exit(1)

    _state.paths = paths
    _state.config = _load_config(paths)

    paths.ensure_dirs()

    if _state.config.get("autostart_zapret"):
        ok, msg = _state.start()
        print(f"[zapretd] автостарт zapret: {'OK' if ok else 'ОШИБКА'}. {msg}")

    server = HTTPServer((DAEMON_HOST, DAEMON_PORT), _Handler)

    def _shutdown(signum, frame):
        print(f"[zapretd] получен сигнал {signum}, завершение...")
        def _do():
            _state.stop()
            server.shutdown()
        threading.Thread(target=_do, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print(f"[zapretd] слушаю {DAEMON_HOST}:{DAEMON_PORT}")
    try:
        server.serve_forever()
    finally:
        _state.stop()
