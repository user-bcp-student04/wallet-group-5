import hmac
import math
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.data_protection import DocumentProtector
from app.onboarding_repositories import AccountExists, AccountRepository, EventRepository, SessionRepository
from app.two_factor import (
    FAILURE_WINDOW_SECONDS,
    MAX_CHALLENGES_PER_ONBOARDING,
    MAX_FAILED_ATTEMPTS,
    OTP_VALIDITY_SECONDS,
    OtpChannel,
    TwoFactorFailed,
    TwoFactorLimit,
    TwoFactorLocked,
    TwoFactorUnavailable,
)
from app.wallet_provider import ProviderError, ProviderUnavailable, WalletProvider, WalletResult


ACTIVE = "ACTIVE"
PENDING = "PENDING"
REJECTED = "REJECTED"
INACTIVE = "INACTIVE"

DOCUMENT_STEP = "DOCUMENT"
TWO_FACTOR_STEP = "TWO_FACTOR"
PERSISTENCE_STEP = "PERSISTENCE"
ACTIVATION_STEP = "ACTIVATION"
EXIT_STEP = "EXIT"

EVENT_STARTED = "onboarding.started"
EVENT_STEP_COMPLETED = "onboarding.step_completed"
EVENT_CLOSED = "onboarding.closed"
START_STEP = "START"
NO_STEP = "-"

PERSIST_STALE_SECONDS = 30
ONBOARDING_ID_BYTES = 16


class OnboardingNotFound(Exception):
    """No existe un onboarding con ese identificador."""


class InvalidStep(Exception):
    """La acción no corresponde al estado actual del onboarding."""


class TwoFactorRequired(Exception):
    """El alta se solicitó sin el segundo factor verificado."""


class RegistrationUnavailable(Exception):
    """El registro no puede continuar; no se revela el motivo (p. ej. una cuenta existente)."""


@dataclass(frozen=True)
class OnboardingView:
    onboarding_id: str
    step: str
    registration: str
    verification: str
    activation: str
    provider_status: str | None
    wallet: WalletResult | None
    two_factor_available: bool

    # El punto de entrada a pagos solo existe con la activación registrada y la wallet confirmada.
    @property
    def payments_entry_available(self) -> bool:
        return self.activation == ACTIVE and self.wallet is not None


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds")


class OnboardingService:
    def __init__(
        self,
        sessions: SessionRepository,
        accounts: AccountRepository,
        events: EventRepository,
        provider: WalletProvider,
        protector: DocumentProtector,
        otp_channel: OtpChannel,
        clock: Callable[[], datetime] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self.sessions = sessions
        self.accounts = accounts
        self.events = events
        self.provider = provider
        self.protector = protector
        self.otp_channel = otp_channel
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.new_id = new_id or (lambda: secrets.token_urlsafe(ONBOARDING_ID_BYTES))

    def start(self) -> OnboardingView:
        onboarding_id = self.new_id()
        now = self._now()
        self.sessions.create(onboarding_id, now)
        self.events.record(onboarding_id, EVENT_STARTED, START_STEP, NO_STEP, now)
        return self._view(self._require(onboarding_id), None)

    def get(self, onboarding_id: str) -> OnboardingView:
        return self._synchronized(self._recovered(self._require(onboarding_id)))

    def submit_document(self, onboarding_id: str, document_type: str, document: str, scenario: str) -> OnboardingView:
        row = self._require(onboarding_id)
        now = self._now()
        saved = self.sessions.save_document(
            onboarding_id,
            document_type,
            self.protector.fingerprint(document_type, document),
            self.protector.encrypt(document),
            scenario,
            now,
        )
        if not saved:
            raise InvalidStep(row["registration"])
        self._step_completed(onboarding_id, DOCUMENT_STEP)
        if self.otp_channel.available():
            self._issue_challenge(self._require(onboarding_id))
        return self._view(self._require(onboarding_id), None)

    def challenge(self, onboarding_id: str) -> OnboardingView:
        row = self._require(onboarding_id)
        if row["registration"] != "DOCUMENT_VALID" or row["verification"] == "VERIFIED":
            raise InvalidStep(row["registration"])
        self._issue_challenge(row)
        return self._view(self._require(onboarding_id), None)

    def verify(self, onboarding_id: str, code: str) -> OnboardingView:
        row = self._require(onboarding_id)
        if row["verification"] == "VERIFIED":
            return self._view(row, None)
        if row["registration"] != "DOCUMENT_VALID" or row["verification"] != "CHALLENGED":
            raise InvalidStep(row["verification"])
        if not self.otp_channel.available():
            raise TwoFactorUnavailable()

        self._ensure_not_locked(row)
        now = self.clock()
        expires_at = row["otp_expires_at"]
        if not expires_at or expires_at <= _iso(now):
            raise TwoFactorFailed("EXPIRED")
        if not hmac.compare_digest(row["otp_hash"] or "", self._otp_digest(onboarding_id, code)):
            self.sessions.record_failure(onboarding_id, self._window_start(now), _iso(now))
            self._ensure_not_locked(self._require(onboarding_id))
            raise TwoFactorFailed("INCORRECT")

        self.sessions.mark_verified(onboarding_id, _iso(now))
        self._step_completed(onboarding_id, TWO_FACTOR_STEP)
        return self._view(self._require(onboarding_id), None)

    # Persiste la cuenta y activa la wallet solo con el documento válido y el segundo factor verificado.
    def activate(self, onboarding_id: str) -> OnboardingView:
        row = self._recovered(self._require(onboarding_id))
        if row["registration"] == "PERSISTED":
            return self._synchronized(row)
        if row["registration"] == "PERSISTING":
            return self._view(row, None)
        if row["verification"] != "VERIFIED":
            raise TwoFactorRequired()
        if not self.sessions.begin_persist(onboarding_id, self._now()):
            return self._view(self._require(onboarding_id), None)

        account_id = self._reserve_account(row)
        try:
            document = self.protector.decrypt(row["document_enc"])
            kyc = self.provider.create_kyc(row["document_type"], document, row["scenario"])
            self.accounts.complete(account_id, kyc.id, kyc.wallet_id, kyc.status, self._now())
            wallet = self._confirmed_wallet(kyc.wallet_id, kyc.status)
            activation = self._activation(kyc.status, wallet)
            self.sessions.complete_persist(onboarding_id, kyc.id, kyc.wallet_id, kyc.status, activation, self._now())
        except BaseException:
            self.accounts.release(account_id)
            self.sessions.revert_persist(onboarding_id, self._now())
            raise

        self._step_completed(onboarding_id, PERSISTENCE_STEP)
        if activation == ACTIVE:
            self._record_activation(onboarding_id)
        return self._view(self._require(onboarding_id), wallet)

    def exit(self, onboarding_id: str, action: str) -> OnboardingView:
        row = self._require(onboarding_id)
        if row["activation"] != ACTIVE:
            raise InvalidStep(row["activation"])
        self.events.record(onboarding_id, EVENT_STEP_COMPLETED, EXIT_STEP, action, self._now())
        return self._synchronized(row)

    def _reserve_account(self, row: Any) -> int:
        try:
            return self.accounts.reserve(row["id"], row["document_type"], row["document_hash"], self._now())
        except AccountExists:
            self.sessions.revert_persist(row["id"], self._now())
            raise RegistrationUnavailable() from None

    def _issue_challenge(self, row: Any) -> None:
        if not self.otp_channel.available():
            raise TwoFactorUnavailable()
        self._ensure_not_locked(row)
        if row["otp_issues"] >= MAX_CHALLENGES_PER_ONBOARDING:
            raise TwoFactorLimit()
        code = self.otp_channel.issue()
        if code is None:
            raise TwoFactorUnavailable()
        now = self.clock()
        expires_at = now + timedelta(seconds=OTP_VALIDITY_SECONDS)
        self.sessions.set_challenge(row["id"], self._otp_digest(row["id"], code), _iso(expires_at), _iso(now))

    def _ensure_not_locked(self, row: Any) -> None:
        now = self.clock()
        failures, latest = self.sessions.failures_in_window(row["id"], row["document_hash"], self._window_start(now))
        if failures < MAX_FAILED_ATTEMPTS or latest is None:
            return
        unlock_at = datetime.fromisoformat(latest) + timedelta(seconds=FAILURE_WINDOW_SECONDS)
        raise TwoFactorLocked(max(1, math.ceil((unlock_at - now).total_seconds())))

    def _otp_digest(self, onboarding_id: str, code: str) -> str:
        return self.protector.digest(f"otp:{onboarding_id}", code)

    def _window_start(self, now: datetime) -> str:
        return _iso(now - timedelta(seconds=FAILURE_WINDOW_SECONDS))

    # Una caída entre la reserva y la respuesta del proveedor no debe bloquear el documento para siempre.
    def _recovered(self, row: Any) -> Any:
        if row["registration"] != "PERSISTING":
            return row
        stale_before = _iso(self.clock() - timedelta(seconds=PERSIST_STALE_SECONDS))
        if row["updated_at"] > stale_before:
            return row
        self.accounts.release_for_session(row["id"])
        self.sessions.revert_persist(row["id"], self._now())
        return self._require(row["id"])

    def _synchronized(self, row: Any) -> OnboardingView:
        if row["registration"] != "PERSISTED" or row["kyc_id"] is None or row["activation"] == REJECTED:
            return self._view(row, None)
        if row["activation"] == ACTIVE:
            return self._view(row, self._confirmed_wallet(row["wallet_id"], ACTIVE))

        kyc = self.provider.get_kyc(row["kyc_id"])
        wallet = self._confirmed_wallet(kyc.wallet_id, kyc.status)
        activation = self._activation(kyc.status, wallet)
        if kyc.status != row["provider_status"] or activation != row["activation"]:
            now = self._now()
            self.sessions.update_provider_state(row["id"], kyc.status, activation, now)
            self.accounts.update_status(row["kyc_id"], kyc.status, now)
        if activation == ACTIVE:
            self._record_activation(row["id"])
        return self._view(self._require(row["id"]), wallet)

    # Solo una wallet activa cuenta como confirmada; el resultado del KYC ya quedó registrado en la cuenta.
    def _confirmed_wallet(self, wallet_id: str, provider_status: str) -> WalletResult | None:
        if provider_status != ACTIVE:
            return None
        try:
            wallet = self.provider.get_wallet(wallet_id)
        except (ProviderUnavailable, ProviderError):
            return None
        return wallet if wallet.status == ACTIVE else None

    @staticmethod
    def _activation(provider_status: str, wallet: WalletResult | None) -> str:
        if wallet is not None:
            return ACTIVE
        return provider_status if provider_status in (PENDING, REJECTED) else INACTIVE

    def _record_activation(self, onboarding_id: str) -> None:
        self._step_completed(onboarding_id, ACTIVATION_STEP)
        self.events.record(onboarding_id, EVENT_CLOSED, NO_STEP, ACTIVE, self._now())

    def _step_completed(self, onboarding_id: str, step: str) -> None:
        self.events.record(onboarding_id, EVENT_STEP_COMPLETED, step, NO_STEP, self._now())

    def _require(self, onboarding_id: str) -> Any:
        row = self.sessions.get(onboarding_id)
        if row is None:
            raise OnboardingNotFound(onboarding_id)
        return row

    def _now(self) -> str:
        return _iso(self.clock())

    def _view(self, row: Any, wallet: WalletResult | None) -> OnboardingView:
        return OnboardingView(
            onboarding_id=row["id"],
            step=self._step(row),
            registration=row["registration"],
            verification=row["verification"],
            activation=row["activation"],
            provider_status=row["provider_status"],
            wallet=wallet,
            two_factor_available=self.otp_channel.available(),
        )

    # El paso se deriva siempre del estado persistido: nunca puede ir por delante de lo completado.
    @staticmethod
    def _step(row: Any) -> str:
        if row["activation"] == ACTIVE:
            return EXIT_STEP
        if row["verification"] == "VERIFIED":
            return ACTIVATION_STEP
        if row["registration"] == "DOCUMENT_VALID":
            return TWO_FACTOR_STEP
        return DOCUMENT_STEP
