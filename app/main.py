import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("NetworkOperationsBuilder")
    app.setApplicationName("Network Operations Builder")
    app.setFont(QFont("Malgun Gothic", 10))
    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv:
        # Exercises bundled definitions and Qt event loop without modifying a project.
        window.service.generate()
        QTimer.singleShot(250, window.close)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
