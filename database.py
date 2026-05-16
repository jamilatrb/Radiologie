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

    def restore_db(self, backup_path):
        backup_path = Path(backup_path)
        if not backup_path.is_absolute():
            backup_path = self.backup_dir / backup_path

        if not backup_path.exists():
            raise FileNotFoundError(f"Sauvegarde introuvable : {backup_path}")

        source_connection = sqlite3.connect(backup_path)
        target_connection = sqlite3.connect(self.db_path)
        try:
            source_connection.backup(target_connection)
            target_connection.commit()
        finally:
            target_connection.close()
            source_connection.close()

        self._initialize_database()
        return self.db_path

    def _initialize_database(self):
        with self._connect() as connection:
            self._create_table(connection)
            self._create_access_table(connection)
            self._migrate_table_if_needed(connection)
            self._normalize_existing_data(connection)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_patients_date_bon ON patients(date_bon)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_patients_schedule ON patients(date_rdv, heure_rdv)"
            )
            connection.commit()

    def _create_table(self, connection):
        connection.execute(CREATE_PATIENTS_TABLE_SQL)

    def _create_access_table(self, connection):
        connection.execute(CREATE_ACCESS_TABLE_SQL)

    def _get_existing_columns(self, connection):
        rows = connection.execute("PRAGMA table_info(patients)").fetchall()
        return [row["name"] for row in rows]

    def _migrate_table_if_needed(self, connection):
        existing_columns = self._get_existing_columns(connection)
        if list(existing_columns) == list(PATIENT_COLUMNS):
            return

        self._rebuild_patients_table(connection, existing_columns)

    def _rebuild_patients_table(self, connection, existing_columns):
        connection.execute("ALTER TABLE patients RENAME TO patients_legacy")
        connection.execute(CREATE_PATIENTS_TABLE_SQL)

        legacy_columns = set(existing_columns)
        select_parts = [
            "id" if "id" in legacy_columns else "NULL AS id",
            "nom" if "nom" in legacy_columns else "'' AS nom",
            "prenom" if "prenom" in legacy_columns else "'' AS prenom",
            "cin" if "cin" in legacy_columns else "'' AS cin",
            "telephone" if "telephone" in legacy_columns else "'' AS telephone",
            "type_examen" if "type_examen" in legacy_columns else "'' AS type_examen",
            "date_bon" if "date_bon" in legacy_columns else "'' AS date_bon",
            "date_rdv" if "date_rdv" in legacy_columns else "'' AS date_rdv",
            "heure_rdv" if "heure_rdv" in legacy_columns else "'' AS heure_rdv",
            "etat" if "etat" in legacy_columns else "'' AS etat",
            (
                "date_validation_reelle"
                if "date_validation_reelle" in legacy_columns
                else "'' AS date_validation_reelle"
            ),
            "ip" if "ip" in legacy_columns else "'' AS ip",
        ]

        connection.execute(
            """
            INSERT INTO patients (
                id, nom, prenom, cin, telephone, type_examen, date_bon, date_rdv,
                heure_rdv, etat, date_validation_reelle, ip
            )
            SELECT
                {select_clause}
            FROM patients_legacy
            """.format(select_clause=", ".join(select_parts))
        )
        connection.execute("DROP TABLE patients_legacy")

    def _normalize_existing_data(self, connection):
        rows = connection.execute(
            "SELECT id, type_examen, date_bon, heure_rdv, date_validation_reelle, ip FROM patients"
        ).fetchall()

        for row in rows:
            canonical_exam = canonicalize_exam_type(row["type_examen"])
            canonical_date_bon = canonicalize_date_only(row["date_bon"])
            canonical_hour = canonicalize_hour(row["heure_rdv"])
            canonical_validation_date = canonicalize_date(row["date_validation_reelle"])
            canonical_ip_value = canonicalize_ip(row["ip"])
            if (
                canonical_exam != row["type_examen"]
                or canonical_date_bon != row["date_bon"]
                or canonical_hour != row["heure_rdv"]
                or canonical_validation_date != row["date_validation_reelle"]
                or canonical_ip_value != row["ip"]
            ):
                connection.execute(
                    """
                    UPDATE patients
                    SET type_examen = ?, date_bon = ?, heure_rdv = ?, date_validation_reelle = ?, ip = ?
                    WHERE id = ?
                    """,
                    (
                        canonical_exam,
                        canonical_date_bon,
                        canonical_hour,
                        canonical_validation_date,
                        canonical_ip_value,
                        row["id"],
                    ),
                )

    def _build_patient_filter_clause(
        self,
        search_term="",
        search_field="Tous",
        exam_filter="",
        status_filter="",
    ):
        where_clauses = []
        params = []
        search_term = search_term.strip()
        exam_filter = canonicalize_exam_type(exam_filter.strip())
        status_filter = status_filter.strip()

        if search_term:
            like_value = f"%{search_term}%"
            filters = {
                "Nom": "nom LIKE ?",
                "CIN": "cin LIKE ?",
                "Telephone": "telephone LIKE ?",
            }

            if search_field in filters:
                where_clauses.append(filters[search_field])
                params.append(like_value)
            else:
                where_clauses.append(
                    """
                    (
                        nom LIKE ?
                        OR cin LIKE ?
                        OR telephone LIKE ?
                    )
                    """
                )
                params.extend([like_value, like_value, like_value])

        if exam_filter:
            where_clauses.append("type_examen = ?")
            params.append(exam_filter)

        if status_filter:
            where_clauses.append("etat = ?")
            params.append(status_filter)

        return where_clauses, params

    def get_patients(
        self,
        search_term="",
        search_field="Tous",
        sort_order="ASC",
        exam_filter="",
        status_filter="",
        limit=None,
        offset=0,
    ):
        query = """
        SELECT id, nom, prenom, cin, telephone, type_examen, date_bon, date_rdv,
               heure_rdv, etat, date_validation_reelle, ip
        FROM patients
        """
        where_clauses, params = self._build_patient_filter_clause(
            search_term=search_term,
            search_field=search_field,
            exam_filter=exam_filter,
            status_filter=status_filter,
        )
        sort_order = sort_order.upper()

        if sort_order not in {"ASC", "DESC"}:
            sort_order = "ASC"

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += (
            f" ORDER BY CASE WHEN date_bon = '' THEN 1 ELSE 0 END ASC, "
            f"date_bon {sort_order}, date_rdv ASC, heure_rdv ASC, nom ASC, prenom ASC"
        )

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, int(limit)), max(0, int(offset))])

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [dict(row) for row in rows]

    def get_patient_stats(
        self,
        search_term="",
        search_field="Tous",
        exam_filter="",
        status_filter="",
    ):
        query = """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN etat = 'Valide' THEN 1 ELSE 0 END) AS valid_count,
            SUM(CASE WHEN etat = 'Non valide' THEN 1 ELSE 0 END) AS invalid_count
        FROM patients
        """
        where_clauses, params = self._build_patient_filter_clause(
            search_term=search_term,
            search_field=search_field,
            exam_filter=exam_filter,
            status_filter=status_filter,
        )

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()

        return {
            "total": int(row["total"] or 0),
            "valid_count": int(row["valid_count"] or 0),
            "invalid_count": int(row["invalid_count"] or 0),
        }

    def get_patient(self, patient_id):
        query = """
        SELECT id, nom, prenom, cin, telephone, type_examen, date_bon, date_rdv,
               heure_rdv, etat, date_validation_reelle, ip
        FROM patients
        WHERE id = ?
        """

        with self._connect() as connection:
            row = connection.execute(query, (patient_id,)).fetchone()

        return dict(row) if row else None

    def appointment_exists(self, date_rdv, heure_rdv, exclude_patient_id=None):
        query = """
        SELECT 1
        FROM patients
        WHERE date_rdv = ? AND heure_rdv = ?
        """
        params = [date_rdv, canonicalize_hour(heure_rdv)]

        if exclude_patient_id is not None:
            query += " AND id != ?"
            params.append(exclude_patient_id)

        query += " LIMIT 1"

        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()

        return row is not None

    def get_next_available_slot(self, start_at=None, exclude_patient_id=None):
        candidate = start_at or datetime.now()
        candidate = candidate.replace(second=0, microsecond=0)

        if start_at is None and (datetime.now().second > 0 or datetime.now().microsecond > 0):
            candidate += timedelta(minutes=1)

        while self.appointment_exists(
            candidate.strftime("%Y-%m-%d"),
            candidate.strftime("%H:%M"),
            exclude_patient_id=exclude_patient_id,
        ):
            candidate += timedelta(minutes=1)

        return candidate.strftime("%Y-%m-%d"), candidate.strftime("%H:%M")

    def has_access_credentials(self):
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM app_access WHERE id = 1").fetchone()
        return row is not None

    def get_access_username(self):
        with self._connect() as connection:
            row = connection.execute("SELECT username FROM app_access WHERE id = 1").fetchone()
        return row["username"] if row else ""

    def create_access_credentials(self, username, password):
        username = (username or "").strip()
        password = password or ""

        if not username:
            raise ValueError("Le nom d'utilisateur est obligatoire.")
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
            )

        salt = secrets.token_hex(16)
        password_hash = hash_password(password, salt)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO app_access (
                    id, username, password_hash, password_salt, updated_at
                ) VALUES (1, ?, ?, ?, ?)
                """,
                (username, password_hash, salt, updated_at),
            )
            connection.commit()

    def verify_access_credentials(self, username, password):
        username = (username or "").strip()
        password = password or ""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT username, password_hash, password_salt
                FROM app_access
                WHERE id = 1
                """
            ).fetchone()

        if row is None or row["username"] != username:
            return False

        computed_hash = hash_password(password, row["password_salt"])
        return hmac.compare_digest(computed_hash, row["password_hash"])

    def add_patient(self, patient):
        query = """
        INSERT INTO patients (
            nom, prenom, cin, telephone, type_examen, date_bon, date_rdv, heure_rdv,
            etat, date_validation_reelle, ip
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            patient["nom"],
            patient["prenom"],
            patient["cin"],
            patient["telephone"],
            canonicalize_exam_type(patient["type_examen"]),
            canonicalize_date_only(patient.get("date_bon", "")),
            patient["date_rdv"],
            canonicalize_hour(patient["heure_rdv"]),
            patient["etat"],
            canonicalize_date(patient.get("date_validation_reelle", "")),
            canonicalize_ip(patient.get("ip", "")),
        )

        with self._connect() as connection:
            connection.execute(query, values)
            connection.commit()
        self.auto_backup()

    def update_patient(self, patient_id, patient):
        query = """
        UPDATE patients
        SET nom = ?,
            prenom = ?,
            cin = ?,
            telephone = ?,
            type_examen = ?,
            date_bon = ?,
            date_rdv = ?,
            heure_rdv = ?,
            etat = ?,
            date_validation_reelle = ?,
            ip = ?
        WHERE id = ?
        """
        values = (
            patient["nom"],
            patient["prenom"],
            patient["cin"],
            patient["telephone"],
            canonicalize_exam_type(patient["type_examen"]),
            canonicalize_date_only(patient.get("date_bon", "")),
            patient["date_rdv"],
            canonicalize_hour(patient["heure_rdv"]),
            patient["etat"],
            canonicalize_date(patient.get("date_validation_reelle", "")),
            canonicalize_ip(patient.get("ip", "")),
            patient_id,
        )

        with self._connect() as connection:
            connection.execute(query, values)
            connection.commit()
        self.auto_backup()

    def delete_patient(self, patient_id):
        with self._connect() as connection:
            connection.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
            connection.commit()
        self.auto_backup()

    def delete_patients(self, patient_ids):
        patient_ids = [int(patient_id) for patient_id in patient_ids]
        if not patient_ids:
            return

        placeholders = ", ".join("?" for _ in patient_ids)
        query = f"DELETE FROM patients WHERE id IN ({placeholders})"

        with self._connect() as connection:
            connection.execute(query, patient_ids)
            connection.commit()
        self.auto_backup()
