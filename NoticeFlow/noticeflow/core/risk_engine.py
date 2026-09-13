from datetime import date

from .models import Action, ActionStatus, Confidence, ImportantDate, Risk, RiskSeverity


def detect_risks(
    deadlines: list[ImportantDate],
    actions: list[Action],
    today: date | None = None,
) -> list[Risk]:
    """Report only risks supported by normalized dates and action state."""
    reference_date = today or date.today()
    incomplete_count = sum(action.status != ActionStatus.COMPLETED for action in actions)
    risks: list[Risk] = []

    if not deadlines and incomplete_count:
        risks.append(
            Risk(
                title="No deadline identified",
                severity=RiskSeverity.LOW,
                explanation="The notice has incomplete actions, but no deadline was found in the source.",
                recommended_action="Confirm the due date with the organizer before starting the submission.",
            )
        )

    for deadline in deadlines:
        if deadline.confidence == Confidence.UNCERTAIN and incomplete_count:
            risks.append(
                Risk(
                    title="Deadline is unclear",
                    severity=RiskSeverity.MEDIUM,
                    explanation=f"The notice uses ambiguous wording: {deadline.original_text}.",
                    recommended_action="Confirm the calendar date before relying on this deadline.",
                )
            )
            continue
        if deadline.normalized_date is None:
            continue
        days_until = (deadline.normalized_date - reference_date).days
        if days_until < 0 and incomplete_count:
            risks.append(
                Risk(
                    title="Deadline passed",
                    severity=RiskSeverity.CRITICAL,
                    explanation=f"{incomplete_count} required action(s) remain incomplete after the deadline.",
                    recommended_action="Complete the remaining actions and contact the organizer about late submission.",
                )
            )
        elif days_until <= 3 and incomplete_count:
            risks.append(
                Risk(
                    title="Deadline risk",
                    severity=RiskSeverity.HIGH,
                    explanation=f"{incomplete_count} required action(s) remain with 3 days or less to go.",
                    recommended_action="Start the highest-priority incomplete action today.",
                )
            )
        elif days_until <= 7 and incomplete_count:
            risks.append(
                Risk(
                    title="Deadline is approaching",
                    severity=RiskSeverity.MEDIUM,
                    explanation=f"{incomplete_count} required action(s) remain with one week or less to go.",
                    recommended_action="Start the next required action before the deadline becomes urgent.",
                )
            )
    return risks
