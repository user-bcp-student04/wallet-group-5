import os
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.onboarding_analytics import summarize
from app.onboarding_repositories import EventRepository
from app.onboarding_service import (
    InvalidStep,
    OnboardingNotFound,
    OnboardingService,
    OnboardingView,
    RegistrationUnavailable,
    TwoFactorRequired,
)
from app.schemas import (
    AnalyticsResponse,
    DocumentRequest,
    ExitRequest,
    OnboardingResponse,
    OnboardingStates,
    TwoFactorRequest,
    WalletResponse,
)
from app.security import verified_identity
from app.two_factor import TwoFactorFailed, TwoFactorLimit, TwoFactorLocked, TwoFactorUnavailable
from app.wallet_provider import ProviderError, ProviderLimit, ProviderUnavailable, ProviderUnreachable


router = APIRouter()
SUPPORT_MESSAGE_ENV = "ONBOARDING_SUPPORT_MESSAGE"
DEFAULT_SUPPORT_MESSAGE = (
    "Si ya usaste la wallet, ingresa por la pantalla de acceso; si no puedes, contacta a asistencia del MVP."
)


def get_onboarding_service(request: Request) -> OnboardingService:
    return request.app.state.onboarding_service


def get_event_repository(request: Request) -> EventRepository:
    return request.app.state.onboarding_events


def as_response(view: OnboardingView) -> OnboardingResponse:
    wallet = view.wallet
    return OnboardingResponse(
        onboardingId=view.onboarding_id,
        step=view.step,
        states=OnboardingStates(
            registration=view.registration,
            verification=view.verification,
            activation=view.activation,
            provider=view.provider_status,
        ),
        twoFactorAvailable=view.two_factor_available,
        wallet=None
        if wallet is None
        else WalletResponse(
            id=wallet.id,
            status=wallet.status,
            balance=wallet.balance,
            reserved=wallet.reserved,
            available=wallet.available,
            currency=wallet.currency,
        ),
        paymentsEntryAvailable=view.payments_entry_available,
    )


def provider_failure(error: Exception) -> HTTPException:
    # Un fallo de red o un timeout deja el resultado incierto: el proveedor pudo haber procesado la solicitud.
    if isinstance(error, ProviderUnreachable):
        return HTTPException(status_code=504, detail={"error": "KYC_RESULT_UNKNOWN"})
    if isinstance(error, ProviderUnavailable):
        return HTTPException(status_code=503, detail={"error": "KYC_UNAVAILABLE"})
    if isinstance(error, ProviderLimit):
        return HTTPException(status_code=429, detail={"error": "PROVIDER_LIMIT_REACHED"})
    return HTTPException(status_code=502, detail={"error": "PROVIDER_ERROR"})


def failure(error: Exception) -> HTTPException:
    if isinstance(error, OnboardingNotFound):
        return HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    if isinstance(error, InvalidStep):
        return HTTPException(status_code=409, detail={"error": "INVALID_STEP"})
    if isinstance(error, TwoFactorRequired):
        return HTTPException(status_code=403, detail={"error": "TWO_FACTOR_REQUIRED"})
    if isinstance(error, RegistrationUnavailable):
        # Respuesta neutra: no distingue una cuenta existente de otras causas ni expone su estado.
        message = os.getenv(SUPPORT_MESSAGE_ENV) or DEFAULT_SUPPORT_MESSAGE
        return HTTPException(status_code=409, detail={"error": "REGISTRATION_UNAVAILABLE", "message": message})
    if isinstance(error, TwoFactorFailed):
        return HTTPException(status_code=400, detail={"error": "TWO_FACTOR_FAILED", "reason": error.reason})
    if isinstance(error, TwoFactorLocked):
        return HTTPException(
            status_code=429,
            detail={"error": "TWO_FACTOR_LOCKED", "retryAfterSeconds": error.retry_after_seconds},
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    if isinstance(error, TwoFactorLimit):
        return HTTPException(status_code=429, detail={"error": "TWO_FACTOR_LIMIT"})
    if isinstance(error, TwoFactorUnavailable):
        return HTTPException(status_code=503, detail={"error": "TWO_FACTOR_UNAVAILABLE"})
    return provider_failure(error)


HANDLED_ERRORS = (
    OnboardingNotFound,
    InvalidStep,
    TwoFactorRequired,
    RegistrationUnavailable,
    TwoFactorFailed,
    TwoFactorLocked,
    TwoFactorLimit,
    TwoFactorUnavailable,
    ProviderUnavailable,
    ProviderError,
)


def respond(action: Callable[[], OnboardingView]) -> OnboardingResponse:
    try:
        return as_response(action())
    except HANDLED_ERRORS as error:
        raise failure(error) from None


# El onboarding es público: quien se registra todavía no tiene una sesión. El identificador aleatorio
# del onboarding es la única referencia que la persona conserva.
@router.post("/api/onboarding", status_code=201, response_model=OnboardingResponse)
def start(service: OnboardingService = Depends(get_onboarding_service)) -> OnboardingResponse:
    return respond(service.start)


@router.get("/api/onboarding/analytics/summary", response_model=AnalyticsResponse)
def analytics(
    _identity: dict[str, str] = Depends(verified_identity),
    events: EventRepository = Depends(get_event_repository),
) -> dict:
    return summarize(events)


@router.get("/api/onboarding/{onboarding_id}", response_model=OnboardingResponse)
def current_state(
    onboarding_id: str, service: OnboardingService = Depends(get_onboarding_service)
) -> OnboardingResponse:
    return respond(lambda: service.get(onboarding_id))


@router.put("/api/onboarding/{onboarding_id}/document", response_model=OnboardingResponse)
def submit_document(
    onboarding_id: str,
    payload: DocumentRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    return respond(
        lambda: service.submit_document(onboarding_id, payload.documentType, payload.document, payload.scenario)
    )


@router.post("/api/onboarding/{onboarding_id}/challenge", response_model=OnboardingResponse)
def request_challenge(
    onboarding_id: str, service: OnboardingService = Depends(get_onboarding_service)
) -> OnboardingResponse:
    return respond(lambda: service.challenge(onboarding_id))


@router.post("/api/onboarding/{onboarding_id}/two-factor", response_model=OnboardingResponse)
def verify_two_factor(
    onboarding_id: str,
    payload: TwoFactorRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    return respond(lambda: service.verify(onboarding_id, payload.code))


@router.post("/api/onboarding/{onboarding_id}/activate", response_model=OnboardingResponse)
def activate(
    onboarding_id: str, service: OnboardingService = Depends(get_onboarding_service)
) -> OnboardingResponse:
    return respond(lambda: service.activate(onboarding_id))


@router.post("/api/onboarding/{onboarding_id}/exit", response_model=OnboardingResponse)
def leave(
    onboarding_id: str,
    payload: ExitRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingResponse:
    return respond(lambda: service.exit(onboarding_id, payload.action))


def validation_error_response(errors: list[dict]) -> JSONResponse:
    # La respuesta estándar repite el valor recibido (`input`); aquí se omite para no devolver documentos ni códigos.
    safe = [{"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")} for error in errors]
    return JSONResponse(status_code=422, content={"detail": safe})
