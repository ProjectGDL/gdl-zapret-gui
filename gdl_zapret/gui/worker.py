from PySide6.QtCore import QThread, Signal

class TaskThread(QThread):
    
    log = Signal(str)
    progress = Signal(int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def emit_log(self, msg):
        self.log.emit(str(msg))

    def emit_progress(self, done, total, text):
        if total:
            pct = min(100, int(done * 100 / total))
        else:
            pct = -1
        self.progress.emit(pct, str(text))

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.finished_ok.emit(result)
