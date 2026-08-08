from PySide6.QtWidgets import QApplication, QMessageBox

from .. import autostart, downloader
from ..client import DaemonClient
from .main_window import MainWindow
from .wizard import FirstRunWizard

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
