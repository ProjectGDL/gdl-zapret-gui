from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from .. import downloader
from ..app_paths import ZAPRET_RECOMMENDED_VERSION
from .worker import TaskThread

def _system_interfaces() -> list:
    from pathlib import Path
    net = Path("/sys/class/net")
    if net.is_dir():
        return sorted(p.name for p in net.iterdir())
    return []

def _status_label(text, ok):
    lbl = QLabel(text)
    lbl.setEnabled(ok)
    return lbl

class AutoDownloadPage(QWizardPage):
    
    def __init__(self, paths, config, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.config = config
        self._task = None
        self._done = False

        self.setTitle("Загрузка компонентов")
        self.setSubTitle("Загружаем nfqws и стратегии обхода...")

        self.lbl_nfqws = QLabel("nfqws: ожидание...")
        self.bar_nfqws = QProgressBar()
        self.bar_nfqws.setRange(0, 100)
        self.bar_nfqws.setValue(0)
        self.bar_nfqws.setTextVisible(False)

        self.lbl_strategies = QLabel("Стратегии: ожидание...")
        self.bar_strategies = QProgressBar()
        self.bar_strategies.setRange(0, 100)
        self.bar_strategies.setValue(0)
        self.bar_strategies.setTextVisible(False)

        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.hide()

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl_nfqws)
        lay.addWidget(self.bar_nfqws)
        lay.addWidget(self.lbl_strategies)
        lay.addWidget(self.bar_strategies)
        lay.addWidget(self.lbl_error)
        lay.addStretch(1)

    def initializePage(self):
        if self._done:
            return
        self._done = False
        self.lbl_error.hide()
        self.lbl_nfqws.setText("nfqws: загрузка...")
        self.lbl_strategies.setText("Стратегии: ожидание...")
        self.bar_nfqws.setValue(0)
        self.bar_strategies.setValue(0)
        self.completeChanged.emit()

        task = TaskThread(self._do_download)
        task.progress.connect(self._on_progress)
        task.finished_ok.connect(self._on_done)
        task.failed.connect(self._on_failed)
        self._task = task
        task.start()

    def _do_download(self):
        tag = downloader.download_nfqws(
            self.paths, "latest", self._progress_nfqws
        )
        self.config["nfqws_version"] = tag
        self.config["nfqws_version_label"] = "latest"
        ver = downloader.download_strategies(
            self.paths, "main", self._progress_strategies
        )
        self.config["strategies_version"] = ver
        self.config.save()

    def _progress_nfqws(self, done, total, text):
        pct = min(100, int(done * 100 / total)) if total else 0
        self._task.progress.emit(pct, f"nfqws:{text}")

    def _progress_strategies(self, done, total, text):
        pct = min(100, int(done * 100 / total)) if total else 0
        self._task.progress.emit(pct, f"strategies:{text}")

    def _on_progress(self, pct, text):
        if text.startswith("nfqws:"):
            self.bar_nfqws.setValue(pct)
            self.lbl_nfqws.setText(f"nfqws: {text[6:]}")
        elif text.startswith("strategies:"):
            self.lbl_nfqws.setText("nfqws: готово")
            self.bar_nfqws.setValue(100)
            self.bar_strategies.setValue(pct)
            self.lbl_strategies.setText(f"Стратегии: {text[11:]}")

    def _on_done(self, _):
        self.bar_nfqws.setValue(100)
        self.bar_strategies.setValue(100)
        self.lbl_nfqws.setText("nfqws: готово")
        self.lbl_strategies.setText("Стратегии: готово")
        self._done = True
        self._task = None
        self.completeChanged.emit()
        self.wizard().next()

    def _on_failed(self, msg):
        self._done = False
        self._task = None
        self.lbl_error.setText(f"Ошибка загрузки: {msg}")
        self.lbl_error.show()
        self.completeChanged.emit()

    def isComplete(self):
        return self._done

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

class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Добро пожаловать")
        lbl = QLabel(
            "Этот мастер поможет настроить обход замедления (zapret) для "
            "YouTube и Discord.\n\n"
            "Сначала будут загружены компоненты, затем вы выберете несколько "
            "параметров. Остальное приложение сделает автоматически.\n\n"
            "Загружаемые файлы (nfqws, стратегии) хранятся в "
            "~/.local/share/gdl-zapret-gui. Конфигурация и управление "
            "передаются системному демону zapretd (/var/lib/zapretgd/)."
        )
        lbl.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(lbl)

class DepsPage(QWizardPage):
    def __init__(self, paths, config, strategy_page=None, parent=None):
        super().__init__(parent)
        self.setTitle("Зависимости")
        self.setSubTitle("Скачайте nfqws и стратегии, либо проверьте уже установленные.")
        self.deps = DepsWidget(paths, config)
        lay = QVBoxLayout(self)
        lay.addWidget(self.deps)
        self.deps.changed.connect(self.completeChanged)
        self.deps.changed.connect(self._on_changed)
        self._strategy_page = strategy_page

    def _on_changed(self):
        if self._strategy_page is not None:
            self._strategy_page.refresh()

    def isComplete(self):
        return self.deps.is_complete()

    def log(self, msg):
        self.deps.log.emit(msg)

class InterfacePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Сетевой интерфейс")
        self.setSubTitle(
            "Укажите сетевой интерфейс для обхода. Вариант «any» применяет "
            "обход ко всему трафику."
        )
        self.combo = QComboBox()
        self.combo.addItem("any (весь трафик)", "any")
        for name in _system_interfaces():
            self.combo.addItem(name, name)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Интерфейс:"))
        lay.addWidget(self.combo)

    def value(self):
        return self.combo.currentData()

class StrategyPage(QWizardPage):
    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.setTitle("Стратегия обхода")
        self.setSubTitle("Стратегия определяет способ обхода. По умолчанию используется general.")
        self.paths = paths
        self.combo = QComboBox()
        self.empty = QLabel(
            "Стратегии не найдены.\n"
            "Вернитесь на шаг «Зависимости» и скачайте их."
        )
        self.empty.setWordWrap(True)
        self.empty.hide()
        self.refresh()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Стратегия:"))
        lay.addWidget(self.combo)
        lay.addWidget(self.empty)

    def initializePage(self):
        self.refresh()

    def refresh(self):
        names = []
        from ..strategy import get_strategies

        for n in get_strategies(self.paths):
            if n.lower() == "general.bat":
                names.insert(0, n)
            else:
                names.append(n)
        current = self.combo.currentData()
        self.combo.clear()
        for n in names:
            self.combo.addItem(n, n)
        if names:
            self.combo.show()
            self.empty.hide()
            idx = self.combo.findData(current)
            self.combo.setCurrentIndex(max(0, idx))
        else:
            self.combo.hide()
            self.empty.show()
        self.completeChanged.emit()

    def isComplete(self):
        return self.combo.count() > 0

    def value(self):
        return self.combo.currentData()

class GameFilterPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("GameFilter (игровой трафик)")
        self.setSubTitle(
            "Включает обработку игровых портов (1024-65535). Обычно не требуется, "
            "по умолчанию отключено."
        )
        self.tcp = QCheckBox("Включить GameFilter TCP")
        self.udp = QCheckBox("Включить GameFilter UDP")
        lay = QVBoxLayout(self)
        lay.addWidget(self.tcp)
        lay.addWidget(self.udp)
        lay.addStretch(1)

    def values(self):
        return self.tcp.isChecked(), self.udp.isChecked()

class BackendPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Файрвол")
        self.setSubTitle(
            "Приложение автоматически определит доступный бэкенд. "
            "Можно выбрать вручную."
        )
        self.combo = QComboBox()
        self.combo.addItem("auto (автоопределение)", "auto")
        from .. import firewall

        for b in firewall.available_backends():
            self.combo.addItem(b, b)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Бэкенд файрвола:"))
        lay.addWidget(self.combo)

    def value(self):
        return self.combo.currentData()

class SummaryPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Готово")
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.start_now = QCheckBox("Запустить zapret сразу после настройки")
        self.start_now.setChecked(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self.summary)
        lay.addWidget(self.start_now)

    def set_text(self, text):
        self.summary.setText(text)

class FirstRunWizard(QWizard):
    def __init__(self, paths, config, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.config = config
        self.setWindowTitle("Первоначальная настройка gdl-zapret-gui")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(560, 480)

        self.download_page = AutoDownloadPage(paths, config)
        self.interface_page = InterfacePage()
        self.strategy_page = StrategyPage(paths)
        self.gamefilter_page = GameFilterPage()
        self.summary_page = SummaryPage()
        self.start_now = True

        self.addPage(WelcomePage())
        self.addPage(self.download_page)
        self.addPage(self.interface_page)
        self.addPage(self.strategy_page)
        self.addPage(self.gamefilter_page)
        self.addPage(self.summary_page)

        self.currentIdChanged.connect(self._update_summary)

    def _update_summary(self, page_id):
        if page_id != self.pageIds()[-1]:
            return
        iface = self.interface_page.value()
        strat = self.strategy_page.value() or "(не выбрана)"
        tcp, udp = self.gamefilter_page.values()
        self.summary_page.set_text(
            "Ваша конфигурация:\n"
            f"Интерфейс: {iface}\n"
            f"Стратегия: {strat}\n"
            f"GameFilter TCP: {'да' if tcp else 'нет'}\n"
            f"GameFilter UDP: {'да' if udp else 'нет'}\n\n"
            "Нажмите «Готово» для сохранения."
        )

    def result_config(self) -> dict:
        return {
            "interface": self.interface_page.value(),
            "strategy": self.strategy_page.value(),
            "gamefiltertcp": self.gamefilter_page.values()[0],
            "gamefilterudp": self.gamefilter_page.values()[1],
            "firewall_backend": "auto",
        }
