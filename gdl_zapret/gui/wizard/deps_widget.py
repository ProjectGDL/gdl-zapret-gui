from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import downloader
from ...app_paths import ZAPRET_RECOMMENDED_VERSION
from ..worker import TaskThread

class DepsWidget(QWidget):
    changed = Signal()
    log = Signal(str)

    def __init__(self, paths, config, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.config = config
        self._task = None

        grid = QGridLayout()
        grid.addWidget(QLabel("<b>Компонент</b>"), 0, 0)
        grid.addWidget(QLabel("<b>Статус</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Версия</b>"), 0, 2)

        self.nfqws_status = QLabel()
        self.strategies_status = QLabel()

        self.nfqws_version = QComboBox()
        self.nfqws_version.addItem(f"Рекомендованная ({ZAPRET_RECOMMENDED_VERSION})", ZAPRET_RECOMMENDED_VERSION)
        self.nfqws_version.addItem("Последняя (latest)", "latest")
        self.nfqws_version.setEnabled(False)

        self.strategies_version = QComboBox()
        self.strategies_version.addItem("main", "main")
        self.strategies_version.setEnabled(False)

        grid.addWidget(QLabel("nfqws (демон zapret)"), 1, 0)
        grid.addWidget(self.nfqws_status, 1, 1)
        grid.addWidget(self.nfqws_version, 1, 2)
        grid.addWidget(QLabel("Стратегии обхода"), 2, 0)
        grid.addWidget(self.strategies_status, 2, 1)
        grid.addWidget(self.strategies_version, 2, 2)

        self.download_btn = QPushButton("Скачать недостающее")
        self.download_btn.clicked.connect(lambda: self.download(force=False))
        self.redownload_btn = QPushButton("Переустановить всё")
        self.redownload_btn.clicked.connect(lambda: self.download(force=True))

        btn_row = QVBoxLayout()
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.redownload_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(btn_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addStretch(1)

        self.refresh()
        self._fetch_versions()

    def _fetch_versions(self):
        self._fetch_task = TaskThread(self._do_fetch_versions)
        self._fetch_task.finished_ok.connect(self._on_versions_fetched)
        self._fetch_task.failed.connect(lambda _: None)
        self._fetch_task.start()

    def _do_fetch_versions(self):
        nfqws = downloader.fetch_nfqws_versions()
        strategies = downloader.fetch_strategies_releases()
        return nfqws, strategies

    def _on_versions_fetched(self, result):
        nfqws_versions, strategies_branches = result

        prev = self.nfqws_version.currentData()
        self.nfqws_version.clear()
        for label, tag in nfqws_versions:
            self.nfqws_version.addItem(label, tag)
        idx = self.nfqws_version.findData(prev)
        self.nfqws_version.setCurrentIndex(max(0, idx))
        self.nfqws_version.setEnabled(True)

        prev = self.strategies_version.currentData()
        self.strategies_version.clear()
        for label, ref in strategies_branches:
            self.strategies_version.addItem(label, ref)
        idx = self.strategies_version.findData(prev)
        self.strategies_version.setCurrentIndex(max(0, idx))
        self.strategies_version.setEnabled(True)

    def is_complete(self):
        return downloader.has_dependencies(self.paths)

    def busy(self):
        return self._task is not None and self._task.isRunning()

    def refresh(self):
        ok_n = downloader.has_nfqws(self.paths)
        ok_s = downloader.has_strategies(self.paths)
        self.nfqws_status.setText("установлен" if ok_n else "не установлен")
        self.nfqws_status.setEnabled(ok_n)
        self.strategies_status.setText("установлены" if ok_s else "не установлены")
        self.strategies_status.setEnabled(ok_s)
        busy = self.busy()
        self.download_btn.setEnabled(not busy and not self.is_complete())
        self.redownload_btn.setEnabled(not busy and self.is_complete())

    def download(self, force=False):
        if self.busy():
            return
        paths, config = self.paths, self.config
        nv = self.nfqws_version.currentData()
        sv = self.strategies_version.currentData()
        task = TaskThread(
            self._do_download, paths, config, nv, sv, force
        )
        task.log.connect(self.log)
        task.progress.connect(self._on_progress)
        task.finished_ok.connect(self._on_done)
        task.failed.connect(self._on_failed)
        self._task = task
        self.download_btn.setEnabled(False)
        self.redownload_btn.setEnabled(False)
        self.status.setText("Загрузка...")
        task.start()

    def _do_download(self, paths, config, nv, sv, force):
        if force or not downloader.has_nfqws(paths):
            tag = downloader.download_nfqws(paths, nv, self._task.emit_progress)
            config["nfqws_version"] = tag
            config["nfqws_version_label"] = nv
        if force or not downloader.has_strategies(paths):
            ver = downloader.download_strategies(paths, sv, self._task.emit_progress)
            config["strategies_version"] = ver
        config.save()
        return True

    def _on_progress(self, pct, text):
        if pct >= 0:
            self.progress.setValue(pct)
        self.status.setText(f"Загрузка: {text}")

    def _on_done(self, _result):
        self.progress.setValue(100)
        self.status.setText("Загрузка завершена.")
        if self._task is not None:
            self._task.wait(15000)
            self._task = None
        self.refresh()
        self.changed.emit()

    def _on_failed(self, message):
        self.status.setText(f"Ошибка: {message}")
        if self._task is not None:
            self._task.wait(15000)
            self._task = None
        self.refresh()
        self.changed.emit()
