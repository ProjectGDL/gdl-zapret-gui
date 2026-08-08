from PySide6.QtWidgets import QWizard

from .pages import (
    AutoDownloadPage,
    GameFilterPage,
    InterfacePage,
    StrategyPage,
    SummaryPage,
    WelcomePage,
)

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
