from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart, downloader
from ..client import DaemonClient, DaemonError
from ..privileged import Elevation
from .main_menu import build_menu
from .settings_dialog import SettingsDialog
from .widgets import LogPanel
from .worker import TaskThread

class MainWindow(QMainWindow):
    def __init__(self, paths, config):
        super().__init__()
        self.paths = paths
        self.config = config
        self.elev = Elevation()
        self.client = DaemonClient()
        self._task = None
        self._last_log_lines = []

        self.setWindowTitle("gdl-zapret-gui")
        self.setMinimumSize(640, 520)

        self._build_ui()
        build_menu(self)
        self._refresh_status()
        self._poll_log()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(2000)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._poll_log)
        self._log_timer.start(1000)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        self.start_btn = QPushButton("Запустить")
        self.start_btn.setMinimumHeight(56)
        self.start_btn.clicked.connect(self._toggle)

        self.log_panel = LogPanel()
        self.log_panel.clear_requested.connect(self._clear_log)

        self._spacer_top = QSpacerItem(0, 50, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._spacer_bottom = QSpacerItem(0, 50, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # бесконечный режим
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)

        root.addItem(self._spacer_top)
        root.addWidget(self.start_btn)
        root.addItem(self._spacer_bottom)
        root.addWidget(self.log_panel, 1)
        root.addWidget(self.progress_bar)
        self._root_layout = root
        self.setCentralWidget(central)
        self.statusBar().showMessage("")

        show_log = self.config.get("show_log", False)
        self.log_panel.setVisible(show_log)
        self._set_spacers_visible(not show_log)
        if show_log:
            self.setMinimumSize(640, 520)
        else:
            self.setMinimumSize(640, 200)

    def _toggle(self):
        if self._busy():
            return
        if not self.client.daemon_alive():
            self._toggle_service(then_start=True)
            return
        if self.client.is_running():
            self._stop()
        else:
            self._start()

    def _start(self):
        if not downloader.has_dependencies(self.paths):
            QMessageBox.warning(
                self,
                "Нет зависимостей",
                "nfqws или стратегии не установлены.\n"
                "Скачайте их в Приложение → Настройки.",
            )
            return
        cfg = dict(self.config.data)
        self._run_task(lambda: self._do_start(cfg))

    def _do_start(self, cfg) -> tuple[bool, str]:
        ok, msg = self.client.start(cfg)
        if not ok:
            raise DaemonError(msg)
        return ok, msg

    def _stop(self):
        self._run_task(lambda: self._do_stop())

    def _do_stop(self) -> tuple[bool, str]:
        ok, msg = self.client.stop()
        if not ok:
            raise DaemonError(msg)
        return ok, msg

    def _open_settings(self):
        dlg = SettingsDialog(self.paths, self.config, self)
        if dlg.exec():
            if self.client.daemon_alive():
                if self.client.is_running():
                    self._run_task(lambda: self._do_restart(dict(self.config.data)))
                else:
                    self.client.set_config(dict(self.config.data))
                    self._refresh_status()
            else:
                self._refresh_status()

    def _do_restart(self, cfg) -> tuple[bool, str]:
        ok, msg = self.client.stop()
        if not ok:
            raise DaemonError(msg)
        ok, msg = self.client.start(cfg)
        if not ok:
            raise DaemonError(msg)
        return ok, msg

    def _toggle_service(self, then_start=False):
        if autostart.service_installed():
            fn = lambda: autostart.remove_service(self.elev)
        else:
            fn = lambda: autostart.install_service(self.elev, client_paths=self.paths)
        self.act_service.setEnabled(False)
        self.progress_bar.setVisible(True)
        task = TaskThread(fn)

        def _done(result):
            self.progress_bar.setVisible(False)
            ok, out = result
            self._refresh_status()
            if not ok:
                QMessageBox.critical(self, "Ошибка", out.strip())
            elif then_start and self.client.daemon_alive():
                self._start()

        def _failed(msg):
            self.progress_bar.setVisible(False)
            self._refresh_status()
            QMessageBox.critical(self, "Ошибка", msg)

        task.finished_ok.connect(_done)
        task.failed.connect(_failed)
        self._svc_task = task
        task.start()

    def _about(self):
        QMessageBox.about(
            self,
            "О программе",
            f"<h3>gdl-zapret-gui {__version__}</h3>"
            "<p>Графический интерфейс для обхода замедления YouTube и Discord "
            "на базе <b>zapret</b> (nfqws) и стратегий "
            "Flowseal/zapret-discord-youtube.</p>"
            "<p>Демон: <code>zapretd</code> (systemd, root, "
            f"localhost:{__import__('gdl_zapret.daemon', fromlist=['DAEMON_PORT']).DAEMON_PORT})</p>"
            f"<p>Данные клиента: <code>{self.paths.base}</code></p>"
            "<p>Данные демона: <code>/var/lib/zapretgd/</code></p>",
        )

    def _busy(self):
        return self._task is not None and self._task.isRunning()

    def _set_busy(self, busy):
        self.start_btn.setEnabled(not busy)
        self.act_toggle.setEnabled(not busy)
        self.progress_bar.setVisible(busy)

    def _run_task(self, fn):
        self._set_busy(True)
        task = TaskThread(fn)

        def _finish():
            task.wait(15000)
            if self._task is task:
                self._task = None
            self._set_busy(False)
            self._refresh_status()

        def on_ok(result):
            _finish()

        def on_fail(msg):
            _finish()
            QMessageBox.critical(self, "Ошибка", msg)

        task.finished_ok.connect(on_ok)
        task.failed.connect(on_fail)
        self._task = task
        task.start()

    def _set_spacers_visible(self, visible: bool):
        size = 50 if visible else 0
        self._spacer_top.changeSize(0, size, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._spacer_bottom.changeSize(0, size, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._root_layout.invalidate()

    def _toggle_log(self, checked: bool):
        self.log_panel.setVisible(checked)
        self._set_spacers_visible(not checked)
        if checked:
            self.setMinimumSize(640, 520)
        else:
            self.setMinimumSize(640, 100)
            self.resize(self.width(), self.minimumHeight())
        self.config["show_log"] = checked
        self.config.save()

    def _poll_log(self):
        if not self.client.daemon_alive():
            return
        lines = self.client.get_log()
        if lines == self._last_log_lines:
            return
        self._last_log_lines = lines
        self.log_panel.set_lines(lines)

    def _clear_log(self):
        self.client.clear_log()
        self._last_log_lines = None
        self.log_panel.clear()

    def _refresh_status(self):
        alive = self.client.daemon_alive()
        running = self.client.is_running() if alive else False

        self.start_btn.setText("Остановить" if running else "Запустить")
        self.start_btn.setIcon(QIcon.fromTheme("media-playback-stop" if running else "media-playback-start"))
        self.act_toggle.setText("Остановить" if running else "Запустить")
        self.act_toggle.setIcon(QIcon.fromTheme("media-playback-stop" if running else "media-playback-start"))

        svc_installed = autostart.service_installed()
        self.act_service.setText(
            "Удалить сервис zapretd" if svc_installed else "Установить сервис zapretd"
        )
        self.act_service.setEnabled(True)

        if running:
            self.statusBar().showMessage("zapret работает")
        elif alive:
            self.statusBar().showMessage("zapret не запущен")
        else:
            self.statusBar().showMessage(
                "Сервис не установлен. Установите его через Сервис → Установить сервис zapretd."
            )

    def closeEvent(self, event):
        if self.client.daemon_alive() and self.client.is_running():
            ret = QMessageBox.question(
                self,
                "Остановить?",
                "zapret работает. Остановить перед выходом?",
            )
            if ret == QMessageBox.Yes:
                self._run_task(self._do_stop)
                if self._task:
                    self._task.wait(15000)
        event.accept()
