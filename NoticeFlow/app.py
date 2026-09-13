from datetime import date

import streamlit as st
from dotenv import load_dotenv

from noticeflow.core.action_engine import select_next_action
from noticeflow.core.ai_service import AIServiceError, build_ai_service
from noticeflow.core.dashboard_engine import (
    DeadlineGroup,
    action_queue,
    analytics_snapshot,
    deadline_radar,
    workload_insight,
)
from noticeflow.core.demo_scenarios import DEMO_SCENARIOS
from noticeflow.core.models import ActionStatus, Notice, Priority
from noticeflow.services.document_service import DocumentProcessingError, extract_text
from noticeflow.services.storage_service import StorageService

load_dotenv()

st.set_page_config(page_title="Noticeflow", page_icon="N", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink: #182026; --muted: #66737b; --line: #dce3e4; --paper: #f7f8f5; --mint: #d9eee5; --amber: #f3d9a3; --red: #e9b7b0; --coral: #d96356; }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stSidebar"] { background: #e9f0ed; border-right: 1px solid var(--line); color: var(--ink); }
    [data-testid="stSidebar"] * { color: var(--ink); }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #3f4d52; }
    [data-testid="stSidebar"] button { background: #dce8e4; border: 1px solid #7a8b86; color: var(--ink); }
    [data-testid="stSidebar"] button p { color: var(--ink); }
    [data-testid="stSidebar"] button[kind="primary"] { background: #ff4b4b; border-color: #c93f3f; color: #182026; }
    [data-testid="stSidebar"] button[kind="primary"] p { color: #182026; }
    h1, h2, h3, [data-testid="stSidebar"] * { font-family: 'Space Grotesk', sans-serif; }
    p, label, button, input, textarea { font-family: 'DM Sans', sans-serif; }
    .eyebrow { color: var(--muted); font-size: .76rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
    .hero { padding: 2.2rem 0 1.5rem; border-bottom: 1px solid var(--line); margin-bottom: 1.7rem; }
    .hero h1 { font-size: clamp(2rem, 4vw, 3.8rem); line-height: 1; margin: .35rem 0 .7rem; }
    .hero p { color: var(--muted); font-size: 1.08rem; max-width: 620px; }
    .action-panel { border: 1px solid #9fc8b7; background: var(--mint); padding: 1.4rem 1.5rem; border-radius: 8px; margin: 1rem 0 1.4rem; }
    .action-panel h2 { margin: .25rem 0 .35rem; font-size: 1.7rem; }
    .value-card { border: 1px solid var(--line); background: #fbfcfa; padding: 1.1rem; min-height: 145px; border-radius: 6px; }
    .value-card h3 { margin: .3rem 0 .45rem; font-size: 1.05rem; }
    .value-card p { color: var(--muted); margin: 0; line-height: 1.45; }
    .section-label { color: var(--muted); font-size: .76rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; margin: 1.8rem 0 .75rem; }
    .attention-item { border-left: 4px solid var(--coral); background: #fffaf8; padding: .9rem 1rem; margin: .55rem 0; }
    .attention-item strong { display: block; }
    .attention-item span { color: var(--muted); font-size: .9rem; }
    .deadline-item { border-bottom: 1px solid var(--line); padding: .7rem 0; }
    .deadline-item strong { display: block; }
    .deadline-item span { color: var(--muted); font-size: .9rem; }
    .status-chip { display: inline-block; color: #74451a; background: #f3d9a3; padding: .2rem .5rem; font-size: .72rem; font-weight: 700; letter-spacing: .08em; }
    .action-panel h2 { margin: .25rem 0 .35rem; font-size: 1.55rem; }
    .notice-panel { border-top: 1px solid var(--line); padding: 1.1rem 0; }
    .meta { color: var(--muted); font-size: .9rem; }
    .risk-panel { border-left: 4px solid #c16a5c; background: #f7e4df; padding: 1rem 1.1rem; margin: 1rem 0; }
    .low-risk-panel { border-left: 4px solid #6b9d87; background: #eef6f1; padding: 1rem 1.1rem; margin: 1rem 0; }
    .evidence { color: var(--muted); border-left: 2px solid var(--line); padding-left: .8rem; font-style: italic; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_storage() -> StorageService:
    return StorageService()


@st.cache_resource
def get_analyzer() -> tuple[object, str]:
    return build_ai_service()


def set_view(view: str) -> None:
    st.session_state.view = view


def priority_color(priority: Priority) -> str:
    return {Priority.URGENT: "#a33f35", Priority.HIGH: "#a86d12", Priority.MEDIUM: "#396b79", Priority.LOW: "#4e7565"}[priority]


def time_remaining(normalized_date: date | None) -> str | None:
    if normalized_date is None:
        return None
    days = (normalized_date - date.today()).days
    if days < 0:
        return "Past due"
    if days == 0:
        return "Due today"
    return f"{days} day{'s' if days != 1 else ''}"


def confidence_label(confidence: str) -> str:
    return {"exact": "CONFIRMED", "approximate": "APPROXIMATE", "uncertain": "UNCERTAIN", "not_found": "NOT FOUND"}.get(confidence, confidence.upper())


def action_status_label(status: ActionStatus) -> str:
    return {ActionStatus.TODO: "PENDING", ActionStatus.STARTED: "IN PROGRESS", ActionStatus.COMPLETED: "COMPLETED"}[status]


def why_notice_matters(notice: Notice) -> str:
    if len(notice.deadlines) >= 2:
        first, second = notice.deadlines[:2]
        if first.label != second.label:
            return f"This notice requires attention because {first.label.lower()} comes before {second.label.lower()}."
    if notice.risks:
        return notice.risks[0].explanation
    if notice.actions:
        count = len(notice.actions)
        return f"This notice contains {count} required action{'s' if count != 1 else ''} that need tracking."
    return "Relevance depends on your eligibility and interest."


def render_sidebar(mode: str) -> None:
    st.sidebar.markdown("## NOTICEFLOW")
    st.sidebar.caption("Turn information overload into your next action.")
    st.sidebar.divider()
    if st.sidebar.button("Overview", width="stretch"):
        set_view("dashboard")
        st.rerun()
    if st.sidebar.button("Analyze a notice", type="primary", width="stretch"):
        set_view("analyze")
        st.rerun()
    st.sidebar.divider()
    st.sidebar.caption(mode)
    if mode == "AI MODE":
        st.sidebar.caption("Structured analysis is active through the configured AI provider.")
    elif mode.startswith("AI MODE"):
        st.sidebar.caption("AI provider is configured but unavailable. Check your environment settings.")
    else:
        st.sidebar.caption("Structured local analysis is active. No API key required.")


def render_dashboard(storage: StorageService) -> None:
    notices = storage.list_notices()
    st.markdown('<div class="hero"><div class="eyebrow">Your attention, organized</div><h1>Make the next move clear.</h1><p>Upload a university notice, assignment, event, scholarship, internship, competition, or circular. NoticeFlow extracts what matters and tells you what to do next.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">The Noticeflow method</div>', unsafe_allow_html=True)
    value_columns = st.columns(3)
    value_cards = (
        ("UNDERSTAND", "Extract deadlines, requirements, eligibility, and important information."),
        ("DECIDE", "Determine priority, urgency, and potential risks from the source."),
        ("ACT", "Get a clear action plan and one next best action."),
    )
    for column, (title, description) in zip(value_columns, value_cards):
        with column:
            st.markdown(f'<div class="value-card"><div class="eyebrow">{title}</div><p>{description}</p></div>', unsafe_allow_html=True)
    if st.button("＋  Analyze a notice", type="primary"):
        set_view("analyze")
        st.rerun()
    if not notices:
        st.markdown('<div class="section-label">Your command center is clear</div>', unsafe_allow_html=True)
        st.info("No saved notices yet. Analyze your first university notice to start building your action queue.")
        return

    analytics = analytics_snapshot(notices)
    queue = action_queue(notices)
    radar = deadline_radar(notices)
    attention = [
        item
        for item in queue
        if item.action.priority in {Priority.URGENT, Priority.HIGH}
        or any(risk.severity.value in {"critical", "high"} for risk in item.notice.risks)
        or (item.due_date is not None and (item.due_date - date.today()).days <= 7)
    ]
    incomplete = queue
    st.markdown('<div class="section-label">Needs attention</div>', unsafe_allow_html=True)
    if attention:
        for item in attention[:4]:
            due_text = item.due_label or "No exact deadline"
            st.markdown(f'<div class="attention-item"><strong>{item.action.title}</strong><span>{item.action.priority.value.upper()} PRIORITY · {item.notice.title}<br>Due: {due_text}</span></div>', unsafe_allow_html=True)
    else:
        st.caption("No overdue, urgent, or high-priority actions right now.")

    st.markdown('<div class="section-label">Your next move</div>', unsafe_allow_html=True)
    if queue:
        next_item = queue[0]
        st.markdown(f'<div class="action-panel"><div class="eyebrow">Your next move</div><h2>{next_item.action.title}</h2><p>{next_item.notice.title} · {action_status_label(next_item.action.status)}</p></div>', unsafe_allow_html=True)
    else:
        st.caption("Your action queue is clear.")

    st.markdown('<div class="section-label">Deadline radar</div>', unsafe_allow_html=True)
    radar_labels = (
        (DeadlineGroup.TODAY, "Today"),
        (DeadlineGroup.THIS_WEEK, "This week"),
        (DeadlineGroup.NEXT_14_DAYS, "Next 14 days"),
        (DeadlineGroup.LATER, "Later"),
    )
    has_deadlines = False
    for group, label in radar_labels:
        items = radar[group]
        if not items:
            continue
        has_deadlines = True
        st.markdown(f"**{label.upper()}**")
        for item in items[:4]:
            st.markdown(f'<div class="deadline-item"><strong>{item.deadline.label}: {item.deadline.original_text}</strong><span>{item.notice.title} · {item.risk.value.upper()} RISK · {time_remaining(item.deadline.normalized_date) or "Past due"}</span></div>', unsafe_allow_html=True)
    if not has_deadlines:
        st.caption("No upcoming deadlines detected.")

    st.markdown('<div class="section-label">Action queue</div>', unsafe_allow_html=True)
    if incomplete:
        for item in incomplete[:8]:
            due_text = item.due_label or "No exact deadline"
            action_col, status_col = st.columns([4, 1])
            with action_col:
                st.markdown(f"**{item.action.title}**  \n<span class='meta'>{item.notice.title} · {item.action.priority.value.upper()} · Due: {due_text} · {action_status_label(item.action.status)}</span>", unsafe_allow_html=True)
            with status_col:
                next_status = ActionStatus.COMPLETED if item.action.status == ActionStatus.STARTED else ActionStatus.STARTED
                button_label = "Complete" if next_status == ActionStatus.COMPLETED else "Start"
                if st.button(button_label, key=f"queue-{item.action.id}", width="stretch"):
                    storage.update_action_status(item.action.id, next_status)
                    st.rerun()
    else:
        st.caption("Your action queue is clear.")

    st.markdown('<div class="section-label">Workload analytics</div>', unsafe_allow_html=True)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Notices analyzed", analytics.notices_analyzed)
    metric_columns[1].metric("Pending actions", analytics.pending_actions)
    metric_columns[2].metric("Completed actions", analytics.completed_actions)
    metric_columns[3].metric("Completion rate", f"{analytics.completion_rate:.0f}%")
    st.info(f"NOTICEFLOW INSIGHT  ·  {workload_insight(analytics, radar)}")
    if len(analytics.categories) >= 2:
        chart_columns = st.columns(2)
        with chart_columns[0]:
            st.caption("Notices by category")
            st.dataframe(
                [{"Category": category.title(), "Notices": count} for category, count in analytics.categories.items()],
                hide_index=True,
                width="stretch",
            )
        with chart_columns[1]:
            st.caption("Priority distribution")
            st.dataframe(
                [{"Priority": priority.upper(), "Notices": count} for priority, count in analytics.priorities.items()],
                hide_index=True,
                width="stretch",
            )
    else:
        st.caption("Analytics will become more useful as you analyze more notice types.")

    st.markdown('<div class="section-label">Recent notices</div>', unsafe_allow_html=True)
    for notice in notices[:6]:
        if st.button(f"{notice.title}  ·  {notice.category.value.title()}", key=f"open-{notice.id}", width="stretch"):
            st.session_state.notice = notice
            set_view("result")
            st.rerun()


def render_analyze(storage: StorageService, analyzer: object) -> None:
    st.markdown('<div class="hero"><div class="eyebrow">Analyze notice</div><h1>Bring the messy part.</h1><p>Paste a notice or upload a PDF, image, or text file. We will find what matters and what to do next.</p></div>', unsafe_allow_html=True)
    if DEMO_SCENARIOS:
        st.markdown('<div class="section-label">Try a fictional demo</div>', unsafe_allow_html=True)
        st.caption("Fictional examples only. Each one uses the same NoticeFlow analysis pipeline.")
        selected_demo = st.selectbox(
            "Demo scenario",
            [scenario.name for scenario in DEMO_SCENARIOS],
            index=0,
            label_visibility="collapsed",
        )
        if st.button("Use this fictional demo notice"):
            scenario = next(item for item in DEMO_SCENARIOS if item.name == selected_demo)
            st.session_state.notice_text = scenario.notice_text
            st.rerun()
    pasted = st.text_area("Notice text", height=230, placeholder="Paste a university announcement here...", key="notice_text")
    uploaded = st.file_uploader("Or upload a notice", type=["txt", "md", "pdf", "png", "jpg", "jpeg", "webp"])
    if st.button("Analyze notice", type="primary", disabled=not pasted.strip() and uploaded is None):
        try:
            with st.status("Reading notice...", expanded=True) as status:
                if uploaded is not None:
                    source_text = extract_text(uploaded.name, uploaded.getvalue())
                else:
                    source_text = pasted
                st.write("Extracting information...")
                st.write("Finding deadlines...")
                st.write("Checking requirements...")
                notice = analyzer.analyze_notice(source_text)
                st.write("Building action plan...")
                st.write("Checking deadline risks...")
                status.update(label="Analysis ready", state="complete", expanded=False)
            storage.save_notice(notice)
            st.session_state.notice = notice
            set_view("result")
            st.rerun()
        except DocumentProcessingError as error:
            st.error(str(error))
        except AIServiceError as error:
            st.error(str(error))
        except ValueError as error:
            st.error(f"Could not analyze this notice: {error}")


def render_result(storage: StorageService, notice: Notice) -> None:
    if st.button("← Back to overview"):
        set_view("dashboard")
        st.rerun()
    st.markdown(f'<div class="hero"><div class="eyebrow">{notice.category.value.title()} · {notice.priority.value.title()} priority</div><h1>{notice.title}</h1><p>{notice.summary}</p></div>', unsafe_allow_html=True)
    st.markdown("### What is this?")
    st.caption(notice.summary)
    st.markdown("### Why this matters")
    st.info(why_notice_matters(notice))
    if notice.actions:
        action = select_next_action(notice.actions) or notice.actions[0]
        st.markdown(f'<div class="action-panel"><div class="eyebrow">Your next move</div><h2>{action.title}</h2><p><strong>Why this matters:</strong> {action.description or action.reasoning}</p></div>', unsafe_allow_html=True)
        if action.status != ActionStatus.COMPLETED and st.button("Mark as started", type="primary"):
            updated = storage.update_action_status(action.id, ActionStatus.STARTED)
            if updated:
                st.session_state.notice = updated
                st.rerun()

    left, right = st.columns([1, 1])
    with left:
        st.markdown("### Deadline")
        if notice.deadlines:
            for deadline in notice.deadlines:
                confidence = confidence_label(deadline.confidence.value)
                normalized = f" · {deadline.normalized_date}" if deadline.normalized_date else ""
                remaining = f" · Due in {time_remaining(deadline.normalized_date)}" if time_remaining(deadline.normalized_date) else " · Time remaining unavailable"
                st.markdown(f"**{deadline.label}: {deadline.original_text}**  \n<span class='meta'>{confidence}{normalized}{remaining}</span>", unsafe_allow_html=True)
        else:
            st.caption("No deadline found in the notice.")
    with right:
        st.markdown("### Priority")
        st.markdown(f"<span style='color:{priority_color(notice.priority)};font-weight:700'>{notice.priority.value.upper()}</span>", unsafe_allow_html=True)
        st.caption(notice.priority_reason or "Priority is calculated from deadline proximity and incomplete required actions.")

    st.markdown("### Risk")
    if notice.risks:
        for risk in notice.risks:
            risk_class = "low-risk-panel" if risk.severity.value == "low" else "risk-panel"
            st.markdown(f'<div class="{risk_class}"><strong>{risk.severity.value.upper()} RISK · {risk.title}</strong><br>{risk.explanation}<br><br><strong>Recommendation:</strong> {risk.recommended_action}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="low-risk-panel"><strong>LOW RISK</strong><br>No immediate blocking risk detected.</div>', unsafe_allow_html=True)
    st.markdown("### Action plan")
    for action in notice.actions:
        completed = action.status == ActionStatus.COMPLETED
        label = f"{'✓' if completed else '○'} {action.title} · {action_status_label(action.status)}"
        if st.button(label, key=f"action-{action.id}", width="stretch"):
            next_status = ActionStatus.TODO if completed else ActionStatus.COMPLETED
            updated = storage.update_action_status(action.id, next_status)
            if updated:
                st.session_state.notice = updated
                st.rerun()
    st.markdown("### Requirements")
    for requirement in notice.requirements:
        st.markdown(f"- {requirement.title}")
    if notice.important_dates:
        st.markdown("### Important dates")
        for important_date in notice.important_dates:
            st.markdown(f"- **{important_date.label}:** {important_date.original_text}")
    if notice.eligibility:
        st.markdown("### Eligibility")
        st.write(notice.eligibility)
    else:
        st.markdown("### Eligibility")
        st.caption("Not found in the source.")
    if notice.uncertainties:
        st.markdown("### Uncertainty")
        for uncertainty in notice.uncertainties:
            st.warning(uncertainty)
    with st.expander("Source evidence"):
        if notice.source_evidence:
            for evidence in notice.source_evidence:
                page = f" · Page {evidence.page_number}" if evidence.page_number else ""
                st.markdown(f"<div class='evidence'>{evidence.field_name}: &quot;{evidence.quote}&quot;<br><span class='meta'>Confidence: {confidence_label(evidence.confidence.value)}{page}</span></div>", unsafe_allow_html=True)
        else:
            st.caption("No source evidence was captured.")


def main() -> None:
    analyzer, mode = get_analyzer()
    render_sidebar(mode)
    storage = get_storage()
    view = st.session_state.get("view", "dashboard")
    if view == "analyze":
        render_analyze(storage, analyzer)
    elif view == "result" and st.session_state.get("notice"):
        render_result(storage, st.session_state.notice)
    else:
        render_dashboard(storage)


if __name__ == "__main__":
    main()