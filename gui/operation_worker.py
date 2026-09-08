"""Keep the UI responsive while preventing edits to active file operations."""
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QProgressBar
from core.file_manager import OperationResult, OperationStatus


class FileOperationWorker(QThread):
    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.result = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.result = OperationResult(0, 1, [str(exc)], status=OperationStatus.FAILED,
                                          reason=str(exc))


class OperationProgress(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procesando archivos")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Verificando y procesando archivos. Espera a que termine."))
        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(progress)

    def reject(self):
        # Do not let Escape destroy a running worker or unlock editable groups.
        pass

    def closeEvent(self, event):
        event.ignore()


def run_file_operation(parent, operation):
    dialog = OperationProgress(parent)
    worker = FileOperationWorker(operation, dialog)
    worker.finished.connect(dialog.accept)
    worker.start()
    dialog.exec()
    worker.wait()
    return worker.result
