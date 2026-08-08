from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import firewall, strategy
from ..client import DaemonClient
from .common import system_interfaces
from .wizard import DepsWidget

class SettingsDialog(QDialog):
    def __init__(self, paths, config, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.config = config
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(460)

        client = DaemonClient()
        daemon_alive = client.daemon_alive()

        strategy_names = client.strategies() if daemon_alive else strategy.get_strategies(paths)
        backends = client.backends() if daemon_alive else firewall.available_backends()

        self.interface = QComboBox()
        self.interface.addItem("any (весь трафик)", "any")
        for name in system_interfaces():
            self.interface.addItem(name, name)
        self.interface.setCurrentIndex(max(0, self.interface.findData(config.get("interface", "any"))))

        self.strategy = QComboBox()
        for name in strategy_names:
            self.strategy.addItem(name, name)
        sidx = self.strategy.findData(config.get("strategy"))
        if sidx >= 0:
            self.strategy.setCurrentIndex(sidx)

        tab_main = QWidget()
        form_main = QFormLayout(tab_main)
        form_main.addRow("Сетевой интерфейс:", self.interface)
        form_main.addRow("Стратегия:", self.strategy)

        self.gamefilter_tcp = QCheckBox("GameFilter TCP (порты 1024-65535)")
        self.gamefilter_tcp.setChecked(bool(config.get("gamefiltertcp")))
        self.gamefilter_udp = QCheckBox("GameFilter UDP (порты 1024-65535)")
        self.gamefilter_udp.setChecked(bool(config.get("gamefilterudp")))

        self.backend = QComboBox()
        self.backend.addItem("auto (автоопределение)", "auto")
        for b in backends:
            self.backend.addItem(b, b)
        self.backend.setCurrentIndex(max(0, self.backend.findData(config.get("firewall_backend", "auto"))))

        self.autostart = QCheckBox("Запускать zapret автоматически вместе с сервисом zapretd")
        self.autostart.setChecked(bool(config.get("autostart_zapret")))

        daemon_status = "работает" if daemon_alive else "не запущен"
        info = QLabel(f"Демон zapretd: {daemon_status}\nДанные клиента: {paths.base}")
        info.setWordWrap(True)

        tab_adv = QWidget()
        form_adv = QFormLayout(tab_adv)
        form_adv.addRow("GameFilter TCP:", self.gamefilter_tcp)
        form_adv.addRow("GameFilter UDP:", self.gamefilter_udp)
        form_adv.addRow("Бэкенд файрвола:", self.backend)
        form_adv.addRow("Автозапуск:", self.autostart)
        form_adv.addRow("", info)

        tab_deps = QWidget()
        lay_deps = QVBoxLayout(tab_deps)
        lay_deps.addWidget(DepsWidget(paths, config))

        tabs = QTabWidget()
        tabs.addTab(tab_main, "Основные")
        tabs.addTab(tab_adv, "Дополнительно")
        tabs.addTab(tab_deps, "Компоненты")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def accept(self):
        self.config.update(
            {
                "interface": self.interface.currentData(),
                "strategy": self.strategy.currentData(),
                "gamefiltertcp": self.gamefilter_tcp.isChecked(),
                "gamefilterudp": self.gamefilter_udp.isChecked(),
                "firewall_backend": self.backend.currentData(),
                "autostart_zapret": self.autostart.isChecked(),
            }
        )
        self.config.save()
        super().accept()
