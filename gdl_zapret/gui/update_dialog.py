import os
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..client import DaemonClient
from ..updater import Updater


class _CheckThread(QThread):
    done = Signal(bool, str)

    def __init__(self, updater: Updater):
        super().__init__()
        self._updater = updater

    def run(self):
        ok, msg = self._updater.check()
        self.done.emit(ok, msg)


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновление")
        self.setMinimumWidth(380)
        self.setWindowModality(Qt.ApplicationModal)

        self._updater = Updater()

        self._label = QLabel("Проверка обновлений...")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._update_btn = QPushButton("Обновить")
        self._update_btn.setVisible(False)
        self._update_btn.clicked.connect(self._launch)

        self._restart_btn = QPushButton("Перезапустить приложение")
        self._restart_btn.setVisible(False)
        self._restart_btn.clicked.connect(self._restart)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._update_btn)
        layout.addWidget(self._restart_btn)
        layout.addWidget(self._buttons)

        self._thread = _CheckThread(self._updater)
        self._thread.done.connect(self._on_check_done)
        self._thread.start()

    def _on_check_done(self, ok: bool, msg: str):
        self._label.setText(msg)
        mode = self._updater.detect_mode()
        if ok and mode != self._updater.MODE_NONE:
            self._update_btn.setVisible(True)

    def _launch(self):
        err = self._updater.launch_update()
        if err:
            self._label.setText(f"Ошибка: {err}")
            return
        self._label.setText(
            "Обновление запущено в терминале.\n\n"
            "После завершения перезапустите приложение."
        )
        self._update_btn.setVisible(False)
        self._restart_btn.setVisible(True)

    def _restart(self):
        client = DaemonClient()
        if client.is_running():
            try:
                client.reload()
            except Exception:
                pass
        os.execv(sys.executable, [sys.executable] + sys.argv)
