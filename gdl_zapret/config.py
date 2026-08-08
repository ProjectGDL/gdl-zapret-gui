import json

from .app_paths import MAIN_REPO_REV, ZAPRET_RECOMMENDED_VERSION

DEFAULTS = {
    "interface": "any",
    "strategy": "general.bat",
    "gamefiltertcp": False,
    "gamefilterudp": False,
    "firewall_backend": "auto",
    "nfqws_version": ZAPRET_RECOMMENDED_VERSION,
    "strategies_version": MAIN_REPO_REV,
    "nfqws_version_label": "v72.9",
    "autostart_zapret": False,
    "show_log": False,
}

class Config:
    def __init__(self, paths):
        self.paths = paths
        self.data = dict(DEFAULTS)

    def load(self):
        if self.paths.config_file.exists():
            try:
                loaded = json.loads(self.paths.config_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass
        return self

    def save(self):
        self.paths.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.config_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, values: dict):
        self.data.update(values)
