from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart, downloader
from ..client import DaemonClient, DaemonError, DaemonUnavailable
from ..privileged import Elevation
from .settings_dialog import SettingsDialog
from .worker import TaskThread
from .wizard import FirstRunWizard

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
        self._build_menu()
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

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace", 9))
        self.log_view.setMaximumBlockCount(5000)

        clear_btn = QPushButton("Очистить лог")
        clear_btn.clicked.connect(self._clear_log)

        log_row = QHBoxLayout()
        log_row.addStretch(1)
        log_row.addWidget(clear_btn)

        root.addWidget(self.start_btn)
        root.addWidget(self.log_view, 1)
        root.addLayout(log_row)
        self.setCentralWidget(central)
        self.statusBar().showMessage("")

    def _build_menu(self):
        menubar = self.menuBar()

        m_app = menubar.addMenu("&Приложение")
        self.act_toggle = QAction("Запустить", self)
        self.act_toggle.setShortcut(QKeySequence("Ctrl+R"))
        self.act_toggle.triggered.connect(self._toggle)
        m_app.addAction(self.act_toggle)
        m_app.addSeparator()
        act_settings = QAction("Настройки...", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings)
        m_app.addAction(act_settings)
        m_app.addSeparator()
        act_quit = QAction("Выход", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        m_app.addAction(act_quit)

        m_srv = menubar.addMenu("&Сервис")
        self.act_service = QAction("Установить сервис", self)
        self.act_service.triggered.connect(self._toggle_service)
        m_srv.addAction(self.act_service)

        m_help = menubar.addMenu("&Справка")
        act_about = QAction("О программе", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

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
        task = TaskThread(fn)

        def _done(result):
            ok, out = result
            self._refresh_status()
            if not ok:
                QMessageBox.critical(self, "Ошибка", out.strip())
            elif then_start and self.client.daemon_alive():
                self._start()

        def _failed(msg):
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

    def _poll_log(self):
        if not self.client.daemon_alive():
            return
        lines = self.client.get_log()
        if lines == self._last_log_lines:
            return
        self._last_log_lines = lines
        sb = self.log_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log_view.setPlainText("\n".join(lines))
        if at_bottom:
            sb.setValue(sb.maximum())

    def _clear_log(self):
        self.client.clear_log()
        self._last_log_lines = None
        self.log_view.clear()

    def _refresh_status(self):
        alive = self.client.daemon_alive()
        running = self.client.is_running() if alive else False

        self.start_btn.setText("Остановить" if running else "Запустить")
        self.act_toggle.setText("Остановить" if running else "Запустить")

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

def run_app(paths, config):
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("gdl-zapret-gui")
    window = MainWindow(paths, config)

    first_run = not paths.config_file.exists() or not downloader.has_dependencies(paths)
    if first_run:
        wizard = FirstRunWizard(paths, config, window)
        if wizard.exec() != FirstRunWizard.Accepted:
            return 0
        config.update(wizard.result_config())
        config.save()
        client = DaemonClient()
        if wizard.summary_page.start_now.isChecked():
            if not client.daemon_alive():
                ok, out = autostart.install_service(
                    window.elev, client_paths=paths
                )
                if not ok:
                    QMessageBox.critical(
                        window,
                        "Ошибка установки сервиса",
                        out.strip() or "Не удалось установить zapretd.",
                    )
            if client.daemon_alive():
                window._start()
    window.show()
    return app.exec()
