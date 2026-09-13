from datetime import date

from .models import Action, ActionStatus, ImportantDate, Priority


def _days_until(deadline: ImportantDate, today: date) -> int | None:
    if deadline.normalized_date is None:
        return None
    return (deadline.normalized_date - today).days


def calculate_priority(
    deadlines: list[ImportantDate],
    actions: list[Action],
    today: date | None = None,
) -> tuple[Priority, str]:
    """Return a priority and a human-readable reason using deterministic rules."""
    reference_date = today or date.today()
    incomplete_count = sum(action.status != ActionStatus.COMPLETED for action in actions)
    normalized_days = [
        days
        for deadline in deadlines
        if (days := _days_until(deadline, reference_date)) is not None
    ]

    if any(days < 0 for days in normalized_days):
        return Priority.URGENT, f"The deadline has passed and {incomplete_count} action(s) remain incomplete."
    if any(days <= 2 for days in normalized_days):
        return Priority.URGENT, f"A deadline is within 48 hours and {incomplete_count} action(s) remain incomplete."
    if any(days <= 7 for days in normalized_days):
        return Priority.HIGH, f"A deadline is within 7 days and {incomplete_count} action(s) remain incomplete."
    if incomplete_count:
        return Priority.MEDIUM, f"{incomplete_count} action(s) remain incomplete."
    return Priority.LOW, "No imminent deadline or incomplete required action was found."