import unittest
from datetime import date

from pydantic import ValidationError

from noticeflow.core.models import (
    Action,
    ActionStatus,
    Confidence,
    ImportantDate,
    Notice,
    NoticeCategory,
    Priority,
    SourceEvidence,
)


class NoticeModelTests(unittest.TestCase):
    def test_notice_preserves_uncertain_relative_deadline(self) -> None:
        deadline = ImportantDate(
            label="Application deadline",
            original_text="Submit by Friday",
            confidence=Confidence.UNCERTAIN,
            source_evidence=SourceEvidence(
                quote="Submit by Friday",
                field_name="deadlines",
                confidence=Confidence.UNCERTAIN,
            ),
        )

        notice = Notice(
            title="Student innovation challenge",
            category=NoticeCategory.COMPETITION,
            summary="Students can submit an innovation challenge entry.",
            deadlines=[deadline],
        )

        self.assertIsNone(notice.deadlines[0].normalized_date)
        self.assertEqual(notice.deadlines[0].confidence, Confidence.UNCERTAIN)

    def test_action_defaults_to_todo(self) -> None:
        action = Action(title="Submit abstract", reasoning="The notice requires an abstract.")

        self.assertEqual(action.status, ActionStatus.TODO)
        self.assertEqual(action.priority, Priority.MEDIUM)

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Notice(
                title="Workshop",
                summary="A useful workshop.",
                invented_deadline="tomorrow",
            )

    def test_exact_date_can_be_normalized(self) -> None:
        deadline = ImportantDate(
            label="Submission deadline",
            original_text="September 18, 2026",
            normalized_date=date(2026, 9, 18),
        )

        self.assertEqual(deadline.normalized_date, date(2026, 9, 18))


if __name__ == "__main__":
    unittest.main()