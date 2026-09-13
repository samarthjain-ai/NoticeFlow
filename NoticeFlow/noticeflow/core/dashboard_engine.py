from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .models import Action, ActionStatus, ImportantDate, Notice, Priority, RiskSeverity


class DeadlineGroup(StrEnum):
    TODAY = "today"
    THIS_WEEK = "this_week"
    NEXT_14_DAYS = "next_14_days"
    LATER = "later"


@dataclass(frozen=True)
class ActionQueueItem:
    action: Action
    notice: Notice
    due_date: date | None
    due_label: str | None


@dataclass(frozen=True)
class DeadlineRadarItem:
    deadline: ImportantDate
    notice: Notice
    group: DeadlineGroup
    risk: RiskSeverity


@dataclass(frozen=True)
class DashboardAnalytics:
    notices_analyzed: int
    saved_notices: int
    pending_actions: int
    completed_actions: int
    high_priority_notices: int
    upcoming_deadlines: int
    completion_rate: float
    categories: dict[str, int]
    priorities: dict[str, int]


PRIORITY_RANK = {
    Priority.URGENT: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}

RISK_RANK = {
    RiskSeverity.CRITICAL: 0,
    RiskSeverity.HIGH: 1,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.LOW: 3,
}


def _first_deadline(notice: Notice) -> ImportantDate | None:
    normalized = [deadline for deadline in notice.deadlines if deadline.normalized_date]
    return min(normalized, key=lambda deadline: deadline.normalized_date, default=None)


def _effective_priority(action: Action, notice: Notice) -> Priority:
    return action.priority if PRIORITY_RANK[action.priority] < PRIORITY_RANK[notice.priority] else notice.priority


def action_queue(notices: list[Notice]) -> list[ActionQueueItem]:
    items: list[ActionQueueItem] = []
    for notice in notices:
        deadline = _first_deadline(notice)
        for action in notice.actions:
            if action.status == ActionStatus.COMPLETED:
                continue
            items.append(
                ActionQueueItem(
                    action=action.model_copy(update={"priority": _effective_priority(action, notice)}),
                    notice=notice,
                    due_date=deadline.normalized_date if deadline else None,
                    due_label=deadline.original_text if deadline else None,
                )
            )
    return sorted(
        items,
        key=lambda item: (
            PRIORITY_RANK[item.action.priority],
            item.due_date is None,
            item.due_date or date.max,
            item.notice.created_at,
        ),
    )


def _risk_for_deadline(notice: Notice, deadline: ImportantDate, today: date) -> RiskSeverity:
    matching = [risk.severity for risk in notice.risks if risk.severity]
    if matching:
        return min(matching, key=RISK_RANK.__getitem__)
    if deadline.normalized_date and (deadline.normalized_date - today).days <= 7:
        return RiskSeverity.MEDIUM
    return RiskSeverity.LOW


def deadline_group(deadline: ImportantDate, today: date) -> DeadlineGroup:
    if deadline.normalized_date is None:
        return DeadlineGroup.LATER
    days = (deadline.normalized_date - today).days
    if days <= 0:
        return DeadlineGroup.TODAY
    if days <= 7:
        return DeadlineGroup.THIS_WEEK
    if days <= 14:
        return DeadlineGroup.NEXT_14_DAYS
    return DeadlineGroup.LATER


def deadline_radar(notices: list[Notice], today: date | None = None) -> dict[DeadlineGroup, list[DeadlineRadarItem]]:
    reference_date = today or date.today()
    radar = {group: [] for group in DeadlineGroup}
    for notice in notices:
        for deadline in notice.deadlines:
            if deadline.normalized_date is None:
                continue
            group = deadline_group(deadline, reference_date)
            radar[group].append(
                DeadlineRadarItem(
                    deadline=deadline,
                    notice=notice,
                    group=group,
                    risk=_risk_for_deadline(notice, deadline, reference_date),
                )
            )
    for items in radar.values():
        items.sort(key=lambda item: (item.deadline.normalized_date, RISK_RANK[item.risk]))
    return radar


def analytics_snapshot(notices: list[Notice], today: date | None = None) -> DashboardAnalytics:
    reference_date = today or date.today()
    actions = [action for notice in notices for action in notice.actions]
    completed = sum(action.status == ActionStatus.COMPLETED for action in actions)
    radar = deadline_radar(notices, reference_date)
    categories: dict[str, int] = {}
    priorities: dict[str, int] = {}
    for notice in notices:
        categories[notice.category.value] = categories.get(notice.category.value, 0) + 1
        priorities[notice.priority.value] = priorities.get(notice.priority.value, 0) + 1
    return DashboardAnalytics(
        notices_analyzed=len(notices),
        saved_notices=len(notices),
        pending_actions=len(actions) - completed,
        completed_actions=completed,
        high_priority_notices=sum(notice.priority in {Priority.URGENT, Priority.HIGH} for notice in notices),
        upcoming_deadlines=sum(
            item.deadline.normalized_date >= reference_date
            for items in radar.values()
            for item in items
        ),
        completion_rate=(completed / len(actions) * 100) if actions else 0.0,
        categories=categories,
        priorities=priorities,
    )


def workload_insight(analytics: DashboardAnalytics, radar: dict[DeadlineGroup, list[DeadlineRadarItem]]) -> str:
    if analytics.high_priority_notices:
        return f"You have {analytics.high_priority_notices} high-priority notice{'s' if analytics.high_priority_notices != 1 else ''}."
    this_week = len(radar[DeadlineGroup.THIS_WEEK])
    if this_week:
        return f"Your busiest period is this week, with {this_week} upcoming deadline{'s' if this_week != 1 else ''}."
    if analytics.completed_actions:
        return f"You have completed {analytics.completed_actions} of {analytics.pending_actions + analytics.completed_actions} tracked actions."
    return "Your command center is clear."