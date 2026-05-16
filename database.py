import hashlib
import hmac
import re
import secrets
import sqlite3
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path


APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
DB_PATH = APP_DIR / "patients.db"
BACKUP_DIR_NAME = "backup"
MAX_BACKUP_FILES = 10
PASSWORD_MIN_LENGTH = 6
EXAM_TYPE_ALIASES = {
    "echographie": "Échographie",
    "tdm / scanner": "TDM / Scanner",
    "tdm/scanner": "TDM / Scanner",
    "echo mammaire": "Écho mammaire",
    "echo-mammaire": "Écho mammaire",
    "irm": "IRM",
}
PATIENT_COLUMNS = (
    "id",
    "nom",
    "prenom",
    "cin",
    "telephone",
    "type_examen",
    "date_bon",
    "date_rdv",
    "heure_rdv",
    "etat",
    "date_validation_reelle",
    "ip",
)


def normalize_text(value):
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def canonicalize_exam_type(value):
    stripped = (value or "").strip()
    if not stripped:
        return stripped
    return EXAM_TYPE_ALIASES.get(normalize_text(stripped), stripped)


def canonicalize_hour(value):
    stripped = (value or "").strip()
    if not stripped:
        return "00:00"

    try:
        return datetime.strptime(stripped, "%H:%M").strftime("%H:%M")
    except ValueError:
        return "00:00"


def canonicalize_date_only(value):
    stripped = (value or "").strip()
    if not stripped:
        return ""

    try:
        return datetime.strptime(stripped, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def canonicalize_date(value):
    stripped = (value or "").strip()
    if not stripped:
        return ""

    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(stripped, pattern)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return ""


def canonicalize_ip(value):
    return (value or "").strip()


def hash_password(password, salt):
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    )
    return derived_key.hex()


CREATE_PATIENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    cin TEXT NOT NULL,
    telephone TEXT NOT NULL,
    type_examen TEXT NOT NULL,
    date_bon TEXT NOT NULL,
    date_rdv TEXT NOT NULL,
    heure_rdv TEXT NOT NULL,
    etat TEXT NOT NULL,
    date_validation_reelle TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT ''
)
"""

CREATE_ACCESS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_access (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.resolve().parent / BACKUP_DIR_NAME
        self.last_backup_path = None
        self.last_backup_error = ""
        self._initialize_database()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_backup_dir(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        return self.backup_dir

    def _backup_glob_pattern(self):
        return f"{self.db_path.stem}_backup_*.db"

    def list_backups(self):
        self._ensure_backup_dir()
        return sorted(
            self.backup_dir.glob(self._backup_glob_pattern()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _build_backup_path(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_name = f"{self.db_path.stem}_backup_{timestamp}"
        candidate = self.backup_dir / f"{base_name}.db"
        counter = 1

        while candidate.exists():
            candidate = self.backup_dir / f"{base_name}_{counter:02d}.db"
            counter += 1

        return candidate

    def _prune_old_backups(self, keep=MAX_BACKUP_FILES):
        for backup_path in self.list_backups()[keep:]:
            try:
                backup_path.unlink()
            except OSError:
                continue

    def auto_backup(self):
        self.last_backup_path = None
        self.last_backup_error = ""

        try:
            if not self.db_path.exists():
                return None

            self._ensure_backup_dir()
            backup_path = self._build_backup_path()

            source_connection = sqlite3.connect(self.db_path)
            backup_connection = sqlite3.connect(backup_path)
            try:
                source_connection.backup(backup_connection)
                backup_connection.commit()
            finally:
                backup_connection.close()
                source_connection.close()

            self._prune_old_backups()
            self.last_backup_path = backup_path
            return backup_path
        except (sqlite3.Error, OSError) as error:
            self.last_backup_error = str(error)
            return None
