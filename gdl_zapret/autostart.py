
import subprocess
import sys
from pathlib import Path

from .privileged import Elevation, shq

SERVICE_NAME = "zapretd"
SERVICE_FILE = f"/etc/systemd/system/{SERVICE_NAME}.service"

def _daemon_script() -> Path:
    
    return Path(__file__).resolve().parent.parent / "main.py"

def _python() -> str:
    return sys.executable

def make_unit(data_dir: str | None = None) -> str:
    
    extra = f" --data-dir {shq(data_dir)}" if data_dir else ""
    return (
        "[Unit]\n"
        "Description=zapretd обход замедления YouTube и Discord через zapret/nfqws\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={_python()} {_daemon_script()} --daemon{extra}\n"
        "Restart=on-failure\n"
        "RestartSec=3\n"
        "StandardOutput=journal\n"
        "StandardError=journal\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )

def install_service(
    elev: Elevation,
    client_paths=None,
    data_dir: str | None = None,
) -> tuple[bool, str]:
    
    from .app_paths import DAEMON_DATA_DIR

    unit = make_unit(data_dir)

    copy_block = ""
    if client_paths is not None:
        src_base = shq(str(client_paths.base))
        dst_base = shq(str(DAEMON_DATA_DIR))
        copy_block = (
            f"mkdir -p {dst_base}\n"
            f"cp -a {shq(str(client_paths.nfqws_dir))} {dst_base}/ 2>/dev/null || true\n"
            f"cp -a {shq(str(client_paths.strategies_dir))} {dst_base}/ 2>/dev/null || true\n"
            f"cp -a {shq(str(client_paths.custom_strategies_dir))} {dst_base}/ 2>/dev/null || true\n"
            f"cp -a {shq(str(client_paths.user_lists_dir))} {dst_base}/ 2>/dev/null || true\n"
            f"[ -f {shq(str(client_paths.config_file))} ] && "
            f"[ ! -f {dst_base}/config.json ] && "
            f"cp {shq(str(client_paths.config_file))} {dst_base}/config.json || true\n"
            f"chmod -R a+rX {dst_base}/strategies 2>/dev/null || true\n"
            f"chmod -R a+rX {dst_base}/user-lists 2>/dev/null || true\n"
            f"chmod +x {dst_base}/nfqws/nfqws 2>/dev/null || true\n"
        )

    script = (
        f"printf '%s' {shq(unit)} > {shq(SERVICE_FILE)}\n"
        f"chmod 644 {shq(SERVICE_FILE)}\n"
        + copy_block
        + f"systemctl daemon-reload\n"
        f"systemctl enable {shq(SERVICE_NAME)}\n"
        f"systemctl restart {shq(SERVICE_NAME)}\n"
        f"sleep 1\n"
        f"systemctl is-active {shq(SERVICE_NAME)}\n"
    )
    try:
        r = elev.run_shell(script)
    except Exception as e:
        return False, str(e)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "active" in out
    return ok, out

def remove_service(elev: Elevation) -> tuple[bool, str]:
    
    script = (
        f"systemctl disable --now {shq(SERVICE_NAME)} 2>/dev/null || true\n"
        f"rm -f {shq(SERVICE_FILE)}\n"
        f"systemctl daemon-reload\n"
        f"echo OK\n"
    )
    try:
        r = elev.run_shell(script)
    except Exception as e:
        return False, str(e)
    return True, (r.stdout or "") + (r.stderr or "")

def service_is_active() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False

def service_installed() -> bool:
    return Path(SERVICE_FILE).exists()
