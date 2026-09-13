import unittest
from datetime import date, timedelta

from noticeflow.core.action_engine import generate_actions, select_next_action
from noticeflow.core.models import (
    Action,
    ActionStatus,
    ImportantDate,
    Priority,
    Requirement,
    RiskSeverity,
)
from noticeflow.core.priority_engine import calculate_priority
from noticeflow.core.risk_engine import detect_risks


class EngineTests(unittest.TestCase):
    def test_actions_only_include_required_requirements(self) -> None:
        actions = generate_actions(
            [
                Requirement(title="Register", required=True),
                Requirement(title="Read the guide", required=False),
            ]
        )

        self.assertEqual([action.title for action in actions], ["Register"])

    def test_next_action_excludes_completed_actions(self) -> None:
        actions = [
            Action(title="Done", reasoning="Required", status=ActionStatus.COMPLETED),
            Action(title="Start here", reasoning="Required", priority=Priority.HIGH),
        ]

        self.assertEqual(select_next_action(actions).title, "Start here")

    def test_priority_explains_imminent_deadline(self) -> None:
        priority, reason = calculate_priority(
            [ImportantDate(label="Deadline", original_text="tomorrow", normalized_date=date(2026, 9, 14))],
            [Action(title="Submit", reasoning="Required")],
            today=date(2026, 9, 13),
        )

        self.assertEqual(priority, Priority.URGENT)
        self.assertIn("48 hours", reason)

    def test_risk_requires_incomplete_actions(self) -> None:
        deadline = ImportantDate(
            label="Deadline",
            original_text="September 14",
            normalized_date=date(2026, 9, 14),
        )
        completed_action = Action(
            title="Submit",
            reasoning="Required",
            status=ActionStatus.COMPLETED,
        )

        self.assertEqual(
            detect_risks([deadline], [completed_action], today=date(2026, 9, 13)),
            [],
        )

    def test_risk_is_explainable_when_deadline_is_near(self) -> None:
        deadline = ImportantDate(
            label="Deadline",
            original_text="September 14",
            normalized_date=date(2026, 9, 14),
        )

        risks = detect_risks(
            [deadline],
            [Action(title="Submit", reasoning="Required")],
            today=date(2026, 9, 13),
        )

        self.assertEqual(risks[0].severity, RiskSeverity.HIGH)
        self.assertIn("3 days", risks[0].explanation)

    def test_missing_deadline_is_a_low_explainable_risk(self) -> None:
        risks = detect_risks([], [Action(title="Apply", reasoning="Required")])

        self.assertEqual(risks[0].severity, RiskSeverity.LOW)
        self.assertIn("no deadline", risks[0].explanation.lower())

    def test_approaching_deadline_is_a_medium_explainable_risk(self) -> None:
        deadline = ImportantDate(
            label="Deadline",
            original_text="September 18",
            normalized_date=date(2026, 9, 18),
        )

        risks = detect_risks(
            [deadline],
            [Action(title="Submit", reasoning="Required")],
            today=date(2026, 9, 13),
        )

        self.assertEqual(risks[0].severity, RiskSeverity.MEDIUM)
        self.assertIn("one week", risks[0].explanation)


if __name__ == "__main__":
    unittest.main()