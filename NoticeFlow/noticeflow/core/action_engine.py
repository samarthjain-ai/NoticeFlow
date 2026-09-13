from .models import Action, Priority, Requirement


def generate_actions(requirements: list[Requirement]) -> list[Action]:
    """Turn explicit notice requirements into practical, trackable actions."""
    actions: list[Action] = []
    for requirement in requirements:
        if not requirement.required:
            continue
        actions.append(
            Action(
                title=requirement.title,
                description=requirement.description,
                priority=Priority.MEDIUM,
                reasoning="This action comes from a required item in the notice.",
            )
        )
    return actions


def select_next_action(actions: list[Action]) -> Action | None:
    """Choose one explainable next move, keeping completed actions out of the queue."""
    pending = [action for action in actions if action.status.value != "completed"]
    rank = {Priority.URGENT: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    return min(pending, key=lambda action: rank[action.priority], default=None)