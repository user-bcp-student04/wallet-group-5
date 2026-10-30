import os
import re
from typing import Protocol


OTP_TEST_CODE_ENV = "ONBOARDING_OTP_TEST_CODE"
OTP_PATTERN = re.compile(r"^\d{6}$")
OTP_VALIDITY_SECONDS = 300
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 300
MAX_CHALLENGES_PER_ONBOARDING = 3


class TwoFactorUnavailable(Exception):
    """No hay un mecanismo de segundo factor configurado."""


class TwoFactorLimit(Exception):
    """Se superó el número de desafíos permitidos para este onboarding."""


class TwoFactorLocked(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class TwoFactorFailed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OtpChannel(Protocol):
    def available(self) -> bool:
        """Indica si hay un mecanismo de segundo factor configurado."""

    def issue(self) -> str | None:
        """Entrega un código por el canal y lo devuelve, o None si el canal no está disponible."""


class TestCodeChannel:
    """Canal simulado: el código de prueba sale del entorno y nunca se devuelve ni se registra."""

    __test__ = False

    def available(self) -> bool:
        return self.issue() is not None

    def issue(self) -> str | None:
        code = os.getenv(OTP_TEST_CODE_ENV, "").strip()
        return code if OTP_PATTERN.fullmatch(code) else None
