from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Signal

class LogPanel(QWidget):
    """Виджет панели лога: текстовое поле + кнопка очистки."""

    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("monospace", 9))
        self.log_view.setMaximumBlockCount(5000)

        self.clear_btn = QPushButton("Очистить лог")
        self.clear_btn.clicked.connect(self.clear_requested.emit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.clear_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.log_view, 1)
        layout.addLayout(row)

    def set_lines(self, lines: list[str]):
        sb = self.log_view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log_view.setPlainText("\n".join(lines))
        if at_bottom:
            sb.setValue(sb.maximum())

    def clear(self):
        self.log_view.clear()
