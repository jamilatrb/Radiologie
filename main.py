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


    class MainWindow(QMainWindow):
        def __init__(self, database, current_username):
            super().__init__()
            self.database = database
            self.current_username = current_username

            self.setWindowTitle(APP_TITLE)
            self.setMinimumSize(1280, 760)
            self.resize(1400, 860)

            self.search_input = QLineEdit()
            self.search_field_combo = QComboBox()
            self.exam_filter_combo = QComboBox()
            self.page_size_combo = QComboBox()
            self.prev_page_button = QPushButton("Precedent")
            self.next_page_button = QPushButton("Suivant")
            self.page_label = QLabel("Page 1 / 1")
            self.status_all_radio = QRadioButton("Tous")
            self.status_valide_radio = QRadioButton("Valide")
            self.status_non_valide_radio = QRadioButton("Non valide")
            self.status_filter_group = QButtonGroup(self)
            self.total_card = StatCard("Rendez-vous trouvés", "primary")
            self.valid_card = StatCard("Valides", "success")
            self.invalid_card = StatCard("Non valides", "danger")
            self.status_label = QLabel("Prêt.")
            self.status_label.setObjectName("footerStatus")
            self.table = QTableWidget(0, 12)
            self.select_all_checkbox = QCheckBox("Tout sélectionner")
            self.bulk_delete_button = QPushButton("Supprimer la sélection")
            self._updating_checkboxes = False
            self.current_page = 1
            self.page_size = 5
            self.total_pages = 1

            self._setup_window()
            self.load_patients("Interface chargée.")

        def _setup_window(self):
            self.setFont(QFont("Segoe UI", 10))

            central = QWidget()
            self.setCentralWidget(central)

            root_layout = QVBoxLayout(central)
            root_layout.setContentsMargins(16, 12, 16, 12)
            root_layout.setSpacing(10)

            hero_card = self._build_hero_card()
            filters_card = self._build_filters_card()
            table_card = self._build_table_card()

            root_layout.addWidget(hero_card)
            root_layout.addWidget(filters_card)
            root_layout.addWidget(table_card, 1)
            root_layout.addWidget(self.status_label)

            root_layout.setStretch(0, 0)
            root_layout.setStretch(1, 0)
            root_layout.setStretch(2, 1)

            self._apply_styles()

        def _build_hero_card(self):
            hero = QFrame()
            hero.setObjectName("heroCard")
            hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            hero.setMaximumHeight(104)
            self._apply_shadow(hero, blur=18, offset_y=6)

            hero_layout = QHBoxLayout(hero)
            hero_layout.setContentsMargins(18, 10, 18, 10)
            hero_layout.setSpacing(10)

            text_column = QVBoxLayout()
            text_column.setSpacing(3)

            title = QLabel(APP_TITLE)
            title.setObjectName("heroTitle")
            subtitle = QLabel(
                f"Utilisateur connecté : {self.current_username}"
            )
            subtitle.setObjectName("heroSubtitle")

            button_row = QHBoxLayout()
            button_row.setSpacing(5)

            add_button = QPushButton("Ajouter un patient")
            add_button.setObjectName("heroPrimaryButton")
            add_button.clicked.connect(self.open_add_dialog)

            refresh_button = QPushButton("Actualiser")
            refresh_button.setObjectName("heroSecondaryButton")
            refresh_button.clicked.connect(lambda: self.load_patients("Liste actualisée."))

            button_row.addWidget(add_button)
            button_row.addWidget(refresh_button)
            button_row.addStretch(1)

            text_column.addWidget(title)
            text_column.addWidget(subtitle)
            text_column.addLayout(button_row)
            text_column.addStretch(1)

            stats_row = QHBoxLayout()
            stats_row.setSpacing(7)
            stats_row.addWidget(self.total_card)
            stats_row.addWidget(self.valid_card)
            stats_row.addWidget(self.invalid_card)

            hero_layout.addLayout(text_column, 2)
            hero_layout.addLayout(stats_row, 2)

            return hero

        def _build_filters_card(self):
            card = QFrame()
            card.setObjectName("panelCard")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            card.setMaximumHeight(146)
            self._apply_shadow(card, blur=12, offset_y=4)

            wrapper = QVBoxLayout(card)
            wrapper.setContentsMargins(16, 12, 16, 12)
            wrapper.setSpacing(10)

            header = QLabel("Filtres et recherche")
            header.setObjectName("sectionTitle")

            self.search_input.setPlaceholderText("Rechercher un patient...")
            self.search_input.setMinimumWidth(280)
            self.search_input.setMaximumWidth(420)
            self.search_field_combo.setMinimumWidth(160)
            self.search_field_combo.setMaximumWidth(200)
            self.exam_filter_combo.setMinimumWidth(160)
            self.exam_filter_combo.setMaximumWidth(200)
            self.search_input.textChanged.connect(
                lambda _text: self._go_to_first_page("Recherche mise à jour.")
            )

            for label, value in SEARCH_FIELDS:
                self.search_field_combo.addItem(label, value)
            self.search_field_combo.currentIndexChanged.connect(
                lambda _index: self._go_to_first_page("Critère de recherche mis à jour.")
            )

            self.exam_filter_combo.addItem(ALL_EXAMS_LABEL, "")
            for exam in EXAM_TYPES:
                self.exam_filter_combo.addItem(exam, exam)
            self.exam_filter_combo.currentIndexChanged.connect(
                lambda _index: self._go_to_first_page("Filtre du type d'examen mis à jour.")
            )

            self.status_filter_group.addButton(self.status_all_radio)
            self.status_filter_group.addButton(self.status_valide_radio)
            self.status_filter_group.addButton(self.status_non_valide_radio)
            self.status_all_radio.setChecked(True)
            self.status_all_radio.toggled.connect(self._status_filter_changed)
            self.status_valide_radio.toggled.connect(self._status_filter_changed)
            self.status_non_valide_radio.toggled.connect(self._status_filter_changed)

            clear_button = QPushButton("Réinitialiser")
            clear_button.setObjectName("ghostButton")
            clear_button.clicked.connect(self.reset_filters)
            clear_button.setMinimumWidth(130)

            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            header_row.setSpacing(8)
            header_row.addWidget(header)
            header_row.addStretch(1)
            header_row.addWidget(clear_button)

            wrapper.addLayout(header_row)

            layout = QGridLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setHorizontalSpacing(10)
            layout.setVerticalSpacing(8)
            layout.setColumnStretch(1, 1)
            layout.setColumnStretch(3, 2)
            layout.setColumnStretch(5, 1)

            layout.addWidget(QLabel("Champ"), 1, 0)
            layout.addWidget(self.search_field_combo, 1, 1)
            layout.addWidget(QLabel("Recherche"), 1, 2)
            layout.addWidget(self.search_input, 1, 3, 1, 3)

            layout.addWidget(QLabel("Type d'examen"), 2, 0)
            layout.addWidget(self.exam_filter_combo, 2, 1)

            status_box = QWidget()
            status_layout = QHBoxLayout(status_box)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(14)
            status_layout.addWidget(self.status_all_radio)
            status_layout.addWidget(self.status_valide_radio)
            status_layout.addWidget(self.status_non_valide_radio)
            status_layout.addStretch(1)

            layout.addWidget(QLabel("État"), 2, 2)
            layout.addWidget(status_box, 2, 3, 1, 3)

            wrapper.addLayout(layout)
            return card

        def _build_table_card(self):
            card = QFrame()
            card.setObjectName("tableCard")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._apply_shadow(card, blur=12, offset_y=4)

            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 16, 16, 14)
            layout.setSpacing(8)

            title_row = QHBoxLayout()
            title = QLabel("Liste des rendez-vous")
            title.setObjectName("sectionTitle")
            helper = QLabel("Double-cliquez une ligne pour modifier rapidement.")
            helper.setObjectName("tableHelper")
            self.select_all_checkbox.toggled.connect(self.toggle_all_rows)
            self.bulk_delete_button.setObjectName("dangerGhostButton")
            self.bulk_delete_button.clicked.connect(self.delete_checked_patients)
            self.bulk_delete_button.setEnabled(False)
            title_row.addWidget(title)
            title_row.addStretch(1)
            title_row.addWidget(self.select_all_checkbox)
            title_row.addWidget(self.bulk_delete_button)
            title_row.addWidget(helper)

            layout.addLayout(title_row)

            self.table.setHorizontalHeaderLabels(
                [
                    "Sélection",
                    "Date et heure",
                    "Date du bon",
                    "Nom",
                    "Prénom",
                    "CIN",
                    "Téléphone",
                    "Type d'examen",
                    "État",
                    "Date validation",
                    "IP",
                    "Actions",
                ]
            )
            self.table.setAlternatingRowColors(True)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setSelectionMode(QTableWidget.NoSelection)
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setShowGrid(False)
            self.table.setWordWrap(False)
            self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.table.setMinimumHeight(250)
            self.table.setFocusPolicy(Qt.NoFocus)
            self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
            self.table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
            self.table.verticalHeader().setVisible(False)
            self.table.horizontalHeader().setHighlightSections(False)
            self.table.horizontalHeader().setStretchLastSection(False)
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(11, QHeaderView.Fixed)
            self.table.setColumnWidth(0, 78)
            self.table.setColumnWidth(11, 240)
            self.table.cellDoubleClicked.connect(self._handle_double_click)
            self.table.itemChanged.connect(self._handle_item_changed)

            layout.addWidget(self.table, 1)

            pagination_row = QHBoxLayout()
            pagination_row.setContentsMargins(0, 2, 0, 0)
            pagination_row.setSpacing(8)

            lines_label = QLabel("Lignes par page")
            lines_label.setObjectName("tableHelper")
            self.page_label.setObjectName("tableHelper")

            self.page_size_combo.addItem("5", 5)
            self.page_size_combo.addItem("10", 10)
            self.page_size_combo.addItem("15", 15)
            self.page_size_combo.addItem("20", 20)
            self.page_size_combo.addItem("30", 30)
            self.page_size_combo.setCurrentIndex(0)
            self.page_size_combo.currentIndexChanged.connect(self._change_page_size)

            self.prev_page_button.setObjectName("ghostButton")
            self.next_page_button.setObjectName("ghostButton")
            self.prev_page_button.clicked.connect(self.go_to_previous_page)
            self.next_page_button.clicked.connect(self.go_to_next_page)

            pagination_row.addWidget(lines_label)
            pagination_row.addWidget(self.page_size_combo)
            pagination_row.addStretch(1)
            pagination_row.addWidget(self.page_label)
            pagination_row.addWidget(self.prev_page_button)
            pagination_row.addWidget(self.next_page_button)

            layout.addLayout(pagination_row)
            return card

        def _apply_styles(self):
            self.setStyleSheet(
                """
                QMainWindow {
                    background: #f4f7fa;
                }
                QWidget {
                    color: #173247;
                }
                QFrame#heroCard {
                    background: white;
                    border: 1px solid #d8e2ea;
                    border-radius: 18px;
                }
                QLabel#heroTitle {
                    color: #12344d;
                    font-size: 20px;
                    font-weight: 700;
                }
                QLabel#heroSubtitle {
                    color: #5e7488;
                    font-size: 11px;
                }
                QFrame#panelCard, QFrame#tableCard {
                    background: white;
                    border: 1px solid #d8e2ea;
                    border-radius: 18px;
                }
                QFrame[cardRole="primary"] {
                    background: #ffffff;
                    border: 1px solid #d8e2ea;
                    border-left: 5px solid #1c6e8c;
                    border-radius: 14px;
                }
                QFrame[cardRole="success"] {
                    background: #ffffff;
                    border: 1px solid #d8e2ea;
                    border-left: 5px solid #2f855a;
                    border-radius: 14px;
                }
                QFrame[cardRole="danger"] {
                    background: #ffffff;
                    border: 1px solid #d8e2ea;
                    border-left: 5px solid #c05621;
                    border-radius: 14px;
                }
                QLabel#statValue {
                    font-size: 20px;
                    font-weight: 700;
                    color: #12344d;
                }
                QLabel#statTitle {
                    font-size: 11px;
                    color: #60788d;
                }
                QLabel#sectionTitle {
                    font-size: 15px;
                    font-weight: 700;
                    color: #11324a;
                }
                QLabel#tableHelper, QLabel#footerStatus, QLabel#dialogSubtitle {
                    color: #667b8d;
                    font-size: 11px;
                }
                QLabel#dialogTitle {
                    font-size: 20px;
                    font-weight: 700;
                    color: #12344d;
                }
                QLabel#appointmentBadge {
                    background: #f6fafc;
                    border: 1px solid #d8e2ea;
                    border-radius: 10px;
                    padding: 10px 12px;
                    font-weight: 600;
                    color: #1a4f6b;
                }
                QLineEdit, QComboBox {
                    background: #ffffff;
                    border: 1px solid #cbd6df;
                    border-radius: 8px;
                    padding: 5px 10px;
                    min-height: 16px;
                }
                QLineEdit:focus, QComboBox:focus {
                    background: white;
                    border: 2px solid #1c6e8c;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QComboBox QAbstractItemView {
                    background: white;
                    border: 1px solid #cbd6df;
                    selection-background-color: #e8f0f5;
                    selection-color: #12344d;
                    padding: 6px;
                }
                QPushButton#heroPrimaryButton {
                    background: #1c6e8c;
                    color: white;
                    border: 1px solid #1c6e8c;
                    border-radius: 10px;
                    padding: 9px 14px;
                    font-weight: 700;
                }
                QPushButton#heroPrimaryButton:hover {
                    background: #175e78;
                }
                QPushButton#heroSecondaryButton {
                    background: white;
                    color: #14324a;
                    border: 1px solid #cdd9e2;
                    border-radius: 10px;
                    padding: 9px 14px;
                    font-weight: 600;
                }
                QPushButton#heroSecondaryButton:hover {
                    background: #f6f9fb;
                }
                QPushButton#primaryButton {
                    background: #1c6e8c;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 12px 18px;
                    font-weight: 700;
                }
                QPushButton#primaryButton:hover {
                    background: #175e78;
                }
                QPushButton#secondaryButton {
                    background: #f6f9fb;
                    color: #14324a;
                    border: 1px solid #d7e2ea;
                    border-radius: 10px;
                    padding: 12px 18px;
                    font-weight: 600;
                }
                QPushButton#secondaryButton:hover {
                    background: #edf3f7;
                }
                QPushButton#ghostButton {
                    background: transparent;
                    color: #456176;
                    border: 1px solid #ccd8e2;
                    border-radius: 10px;
                    padding: 10px 16px;
                    font-weight: 600;
                }
                QPushButton#ghostButton:hover {
                    background: #f5f8fa;
                }
                QPushButton#dangerGhostButton {
                    background: #fff7f2;
                    color: #a55321;
                    border: 1px solid #f0d7c7;
                    border-radius: 10px;
                    padding: 10px 16px;
                    font-weight: 600;
                }
                QPushButton#dangerGhostButton:hover {
                    background: #fef0e7;
                }
                QPushButton#dangerGhostButton:disabled {
                    background: #f7f7f7;
                    color: #9aa8b5;
                    border: 1px solid #e0e6eb;
                }
                QRadioButton {
                    spacing: 8px;
                    color: #204761;
                    font-weight: 500;
                }
                QCheckBox {
                    color: #355066;
                    font-weight: 600;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border-radius: 5px;
                }
                QCheckBox::indicator:unchecked {
                    background: white;
                    border: 1px solid #9fb0bc;
                }
                QCheckBox::indicator:checked {
                    background: #1c6e8c;
                    border: 1px solid #1c6e8c;
                }
                QRadioButton::indicator {
                    width: 18px;
                    height: 18px;
                }
                QRadioButton::indicator:unchecked {
                    border: 2px solid #90a4b4;
                    border-radius: 9px;
                    background: white;
                }
                QRadioButton::indicator:checked {
                    border: 5px solid #1c6e8c;
                    border-radius: 9px;
                    background: white;
                }
                QTableWidget {
                    background: white;
                    border: 1px solid #d9e3ea;
                    border-radius: 12px;
                    alternate-background-color: #f8fbfd;
                    gridline-color: #ecf1f5;
                    selection-background-color: #eef5fa;
                    selection-color: #12344d;
                }
                QHeaderView::section {
                    background: #edf3f7;
                    color: #25485f;
                    border: none;
                    border-bottom: 1px solid #d4dee5;
                    padding: 13px 12px;
                    font-weight: 700;
                }
                QTableWidget::item {
                    padding: 8px 10px;
                    border-bottom: 1px solid #edf2f6;
                }
                QToolButton#editActionButton {
                    background: #edf6fb;
                    color: #0f5f84;
                    border: 1px solid #bfd8e8;
                    border-radius: 10px;
                    padding: 6px 10px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QToolButton#editActionButton:hover {
                    background: #e2f0f8;
                }
                QToolButton#deleteActionButton {
                    background: #fff2eb;
                    color: #b45309;
                    border: 1px solid #f2c5ab;
                    border-radius: 10px;
                    padding: 6px 10px;
                    font-weight: 700;
                    font-size: 11px;
                }
                QToolButton#deleteActionButton:hover {
                    background: #fee8da;
                }
                """
            )

        def _apply_shadow(self, widget, blur=12, offset_y=4):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(blur)
            shadow.setOffset(0, offset_y)
            shadow.setColor(QColor(16, 52, 77, 18))
            widget.setGraphicsEffect(shadow)

        def _status_filter_changed(self):
            self._go_to_first_page("Filtre d'état mis à jour.")

        def _current_status_filter(self):
            if self.status_valide_radio.isChecked():
                return STATUS_VALUES[0]
            if self.status_non_valide_radio.isChecked():
                return STATUS_VALUES[1]
            return ""

        def _create_table_item(self, value, alignment=Qt.AlignVCenter | Qt.AlignLeft):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(alignment)
            return item

        def _create_status_item(self, value):
            item = self._create_table_item(value, Qt.AlignCenter)
            if value == STATUS_VALUES[0]:
                item.setForeground(QColor("#0f766e"))
                item.setBackground(QColor("#ecfdf5"))
            else:
                item.setForeground(QColor("#b4233d"))
                item.setBackground(QColor("#fff1f3"))
            return item

        def _create_checkbox_item(self, patient_id):
            item = QTableWidgetItem()
            item.setData(Qt.UserRole, patient_id)
            item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
            )
            item.setCheckState(Qt.Unchecked)
            item.setTextAlignment(Qt.AlignCenter)
            return item

        def _create_actions_widget(self, patient_id):
            container = QWidget()
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout = QHBoxLayout(container)
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(6)

            edit_button = QToolButton()
            edit_button.setObjectName("editActionButton")
            edit_button.setText("✎ Modifier")
            edit_button.setMinimumWidth(92)
            edit_button.setMinimumHeight(28)
            edit_button.clicked.connect(lambda: self.open_edit_dialog(patient_id))

            delete_button = QToolButton()
            delete_button.setObjectName("deleteActionButton")
            delete_button.setText("🗑 Supprimer")
            delete_button.setMinimumWidth(100)
            delete_button.setMinimumHeight(28)
            delete_button.clicked.connect(lambda: self.delete_patient(patient_id))

            layout.addWidget(edit_button)
            layout.addWidget(delete_button)
            layout.addStretch(1)

            return container

        def _handle_double_click(self, row, _column):
            patient_id_item = self.table.item(row, 1)
            if patient_id_item is None:
                return
            patient_id = patient_id_item.data(Qt.UserRole)
            if patient_id is not None:
                self.open_edit_dialog(patient_id)

        def _set_footer_message(self, message):
            self.status_label.setText(message)

        def _current_filters(self):
            return {
                "search_term": self.search_input.text(),
                "search_field": self.search_field_combo.currentData(),
                "sort_order": "ASC",
                "exam_filter": self.exam_filter_combo.currentData(),
                "status_filter": self._current_status_filter(),
            }

        def _go_to_first_page(self, status_message=None):
            self.current_page = 1
            self.load_patients(status_message)

        def _change_page_size(self, _index):
            selected_size = self.page_size_combo.currentData()
            self.page_size = selected_size or self.page_size
            self.current_page = 1
            self.load_patients("Pagination mise à jour.")

        def go_to_previous_page(self):
            if self.current_page <= 1:
                return
            self.current_page -= 1
            self.load_patients("Page précédente chargée.")

        def go_to_next_page(self):
            if self.current_page >= self.total_pages:
                return
            self.current_page += 1
            self.load_patients("Page suivante chargée.")

        def reset_filters(self):
            self.search_input.clear()
            self.search_field_combo.setCurrentIndex(0)
            self.exam_filter_combo.setCurrentIndex(0)
            self.status_all_radio.setChecked(True)
            self.current_page = 1
            self.load_patients("Filtres réinitialisés.")

        def load_patients(self, status_message=None):
            filters = self._current_filters()
            stats = self.database.get_patient_stats(
                search_term=filters["search_term"],
                search_field=filters["search_field"],
                exam_filter=filters["exam_filter"],
                status_filter=filters["status_filter"],
            )
            total_count = stats["total"]
            self.page_size = self.page_size_combo.currentData() or self.page_size

            if total_count <= 0:
                self.current_page = 1
                self.total_pages = 1
            else:
                self.total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
                if self.current_page > self.total_pages:
                    self.current_page = self.total_pages

            offset = (self.current_page - 1) * self.page_size
            patients = self.database.get_patients(
                search_term=filters["search_term"],
                search_field=filters["search_field"],
                sort_order=filters["sort_order"],
                exam_filter=filters["exam_filter"],
                status_filter=filters["status_filter"],
                limit=self.page_size,
                offset=offset,
            )

            self._updating_checkboxes = True
            self.table.setRowCount(0)
            for patient in patients:
                row = self.table.rowCount()
                self.table.insertRow(row)

                self.table.setItem(row, 0, self._create_checkbox_item(patient["id"]))
                appointment_item = self._create_table_item(
                    build_rdv_datetime(patient["date_rdv"], patient["heure_rdv"]),
                    Qt.AlignCenter,
                )
                appointment_item.setData(Qt.UserRole, patient["id"])
                self.table.setItem(row, 1, appointment_item)
                self.table.setItem(
                    row, 2, self._create_table_item(patient.get("date_bon", ""), Qt.AlignCenter)
                )
                self.table.setItem(row, 3, self._create_table_item(patient["nom"]))
                self.table.setItem(row, 4, self._create_table_item(patient["prenom"]))
                self.table.setItem(row, 5, self._create_table_item(patient["cin"], Qt.AlignCenter))
                self.table.setItem(
                    row, 6, self._create_table_item(patient["telephone"], Qt.AlignCenter)
                )
                self.table.setItem(
                    row,
                    7,
                    self._create_table_item(patient["type_examen"], Qt.AlignCenter),
                )
                self.table.setItem(row, 8, self._create_status_item(patient["etat"]))
                self.table.setItem(
                    row,
                    9,
                    self._create_table_item(
                        format_validation_date(patient.get("date_validation_reelle", "")),
                        Qt.AlignCenter,
                    ),
                )
                self.table.setItem(
                    row,
                    10,
                    self._create_table_item(patient.get("ip", ""), Qt.AlignCenter),
                )
                self.table.setCellWidget(row, 11, self._create_actions_widget(patient["id"]))
                self.table.setRowHeight(row, 56)
            self._updating_checkboxes = False
            self._sync_selection_controls()

            self._update_stats(stats)
            self._update_pagination_controls(total_count, len(patients))

            if status_message:
                self._set_footer_message(status_message)
            elif total_count == 0:
                if (
                    filters["search_term"].strip()
                    or filters["exam_filter"]
                    or filters["status_filter"]
                ):
                    self._set_footer_message("Aucun résultat pour les filtres en cours.")
                else:
                    self._set_footer_message("Aucun rendez-vous enregistré pour le moment.")
            else:
                self._set_footer_message("Liste des rendez-vous chargée.")

        def _handle_item_changed(self, item):
            if self._updating_checkboxes or item.column() != 0:
                return
            self._sync_selection_controls()

        def _sync_selection_controls(self):
            total_rows = self.table.rowCount()
            checked_rows = len(self.get_checked_patient_ids())

            self.bulk_delete_button.setEnabled(checked_rows > 0)
            self.bulk_delete_button.setText(
                "Supprimer la sélection"
                if checked_rows == 0
                else f"Supprimer la sélection ({checked_rows})"
            )

            self.select_all_checkbox.blockSignals(True)
            self.select_all_checkbox.setEnabled(total_rows > 0)
            self.select_all_checkbox.setChecked(total_rows > 0 and checked_rows == total_rows)
            self.select_all_checkbox.blockSignals(False)

        def toggle_all_rows(self, checked):
            self._updating_checkboxes = True
            state = Qt.Checked if checked else Qt.Unchecked
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None:
                    item.setCheckState(state)
            self._updating_checkboxes = False
            self._sync_selection_controls()

        def get_checked_patient_ids(self):
            patient_ids = []
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.checkState() == Qt.Checked:
                    patient_ids.append(item.data(Qt.UserRole))
            return patient_ids

        def _update_pagination_controls(self, total_count, page_count):
            if total_count <= 0:
                self.page_label.setText("Page 0 / 0  •  0 resultat")
                self.prev_page_button.setEnabled(False)
                self.next_page_button.setEnabled(False)
                return

            start_row = ((self.current_page - 1) * self.page_size) + 1
            end_row = start_row + page_count - 1
            self.page_label.setText(
                f"Page {self.current_page} / {self.total_pages}  •  {start_row}-{end_row} sur {total_count}"
            )
            self.prev_page_button.setEnabled(self.current_page > 1)
            self.next_page_button.setEnabled(self.current_page < self.total_pages)

        def _update_stats(self, stats):
            self.total_card.set_value(stats["total"])
            self.valid_card.set_value(stats["valid_count"])
            self.invalid_card.set_value(stats["invalid_count"])

        def open_add_dialog(self):
            dialog = PatientDialog(self.database, parent=self)
            if dialog.exec_() != QDialog.Accepted or dialog.payload is None:
                return

            try:
                self.database.add_patient(dialog.payload)
            except sqlite3.IntegrityError:
                QMessageBox.critical(self, "Erreur", "Impossible d'enregistrer ce patient.")
                return

            self.load_patients("Patient ajouté avec succès.")

        def open_edit_dialog(self, patient_id):
            patient = self.database.get_patient(patient_id)
            if not patient:
                QMessageBox.critical(self, "Erreur", "Le patient sélectionné est introuvable.")
                self.load_patients()
                return

            dialog = PatientDialog(self.database, parent=self, patient=patient)
            if dialog.exec_() != QDialog.Accepted or dialog.payload is None:
                return

            try:
                self.database.update_patient(patient_id, dialog.payload)
            except sqlite3.IntegrityError:
                QMessageBox.critical(self, "Erreur", "Impossible d'enregistrer ce patient.")
                return

            self.load_patients("Patient modifié avec succès.")

        def delete_patient(self, patient_id):
            patient = self.database.get_patient(patient_id)
            if not patient:
                QMessageBox.critical(self, "Erreur", "Le patient sélectionné est introuvable.")
                self.load_patients()
                return

            answer = QMessageBox.question(
                self,
                "Confirmation",
                f"Voulez-vous vraiment supprimer le patient {patient['nom']} {patient['prenom']} ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._set_footer_message("Suppression annulée.")
                return

            self.database.delete_patient(patient_id)
            self.load_patients("Patient supprimé avec succès.")

        def delete_checked_patients(self):
            patient_ids = self.get_checked_patient_ids()
            if not patient_ids:
                self._set_footer_message("Sélectionnez au moins un patient à supprimer.")
                return

            answer = QMessageBox.question(
                self,
                "Confirmation",
                f"Voulez-vous vraiment supprimer {len(patient_ids)} patient(s) sélectionné(s) ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._set_footer_message("Suppression multiple annulée.")
                return

            self.database.delete_patients(patient_ids)
            self.load_patients(f"{len(patient_ids)} patient(s) supprimé(s) avec succès.")


def main():
    if PYQT_IMPORT_ERROR is not None:
        show_blocking_message(
            APP_TITLE,
            "PyQt5 n'est pas installé sur ce poste.\n\n"
            "Installez-le avec :\n"
            "python -m pip install PyQt5\n\n"
            f"Détail technique : {PYQT_IMPORT_ERROR}",
        )
        return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    icon_path = APP_DIR / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    database = Database()

    if not database.has_access_credentials():
        setup_dialog = AccessSetupDialog(database)
        if icon_path.exists():
            setup_dialog.setWindowIcon(QIcon(str(icon_path)))
        if setup_dialog.exec_() != QDialog.Accepted:
            return

    login_dialog = LoginDialog(database)
    if icon_path.exists():
        login_dialog.setWindowIcon(QIcon(str(icon_path)))
    if login_dialog.exec_() != QDialog.Accepted:
        return

    window = MainWindow(database, login_dialog.authenticated_username)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
