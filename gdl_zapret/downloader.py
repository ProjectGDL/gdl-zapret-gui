import json
import os
import platform as _platform
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from .app_paths import (
    MAIN_REPO_REV,
    STRATEGIES_REPO_URL,
    TRANSLIT_MAP,
    USER_LIST_FILES,
    ZAPRET_RECOMMENDED_VERSION,
    ZAPRET_REPO,
)

_UA = "gdl-zapret-gui/0.1"

class DownloadError(RuntimeError):
    pass

def _urlopen(url):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    return urllib.request.urlopen(req, timeout=60)

def download_url(url: str, dest: Path, progress_cb=None) -> None:
    
    with _urlopen(url) as resp:
        total = int(resp.headers.get("Content-Length", 0)) or None
        done = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress_cb is not None:
                    if progress_cb(done, total, dest.name) is False:
                        raise DownloadError("Загрузка отменена")
        if progress_cb is not None:
            progress_cb(done, total, dest.name)

def detect_platform() -> str:
    arch = _platform.machine()
    if _platform.system() != "Linux":
        raise DownloadError("Поддерживается только Linux")
    table = {
        "x86_64": "linux-x86_64",
        "i686": "linux-x86",
        "i386": "linux-x86",
        "armv7l": "linux-arm",
        "armv6l": "linux-arm",
        "aarch64": "linux-arm64",
        "mips64": "linux-mips64",
        "mips64el": "linux-mips64el",
        "mipsel": "linux-mipsel",
        "mips": "linux-mips",
    }
    for key, val in table.items():
        if arch.startswith(key):
            return val
    raise DownloadError(f"Неподдерживаемая архитектура: {arch}")

def resolve_zapret_version(version: str) -> str:
    if version != "latest":
        return version
    with _urlopen(f"https://api.github.com/repos/{ZAPRET_REPO}/releases/latest") as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tag = data.get("tag_name")
    if not tag:
        raise DownloadError("Не удалось определить последний релиз zapret")
    return tag

def download_nfqws(paths, version, progress_cb=None) -> str:
    platform = detect_platform()
    tag = resolve_zapret_version(version)
    archive = f"zapret-{tag}.tar.gz"
    url = f"https://github.com/{ZAPRET_REPO}/releases/download/{tag}/{archive}"

    def cb(done, total, _name):
        return progress_cb(done, total, f"nfqws {tag}") if progress_cb else True

    tmpdir = Path(tempfile.mkdtemp(prefix="gdl-zapret-"))
    try:
        archive_path = tmpdir / archive
        download_url(url, archive_path, cb)
        paths.nfqws_dir.mkdir(parents=True, exist_ok=True)
        found = extract_file(archive_path, f"binaries/{platform}/nfqws", paths.nfqws_bin)
        if not found:
            raise DownloadError(
                f"nfqws не найден в архиве для платформы {platform}"
            )
        os.chmod(paths.nfqws_bin, os.stat(paths.nfqws_bin).st_mode | stat.S_IXUSR)
        return tag
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def extract_file(archive_path: Path, member_suffix: str, dest: Path) -> bool:
    
    with tarfile.open(archive_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            if member.name.endswith(member_suffix):
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                return True
    return False

def transliterate_filename(name: str) -> str:
    s = "".join(TRANSLIT_MAP.get(ch, ch) for ch in name)
    s = s.lower()
    s = re.sub(r"[\s()]+", "_", s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"_+\.bat", ".bat", s)
    return s

def download_strategies(paths, version, progress_cb=None) -> str:
    
    url = f"{STRATEGIES_REPO_URL}/archive/{version}.tar.gz"

    def cb(done, total, _name):
        return progress_cb(done, total, "стратегии") if progress_cb else True

    tmpdir = Path(tempfile.mkdtemp(prefix="gdl-zapret-strategies-"))
    try:
        archive_path = tmpdir / "strategies.tar.gz"
        download_url(url, archive_path, cb)

        extract_dir = tmpdir / "extracted"
        extract_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(extract_dir)

        top = next(d for d in extract_dir.iterdir() if d.is_dir())
        _replace_dir(paths.strategies_dir, top)
        _rename_bat_files(paths.strategies_dir)
        _prepare_user_lists(paths)
        return version
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def _replace_dir(dest: Path, src: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))

def _rename_bat_files(strategies_dir: Path) -> None:
    for f in strategies_dir.rglob("*.bat"):
        new_name = transliterate_filename(f.name)
        if new_name == f.name:
            continue
        target = f.parent / new_name
        if target.exists():
            print(f"Warning: не удалось переименовать {f.name}: файл с этим именем уже существует")
            continue
        f.rename(target)

def _prepare_user_lists(paths) -> None:
    paths.user_lists_dir.mkdir(parents=True, exist_ok=True)
    for name in USER_LIST_FILES:
        p = paths.user_lists_dir / name
        if not p.exists():
            p.touch()
        os.chmod(p, 0o644)
    lists_dir = paths.strategies_dir / "lists"
    if not lists_dir.is_dir():
        return
    for name in USER_LIST_FILES:
        src = paths.user_lists_dir / name
        dst = lists_dir / name
        try:
            if dst.exists():
                dst.unlink()
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

def has_nfqws(paths) -> bool:
    return paths.nfqws_bin.is_file() and os.access(paths.nfqws_bin, os.X_OK)

def has_strategies(paths) -> bool:
    if not paths.strategies_dir.is_dir():
        return False
    return any(
        f.is_file() and f.suffix.lower() == ".bat" and f.name.lower().startswith(("general", "discord"))
        for f in paths.strategies_dir.iterdir()
    )

def has_dependencies(paths) -> bool:
    return has_nfqws(paths) and has_strategies(paths)

def fetch_nfqws_versions(limit: int = 10) -> list[tuple[str, str]]:
    
    url = f"https://api.github.com/repos/{ZAPRET_REPO}/releases?per_page={limit}"
    with _urlopen(url) as resp:
        releases = json.loads(resp.read().decode("utf-8"))
    result = []
    for r in releases:
        tag = r.get("tag_name", "")
        name = r.get("name") or tag
        if tag:
            result.append((name or tag, tag))
    return result

def fetch_strategies_releases(limit: int = 10) -> list[tuple[str, str]]:
    
    repo_path = STRATEGIES_REPO_URL.removeprefix("https://github.com/")
    url = f"https://api.github.com/repos/{repo_path}/releases?per_page={limit}"
    with _urlopen(url) as resp:
        releases = json.loads(resp.read().decode("utf-8"))
    result = []
    for r in releases:
        tag = r.get("tag_name", "")
        name = r.get("name") or tag
        if tag:
            result.append((name or tag, tag))
    return result

    return {
        "nfqws": ZAPRET_RECOMMENDED_VERSION,
        "strategies": MAIN_REPO_REV,
    }
