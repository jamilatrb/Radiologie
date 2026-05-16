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


    class PatientDialog(QDialog):
        def __init__(self, database, parent=None, patient=None):
            super().__init__(parent)
            self.database = database
            self.patient = patient
            self.payload = None

            self.setWindowTitle("Modifier un patient" if patient else "Ajouter un patient")
            self.setModal(True)
            self.setMinimumWidth(540)

            self.nom_input = QLineEdit()
            self.prenom_input = QLineEdit()
            self.cin_input = QLineEdit()
            self.telephone_input = QLineEdit()
            self.type_examen_input = QComboBox()
            self.type_examen_input.addItems(EXAM_TYPES)
            self.date_bon_input = QLineEdit()
            self.date_bon_input.setPlaceholderText("YYYY-MM-DD")
            self.rdv_label = QLabel()
            self.rdv_label.setObjectName("appointmentBadge")
            self.validation_input = QLineEdit()
            self.validation_input.setPlaceholderText("YYYY-MM-DD")
            self.ip_input = QLineEdit()
            self.ip_input.setPlaceholderText("Obligatoire si l'état est Valide")
            self.etat_group = QButtonGroup(self)
            self.valide_radio = QRadioButton("Valide")
            self.non_valide_radio = QRadioButton("Non valide")
            self.etat_group.addButton(self.valide_radio)
            self.etat_group.addButton(self.non_valide_radio)
            self.valide_radio.toggled.connect(self._refresh_validation_ui)
            self.non_valide_radio.toggled.connect(self._refresh_validation_ui)

            self.date_rdv = ""
            self.heure_rdv = ""
            self.date_validation_reelle = ""

            self._build_ui()
            self._load_values()

        def _build_ui(self):
            layout = QVBoxLayout(self)
            layout.setContentsMargins(24, 24, 24, 20)
            layout.setSpacing(18)

            title = QLabel("Fiche patient")
            title.setObjectName("dialogTitle")
            subtitle = QLabel(
                "Saisissez les informations essentielles. Le rendez-vous est attribué automatiquement."
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

            form_layout.addRow("Nom *", self.nom_input)
            form_layout.addRow("Prénom *", self.prenom_input)
            form_layout.addRow("CIN *", self.cin_input)
            form_layout.addRow("Téléphone *", self.telephone_input)
            form_layout.addRow("Type d'examen *", self.type_examen_input)
            form_layout.addRow("Date du bon *", self.date_bon_input)
            form_layout.addRow("Rendez-vous", self.rdv_label)
            form_layout.addRow("Date validation finale", self.validation_input)
            form_layout.addRow("IP", self.ip_input)

            status_box = QWidget()
            status_layout = QHBoxLayout(status_box)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(16)
            status_layout.addWidget(self.valide_radio)
            status_layout.addWidget(self.non_valide_radio)
            status_layout.addStretch(1)
            form_layout.addRow("État *", status_box)

            layout.addWidget(form_card)

            actions = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            actions.button(QDialogButtonBox.Save).setText("Enregistrer")
            actions.button(QDialogButtonBox.Cancel).setText("Annuler")
            actions.accepted.connect(self._submit)
            actions.rejected.connect(self.reject)

            save_button = actions.button(QDialogButtonBox.Save)
            cancel_button = actions.button(QDialogButtonBox.Cancel)
            save_button.setObjectName("primaryButton")
            cancel_button.setObjectName("secondaryButton")

            layout.addWidget(actions)

        def _load_values(self):
            if self.patient:
                self.nom_input.setText(self.patient.get("nom", ""))
                self.prenom_input.setText(self.patient.get("prenom", ""))
                self.cin_input.setText(self.patient.get("cin", ""))
                self.telephone_input.setText(self.patient.get("telephone", ""))

                current_exam = self.patient.get("type_examen", "")
                index = self.type_examen_input.findText(current_exam)
                if index >= 0:
                    self.type_examen_input.setCurrentIndex(index)

                self.date_bon_input.setText(self.patient.get("date_bon", ""))
                self.date_rdv = self.patient.get("date_rdv", "")
                self.heure_rdv = self.patient.get("heure_rdv", "")
                self.date_validation_reelle = self.patient.get("date_validation_reelle", "")
            else:
                self.date_rdv, self.heure_rdv = self.database.get_next_available_slot()
                self.date_validation_reelle = ""

            if not self.date_rdv or not self.heure_rdv:
                self.date_rdv, self.heure_rdv = self.database.get_next_available_slot(
                    exclude_patient_id=self.patient["id"] if self.patient else None
                )

            self.rdv_label.setText(build_rdv_datetime(self.date_rdv, self.heure_rdv))

            self.validation_input.setText(
                format_validation_date(self.date_validation_reelle)
                if self.date_validation_reelle
                else ""
            )
            self.ip_input.setText(self.patient.get("ip", "") if self.patient else "")

            etat = self.patient.get("etat") if self.patient else STATUS_VALUES[1]
            if etat == STATUS_VALUES[1]:
                self.non_valide_radio.setChecked(True)
            else:
                self.valide_radio.setChecked(True)

            self._refresh_validation_ui()

        def _refresh_validation_ui(self):
            is_valid = self.valide_radio.isChecked()
            self.validation_input.setEnabled(is_valid)
            self.ip_input.setEnabled(is_valid)
            if is_valid:
                self.validation_input.setPlaceholderText("YYYY-MM-DD")
                self.ip_input.setPlaceholderText("Saisir la valeur IP")
            else:
                self.validation_input.setPlaceholderText("Disponible uniquement si l'état est Valide")
                self.ip_input.setPlaceholderText("Disponible uniquement si l'état est Valide")

        def _validate(self):
            etat = STATUS_VALUES[1] if self.non_valide_radio.isChecked() else STATUS_VALUES[0]
            date_validation_reelle = self.validation_input.text().strip()
            ip_value = self.ip_input.text().strip()

            if etat == STATUS_VALUES[1]:
                date_validation_reelle = ""
                ip_value = ""
            elif not date_validation_reelle:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "La date de validation finale est obligatoire quand l'état est Valide.",
                )
                return None
            elif not ip_value:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Le champ IP est obligatoire quand l'état est Valide.",
                )
                return None

            data = {
                "nom": self.nom_input.text().strip(),
                "prenom": self.prenom_input.text().strip(),
                "cin": self.cin_input.text().strip(),
                "telephone": self.telephone_input.text().strip(),
                "type_examen": self.type_examen_input.currentText().strip(),
                "date_bon": self.date_bon_input.text().strip(),
                "date_rdv": self.date_rdv,
                "heure_rdv": self.heure_rdv,
                "etat": etat,
                "date_validation_reelle": date_validation_reelle,
                "ip": ip_value,
            }

            required_values = [
                data["nom"],
                data["prenom"],
                data["cin"],
                data["telephone"],
                data["type_examen"],
                data["date_bon"],
                data["date_rdv"],
                data["heure_rdv"],
                data["etat"],
            ]
            if not all(required_values):
                QMessageBox.warning(self, "Validation", "Tous les champs obligatoires doivent être remplis.")
                return None

            if not re.fullmatch(r"[0-9+\s-]+", data["telephone"]):
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Le téléphone doit contenir uniquement des chiffres, espaces, + ou -.",
                )
                return None

            digits = re.sub(r"\D", "", data["telephone"])
            if len(digits) < 8 or len(digits) > 15:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Le numéro de téléphone doit contenir entre 8 et 15 chiffres.",
                )
                return None

            try:
                datetime.strptime(data["date_bon"], "%Y-%m-%d")
                datetime.strptime(data["date_rdv"], "%Y-%m-%d")
                datetime.strptime(data["heure_rdv"], "%H:%M")
                if data["date_validation_reelle"]:
                    datetime.strptime(data["date_validation_reelle"], "%Y-%m-%d")
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "La date du bon, la date/heure du rendez-vous ou la date de validation finale est invalide.",
                )
                return None

            return data

        def _submit(self):
            payload = self._validate()
            if payload is None:
                return

            self.payload = payload
            self.accept()

