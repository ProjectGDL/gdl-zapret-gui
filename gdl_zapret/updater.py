import subprocess
from pathlib import Path


RAW_EXTENSION = Path("/var/lib/extensions/gdl-zapret-gui.raw")
_UJUST_CMD = "ujust zapret-install"


def _find_git_root() -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        root = Path(out)
        if (root / "main.py").is_file():
            return root
    except Exception:
        pass
    return None


class Updater:
    MODE_EXTENSION = "extension"
    MODE_GIT       = "git"
    MODE_NONE      = "none"

    def __init__(self):
        self._mode = None

    def detect_mode(self) -> str:
        if self._mode is None:
            if RAW_EXTENSION.exists():
                self._mode = self.MODE_EXTENSION
            elif _find_git_root() is not None:
                self._mode = self.MODE_GIT
            else:
                self._mode = self.MODE_NONE
        return self._mode

    def check(self) -> tuple[bool, str]:
        mode = self.detect_mode()
        if mode == self.MODE_NONE:
            return False, "Источник обновлений не обнаружен."
        if mode == self.MODE_EXTENSION:
            return True, f"Обновление через системное расширение ({RAW_EXTENSION.name})."
        if mode == self.MODE_GIT:
            root = _find_git_root()
            try:
                subprocess.check_output(
                    ["git", "fetch"],
                    cwd=root,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
                behind = subprocess.check_output(
                    ["git", "rev-list", "HEAD..@{u}", "--count"],
                    cwd=root,
                    text=True,
                    timeout=5,
                ).strip()
                n = int(behind)
                if n == 0:
                    return True, "Уже последняя версия (git)."
                return True, f"Доступно {n} новых коммитов (git)."
            except Exception as e:
                return True, f"Git-репозиторий найден, статус недоступен: {e}"
        return False, "Неизвестный режим."

    def build_terminal_command(self) -> list[str] | None:
        mode = self.detect_mode()
        if mode == self.MODE_NONE:
            return None

        if mode == self.MODE_EXTENSION:
            script = _UJUST_CMD
        else:
            root = _find_git_root()
            script = f"cd {root} && git pull"

        wrapped = (
            f"( {script}\n)\n"
            "status=$?\n"
            "echo\n"
            'if [ "$status" -ne 0 ]; then echo "Завершено с ошибкой ($status)."; fi\n'
            'read -n 1 -s -r -p "Нажмите любую клавишу для закрытия..."\n'
        )
        return [
            "xdg-terminal-exec",
            "--title=gdl-zapret-gui: обновление",
            "--",
            "bash",
            "--noprofile",
            "--norc",
            "-lc",
            wrapped,
        ]

    def launch_update(self) -> str | None:
        cmd = self.build_terminal_command()
        if cmd is None:
            return "Источник обновлений не обнаружен."
        try:
            subprocess.Popen(cmd)
            return None
        except FileNotFoundError:
            return "xdg-terminal-exec не найден."
        except Exception as e:
            return f"Не удалось открыть терминал: {e}"
