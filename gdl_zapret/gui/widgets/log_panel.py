from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget

_BTN_STYLE = (
    "QPushButton {"
    "  padding-left: 18px; padding-right: 18px;"
    "  padding-top: 10px; padding-bottom: 10px;"
    "  margin-top: 5px;"
    "}"
)

_TOGGLE_BTN_STYLE = (
    "QPushButton {"
    "  padding-left: 28px; padding-right: 28px;"
    "  padding-top: 10px; padding-bottom: 10px;"
    "  margin-top: 5px;"
    "}"
)


class LogPanel(QWidget):
    clear_requested  = Signal()
    toggle_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace", 9))
        self.log_view.setMaximumBlockCount(5000)

        self.toggle_btn = QPushButton("  Запустить")
        self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        self.toggle_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.toggle_btn.setStyleSheet(_TOGGLE_BTN_STYLE)
        self.toggle_btn.clicked.connect(self.toggle_requested.emit)

        self.clear_btn = QPushButton("Очистить лог")
        self.clear_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clear_btn.setStyleSheet(_BTN_STYLE)
        self.clear_btn.clicked.connect(self.clear_requested.emit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.toggle_btn)
        row.addWidget(self.clear_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.log_view, 1)
        layout.addLayout(row)

    def set_running(self, running: bool):
        self.toggle_btn.setText("  Остановить" if running else "  Запустить")
        self.toggle_btn.setIcon(QIcon.fromTheme(
            "media-playback-stop" if running else "media-playback-start"
        ))

    def set_lines(self, lines: list[str]):
        sb = self.log_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log_view.setPlainText("\n".join(lines))
        if at_bottom:
            sb.setValue(sb.maximum())

    def clear(self):
        self.log_view.clear()
