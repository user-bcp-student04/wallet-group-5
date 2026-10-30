import sqlite3
import threading


PROCESSING = "PROCESSING"
SESSION_COLUMNS = (
    "id,registration,verification,activation,document_type,document_hash,document_enc,scenario,"
    "otp_hash,otp_expires_at,otp_issues,otp_failures,last_failure_at,"
    "kyc_id,wallet_id,provider_status,created_at,updated_at"
)


class AccountExists(Exception):
    """El documento ya tiene una cuenta (o una reserva en curso); no se expone su estado."""


class OnboardingStore:
    """Conexión SQLite compartida entre hilos con un único candado para las escrituras de onboarding."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.lock = threading.RLock()
        with self.lock:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS onboarding_sessions ("
                "id TEXT PRIMARY KEY, "
                "registration TEXT NOT NULL, "
                "verification TEXT NOT NULL, "
                "activation TEXT NOT NULL, "
                "document_type TEXT, "
                "document_hash TEXT, "
                "document_enc TEXT, "
                "scenario TEXT NOT NULL, "
                "otp_hash TEXT, "
                "otp_expires_at TEXT, "
                "otp_issues INTEGER NOT NULL DEFAULT 0, "
                "otp_failures INTEGER NOT NULL DEFAULT 0, "
                "last_failure_at TEXT, "
                "kyc_id TEXT UNIQUE, "
                "wallet_id TEXT, "
                "provider_status TEXT, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS onboarding_accounts ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id TEXT NOT NULL, "
                "document_type TEXT NOT NULL, "
                "document_hash TEXT NOT NULL, "
                "kyc_id TEXT UNIQUE, "
                "wallet_id TEXT, "
                "status TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "UNIQUE(document_type, document_hash))"
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS onboarding_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "onboarding_id TEXT NOT NULL, "
                "event TEXT NOT NULL, "
                "step TEXT NOT NULL, "
                "outcome TEXT NOT NULL, "
                "occurred_at TEXT NOT NULL, "
                "UNIQUE(onboarding_id, event, step))"
            )
            self.connection.commit()


class SessionRepository:
    def __init__(self, store: OnboardingStore) -> None:
        self.connection = store.connection
        self.lock = store.lock

    def create(self, onboarding_id: str, now: str) -> None:
        self._execute(
            "INSERT INTO onboarding_sessions(id,registration,verification,activation,scenario,created_at,updated_at) "
            "VALUES (?, 'STARTED', 'PENDING', 'INACTIVE', 'APPROVED', ?, ?)",
            (onboarding_id, now, now),
        )

    def get(self, onboarding_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.connection.execute(
                f"SELECT {SESSION_COLUMNS} FROM onboarding_sessions WHERE id=?", (onboarding_id,)
            ).fetchone()

    def save_document(
        self, onboarding_id: str, document_type: str, document_hash: str, document_enc: str, scenario: str, now: str
    ) -> bool:
        return self._execute(
            "UPDATE onboarding_sessions SET registration='DOCUMENT_VALID', verification='PENDING', "
            "document_type=?, document_hash=?, document_enc=?, scenario=?, otp_hash=NULL, otp_expires_at=NULL, "
            "updated_at=? WHERE id=? AND registration IN ('STARTED','DOCUMENT_VALID') AND verification!='VERIFIED'",
            (document_type, document_hash, document_enc, scenario, now, onboarding_id),
        )

    def set_challenge(self, onboarding_id: str, otp_hash: str, expires_at: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_sessions SET verification='CHALLENGED', otp_hash=?, otp_expires_at=?, "
            "otp_issues=otp_issues+1, updated_at=? WHERE id=?",
            (otp_hash, expires_at, now, onboarding_id),
        )

    def record_failure(self, onboarding_id: str, window_start: str, now: str) -> None:
        # Los fallos anteriores a la ventana ya no cuentan: el contador vuelve a empezar.
        self._execute(
            "UPDATE onboarding_sessions SET "
            "otp_failures=CASE WHEN last_failure_at IS NOT NULL AND last_failure_at>=? THEN otp_failures+1 ELSE 1 END, "
            "last_failure_at=?, updated_at=? WHERE id=?",
            (window_start, now, now, onboarding_id),
        )

    def failures_in_window(self, onboarding_id: str, document_hash: str | None, window_start: str) -> tuple[int, str | None]:
        """Mayor número de fallos recientes del onboarding o de su documento y la marca del último."""
        with self.lock:
            own = self.connection.execute(
                "SELECT otp_failures, last_failure_at FROM onboarding_sessions WHERE id=? AND last_failure_at>=?",
                (onboarding_id, window_start),
            ).fetchone()
            same_document = (
                self.connection.execute(
                    "SELECT COALESCE(SUM(otp_failures),0) AS failures, MAX(last_failure_at) AS latest "
                    "FROM onboarding_sessions WHERE document_hash=? AND last_failure_at>=?",
                    (document_hash, window_start),
                ).fetchone()
                if document_hash
                else None
            )
        counts = [(own["otp_failures"], own["last_failure_at"])] if own else []
        if same_document and same_document["latest"]:
            counts.append((same_document["failures"], same_document["latest"]))
        if not counts:
            return 0, None
        return max(count for count, _ in counts), max(latest for _, latest in counts)

    def mark_verified(self, onboarding_id: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_sessions SET verification='VERIFIED', otp_hash=NULL, otp_expires_at=NULL, "
            "otp_failures=0, last_failure_at=NULL, updated_at=? WHERE id=?",
            (now, onboarding_id),
        )

    def begin_persist(self, onboarding_id: str, now: str) -> bool:
        return self._execute(
            "UPDATE onboarding_sessions SET registration='PERSISTING', updated_at=? "
            "WHERE id=? AND registration='DOCUMENT_VALID' AND verification='VERIFIED'",
            (now, onboarding_id),
        )

    def revert_persist(self, onboarding_id: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_sessions SET registration='DOCUMENT_VALID', updated_at=? "
            "WHERE id=? AND registration='PERSISTING'",
            (now, onboarding_id),
        )

    def complete_persist(
        self, onboarding_id: str, kyc_id: str, wallet_id: str, provider_status: str, activation: str, now: str
    ) -> None:
        self._execute(
            "UPDATE onboarding_sessions SET registration='PERSISTED', kyc_id=?, wallet_id=?, provider_status=?, "
            "activation=?, updated_at=? WHERE id=?",
            (kyc_id, wallet_id, provider_status, activation, now, onboarding_id),
        )

    def update_provider_state(self, onboarding_id: str, provider_status: str, activation: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_sessions SET provider_status=?, activation=?, updated_at=? WHERE id=?",
            (provider_status, activation, now, onboarding_id),
        )

    def _execute(self, sql: str, parameters: tuple) -> bool:
        with self.lock:
            cursor = self.connection.execute(sql, parameters)
            self.connection.commit()
            return cursor.rowcount > 0


class AccountRepository:
    """Cuentas de onboarding; la restricción única sobre el documento protegido impide duplicados."""

    def __init__(self, store: OnboardingStore) -> None:
        self.connection = store.connection
        self.lock = store.lock

    def reserve(self, session_id: str, document_type: str, document_hash: str, now: str) -> int:
        with self.lock:
            try:
                cursor = self.connection.execute(
                    "INSERT INTO onboarding_accounts(session_id,document_type,document_hash,status,created_at,updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, document_type, document_hash, PROCESSING, now, now),
                )
                self.connection.commit()
            except sqlite3.IntegrityError:
                self.connection.rollback()
                raise AccountExists() from None
            if cursor.lastrowid is None:
                raise RuntimeError("Reserved account could not be identified")
            return cursor.lastrowid

    def complete(self, account_id: int, kyc_id: str, wallet_id: str, status: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_accounts SET kyc_id=?, wallet_id=?, status=?, updated_at=? WHERE id=?",
            (kyc_id, wallet_id, status, now, account_id),
        )

    def update_status(self, kyc_id: str, status: str, now: str) -> None:
        self._execute(
            "UPDATE onboarding_accounts SET status=?, updated_at=? WHERE kyc_id=?", (status, now, kyc_id)
        )

    def release(self, account_id: int) -> None:
        self._execute("DELETE FROM onboarding_accounts WHERE id=? AND status=?", (account_id, PROCESSING))

    def release_for_session(self, session_id: str) -> None:
        self._execute("DELETE FROM onboarding_accounts WHERE session_id=? AND status=?", (session_id, PROCESSING))

    def _execute(self, sql: str, parameters: tuple) -> None:
        with self.lock:
            self.connection.execute(sql, parameters)
            self.connection.commit()


class EventRepository:
    """Eventos de analítica: solo identificador técnico, nombre, paso y marca de tiempo."""

    def __init__(self, store: OnboardingStore) -> None:
        self.connection = store.connection
        self.lock = store.lock

    def record(self, onboarding_id: str, event: str, step: str, outcome: str, occurred_at: str) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT OR IGNORE INTO onboarding_events(onboarding_id,event,step,outcome,occurred_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (onboarding_id, event, step, outcome, occurred_at),
            )
            self.connection.commit()

    def list_for(self, onboarding_id: str) -> list[sqlite3.Row]:
        with self.lock:
            return self.connection.execute(
                "SELECT onboarding_id,event,step,outcome,occurred_at FROM onboarding_events "
                "WHERE onboarding_id=? ORDER BY occurred_at,id",
                (onboarding_id,),
            ).fetchall()

    def list_lifecycle(self, events: tuple[str, ...]) -> list[sqlite3.Row]:
        placeholders = ",".join("?" for _ in events)
        with self.lock:
            return self.connection.execute(
                f"SELECT onboarding_id,event,step,outcome,occurred_at FROM onboarding_events "
                f"WHERE event IN ({placeholders}) ORDER BY occurred_at,id",
                events,
            ).fetchall()
