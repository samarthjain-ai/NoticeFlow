import re
import os
from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .action_engine import generate_actions
from .models import (
    Confidence,
    ImportantDate,
    Notice,
    NoticeCategory,
    Priority,
    Requirement,
    SourceEvidence,
)
from .priority_engine import calculate_priority
from .risk_engine import detect_risks


class AIService(Protocol):
    def analyze_notice(self, text: str) -> Notice:
        """Analyze source text into a validated notice."""


class AIServiceError(RuntimeError):
    """A safe error raised when an AI provider cannot analyze a notice."""


class UnavailableAIService:
    def __init__(self, message: str) -> None:
        self.message = message

    def analyze_notice(self, text: str) -> Notice:
        raise AIServiceError(self.message)


class ExtractionResult(BaseModel):
    """The only structured shape accepted from an external model."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    category: NoticeCategory = NoticeCategory.OTHER
    summary: str = Field(min_length=1)
    organizer: str | None = None
    eligibility: str | None = None
    deadlines: list[ImportantDate] = Field(default_factory=list)
    important_dates: list[ImportantDate] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)


def materialize_notice(extraction: ExtractionResult, source_text: str) -> Notice:
    """Validate model output, then let deterministic engines own the application state."""
    source = source_text.strip()
    evidence = [item for item in extraction.source_evidence if item.quote in source]
    deadlines = [
        deadline.model_copy(
            update={
                "normalized_date": _safe_normalized_date(deadline),
                "source_evidence": deadline.source_evidence
                if deadline.source_evidence and deadline.source_evidence.quote in source
                else None
            }
        )
        for deadline in extraction.deadlines
    ]
    requirements = [
        requirement.model_copy(
            update={
                "source_evidence": requirement.source_evidence
                if requirement.source_evidence and requirement.source_evidence.quote in source
                else None
            }
        )
        for requirement in extraction.requirements
    ]
    evidence.extend(
        requirement.source_evidence
        for requirement in requirements
        if requirement.source_evidence is not None
        and requirement.source_evidence.quote not in {item.quote for item in evidence}
    )
    actions = generate_actions(requirements)
    priority, priority_reason = calculate_priority(deadlines, actions)
    notice = Notice(
        title=extraction.title,
        category=extraction.category,
        summary=extraction.summary,
        organizer=extraction.organizer,
        eligibility=extraction.eligibility,
        deadlines=deadlines,
        important_dates=extraction.important_dates,
        requirements=requirements,
        links=extraction.links,
        priority=priority,
        priority_reason=priority_reason,
        actions=actions,
        uncertainties=extraction.uncertainties,
        source_evidence=evidence,
        created_at=datetime.now(),
    )
    notice.risks = detect_risks(notice.deadlines, notice.actions)
    return notice


def _safe_normalized_date(deadline: ImportantDate) -> date | None:
    """Keep exact dates only when the model supplied a usable normalized value."""
    if deadline.confidence == Confidence.UNCERTAIN:
        return None
    return deadline.normalized_date


EXTRACTION_SYSTEM_PROMPT = """You extract facts from university and student notices.
Return only the requested structured fields. Treat the source as authoritative.
Never invent dates, links, organizers, eligibility, requirements, or evidence.
Use null when a singular field is absent and an empty list when a collection is absent.
For a relative or ambiguous date, preserve the original wording, leave normalized_date null,
and set confidence to uncertain. Every evidence quote must be copied exactly from the source.
Do not generate actions, priority, or risks; the application computes those deterministically.
"""


def prepare_notice_text(text: str, max_characters: int = 30_000) -> str:
    """Normalize extraction noise and bound provider cost without dropping the beginning or end."""
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    normalized = "\n".join(lines).strip()
    if len(normalized) <= max_characters:
        return normalized
    marker = "\n[Middle of very long notice omitted for analysis]\n"
    remaining = max_characters - len(marker)
    first_line = normalized.split("\n", 1)[0]
    head_size = max(remaining // 2, len(first_line)) if len(first_line) <= remaining else remaining // 2
    head = normalized[:head_size] if head_size >= len(first_line) else normalized[:head_size].rsplit(" ", 1)[0]
    tail = normalized[-(remaining - len(head)):].split(" ", 1)[-1]
    return head + marker + tail


class DemoAIService:
    """Credential-free analyzer used for demos and deterministic local testing."""

    def analyze_notice(self, text: str) -> Notice:
        cleaned_text = prepare_notice_text(text)
        if not cleaned_text:
            raise ValueError("Notice text cannot be empty.")

        lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
        title = lines[0][:120] if lines else "Untitled notice"
        category = self._category_for(cleaned_text.lower())
        deadlines = self._extract_dates(cleaned_text)
        requirements = self._extract_requirements(lines)
        eligibility = self._extract_eligibility(lines)
        actions = generate_actions(requirements)
        priority, _ = calculate_priority(deadlines, actions)

        notice = Notice(
            title=title,
            category=category,
            summary=self._summary(lines),
            deadlines=deadlines,
            important_dates=deadlines,
            requirements=requirements,
            eligibility=eligibility,
            priority=priority,
            priority_reason=calculate_priority(deadlines, actions)[1],
            actions=actions,
            source_evidence=[
                deadline.source_evidence
                for deadline in deadlines
                if deadline.source_evidence is not None
            ] + [
                requirement.source_evidence
                for requirement in requirements
                if requirement.source_evidence is not None
            ],
            uncertainties=[
                "Calendar date could not be safely determined from the source."
                for deadline in deadlines
                if deadline.confidence == Confidence.UNCERTAIN
            ],
        )
        notice.risks = detect_risks(notice.deadlines, notice.actions)
        return notice

    @staticmethod
    def _category_for(text: str) -> NoticeCategory:
        categories = {
            "hackathon": NoticeCategory.HACKATHON,
            "scholarship": NoticeCategory.SCHOLARSHIP,
            "workshop": NoticeCategory.WORKSHOP,
            "assignment": NoticeCategory.ASSIGNMENT,
            "exam": NoticeCategory.EXAMINATION,
            "internship": NoticeCategory.INTERNSHIP,
            "competition": NoticeCategory.COMPETITION,
        }
        return next((category for keyword, category in categories.items() if keyword in text), NoticeCategory.OTHER)

    @staticmethod
    def _extract_dates(text: str) -> list[ImportantDate]:
        dates: list[ImportantDate] = []
        exact_pattern = re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?\b",
            re.IGNORECASE,
        )
        for match in exact_pattern.finditer(text):
            original_text = match.group(0)
            has_year = bool(re.search(r"\b\d{4}\b", original_text))
            normalized_date = None
            if has_year:
                normalized_date = datetime.strptime(original_text, "%B %d, %Y").date()
            line_start = text.rfind("\n", 0, match.start()) + 1
            context = text[line_start:match.start()].lower()
            label = "Deadline"
            for keyword, candidate in (
                ("registration", "Registration deadline"),
                ("submit", "Submission deadline"),
                ("submission", "Submission deadline"),
                ("exam", "Examination date"),
                ("event", "Event date"),
            ):
                if keyword in context:
                    label = candidate
                    break
            dates.append(
                ImportantDate(
                    label=label,
                    original_text=original_text,
                    normalized_date=normalized_date,
                    confidence=Confidence.EXACT if has_year else Confidence.APPROXIMATE,
                    source_evidence=SourceEvidence(quote=original_text, field_name="important_dates"),
                )
            )
        if dates:
            return dates
        relative_match = re.search(r"\b(?:by|before|on)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", text, re.IGNORECASE)
        if relative_match:
            phrase = relative_match.group(0)
            return [
                ImportantDate(
                    label="Deadline",
                    original_text=phrase,
                    confidence=Confidence.UNCERTAIN,
                    source_evidence=SourceEvidence(
                        quote=phrase,
                        field_name="deadlines",
                        confidence=Confidence.UNCERTAIN,
                    ),
                )
            ]
        return []

    @staticmethod
    def _extract_requirements(lines: list[str]) -> list[Requirement]:
        requirement_markers = ("submit", "register", "apply", "bring", "upload", "complete", "attend")
        requirements: list[Requirement] = []
        for line in lines:
            if any(marker in line.lower() for marker in requirement_markers):
                requirements.append(Requirement(title=line[:120], source_evidence=SourceEvidence(quote=line, field_name="requirements")))
        return requirements

    @staticmethod
    def _extract_eligibility(lines: list[str]) -> str | None:
        eligibility_lines = [line for line in lines if "eligib" in line.lower()]
        return " ".join(eligibility_lines)[:400] or None

    @staticmethod
    def _summary(lines: list[str]) -> str:
        summary = " ".join(lines[:3])
        return summary[:400] or "No summary could be extracted."


class OpenAIService:
    """OpenAI structured-output provider; it never receives database or UI state."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        if not api_key:
            raise AIServiceError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise AIServiceError("OpenAI support is not installed. Install the project dependencies first.") from error
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze_notice(self, text: str) -> Notice:
        cleaned_text = prepare_notice_text(text)
        if not cleaned_text:
            raise AIServiceError("Notice text cannot be empty.")
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": cleaned_text},
                ],
                response_format=ExtractionResult,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise AIServiceError("The AI service returned no structured analysis.")
            return materialize_notice(parsed, cleaned_text)
        except AIServiceError:
            raise
        except Exception as error:
            raise AIServiceError("NoticeFlow could not reach the AI service or validate its response.") from error


def build_ai_service() -> tuple[AIService, str]:
    provider = os.getenv("AI_PROVIDER", "demo").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider == "openai" or (provider == "auto" and api_key):
        try:
            return OpenAIService(api_key, os.getenv("OPENAI_MODEL", "gpt-4o-mini")), "AI MODE"
        except AIServiceError as error:
            return UnavailableAIService(str(error)), "AI MODE · unavailable"
    return DemoAIService(), "DEMO MODE"