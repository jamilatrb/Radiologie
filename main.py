import ctypes
import re
import sqlite3
import sys
from datetime import datetime

from database import APP_DIR, Database, PASSWORD_MIN_LENGTH

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QFont, QIcon
    from PyQt5.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QFrame,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QSizePolicy,
        QTableWidget,
        QTableWidgetItem,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError as error:
    PYQT_IMPORT_ERROR = error
else:
    PYQT_IMPORT_ERROR = None


APP_TITLE = "Gestion des rendez-vous de radiologie"
EXAM_TYPES = ["Échographie", "TDM / Scanner", "Écho mammaire", "IRM"]
STATUS_VALUES = ["Valide", "Non valide"]
SEARCH_FIELDS = [
    ("Tous", "Tous"),
    ("Nom", "Nom"),
    ("CIN", "CIN"),
    ("Téléphone", "Telephone"),
]
ALL_EXAMS_LABEL = "Tous les examens"


def build_rdv_datetime(date_value="", hour_value=""):
    date_value = (date_value or "").strip()
    hour_value = (hour_value or "").strip() or "00:00"

    if not date_value:
        return datetime.today().strftime("%Y-%m-%d %H:%M")

    return f"{date_value} {hour_value}"


def format_validation_date(date_value=""):
    value = (date_value or "").strip()
    if not value:
        return "Non validée"

    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def show_blocking_message(title, message):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        print(f"{title}\n{message}")


if PYQT_IMPORT_ERROR is None:

    class StatCard(QFrame):
        def __init__(self, title, accent_class):
            super().__init__()
            self.setObjectName(f"statCard {accent_class}")
            self.setProperty("cardRole", accent_class)
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.setMaximumHeight(88)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(4)

            self.value_label = QLabel("0")
            self.value_label.setObjectName("statValue")

            self.title_label = QLabel(title)
            self.title_label.setObjectName("statTitle")

            layout.addWidget(self.value_label)
            layout.addWidget(self.title_label)

        def set_value(self, value):
            self.value_label.setText(str(value))


    class AccessSetupDialog(QDialog):
        def __init__(self, database, parent=None):
            super().__init__(parent)
            self.database = database
            self.created_username = ""

            self.setWindowTitle("Créer l'accès principal")
            self.setModal(True)
            self.setMinimumWidth(460)

            self.username_input = QLineEdit()
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.Password)

            self._build_ui()

        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 20)
            layout.setSpacing(18)

            title = QLabel("Créer l'accès principal")
            title.setObjectName("dialogTitle")
            subtitle = QLabel(
                f"Ce compte local sera demandé à chaque ouverture du logiciel. "
                f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
            )
            subtitle.setObjectName("dialogSubtitle")

            layout.addWidget(title)
            layout.addWidget(subtitle)

            form_card = QFrame()
            form_card.setObjectName("panelCard")
            form_layout = QFormLayout(form_card)
            form_layout.setContentsMargins(20, 20, 20, 20)
            form_layout.setHorizontalSpacing(16)
            form_layout.setVerticalSpacing(14)
            form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            form_layout.addRow("Nom d'utilisateur *", self.username_input)
            form_layout.addRow("Mot de passe *", self.password_input)
            form_layout.addRow("Confirmation *", self.confirm_password_input)

            layout.addWidget(form_card)

            actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            actions.button(QDialogButtonBox.Save).setText("Créer l'accès")
            actions.button(QDialogButtonBox.Cancel).setText("Annuler")
            actions.accepted.connect(self._submit)
            actions.rejected.connect(self.reject)

            actions.button(QDialogButtonBox.Save).setObjectName("primaryButton")
            actions.button(QDialogButtonBox.Cancel).setObjectName("secondaryButton")

            layout.addWidget(actions)

        def _submit(self):
            username = self.username_input.text().strip()
            password = self.password_input.text()
            confirmation = self.confirm_password_input.text()

            if not username or not password or not confirmation:
                QMessageBox.warning(self, "Validation", "Tous les champs sont obligatoires.")
                return

            if password != confirmation:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "La confirmation du mot de passe ne correspond pas.",
                )
                return

            try:
                self.database.create_access_credentials(username, password)
            except ValueError as error:
                QMessageBox.warning(self, "Validation", str(error))
                return

            self.created_username = username
            self.accept()


    class LoginDialog(QDialog):
        def __init__(self, database, parent=None):
            super().__init__(parent)
            self.database = database
            self.authenticated_username = ""

            self.setWindowTitle("Connexion")
            self.setModal(True)
            self.setMinimumWidth(440)

            self.username_input = QLineEdit()
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)

            self._build_ui()
            self.username_input.setText(self.database.get_access_username())
            self.password_input.setFocus()

        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 20)
            layout.setSpacing(18)

            title = QLabel("Connexion")
            title.setObjectName("dialogTitle")
            subtitle = QLabel("Saisissez le nom d'utilisateur et le mot de passe du poste.")
            subtitle.setObjectName("dialogSubtitle")

            layout.addWidget(title)
            layout.addWidget(subtitle)

            form_card = QFrame()
            form_card.setObjectName("panelCard")
            form_layout = QFormLayout(form_card)
            form_layout.setContentsMargins(20, 20, 20, 20)
            form_layout.setHorizontalSpacing(16)
            form_layout.setVerticalSpacing(14)
            form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            form_layout.addRow("Nom d'utilisateur", self.username_input)
            form_layout.addRow("Mot de passe", self.password_input)

            layout.addWidget(form_card)

            actions = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            actions.button(QDialogButtonBox.Ok).setText("Se connecter")
            actions.button(QDialogButtonBox.Cancel).setText("Quitter")
            actions.accepted.connect(self._submit)
            actions.rejected.connect(self.reject)

            actions.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
            actions.button(QDialogButtonBox.Cancel).setObjectName("secondaryButton")

            layout.addWidget(actions)

        def _submit(self):
            username = self.username_input.text().strip()
            password = self.password_input.text()

            if not username or not password:
                QMessageBox.warning(
                    self,
                    "Connexion",
                    "Le nom d'utilisateur et le mot de passe sont obligatoires.",
                )
                return

            if not self.database.verify_access_credentials(username, password):
                QMessageBox.critical(
                    self,
                    "Connexion",
                    "Nom d'utilisateur ou mot de passe incorrect.",
                )
                self.password_input.clear()
                self.password_input.setFocus()
                return

            self.authenticated_username = username
            self.accept()

