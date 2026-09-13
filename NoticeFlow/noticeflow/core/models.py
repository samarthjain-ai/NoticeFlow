from datetime import date, datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class NoticeCategory(StrEnum):
    HACKATHON = "hackathon"
    ASSIGNMENT = "assignment"
    SCHOLARSHIP = "scholarship"
    WORKSHOP = "workshop"
    EXAMINATION = "examination"
    INTERNSHIP = "internship"
    COMPETITION = "competition"
    CLUB = "club"
    ADMINISTRATIVE = "administrative"
    OTHER = "other"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ActionStatus(StrEnum):
    TODO = "todo"
    STARTED = "started"
    COMPLETED = "completed"


class Confidence(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNCERTAIN = "uncertain"
    NOT_FOUND = "not_found"


class RiskSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NoticeflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceEvidence(NoticeflowModel):
    quote: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    confidence: Confidence = Confidence.EXACT
    page_number: Optional[int] = Field(default=None, ge=1)


class ImportantDate(NoticeflowModel):
    label: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    normalized_date: Optional[date] = None
    confidence: Confidence = Confidence.EXACT
    source_evidence: Optional[SourceEvidence] = None


class Requirement(NoticeflowModel):
    title: str = Field(min_length=1)
    description: Optional[str] = None
    required: bool = True
    source_evidence: Optional[SourceEvidence] = None


class Action(NoticeflowModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    description: Optional[str] = None
    deadline: Optional[ImportantDate] = None
    priority: Priority = Priority.MEDIUM
    status: ActionStatus = ActionStatus.TODO
    reasoning: str = Field(min_length=1)


class Risk(NoticeflowModel):
    title: str = Field(min_length=1)
    severity: RiskSeverity
    explanation: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class Notice(NoticeflowModel):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    category: NoticeCategory = NoticeCategory.OTHER
    summary: str = Field(min_length=1)
    organizer: Optional[str] = None
    eligibility: Optional[str] = None
    deadlines: list[ImportantDate] = Field(default_factory=list)
    important_dates: list[ImportantDate] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    priority_reason: Optional[str] = None
    actions: list[Action] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
