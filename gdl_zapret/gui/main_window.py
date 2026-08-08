from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressBar,
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
from .update_dialog import UpdateDialog
from .widgets import LogPanel, RoundButton
from .worker import TaskThread

class _StatusPoller(QObject):
    result = Signal(bool, bool)

    def __init__(self, client):
        super().__init__()
        self._client = client

    def poll(self):
        alive = self._client.daemon_alive()
        running = self._client.is_running() if alive else False
        self.result.emit(alive, running)


class _LogPoller(QObject):
    result = Signal(object)

    def __init__(self, client):
        super().__init__()
        self._client = client

    def poll(self):
        if not self._client.daemon_alive():
            self.result.emit(None)
            return
        self.result.emit(self._client.get_log())


class MainWindow(QMainWindow):
    def __init__(self, paths, config):
        super().__init__()
        self.paths = paths
        self.config = config
        self.elev = Elevation()
        self.client = DaemonClient()
        self._task = None
        self._last_log_lines = []
        self._start_after_show = False
        self._first_run = False
        self._daemon_alive = False
        self._daemon_running = False

        self.setWindowTitle("gdl-zapret-gui")
        self.setMinimumSize(640, 520)

        self._timers_started = False

        self._build_ui()
        build_menu(self)

        self._status_thread = QThread(self)
        self._status_poller = _StatusPoller(self.client)
        self._status_poller.moveToThread(self._status_thread)
        self._status_poller.result.connect(self._on_status)
        self._status_timer = QTimer()
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._status_poller.poll)
        self._status_timer.moveToThread(self._status_thread)
        self._status_thread.started.connect(self._status_timer.start)

        self._log_thread = QThread(self)
        self._log_poller = _LogPoller(self.client)
        self._log_poller.moveToThread(self._log_thread)
        self._log_poller.result.connect(self._on_log)
        self._log_timer = QTimer()
        self._log_timer.setInterval(1000)
        self._log_timer.timeout.connect(self._log_poller.poll)
        self._log_timer.moveToThread(self._log_thread)
        self._log_thread.started.connect(self._log_timer.start)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        self.start_btn = RoundButton()
        self.start_btn.clicked.connect(self._toggle)

        self._btn_row = QHBoxLayout()
        self._btn_row.addWidget(self.start_btn)
        self._btn_wrapper = QWidget()
        self._btn_wrapper.setLayout(self._btn_row)

        self.log_panel = LogPanel()
        self.log_panel.clear_requested.connect(self._clear_log)
        self.log_panel.toggle_requested.connect(self._toggle)

        self._spacer_top = QSpacerItem(0, 50, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._spacer_bottom = QSpacerItem(0, 50, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._spacer_btn_bottom = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setMaximumWidth(120)
        self.progress_bar.setVisible(False)

        root.addItem(self._spacer_top)
        root.addWidget(self._btn_wrapper)
        root.addItem(self._spacer_btn_bottom)
        root.addItem(self._spacer_bottom)
        root.addWidget(self.log_panel, 1)
        self._root_layout = root
        self.setCentralWidget(central)
        self.statusBar().showMessage("")
        self.statusBar().addPermanentWidget(self.progress_bar)

        show_log = self.config.get("show_log", False)
        self.log_panel.setVisible(show_log)
        self._btn_wrapper.setVisible(not show_log)
        self._set_spacers_visible(not show_log)
        self._set_btn_mode(show_log)
        if show_log:
            self.setMinimumSize(640, 520)
        else:
            self.setMinimumSize(360, 460)
            self.resize(420, 460)

    def _toggle(self):
        if self._busy():
            return
        if not self._daemon_alive:
            self._toggle_service(then_start=True)
            return
        if self._daemon_running:
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
            if self._daemon_alive:
                if self._daemon_running:
                    self._run_task(lambda: self._do_restart(dict(self.config.data)))
                else:
                    cfg = dict(self.config.data)
                    self._run_task(lambda: self.client.set_config(cfg) and None or (True, ""))

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
        self._set_progress(True)
        task = TaskThread(fn)

        def _done(result):
            self._set_progress(False)
            ok, out = result
            self._refresh_status()
            if not ok:
                QMessageBox.critical(self, "Ошибка", out.strip())
            elif then_start and self.client.daemon_alive():
                self._start()

        def _failed(msg):
            self._set_progress(False)
            self._refresh_status()
            QMessageBox.critical(self, "Ошибка", msg)

        task.finished_ok.connect(_done)
        task.failed.connect(_failed)
        self._svc_task = task
        task.start()

    def _check_updates(self):
        dlg = UpdateDialog(self)
        dlg.exec()

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
        self._set_progress(busy)

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

    def _set_progress(self, visible: bool):
        self.progress_bar.setVisible(visible)

    def _set_spacers_visible(self, visible: bool):
        size = 50 if visible else 0
        self._spacer_top.changeSize(0, size, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._spacer_bottom.changeSize(0, size, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._root_layout.invalidate()

    def _set_btn_mode(self, log_visible: bool):
        for i in reversed(range(self._btn_row.count())):
            item = self._btn_row.itemAt(i)
            if item and item.spacerItem():
                self._btn_row.removeItem(item)

        if not log_visible:
            self._btn_row.insertStretch(0, 1)
            self._btn_row.addStretch(1)

        self._root_layout.invalidate()

    def _toggle_log(self, checked: bool):
        self.log_panel.setVisible(checked)
        self._btn_wrapper.setVisible(not checked)
        self._set_spacers_visible(not checked)
        self._set_btn_mode(checked)
        if checked:
            self.setMinimumSize(640, 520)
        else:
            self.setMinimumSize(360, 460)
            self.resize(420, 460)
        self.config["show_log"] = checked
        self.config.save()

    def _poll_log(self):
        self._log_poller.poll()

    def _clear_log(self):
        self._last_log_lines = None
        self.log_panel.clear()
        self._run_task(lambda: (self.client.clear_log(), (True, ""))[1])

    def _on_status(self, alive: bool, running: bool):
        self._daemon_alive = alive
        self._daemon_running = running
        self._refresh_status()

    def _on_log(self, lines):
        if lines is None:
            return
        if lines == self._last_log_lines:
            return
        self._last_log_lines = lines
        self.log_panel.set_lines(lines)

    def _refresh_status(self):
        alive = self._daemon_alive
        running = self._daemon_running

        self.start_btn.setRunning(running)
        self.log_panel.set_running(running)
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

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timers_started:
            self._timers_started = True
            self._status_thread.start()
            self._log_thread.start()
            if self._start_after_show:
                self._start_after_show = False
                QTimer.singleShot(0, self._start_after_wizard)

    def _start_after_wizard(self):
        def _do():
            if self._first_run:
                try:
                    self.client.stop()
                except Exception:
                    pass
                if autostart.service_installed():
                    autostart.remove_service(self.elev)

            ok, out = autostart.install_service(self.elev, client_paths=self.paths)
            if not ok:
                raise RuntimeError(out.strip() or "Не удалось установить zapretd.")
            if self.client.daemon_alive():
                ok, msg = self.client.start(dict(self.config.data))
                if not ok:
                    raise RuntimeError(msg)
            return None, ""

        self._run_task(_do)

    def closeEvent(self, event):
        for thread in (self._status_thread, self._log_thread):
            thread.quit()
            thread.wait(2000)

        if self._daemon_alive and self._daemon_running:
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
