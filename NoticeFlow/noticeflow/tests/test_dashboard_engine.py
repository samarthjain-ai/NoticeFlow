import unittest
from datetime import date, datetime

from noticeflow.core.dashboard_engine import (
    DeadlineGroup,
    action_queue,
    analytics_snapshot,
    deadline_radar,
    workload_insight,
)
from noticeflow.core.models import Action, ActionStatus, ImportantDate, Notice, NoticeCategory, Priority


class DashboardEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 9, 13)
        self.notice = Notice(
            title="Hackathon",
            category=NoticeCategory.HACKATHON,
            summary="Build a prototype.",
            priority=Priority.HIGH,
            created_at=datetime(2026, 9, 13),
            deadlines=[
                ImportantDate(
                    label="Registration deadline",
                    original_text="September 18, 2026",
                    normalized_date=date(2026, 9, 18),
                )
            ],
            actions=[
                Action(title="Register", reasoning="Required", priority=Priority.MEDIUM),
                Action(title="Submit", reasoning="Required", status=ActionStatus.COMPLETED),
            ],
        )

    def test_deadline_radar_groups_this_week(self) -> None:
        radar = deadline_radar([self.notice], self.today)

        self.assertEqual(len(radar[DeadlineGroup.THIS_WEEK]), 1)
        self.assertEqual(radar[DeadlineGroup.THIS_WEEK][0].notice.title, "Hackathon")

    def test_action_queue_sorts_notice_priority_and_excludes_completed(self) -> None:
        queue = action_queue([self.notice])

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].action.title, "Register")
        self.assertEqual(queue[0].action.priority, Priority.HIGH)

    def test_analytics_completion_rate_uses_persisted_actions(self) -> None:
        analytics = analytics_snapshot([self.notice], self.today)

        self.assertEqual(analytics.notices_analyzed, 1)
        self.assertEqual(analytics.pending_actions, 1)
        self.assertEqual(analytics.completed_actions, 1)
        self.assertEqual(analytics.completion_rate, 50.0)

    def test_workload_insight_is_deterministic(self) -> None:
        analytics = analytics_snapshot([self.notice], self.today)
        radar = deadline_radar([self.notice], self.today)

        self.assertEqual(workload_insight(analytics, radar), "You have 1 high-priority notice.")

    def test_empty_analytics_has_clean_zero_state(self) -> None:
        analytics = analytics_snapshot([], self.today)

        self.assertEqual(analytics.notices_analyzed, 0)
        self.assertEqual(analytics.pending_actions, 0)
        self.assertEqual(analytics.completion_rate, 0.0)


if __name__ == "__main__":
    unittest.main()