import os
import re
import shlex
import shutil
from pathlib import Path

from .app_paths import GAME_FILTER_OFF_PORTS, GAME_FILTER_PORTS

_TMP_STRATS = Path("/tmp/gdlzstrats")

def prepare_tmp_dirs(strategies_dir: Path, user_lists_dir: Path | None = None) -> tuple[Path, Path]:
    tmp_lists = _TMP_STRATS / "lists"
    tmp_bin = _TMP_STRATS / "bin"
    tmp_lists.mkdir(parents=True, exist_ok=True)
    tmp_bin.mkdir(parents=True, exist_ok=True)
    tmp_lists.chmod(0o755)
    tmp_bin.chmod(0o755)
    _TMP_STRATS.chmod(0o755)

    for src_dir, dst_dir in (
        (strategies_dir / "lists", tmp_lists),
        (strategies_dir / "bin",   tmp_bin),
    ):
        if not src_dir.is_dir():
            continue
        for src in src_dir.iterdir():
            if not src.is_file():
                continue
            dst = dst_dir / src.name
            try:
                if dst.exists():
                    dst.unlink()
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            dst.chmod(0o644)

    if user_lists_dir is not None and user_lists_dir.is_dir():
        for src in user_lists_dir.iterdir():
            if not src.is_file():
                continue
            dst = tmp_lists / src.name
            try:
                if dst.exists():
                    dst.unlink()
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            dst.chmod(0o644)

    return tmp_lists, tmp_bin

class StrategyError(RuntimeError):
    pass

class ParsedStrategy:
    def __init__(self, name, tcp_ports, udp_ports, workers):
        self.name = name
        self.tcp_ports = tcp_ports
        self.udp_ports = udp_ports
        self.workers = workers

    @property
    def worker_count(self):
        return len(self.workers)

def get_strategies(paths) -> list:
    names = set()
    for d in (paths.custom_strategies_dir, paths.strategies_dir):
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.suffix.lower() != ".bat":
                continue
            low = f.name.lower()
            if d == paths.strategies_dir and not (
                low.startswith("general") or low.startswith("discord")
            ):
                continue
            names.add(f.name)
    return sorted(names)

def get_strategy_path(paths, name) -> Path | None:
    for d in (paths.custom_strategies_dir, paths.strategies_dir):
        p = d / name
        if p.is_file():
            return p
    return None

def _replace_game_filters(content, tcp, udp):
    if tcp and udp:
        use_tcp, use_udp = True, True
    elif tcp:
        use_tcp, use_udp = True, False
    elif udp:
        use_tcp, use_udp = False, True
    else:
        use_tcp, use_udp = False, False
    use = tcp or udp

    if use:
        content = content.replace("%GameFilter%", GAME_FILTER_PORTS)
        content = content.replace(
            "%GameFilterTCP%",
            GAME_FILTER_PORTS if use_tcp else GAME_FILTER_OFF_PORTS,
        )
        content = content.replace(
            "%GameFilterUDP%",
            GAME_FILTER_PORTS if use_udp else GAME_FILTER_OFF_PORTS,
        )
    else:
        for token in ("%GameFilter%", "%GameFilterTCP%", "%GameFilterUDP%"):
            content = content.replace(f",{token}", "")
            content = content.replace(f"{token},", "")
    return content

_WF_RE = re.compile(r"--wf-(tcp|udp)=([0-9,\-]+)")
_WORKER_RE = re.compile(r"--filter-(tcp|udp)=([0-9,\-]+)\s+(?:[\s\S]*?--new|.*)")

def parse_bat_file(path, gamefiltertcp=False, gamefilterudp=False, user_lists_dir=None) -> ParsedStrategy:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    content = raw.replace("\r", "")
    name = Path(path).name

    strategies_dir = Path(path).parent
    tmp_lists, tmp_bin = prepare_tmp_dirs(strategies_dir, user_lists_dir)
    content = content.replace("%BIN%", str(tmp_bin) + "/").replace(
        "%LISTS%", str(tmp_lists) + "/"
    )
    content = _replace_game_filters(content, gamefiltertcp, gamefilterudp)

    wf = dict(_WF_RE.findall(content))
    if len(wf) != 2 or "tcp" not in wf or "udp" not in wf:
        raise StrategyError(
            f"В стратегии {name} не найдены (или найдены повторно) параметры "
            f"--wf-tcp / --wf-udp"
        )
    tcp_ports, udp_ports = wf["tcp"], wf["udp"]

    workers = []
    for m in _WORKER_RE.finditer(content):
        text = m.group(0)
        try:
            tokens = shlex.split(text, posix=True)
        except ValueError:
            tokens = text.split()
        line = " ".join(tokens).replace("=^!", "=!")
        if line.strip():
            workers.append(line)

    return ParsedStrategy(name, tcp_ports, udp_ports, workers)

def build_nfqws_command(paths, parsed: ParsedStrategy):
    
    argv = [
        str(paths.nfqws_bin),
        "--user=root",
        "--dpi-desync-fwmark=0x40000000",
        "--qnum=220",
    ]
    for worker in parsed.workers:
        argv.extend(shlex.split(worker))
    return argv

def nfqws_args_text(paths, parsed: ParsedStrategy) -> str:
    
    return " ".join(shlex.quote(a) for a in build_nfqws_command(paths, parsed))
