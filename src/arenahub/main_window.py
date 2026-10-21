from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ArenaHub")
        self.resize(800, 600)
        label = QLabel("ArenaHub", alignment=Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)
