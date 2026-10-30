import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import urllib3


WALLET_MOCK_URL_ENV = "WALLET_MOCK_URL"
DEFAULT_WALLET_MOCK_URL = "http://127.0.0.1:8787"
PROVIDER_TIMEOUT_SECONDS = 5.0
KYC_STATUSES = ("ACTIVE", "PENDING", "REJECTED")
PROVIDER_UNAVAILABLE_STATUS = 503
PROVIDER_LIMIT_STATUS = 429


class ProviderUnavailable(Exception):
    """The provider reports that it is unavailable; it did not create anything."""


class ProviderUnreachable(ProviderUnavailable):
    """The call failed or timed out, so the provider may or may not have processed it."""


class ProviderError(Exception):
    """The provider answered in a way the onboarding cannot use."""


class ProviderLimit(ProviderError):
    """The provider rejected the call because its usage limit was reached."""


@dataclass(frozen=True)
class KycResult:
    id: str
    wallet_id: str
    status: str


@dataclass(frozen=True)
class WalletResult:
    id: str
    status: str
    balance: int
    reserved: int
    available: int
    currency: str


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_amount(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class WalletProvider:
    def __init__(
        self,
        base_url: str | None = None,
        http: urllib3.PoolManager | None = None,
    ) -> None:
        selected = base_url or os.getenv(WALLET_MOCK_URL_ENV) or DEFAULT_WALLET_MOCK_URL
        self.base_url = selected.rstrip("/")
        self.http = http or urllib3.PoolManager()

    def create_kyc(self, document_type: str, document: str, scenario: str) -> KycResult:
        payload = self._request(
            "POST",
            "/kyc/verifications",
            {"documentType": document_type, "document": document, "scenario": scenario},
        )
        return self._kyc(payload)

    def get_kyc(self, kyc_id: str) -> KycResult:
        payload = self._request("GET", f"/kyc/verifications/{quote(kyc_id, safe='')}")
        return self._kyc(payload)

    def get_wallet(self, wallet_id: str) -> WalletResult:
        payload = self._request("GET", f"/wallets/{quote(wallet_id, safe='')}")
        status = payload.get("status")
        if not (
            _is_text(payload.get("id"))
            and status in KYC_STATUSES
            and all(_is_amount(payload.get(key)) for key in ("balance", "reserved", "available"))
            and _is_text(payload.get("currency"))
        ):
            raise ProviderError("Unexpected wallet payload")
        return WalletResult(
            id=payload["id"],
            status=status,
            balance=payload["balance"],
            reserved=payload["reserved"],
            available=payload["available"],
            currency=payload["currency"],
        )

    @staticmethod
    def _kyc(payload: dict[str, Any]) -> KycResult:
        if not (
            _is_text(payload.get("id"))
            and _is_text(payload.get("wallet_id"))
            and payload.get("status") in KYC_STATUSES
        ):
            raise ProviderError("Unexpected KYC payload")
        return KycResult(payload["id"], payload["wallet_id"], payload["status"])

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.http.request(
                method,
                f"{self.base_url}{path}",
                body=None if body is None else json.dumps(body),
                headers={"Content-Type": "application/json"},
                timeout=urllib3.Timeout(total=PROVIDER_TIMEOUT_SECONDS),
                retries=False,
            )
        except urllib3.exceptions.HTTPError as error:
            raise ProviderUnreachable("Provider unreachable") from error

        if response.status == PROVIDER_UNAVAILABLE_STATUS:
            raise ProviderUnavailable("Provider unavailable")
        if response.status == PROVIDER_LIMIT_STATUS:
            raise ProviderLimit("Provider limit reached")
        if response.status not in (200, 201):
            raise ProviderError(f"Unexpected provider status {response.status}")
        try:
            payload = json.loads(response.data)
        except (ValueError, UnicodeDecodeError) as error:
            raise ProviderError("Provider returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise ProviderError("Provider returned an unexpected body")
        return payload
