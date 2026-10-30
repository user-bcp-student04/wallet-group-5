import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.data_protection import DATA_KEY_ENV, DocumentProtector
from app.main import create_app
from app.onboarding_repositories import AccountExists
from app.onboarding_routes import DEFAULT_SUPPORT_MESSAGE, SUPPORT_MESSAGE_ENV
from app.onboarding_service import RegistrationUnavailable
from app.security import verified_identity
from app.two_factor import OTP_TEST_CODE_ENV, TestCodeChannel
from app.wallet_provider import (
    KycResult,
    ProviderError,
    ProviderLimit,
    ProviderUnavailable,
    ProviderUnreachable,
    WalletResult,
)


CODE = "123456"
DOCUMENT = "TEST-001"
STATUS_BY_SCENARIO = {"APPROVED": "ACTIVE", "MANUAL_REVIEW": "PENDING", "REJECTED": "REJECTED"}


class FakeProvider:
    def __init__(self) -> None:
        self.kycs: dict[str, KycResult] = {}
        self.create_calls = 0
        self.get_calls = 0
        self.create_failure: Exception | None = None
        self.get_failure: Exception | None = None
        self.wallet_failure: Exception | None = None
        self.wallet_status = "ACTIVE"
        self._lock = threading.Lock()

    def create_kyc(self, document_type: str, document: str, scenario: str) -> KycResult:
        with self._lock:
            self.create_calls += 1
            if self.create_failure is not None:
                raise self.create_failure
            if scenario == "UNAVAILABLE":
                raise ProviderUnavailable("down")
            number = len(self.kycs) + 1
            kyc = KycResult(f"kyc-{number}", f"wal-{number}", STATUS_BY_SCENARIO[scenario])
            self.kycs[kyc.id] = kyc
            return kyc

    def get_kyc(self, kyc_id: str) -> KycResult:
        self.get_calls += 1
        if self.get_failure is not None:
            raise self.get_failure
        return self.kycs[kyc_id]

    def get_wallet(self, wallet_id: str) -> WalletResult:
        if self.wallet_failure is not None:
            raise self.wallet_failure
        return WalletResult(wallet_id, self.wallet_status, 0, 0, 0, "PEN")

    def decide(self, kyc_id: str, status: str) -> None:
        kyc = self.kycs[kyc_id]
        self.kycs[kyc_id] = KycResult(kyc.id, kyc.wallet_id, status)


class FakeChannel:
    def __init__(self, code: str | None = CODE) -> None:
        self.code = code
        self.issued = 0

    def available(self) -> bool:
        return self.code is not None

    def issue(self) -> str | None:
        self.issued += 1
        return self.code


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def channel() -> FakeChannel:
    return FakeChannel()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def protector() -> DocumentProtector:
    return DocumentProtector(Fernet.generate_key())


@pytest.fixture
def app_paths(tmp_path: Path) -> dict[str, str]:
    return {"db_path": str(tmp_path / "api.db"), "upload_dir": str(tmp_path / "uploads")}


@pytest.fixture
def app(app_paths, provider, channel, clock, protector):
    return create_app(
        **app_paths, wallet_provider=provider, otp_channel=channel, protector=protector, clock=clock
    )


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


def begin(client: TestClient) -> str:
    response = client.post("/api/onboarding")
    assert response.status_code == 201
    return response.json()["onboardingId"]


def submit(client: TestClient, onboarding_id: str, document: str = DOCUMENT, scenario: str = "APPROVED"):
    return client.put(
        f"/api/onboarding/{onboarding_id}/document",
        json={"documentType": "TEST", "document": document, "scenario": scenario},
    )


def verify(client: TestClient, onboarding_id: str, code: str = CODE):
    return client.post(f"/api/onboarding/{onboarding_id}/two-factor", json={"code": code})


def activate(client: TestClient, onboarding_id: str):
    return client.post(f"/api/onboarding/{onboarding_id}/activate")


def verified_onboarding(client: TestClient, document: str = DOCUMENT, scenario: str = "APPROVED") -> str:
    onboarding_id = begin(client)
    assert submit(client, onboarding_id, document, scenario).status_code == 200
    assert verify(client, onboarding_id).status_code == 200
    return onboarding_id


def event_names(app, onboarding_id: str) -> list[tuple[str, str]]:
    return [(row["event"], row["step"]) for row in app.state.onboarding_events.list_for(onboarding_id)]


def test_start_shows_the_document_step_with_separate_states_and_needs_no_session(client: TestClient, app) -> None:
    response = client.post("/api/onboarding")

    assert response.status_code == 201
    body = response.json()
    assert body["step"] == "DOCUMENT"
    assert body["states"] == {
        "registration": "STARTED",
        "verification": "PENDING",
        "activation": "INACTIVE",
        "provider": None,
    }
    assert body["wallet"] is None and body["paymentsEntryAvailable"] is False
    assert event_names(app, body["onboardingId"]) == [("onboarding.started", "START")]
    assert client.get("/api/tasks").status_code == 401


def test_a_complete_onboarding_activates_the_wallet_and_records_every_event(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = begin(client)
    document = submit(client, onboarding_id)
    assert document.json()["step"] == "TWO_FACTOR"
    assert document.json()["states"]["verification"] == "CHALLENGED"

    verified = verify(client, onboarding_id)
    assert verified.json()["step"] == "ACTIVATION"
    assert verified.json()["states"]["verification"] == "VERIFIED"
    assert provider.create_calls == 0

    activated = activate(client, onboarding_id).json()
    assert activated["step"] == "EXIT"
    assert activated["states"] == {
        "registration": "PERSISTED",
        "verification": "VERIFIED",
        "activation": "ACTIVE",
        "provider": "ACTIVE",
    }
    assert activated["wallet"] == {
        "id": "wal-1",
        "status": "ACTIVE",
        "balance": 0,
        "reserved": 0,
        "available": 0,
        "currency": "PEN",
    }
    assert activated["paymentsEntryAvailable"] is True

    left = client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "CONTINUE"})
    assert left.status_code == 200
    assert event_names(app, onboarding_id) == [
        ("onboarding.started", "START"),
        ("onboarding.step_completed", "DOCUMENT"),
        ("onboarding.step_completed", "TWO_FACTOR"),
        ("onboarding.step_completed", "PERSISTENCE"),
        ("onboarding.step_completed", "ACTIVATION"),
        ("onboarding.closed", "-"),
        ("onboarding.step_completed", "EXIT"),
    ]


def test_repeated_requests_do_not_duplicate_events_or_provider_calls(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = verified_onboarding(client)
    assert activate(client, onboarding_id).status_code == 200
    assert activate(client, onboarding_id).json()["step"] == "EXIT"
    for _ in range(2):
        assert client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "END"}).status_code == 200

    assert provider.create_calls == 1
    names = event_names(app, onboarding_id)
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "document",
    ["", "TEST-", "   ", "001", "REAL-001", "SECRETO-123", "TEST-" + "9" * 196, None, 7],
)
def test_invalid_documents_are_rejected_without_echoing_them(client: TestClient, app, document) -> None:
    onboarding_id = begin(client)

    response = submit(client, onboarding_id, document)

    assert response.status_code == 422
    assert "input" not in response.text
    if isinstance(document, str) and document.strip() and not document.startswith("TEST"):
        assert document not in response.text
    state = client.get(f"/api/onboarding/{onboarding_id}").json()
    assert state["step"] == "DOCUMENT" and state["states"]["registration"] == "STARTED"


def test_invalid_document_type_and_unknown_fields_are_rejected(client: TestClient) -> None:
    onboarding_id = begin(client)
    path = f"/api/onboarding/{onboarding_id}/document"
    assert client.put(path, json={"documentType": "DNI", "document": DOCUMENT}).status_code == 422
    assert client.put(path, json={"documentType": "TEST", "document": DOCUMENT, "extra": 1}).status_code == 422


def test_longest_valid_document_is_accepted_and_trimmed(client: TestClient) -> None:
    onboarding_id = begin(client)
    assert submit(client, onboarding_id, "TEST-" + "9" * 195).status_code == 200
    other = begin(client)
    assert submit(client, other, "  TEST-002  ").status_code == 200


def test_the_document_can_be_corrected_until_the_second_factor_is_verified(client: TestClient) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id, "TEST-001")
    assert submit(client, onboarding_id, "TEST-002").json()["step"] == "TWO_FACTOR"
    verify(client, onboarding_id)

    locked = submit(client, onboarding_id, "TEST-003")

    assert locked.status_code == 409 and locked.json() == {"detail": {"error": "INVALID_STEP"}}


def test_wrong_code_does_not_verify_and_the_person_can_retry(client: TestClient) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)

    wrong = verify(client, onboarding_id, "000000")

    assert wrong.status_code == 400
    assert wrong.json() == {"detail": {"error": "TWO_FACTOR_FAILED", "reason": "INCORRECT"}}
    assert CODE not in wrong.text
    assert client.get(f"/api/onboarding/{onboarding_id}").json()["step"] == "TWO_FACTOR"
    assert verify(client, onboarding_id).status_code == 200


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef"])
def test_malformed_codes_are_rejected_without_echoing_them(client: TestClient, code: str) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)

    response = verify(client, onboarding_id, code)

    assert response.status_code == 422
    assert "input" not in response.text


def test_an_expired_code_is_reported_and_a_new_challenge_works(client: TestClient, clock: Clock) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)
    clock.advance(301)

    expired = verify(client, onboarding_id)

    assert expired.status_code == 400 and expired.json()["detail"]["reason"] == "EXPIRED"
    assert client.post(f"/api/onboarding/{onboarding_id}/challenge").status_code == 200
    assert verify(client, onboarding_id).status_code == 200


def test_repeated_failures_lock_the_second_factor_temporarily(client: TestClient, clock: Clock) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)
    for _ in range(4):
        assert verify(client, onboarding_id, "000000").status_code == 400

    locked = verify(client, onboarding_id, "000000")

    assert locked.status_code == 429
    assert locked.json()["detail"]["error"] == "TWO_FACTOR_LOCKED"
    assert locked.headers["Retry-After"] == str(locked.json()["detail"]["retryAfterSeconds"])
    assert verify(client, onboarding_id).status_code == 429
    assert client.post(f"/api/onboarding/{onboarding_id}/challenge").status_code == 429

    clock.advance(301)
    assert client.post(f"/api/onboarding/{onboarding_id}/challenge").status_code == 200
    assert verify(client, onboarding_id).status_code == 200


def test_failures_count_against_the_document_across_onboardings(client: TestClient) -> None:
    first = begin(client)
    submit(client, first)
    for _ in range(5):
        verify(client, first, "000000")

    second = begin(client)

    locked = submit(client, second)

    assert locked.status_code == 429 and locked.json()["detail"]["error"] == "TWO_FACTOR_LOCKED"
    assert verify(client, second).status_code == 409


def test_challenges_are_limited_per_onboarding(client: TestClient, channel: FakeChannel) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)
    path = f"/api/onboarding/{onboarding_id}/challenge"
    assert client.post(path).status_code == 200
    assert client.post(path).status_code == 200

    limited = client.post(path)

    assert limited.status_code == 429 and limited.json() == {"detail": {"error": "TWO_FACTOR_LIMIT"}}
    assert channel.issued == 3


def test_verifying_again_after_success_is_idempotent(client: TestClient, app) -> None:
    onboarding_id = verified_onboarding(client)

    again = verify(client, onboarding_id, "000000")

    assert again.status_code == 200 and again.json()["states"]["verification"] == "VERIFIED"
    assert event_names(app, onboarding_id).count(("onboarding.step_completed", "TWO_FACTOR")) == 1


def test_a_mechanism_withdrawn_after_the_challenge_blocks_verification(
    client: TestClient, channel: FakeChannel
) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)
    channel.code = None

    assert verify(client, onboarding_id).status_code == 503


def test_verification_requires_a_challenge_first(client: TestClient) -> None:
    onboarding_id = begin(client)

    assert verify(client, onboarding_id).status_code == 409
    assert client.post(f"/api/onboarding/{onboarding_id}/challenge").status_code == 409


def test_without_an_approved_mechanism_nothing_can_be_verified_or_activated(
    app_paths, provider: FakeProvider, protector: DocumentProtector
) -> None:
    app = create_app(**app_paths, wallet_provider=provider, otp_channel=FakeChannel(None), protector=protector)
    client = TestClient(app)
    onboarding_id = begin(client)

    document = submit(client, onboarding_id)

    assert document.status_code == 200
    assert document.json()["twoFactorAvailable"] is False
    assert document.json()["step"] == "TWO_FACTOR"
    assert client.post(f"/api/onboarding/{onboarding_id}/challenge").status_code == 503
    assert verify(client, onboarding_id).status_code == 409
    assert activate(client, onboarding_id).status_code == 403
    assert provider.create_calls == 0


def test_activation_without_the_second_factor_is_rejected_and_creates_nothing(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = begin(client)
    submit(client, onboarding_id)

    response = activate(client, onboarding_id)

    assert response.status_code == 403 and response.json() == {"detail": {"error": "TWO_FACTOR_REQUIRED"}}
    assert provider.create_calls == 0
    state = client.get(f"/api/onboarding/{onboarding_id}").json()
    assert state["states"]["registration"] == "DOCUMENT_VALID" and state["states"]["activation"] == "INACTIVE"
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)


def test_activation_before_the_document_is_rejected(client: TestClient) -> None:
    assert activate(client, begin(client)).status_code == 403


@pytest.mark.parametrize("scenario", ["APPROVED", "MANUAL_REVIEW", "REJECTED"])
def test_an_existing_account_gets_the_same_neutral_answer_in_any_state(
    client: TestClient, provider: FakeProvider, scenario: str
) -> None:
    first = verified_onboarding(client, scenario=scenario)
    assert activate(client, first).status_code == 200
    calls = provider.create_calls

    duplicate = activate(client, verified_onboarding(client))

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": {"error": "REGISTRATION_UNAVAILABLE", "message": DEFAULT_SUPPORT_MESSAGE}
    }
    assert provider.create_calls == calls


def test_the_neutral_answer_does_not_reveal_status_ids_or_the_document(client: TestClient) -> None:
    assert activate(client, verified_onboarding(client)).status_code == 200
    second = verified_onboarding(client)

    duplicate = activate(client, second)

    for leaked in ("ACTIVE", "PENDING", "REJECTED", "kyc-", "wal-", DOCUMENT, "exist"):
        assert leaked not in duplicate.text
    again = client.get(f"/api/onboarding/{second}").json()
    assert again["states"]["registration"] == "DOCUMENT_VALID" and again["wallet"] is None


def test_the_support_message_can_be_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SUPPORT_MESSAGE_ENV, "Escribe a asistencia.")
    assert activate(client, verified_onboarding(client)).status_code == 200

    duplicate = activate(client, verified_onboarding(client))

    assert duplicate.json()["detail"]["message"] == "Escribe a asistencia."


def test_concurrent_registrations_for_one_document_create_a_single_account(
    client: TestClient, app, provider: FakeProvider
) -> None:
    ids = [begin(client) for _ in range(8)]
    for onboarding_id in ids:
        submit(client, onboarding_id, "TEST-RACE")
        verify(client, onboarding_id)
    service = app.state.onboarding_service
    outcomes: list[str] = []
    barrier = threading.Barrier(len(ids))

    def register(onboarding_id: str) -> None:
        barrier.wait()
        try:
            service.activate(onboarding_id)
            outcomes.append("created")
        except RegistrationUnavailable:
            outcomes.append("neutral")

    threads = [threading.Thread(target=register, args=(onboarding_id,)) for onboarding_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert outcomes.count("created") == 1 and outcomes.count("neutral") == len(ids) - 1
    assert provider.create_calls == 1


def test_accounts_and_state_survive_a_restart_and_keep_blocking_duplicates(
    app_paths, provider: FakeProvider, channel: FakeChannel, protector: DocumentProtector
) -> None:
    def new_client() -> TestClient:
        return TestClient(create_app(**app_paths, wallet_provider=provider, otp_channel=channel, protector=protector))

    first = new_client()
    onboarding_id = verified_onboarding(first)
    assert activate(first, onboarding_id).status_code == 200

    restarted = new_client()
    assert restarted.get(f"/api/onboarding/{onboarding_id}").json()["states"]["activation"] == "ACTIVE"
    assert activate(restarted, verified_onboarding(restarted)).status_code == 409


def test_an_interrupted_onboarding_resumes_from_a_safe_step_without_fake_completions(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = begin(client)
    assert client.get(f"/api/onboarding/{onboarding_id}").json()["step"] == "DOCUMENT"
    submit(client, onboarding_id)
    assert client.get(f"/api/onboarding/{onboarding_id}").json()["step"] == "TWO_FACTOR"

    state = client.get(f"/api/onboarding/{onboarding_id}").json()

    assert state["states"]["activation"] == "INACTIVE" and state["wallet"] is None
    assert provider.create_calls == 0
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)
    assert ("onboarding.step_completed", "TWO_FACTOR") not in event_names(app, onboarding_id)


def test_manual_review_stays_pending_without_a_wallet_until_the_operator_decides(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = verified_onboarding(client, scenario="MANUAL_REVIEW")

    pending = activate(client, onboarding_id).json()

    assert pending["step"] == "ACTIVATION"
    assert pending["states"]["activation"] == "PENDING" and pending["states"]["provider"] == "PENDING"
    assert pending["wallet"] is None and pending["paymentsEntryAvailable"] is False
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)
    assert client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "END"}).status_code == 409

    provider.decide("kyc-1", "ACTIVE")
    resolved = client.get(f"/api/onboarding/{onboarding_id}").json()

    assert resolved["step"] == "EXIT" and resolved["wallet"]["status"] == "ACTIVE"
    assert resolved["paymentsEntryAvailable"] is True
    assert event_names(app, onboarding_id).count(("onboarding.closed", "-")) == 1


def test_manual_review_can_end_rejected(client: TestClient, provider: FakeProvider) -> None:
    onboarding_id = verified_onboarding(client, scenario="MANUAL_REVIEW")
    activate(client, onboarding_id)
    provider.decide("kyc-1", "REJECTED")

    rejected = client.get(f"/api/onboarding/{onboarding_id}").json()

    assert rejected["states"]["activation"] == "REJECTED" and rejected["wallet"] is None
    calls = provider.get_calls
    client.get(f"/api/onboarding/{onboarding_id}")
    assert provider.get_calls == calls


def test_rejected_onboarding_returns_no_wallet_and_no_payments_entry(client: TestClient, app) -> None:
    onboarding_id = verified_onboarding(client, scenario="REJECTED")

    rejected = activate(client, onboarding_id).json()

    assert rejected["states"]["activation"] == "REJECTED" and rejected["wallet"] is None
    assert rejected["paymentsEntryAvailable"] is False
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)


@pytest.mark.parametrize(
    ("failure", "status_code", "error"),
    [
        (ProviderUnavailable("down"), 503, "KYC_UNAVAILABLE"),
        (ProviderUnreachable("timeout"), 504, "KYC_RESULT_UNKNOWN"),
        (ProviderLimit("limit"), 429, "PROVIDER_LIMIT_REACHED"),
        (ProviderError("bad"), 502, "PROVIDER_ERROR"),
    ],
)
def test_provider_failures_leave_nothing_active_and_allow_a_retry(
    client: TestClient, app, provider: FakeProvider, failure: Exception, status_code: int, error: str
) -> None:
    onboarding_id = verified_onboarding(client)
    provider.create_failure = failure

    response = activate(client, onboarding_id)

    assert response.status_code == status_code and response.json() == {"detail": {"error": error}}
    state = client.get(f"/api/onboarding/{onboarding_id}").json()
    assert state["step"] == "ACTIVATION" and state["states"]["registration"] == "DOCUMENT_VALID"
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)

    provider.create_failure = None
    assert activate(client, onboarding_id).json()["states"]["activation"] == "ACTIVE"


def test_the_unavailable_scenario_releases_the_document(client: TestClient, provider: FakeProvider) -> None:
    unavailable = verified_onboarding(client, scenario="UNAVAILABLE")
    assert activate(client, unavailable).status_code == 503

    assert activate(client, verified_onboarding(client)).status_code == 200


def test_an_unexpected_exception_also_releases_the_document(client: TestClient, provider: FakeProvider) -> None:
    onboarding_id = verified_onboarding(client)
    provider.create_failure = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        activate(client, onboarding_id)
    provider.create_failure = None

    assert activate(client, onboarding_id).status_code == 200


def test_an_unconfirmed_wallet_does_not_activate_or_close_the_flow(
    client: TestClient, app, provider: FakeProvider
) -> None:
    onboarding_id = verified_onboarding(client)
    provider.wallet_failure = ProviderUnavailable("down")

    unconfirmed = activate(client, onboarding_id).json()

    assert unconfirmed["states"]["provider"] == "ACTIVE" and unconfirmed["states"]["activation"] == "INACTIVE"
    assert unconfirmed["wallet"] is None and unconfirmed["paymentsEntryAvailable"] is False
    assert unconfirmed["step"] == "ACTIVATION"
    assert ("onboarding.closed", "-") not in event_names(app, onboarding_id)

    provider.wallet_failure = None
    confirmed = client.get(f"/api/onboarding/{onboarding_id}").json()
    assert confirmed["states"]["activation"] == "ACTIVE" and confirmed["wallet"]["status"] == "ACTIVE"


def test_a_wallet_that_is_not_active_is_not_confirmed(client: TestClient, provider: FakeProvider) -> None:
    provider.wallet_status = "PENDING"
    onboarding_id = verified_onboarding(client)

    state = activate(client, onboarding_id).json()

    assert state["wallet"] is None and state["states"]["activation"] == "INACTIVE"


def test_a_later_wallet_failure_keeps_the_activation_but_hides_the_payments_entry(
    client: TestClient, provider: FakeProvider
) -> None:
    onboarding_id = verified_onboarding(client)
    activate(client, onboarding_id)
    provider.wallet_failure = ProviderError("bad")

    state = client.get(f"/api/onboarding/{onboarding_id}").json()

    assert state["states"]["activation"] == "ACTIVE" and state["wallet"] is None
    assert state["paymentsEntryAvailable"] is False


@pytest.mark.parametrize(
    ("failure", "status_code"),
    [(ProviderUnreachable("t"), 504), (ProviderUnavailable("d"), 503), (ProviderError("e"), 502)],
)
def test_refresh_failures_are_reported_without_changing_the_state(
    client: TestClient, provider: FakeProvider, failure: Exception, status_code: int
) -> None:
    onboarding_id = verified_onboarding(client, scenario="MANUAL_REVIEW")
    activate(client, onboarding_id)
    provider.get_failure = failure

    assert client.get(f"/api/onboarding/{onboarding_id}").status_code == status_code

    provider.get_failure = None
    assert client.get(f"/api/onboarding/{onboarding_id}").json()["states"]["activation"] == "PENDING"


def test_unknown_onboardings_return_404_without_calling_the_provider(
    client: TestClient, provider: FakeProvider
) -> None:
    calls = [
        client.get("/api/onboarding/unknown"),
        submit(client, "unknown"),
        client.post("/api/onboarding/unknown/challenge"),
        verify(client, "unknown"),
        activate(client, "unknown"),
        client.post("/api/onboarding/unknown/exit", json={"action": "END"}),
    ]

    assert [call.status_code for call in calls] == [404] * 6
    assert provider.get_calls == 0 and provider.create_calls == 0


def test_exit_is_only_available_with_an_active_wallet(client: TestClient) -> None:
    onboarding_id = verified_onboarding(client)

    assert client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "CONTINUE"}).status_code == 409
    assert client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "PAY"}).status_code == 422


def test_ending_the_session_records_the_exit_and_never_starts_a_payment(client: TestClient, app) -> None:
    onboarding_id = verified_onboarding(client)
    activate(client, onboarding_id)

    assert client.post(f"/api/onboarding/{onboarding_id}/exit", json={"action": "END"}).status_code == 200

    rows = app.state.onboarding_events.list_for(onboarding_id)
    assert [(row["step"], row["outcome"]) for row in rows if row["step"] == "EXIT"] == [("EXIT", "END")]


def test_a_stalled_registration_is_recovered_and_frees_the_document(
    client: TestClient, app, clock: Clock, provider: FakeProvider
) -> None:
    onboarding_id = verified_onboarding(client)
    sessions = app.state.onboarding_service.sessions
    accounts = app.state.onboarding_service.accounts
    row = sessions.get(onboarding_id)
    assert sessions.begin_persist(onboarding_id, "2026-10-30T12:00:00.000+00:00")
    accounts.reserve(onboarding_id, "TEST", row["document_hash"], "2026-10-30T12:00:00.000+00:00")

    assert activate(client, onboarding_id).json()["states"]["registration"] == "PERSISTING"
    clock.advance(31)

    assert client.get(f"/api/onboarding/{onboarding_id}").json()["states"]["registration"] == "DOCUMENT_VALID"
    assert activate(client, onboarding_id).json()["states"]["activation"] == "ACTIVE"


def test_documents_are_protected_at_rest_and_never_logged(
    client: TestClient, app_paths: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        onboarding_id = verified_onboarding(client, "TEST-SECRET-77")
        activate(client, onboarding_id)
        submit(client, begin(client), "bad document")

    dump = "\n".join(sqlite3.connect(app_paths["db_path"]).iterdump())
    assert "TEST-SECRET-77" not in dump
    assert CODE not in dump
    assert "TEST-SECRET-77" not in caplog.text and CODE not in caplog.text
    row = sqlite3.connect(app_paths["db_path"]).execute(
        "SELECT document_hash, document_enc FROM onboarding_sessions WHERE id=?", (onboarding_id,)
    ).fetchone()
    assert len(row[0]) == 64 and row[1].startswith("gAAAA")


def test_events_never_contain_the_document_or_the_code(client: TestClient, app) -> None:
    onboarding_id = verified_onboarding(client, "TEST-EVENT-55")
    activate(client, onboarding_id)

    serialized = repr([tuple(row) for row in app.state.onboarding_events.list_for(onboarding_id)])

    assert "TEST-EVENT-55" not in serialized and CODE not in serialized


def test_the_analytics_summary_requires_a_session(client: TestClient) -> None:
    assert client.get("/api/onboarding/analytics/summary").status_code == 401


def test_the_analytics_summary_reports_duration_new_users_and_the_missing_spend_source(
    client: TestClient, app, clock: Clock
) -> None:
    app.dependency_overrides[verified_identity] = lambda: {"username": "analyst", "role": ""}
    for number, seconds in enumerate((60, 120, 300)):
        onboarding_id = begin(client)
        clock.advance(seconds)
        submit(client, onboarding_id, f"TEST-{number}")
        verify(client, onboarding_id)
        activate(client, onboarding_id)
    abandoned = begin(client)
    submit(client, abandoned, "TEST-ABANDONED")

    summary = client.get("/api/onboarding/analytics/summary").json()

    assert summary["boundary"] == {"start": "onboarding.started", "end": "onboarding.closed", "outcome": "ACTIVE"}
    assert summary["targetMedianSeconds"] == 180
    assert summary["months"] == [
        {"month": "2026-10", "started": 4, "newActiveUsers": 3, "medianSeconds": 120.0, "withinTarget": True}
    ]
    assert summary["cac"] is None and summary["acquisitionSpend"] == {"status": "SOURCE_PENDING"}


def test_the_analytics_summary_without_data_has_no_months(client: TestClient, app) -> None:
    app.dependency_overrides[verified_identity] = lambda: {"username": "analyst", "role": ""}

    assert client.get("/api/onboarding/analytics/summary").json()["months"] == []


def test_a_median_above_the_target_is_flagged(client: TestClient, app, clock: Clock) -> None:
    app.dependency_overrides[verified_identity] = lambda: {"username": "analyst", "role": ""}
    onboarding_id = begin(client)
    clock.advance(400)
    submit(client, onboarding_id)
    verify(client, onboarding_id)
    activate(client, onboarding_id)

    month = client.get("/api/onboarding/analytics/summary").json()["months"][0]

    assert month["medianSeconds"] == 400.0 and month["withinTarget"] is False


def test_released_reservations_do_not_remove_completed_accounts(app) -> None:
    accounts = app.state.onboarding_service.accounts
    account_id = accounts.reserve("s-1", "TEST", "hash-1", "2026-10-30T12:00:00.000+00:00")
    accounts.complete(account_id, "kyc-5", "wal-5", "ACTIVE", "2026-10-30T12:00:00.000+00:00")

    accounts.release(account_id)
    with pytest.raises(AccountExists):
        accounts.reserve("s-2", "TEST", "hash-1", "2026-10-30T12:00:00.000+00:00")


def test_status_updates_follow_the_provider_verification(app) -> None:
    accounts = app.state.onboarding_service.accounts
    account_id = accounts.reserve("s-1", "TEST", "hash-2", "t")
    accounts.complete(account_id, "kyc-7", "wal-7", "PENDING", "t")

    accounts.update_status("kyc-7", "ACTIVE", "t2")

    row = app.state.onboarding_service.accounts.connection.execute(
        "SELECT status FROM onboarding_accounts WHERE kyc_id='kyc-7'"
    ).fetchone()
    assert row["status"] == "ACTIVE"


def test_the_document_protector_is_deterministic_for_uniqueness_and_reversible(protector: DocumentProtector) -> None:
    token = protector.encrypt("TEST-1")

    assert protector.decrypt(token) == "TEST-1" and token != protector.encrypt("TEST-1")
    assert protector.fingerprint("TEST", "TEST-1") == protector.fingerprint("TEST", "TEST-1")
    assert protector.fingerprint("TEST", "TEST-1") != protector.fingerprint("TEST", "TEST-2")
    assert protector.digest("otp:a", "1") != protector.digest("otp:b", "1")


def test_the_protector_uses_the_configured_key_or_a_local_key_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(DATA_KEY_ENV, key)
    configured = DocumentProtector.from_environment(tmp_path)
    assert DocumentProtector(key.encode()).decrypt(configured.encrypt("TEST-1")) == "TEST-1"
    assert not (tmp_path / "onboarding.key").exists()

    monkeypatch.delenv(DATA_KEY_ENV)
    generated = DocumentProtector.from_environment(tmp_path)
    again = DocumentProtector.from_environment(tmp_path)
    assert (tmp_path / "onboarding.key").exists()
    assert again.decrypt(generated.encrypt("TEST-2")) == "TEST-2"


def test_the_test_code_channel_needs_a_valid_code_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = TestCodeChannel()
    monkeypatch.delenv(OTP_TEST_CODE_ENV, raising=False)
    assert channel.available() is False and channel.issue() is None
    monkeypatch.setenv(OTP_TEST_CODE_ENV, "12ab56")
    assert channel.available() is False
    monkeypatch.setenv(OTP_TEST_CODE_ENV, " 654321 ")
    assert channel.available() is True and channel.issue() == "654321"
