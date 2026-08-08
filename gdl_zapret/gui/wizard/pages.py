from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWizardPage,
)

from ... import downloader
from ..common import system_interfaces, _iface_label
from ..worker import TaskThread

class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Добро пожаловать")
        lbl = QLabel(
            "Этот мастер поможет настроить zapret для "
            "YouTube и Discord.\n\n"
            "Сначала будут загружены компоненты, затем вы выберете несколько "
            "параметров. Остальное приложение сделает автоматически.\n\n"
        )
        lbl.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(lbl)

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

class InterfacePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Сетевой интерфейс")
        self.setSubTitle(
            "Укажите сетевой интерфейс для обхода. Вариант «any» применяет "
            "обход ко всему трафику."
        )
        self.combo = QComboBox()
        self.combo.addItem("Весь трафик (any)", "any")
        for name in system_interfaces():
            self.combo.addItem(_iface_label(name), name)
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
        from ...strategy import get_strategies

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
