from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class CreateTaskRequest(BaseModel):
    title: str = ""
    description: str = ""
    status: str = "TODO"
    priority: str = "MEDIUM"
    owner: str | None = None

    @model_validator(mode="before")
    @classmethod
    def preserve_legacy_string_conversion(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        defaults = {
            "title": "",
            "description": "",
            "status": "TODO",
            "priority": "MEDIUM",
        }
        for field, default in defaults.items():
            normalized[field] = str(normalized.get(field, default))
        if "owner" in normalized:
            normalized["owner"] = str(normalized["owner"])
        return normalized


class TaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    description: str
    status: str
    owner: str
    priority: str
    created_at: str = Field(alias="createdAt")


class SummaryResponse(BaseModel):
    owner: str
    total: int
    byStatus: dict[str, int]
    highPriorityOpen: int


class RequirementResponse(BaseModel):
    owner: str
    fileName: str
    storedAt: str
    size: int


class BackendHealthResponse(BaseModel):
    requestedBy: str
    status: int
    body: str


TestDocument = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=200, pattern=r"^TEST-.+$"),
]


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentType: Literal["TEST"]
    document: TestDocument
    scenario: Literal["APPROVED", "MANUAL_REVIEW", "REJECTED", "UNAVAILABLE"] = "APPROVED"


class TwoFactorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class ExitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["CONTINUE", "END"]


class WalletResponse(BaseModel):
    id: str
    status: str
    balance: int
    reserved: int
    available: int
    currency: str


class OnboardingStates(BaseModel):
    registration: Literal["STARTED", "DOCUMENT_VALID", "PERSISTING", "PERSISTED"]
    verification: Literal["PENDING", "CHALLENGED", "VERIFIED"]
    activation: Literal["INACTIVE", "PENDING", "REJECTED", "ACTIVE"]
    provider: Literal["ACTIVE", "PENDING", "REJECTED"] | None = None


class OnboardingResponse(BaseModel):
    onboardingId: str
    step: Literal["DOCUMENT", "TWO_FACTOR", "ACTIVATION", "EXIT"]
    states: OnboardingStates
    twoFactorAvailable: bool
    wallet: WalletResponse | None = None
    paymentsEntryAvailable: bool = False


class AnalyticsMonth(BaseModel):
    month: str
    started: int
    newActiveUsers: int
    medianSeconds: float | None
    withinTarget: bool | None


class AnalyticsResponse(BaseModel):
    boundary: dict[str, str]
    targetMedianSeconds: int
    months: list[AnalyticsMonth]
    acquisitionSpend: dict[str, str]
    cac: float | None = None