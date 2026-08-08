from PySide6.QtWidgets import QApplication

from .. import downloader
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
        window._start_after_show = wizard.summary_page.start_now.isChecked()
        window._first_run = True

    window.show()
    return app.exec()
