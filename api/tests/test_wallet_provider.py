import json
from types import SimpleNamespace

import pytest
import urllib3

from app.wallet_provider import (
    DEFAULT_WALLET_MOCK_URL,
    KycResult,
    ProviderError,
    ProviderLimit,
    ProviderUnavailable,
    ProviderUnreachable,
    WalletProvider,
    WalletResult,
)


class FakePool:
    def __init__(self, status: int = 200, data: bytes = b"{}", failure: Exception | None = None) -> None:
        self.status = status
        self.data = data
        self.failure = failure
        self.calls: list[tuple] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.failure is not None:
            raise self.failure
        return SimpleNamespace(status=self.status, data=self.data)


def kyc_body(**overrides: object) -> bytes:
    body = {"id": "kyc-1", "wallet_id": "wal-1", "scenario": "APPROVED", "status": "ACTIVE", **overrides}
    return json.dumps(body).encode()


def test_provider_posts_the_documented_request_with_a_bounded_timeout() -> None:
    pool = FakePool(201, kyc_body())
    result = WalletProvider("http://mock:8787/", pool).create_kyc("TEST", "TEST-001", "APPROVED")

    method, url, kwargs = pool.calls[0]
    assert (method, url) == ("POST", "http://mock:8787/kyc/verifications")
    assert json.loads(kwargs["body"]) == {
        "documentType": "TEST",
        "document": "TEST-001",
        "scenario": "APPROVED",
    }
    assert kwargs["timeout"].total == 5.0
    assert kwargs["retries"] is False
    assert result == KycResult("kyc-1", "wal-1", "ACTIVE")


def test_provider_keeps_the_path_prefix_of_a_group_url() -> None:
    pool = FakePool(200, kyc_body())
    WalletProvider("https://mock.example/groups/5/", pool).get_kyc("kyc-1")
    assert pool.calls[0][1] == "https://mock.example/groups/5/kyc/verifications/kyc-1"


def test_provider_encodes_identifiers_in_the_path() -> None:
    pool = FakePool(200, kyc_body())
    WalletProvider("http://mock", pool).get_kyc("a b/../c")
    assert pool.calls[0][1] == "http://mock/kyc/verifications/a%20b%2F..%2Fc"
    assert pool.calls[0][2]["body"] is None


def test_provider_reads_a_wallet() -> None:
    data = b'{"id":"wal-1","status":"ACTIVE","balance":0,"reserved":0,"available":0,"currency":"PEN"}'
    wallet = WalletProvider("http://mock", FakePool(200, data)).get_wallet("wal-1")
    assert wallet == WalletResult("wal-1", "ACTIVE", 0, 0, 0, "PEN")


def test_provider_uses_the_environment_or_the_default_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WALLET_MOCK_URL", "http://configured:9000/")
    assert WalletProvider().base_url == "http://configured:9000"
    monkeypatch.delenv("WALLET_MOCK_URL")
    assert WalletProvider().base_url == DEFAULT_WALLET_MOCK_URL


@pytest.mark.parametrize(
    "failure",
    [urllib3.exceptions.MaxRetryError(None, "http://mock"), urllib3.exceptions.ReadTimeoutError(None, "u", "t")],
)
def test_provider_treats_network_failures_as_uncertain(failure: Exception) -> None:
    with pytest.raises(ProviderUnreachable):
        WalletProvider("http://mock", FakePool(failure=failure)).get_kyc("kyc-1")


def test_provider_treats_503_as_unavailable_but_not_uncertain() -> None:
    with pytest.raises(ProviderUnavailable) as raised:
        WalletProvider("http://mock", FakePool(503, b'{"error":"KYC_UNAVAILABLE"}')).create_kyc("TEST", "TEST-1", "UNAVAILABLE")
    assert not isinstance(raised.value, ProviderUnreachable)


def test_provider_reports_its_usage_limit() -> None:
    with pytest.raises(ProviderLimit):
        WalletProvider("http://mock", FakePool(429, b'{"error":"GROUP_LIMIT_RESET_REQUIRED"}')).create_kyc("TEST", "TEST-1", "APPROVED")


@pytest.mark.parametrize(
    ("status", "data"),
    [
        (400, b'{"error":"INVALID"}'),
        (404, b"{}"),
        (500, b"{}"),
        (200, b"not json"),
        (200, b"\xff"),
        (200, b"[]"),
        (200, kyc_body(status="DONE")),
        (200, kyc_body(id="")),
        (200, b'{"id":"kyc-1"}'),
    ],
)
def test_provider_rejects_unusable_responses(status: int, data: bytes) -> None:
    with pytest.raises(ProviderError):
        WalletProvider("http://mock", FakePool(status, data)).get_kyc("kyc-1")


@pytest.mark.parametrize(
    "body",
    [
        b'{"id":"w","status":"ACTIVE","balance":"0","reserved":0,"available":0,"currency":"PEN"}',
        b'{"id":"w","status":"ACTIVE","balance":true,"reserved":0,"available":0,"currency":"PEN"}',
        b'{"id":"w","status":"CLOSED","balance":0,"reserved":0,"available":0,"currency":"PEN"}',
        b'{"id":"w","status":"ACTIVE","balance":0,"reserved":0,"available":0}',
    ],
)
def test_provider_rejects_unexpected_wallet_payloads(body: bytes) -> None:
    with pytest.raises(ProviderError):
        WalletProvider("http://mock", FakePool(200, body)).get_wallet("w")
