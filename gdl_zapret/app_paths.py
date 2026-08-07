import os
from pathlib import Path

DAEMON_DATA_DIR = Path("/var/lib/zapretgd")

class DaemonPaths:
    
    def __init__(self, data_dir=None):
        self.base = Path(data_dir) if data_dir else DAEMON_DATA_DIR
        self.nfqws_dir = self.base / "nfqws"
        self.nfqws_bin = self.nfqws_dir / "nfqws"
        self.strategies_dir = self.base / "strategies"
        self.custom_strategies_dir = self.base / "custom-strategies"
        self.user_lists_dir = self.base / "user-lists"
        self.config_file = self.base / "config.json"
        self.pid_file = self.base / "nfqws.pid"
        self.log_file = self.base / "daemon.log"

    def ensure_dirs(self):
        for d in (
            self.nfqws_dir,
            self.strategies_dir,
            self.custom_strategies_dir,
            self.user_lists_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

def default_client_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "gdl-zapret-gui"
    return Path.home() / ".local" / "share" / "gdl-zapret-gui"

class ClientPaths:
    
    def __init__(self, data_dir=None):
        self.base = Path(data_dir) if data_dir else default_client_data_dir()
        self.nfqws_dir = self.base / "nfqws"
        self.nfqws_bin = self.nfqws_dir / "nfqws"
        self.strategies_dir = self.base / "strategies"
        self.custom_strategies_dir = self.base / "custom-strategies"
        self.user_lists_dir = self.base / "user-lists"
        self.config_file = self.base / "config.json"

    def ensure_dirs(self):
        for d in (
            self.nfqws_dir,
            self.strategies_dir,
            self.custom_strategies_dir,
            self.user_lists_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

Paths = ClientPaths

SERVICE_NAME = "zapret_discord_youtube"

NFT_TABLE = "inet zapretunix"
NFT_CHAIN = "post"
NFT_CHAIN_PRE = "pre"
NFT_QUEUE_NUM = "220"
NFT_MARK = "0x40000000"
NFT_RULE_COMMENT = "zapret DPI bypass rule"

IPT_CHAIN = "zapret"
IPT_CHAIN_REPLY = "reply"
IPT_TABLE = "mangle"

GAME_FILTER_PORTS = "1024-65535"
GAME_FILTER_OFF_PORTS = "12"

STRATEGIES_REPO_URL = "https://github.com/Flowseal/zapret-discord-youtube"
MAIN_REPO_REV = "ef19845a801e4e743f7bdfdbd58f9745c6adbd60"

ZAPRET_REPO = "bol-van/zapret"
ZAPRET_RECOMMENDED_VERSION = "v72.9"

USER_LIST_FILES = (
    "ipset-exclude-user.txt",
    "list-general-user.txt",
    "list-exclude-user.txt",
)

TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "H", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Sch", "Ъ": "",
    "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
}
