import sys
import os


def resource_path(relative_path):

    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox
)

from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile


class LoginWindow:

    def __init__(self):

        loader = QUiLoader()

        ui_file = QFile(resource_path("login.ui"))
        ui_file.open(QFile.ReadOnly)

        self.window = loader.load(ui_file)

        ui_file.close()

        self.window.btnLogin.clicked.connect(self.login)

    def login(self):

        username = self.window.txtUsername.text()
        password = self.window.txtPassword.text()

        if username == "admin" and password == "admin":

            dashboard_file = QFile(resource_path("dashboard.ui"))
            dashboard_file.open(QFile.ReadOnly)

            loader = QUiLoader()

            self.dashboard = loader.load(dashboard_file)

            dashboard_file.close()

            self.dashboard.show()

            self.window.close()

        else:
            QMessageBox.warning(
                self.window,
                "Login Failed",
                "Invalid username or password"
            )


app = QApplication(sys.argv)

login = LoginWindow()

login.window.show()

sys.exit(app.exec())